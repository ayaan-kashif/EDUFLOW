"""Portable column types that work with both PostgreSQL and SQLite.

PostgreSQL uses native ARRAY, JSONB, UUID, and Vector types.  SQLite has
none of these, so we fall back to Text columns that store JSON-encoded
values.  The helper functions ``to_db`` / ``from_db`` handle the
conversion transparently.
"""

from __future__ import annotations

import json
import uuid as _uuid

from sqlalchemy import String, Text, TypeDecorator


class PortableUUID(TypeDecorator):
    """UUID that stores as TEXT on SQLite and native UUID on Postgres."""

    impl = Text
    cache_ok = True

    def __init__(self, as_uuid: bool = True, **kw):
        super().__init__(**kw)
        self.as_uuid = as_uuid

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if self.as_uuid and isinstance(value, _uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if self.as_uuid:
            return _uuid.UUID(value) if not isinstance(value, _uuid.UUID) else value
        return value

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PG_UUID
            return dialect.type_descriptor(PG_UUID(as_uuid=self.as_uuid))
        return dialect.type_descriptor(Text())


class PortableJSON(TypeDecorator):
    """JSON that stores as TEXT on SQLite and JSONB on Postgres."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(Text())


class PortableArray(TypeDecorator):
    """Array that stores as JSON TEXT on SQLite and native ARRAY on Postgres."""

    impl = Text
    cache_ok = True

    def __init__(self, item_type=None, **kw):
        super().__init__(**kw)
        self.item_type = item_type

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps([str(v) for v in value])

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy import ARRAY
            return dialect.type_descriptor(ARRAY(String))
        return dialect.type_descriptor(Text())


class PortableVector(TypeDecorator):
    """Vector that stores as JSON TEXT on SQLite and native Vector on Postgres."""

    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = 1024, **kw):
        super().__init__(**kw)
        self.dimensions = dimensions

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(Text())
