"""Shared test fixtures.

FakeSession handles real SQLAlchemy ``select()`` / ``.where()`` / ``.in_()``
/ ``.join()`` / ``.order_by()`` patterns so service tests exercise actual
query construction against in-memory data, not hand-written mocks per test.
"""

from __future__ import annotations

import uuid
from typing import Any


class FakeResult:
    """Mimics the sqlalchemy Result object returned by session.execute()."""

    def __init__(self, rows: list[Any]):
        self._rows = rows

    def scalars(self):
        """Return a shim whose .all() yields the stored objects."""

        class _ScalarResult:
            def __init__(self, items):
                self._items = items

            def all(self):
                return list(self._items)

            def first(self):
                return self._items[0] if self._items else None

        return _ScalarResult(self._rows)

    def first(self):
        """Return the first row, or None."""
        return self._rows[0] if self._rows else None

    def scalar(self):
        """Return the first column of the first row, or None.
        For aggregate queries (select(func.count(...))), the stored row
        should already be the scalar result.
        """
        if not self._rows:
            return None
        first = self._rows[0]
        # If it's a tuple (multi-entity select), return first element
        if isinstance(first, tuple):
            return first[0]
        # If it's an ORM model but we wanted an aggregate, the FakeSession
        # should have stored the int directly. Return as-is.
        return first

    def all(self):
        """For multi-entity selects like select(A, B).join(B)."""
        return list(self._rows)


class FakeSession:
    """In-memory async session for service-level tests.

    Stores rows by model type. Supports the SQLAlchemy ``select()`` query
    patterns that the planning, ingestion, and mastery services actually
    use:

    - ``select(Model).where(col == val)``
    - ``select(Model).where(col.in_([vals]))``
    - ``select(Model).order_by(col)``
    - ``select(A, B).join(B, ...).where(...)``
    """

    def __init__(self, rows: dict[type, list] | None = None):
        self._rows: dict[type, list] = dict(rows) if rows else {}
        self.added: list = []
        self.committed = False
        self.flushed = False

    def _store(self, obj):
        """Auto-assign an id and register in the row store."""
        t = type(obj)
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self._rows.setdefault(t, []).append(obj)

    def add(self, obj):
        self.added.append(obj)

    async def get(self, model, id_):
        for obj in self._rows.get(model, []):
            if getattr(obj, "id", None) == id_:
                return obj
        return None

    async def flush(self):
        self.flushed = True
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()

    async def commit(self):
        self.committed = True
        # Persist added objects into the row store
        for obj in self.added:
            self._store(obj)

    async def refresh(self, obj):
        pass

    async def execute(self, stmt):
        """Intercept real SQLAlchemy ``select()`` objects and filter
        the in-memory row store accordingly."""
        # Extract select targets
        columns = getattr(stmt, "columns_clause_froms", None)
        if columns is None:
            columns = getattr(stmt, "column_descriptions", None)

        # Determine which models we're selecting
        select_entities = _extract_select_entities(stmt)
        where_clauses = list(getattr(stmt, "_where_criteria", ()))
        order_by_clauses = list(getattr(stmt, "_order_by_clauses", ()))

        # Check for joins
        joins = getattr(stmt, "_setup_joins", ())

        if joins:
            return _execute_joins(self, select_entities, joins, where_clauses)

        if not select_entities:
            return FakeResult([])

        # Check for aggregate functions like func.count()
        if _has_aggregate(stmt):
            primary_model = select_entities[0]
            candidates = list(self._rows.get(primary_model, []))
            # Apply where clauses to filter
            for clause in where_clauses:
                candidates = _apply_clause(candidates, clause)
            return FakeResult([len(candidates)])

        primary_model = select_entities[0]

        # Get candidates
        candidates = list(self._rows.get(primary_model, []))
        if len(select_entities) > 1:
            # Multi-entity select — fetch from all models
            pass

        # Apply where clauses
        for clause in where_clauses:
            candidates = _apply_clause(candidates, clause)

        # Apply order by
        for order_clause in order_by_clauses:
            candidates = _apply_order(candidates, order_clause)

        if len(select_entities) > 1:
            # Return tuples of (entity1, entity2, ...) — for multi-entity selects
            return FakeResult([tuple(candidates)])

        return FakeResult(candidates)


def _extract_select_entities(stmt):
    """Extract the entity types from a select() statement."""
    entities = []
    # SQLAlchemy select stores column descriptions
    col_descs = getattr(stmt, "column_descriptions", [])
    for desc in col_descs:
        entity = desc.get("entity")
        if entity is not None:
            entities.append(entity)
    if not entities:
        # Try _raw_columns
        for col in getattr(stmt, "_raw_columns", []):
            entity = getattr(col, "entity", None)
            if entity is not None and entity not in entities:
                entities.append(entity)
    return entities


def _resolve_model(session, target):
    """Resolve a SQLAlchemy Table/AnnotatedTable to a model class."""
    target_tablename = (
        target if isinstance(target, str)
        else getattr(target, "name", None)
    )
    if target_tablename and not isinstance(target, type):
        for model_cls in session._rows:
            if getattr(model_cls, "__tablename__", None) == target_tablename:
                return model_cls
    return target


def _apply_clause(rows, clause):
    """Apply a single where clause to a list of row objects."""
    # BinaryExpression: column == value or column.in_([...])
    clause_type = type(clause).__name__

    if clause_type == "BinaryExpression":
        left = clause.left
        right = clause.right
        operator = clause.operator

        # Get column name from the left side
        col_name = _get_column_name(left)

        if operator.__name__ == "in_op":
            # IN clause: column.in_([val1, val2, ...])
            values = _extract_in_values(right)
            return [r for r in rows if getattr(r, col_name, None) in values]
        elif operator.__name__ == "eq" or str(operator) == "operator.eq":
            value = _extract_scalar_value(right)
            return [r for r in rows if getattr(r, col_name, None) == value]
        elif operator.__name__ == "ne" or str(operator) == "operator.ne":
            value = _extract_scalar_value(right)
            return [r for r in rows if getattr(r, col_name, None) != value]
        else:
            # Unknown operator — pass through
            return rows

    elif clause_type == "BooleanClauseList":
        # AND / OR conjunction
        clauses = list(clause.clauses)
        if clause.operator.__name__ == "and_":
            result = rows
            for c in clauses:
                result = _apply_clause(result, c)
            return result
        elif clause.operator.__name__ == "or_":
            all_results = set()
            for c in clauses:
                for r in _apply_clause(rows, c):
                    all_results.add(id(r))
            return [r for r in rows if id(r) in all_results]

    # Fallback — don't filter
    return rows


def _apply_order(rows, order_clause):
    """Apply an order_by clause."""
    if hasattr(order_clause, "element"):
        element = order_clause.element
    else:
        element = order_clause

    col_name = _get_column_name(element)
    if not col_name:
        return rows

    desc = getattr(order_clause, "descending", lambda: False)()
    if desc:
        return sorted(rows, key=lambda r: getattr(r, col_name, None) or "", reverse=True)
    return sorted(rows, key=lambda r: getattr(r, col_name, None) or "")


def _has_aggregate(stmt):
    """Check if a select statement contains aggregate functions like func.count()."""
    # Check _raw_columns for functions
    for col in getattr(stmt, "_raw_columns", []):
        if hasattr(col, "clause_expr"):
            clause_expr = col.clause_expr
            # func.count() creates a Function object
            if hasattr(clause_expr, "name") and hasattr(clause_expr, "clauses"):
                return True
        # Also check if the column itself is a function
        if type(col).__name__ == "AnnotatedColumn":
            # Skip — this is a regular column reference
            pass
    # Check column_descriptions for func.count patterns
    for desc in getattr(stmt, "column_descriptions", []):
        expr = desc.get("expr")
        if expr is not None and hasattr(expr, "name") and hasattr(expr, "clauses"):
            return True
    return False


def _clause_references_table(clause):
    """Determine which table a where clause references."""
    clause_type = type(clause).__name__
    if clause_type == "BinaryExpression":
        table = getattr(clause.left, "table", None)
        if table is not None:
            return getattr(table, "name", None)
    elif clause_type == "BooleanClauseList":
        for c in clause.clauses:
            result = _clause_references_table(c)
            if result:
                return result
    return None


def _get_column_name(element):
    """Extract the column name from a SQLAlchemy column element."""
    name = getattr(element, "key", None)
    if name:
        return name
    name = getattr(element, "name", None)
    if name:
        return name
    # Try _label
    name = getattr(element, "_label", None)
    if name:
        return name
    return None


def _extract_scalar_value(right):
    """Extract a scalar value from the right side of a comparison."""
    if hasattr(right, "value"):
        return right.value
    if hasattr(right, "element"):
        return _extract_scalar_value(right.element)
    return right


def _extract_in_values(right):
    """Extract the list of values from an IN clause."""
    if hasattr(right, "clauses"):
        return [_extract_scalar_value(c) for c in right.clauses]
    if hasattr(right, "value"):
        return right.value
    return []


def _execute_joins(session, select_entities, joins, where_clauses):
    """Execute a multi-table join query progressively.

    Each join adds one more entity to the tuple.  ``_setup_joins`` is a
    tuple of ``(target, onclause, isouter, full)`` entries in join order.
    """
    # Start with rows from the first (primary) entity
    primary = select_entities[0]
    primary_rows = list(session._rows.get(primary, []))
    # Each row in `joined` is a tuple of objects, one per entity so far
    joined = [(p,) for p in primary_rows]

    # Collect all model classes involved so far
    models_so_far = [primary]

    for target, onclause, _isouter, _full in joins:
        secondary = _resolve_model(session, target)
        secondary_rows = list(session._rows.get(secondary, []))

        # Determine join columns from onclause
        left_name = _get_column_name(onclause.left)
        right_name = _get_column_name(onclause.right)
        left_table = getattr(onclause.left, "table", None)
        right_table = getattr(onclause.right, "table", None)

        # Figure out which side belongs to which entity
        primary_col = None
        foreign_col = None
        if left_table is not None and right_table is not None:
            left_tn = getattr(left_table, "name", None)
            right_tn = getattr(right_table, "name", None)
            primary_tn = getattr(primary, "__tablename__", None)
            if left_tn == primary_tn:
                primary_col, foreign_col = left_name, right_name
            else:
                primary_col, foreign_col = right_name, left_name
        else:
            primary_col, foreign_col = right_name, left_name

        # Build new joined tuples
        new_joined = []
        for existing in joined:
            # existing is (entity0, entity1, ...)
            # Find which entity in the chain matches the right side's table
            ref_entity = existing[-1]  # default: last entity
            if right_table is not None:
                ref_tn = getattr(right_table, "name", None)
                for i, m in enumerate(models_so_far):
                    if getattr(m, "__tablename__", None) == ref_tn:
                        ref_entity = existing[i]
                        break
            if primary_col and foreign_col:
                join_val = getattr(ref_entity, primary_col, None)
                for s in secondary_rows:
                    if getattr(s, foreign_col, None) == join_val:
                        new_joined.append(existing + (s,))
            else:
                for s in secondary_rows:
                    new_joined.append(existing + (s,))
        joined = new_joined
        models_so_far.append(secondary)

    # Apply where clauses — determine which entity each clause references
    for clause in where_clauses:
        ref_table = _clause_references_table(clause)
        new_joined = []
        for tup in joined:
            # Find which position matches the referenced table
            matched = False
            for i, m in enumerate(models_so_far):
                if getattr(m, "__tablename__", None) == ref_table:
                    if _apply_clause([tup[i]], clause):
                        matched = True
                    break
            else:
                # Unknown table — apply to first entity as fallback
                matched = bool(_apply_clause([tup[0]], clause))
            if matched:
                new_joined.append(tup)
        joined = new_joined

    if len(select_entities) == 1:
        return FakeResult([t[0] for t in joined])
    return FakeResult(joined)
