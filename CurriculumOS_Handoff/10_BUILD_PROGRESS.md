# 10 - Build Progress

This file is the current engineering handoff. Read this first before scanning
the whole repository. Keep it updated after each major change.

## Current State

- Branch: `main`
- Last pushed commit observed: `d5e82e1`
- Local app was verified running at `http://127.0.0.1:8000`
- Docker services were verified:
  - `curriculumos-db-1` using `pgvector/pgvector:pg16`
  - `curriculumos-redis-1` using `redis:7-alpine`
- Alembic migrations were run successfully against local Postgres.
- Minimal runtime dependencies were installed into the bundled Codex Python:
  FastAPI, Uvicorn, SQLAlchemy, AsyncPG, Psycopg, pgvector, Pydantic Settings,
  PyYAML, Tenacity, HTTPX, python-multipart, Alembic, and OR-Tools.
- Dependency groups have been split so `pip install -e ".[dev]"` stays
  lightweight. Heavy parsing, cloud-provider, and worker packages are available
  through explicit extras.
- Lightweight dev install was verified with `pip install -e ".[dev]"`.

## Implemented Product Areas

- FastAPI app with a single static teacher workspace at `/`.
- Health, ingestion, calendar, mapping, emphasis, planning, correction,
  mastery, generation, browse, and debug routers.
- SQLAlchemy ORM models for the MVP schema, including:
  - source documents and source spans
  - curriculum nodes and edges
  - exam questions and mark scheme entries
  - question/span attribution join tables
  - question-objective mappings
  - academic calendars and instruction windows
  - plan versions and scheduled units
  - teacher corrections
  - class-level mastery signals
  - generated claims and claim evidence
- Alembic migrations through `0003_add_curriculum_node_embedding.py`.
- Provider abstraction and fallback routing for LLM, embedding, and parsing
  providers.
- Provenance-preserving ingestion service.
- Question and mark-scheme parsing with span/page attribution.
- Curriculum extraction from source spans via LLM JSON output.
- Multi-signal question-to-objective mapper:
  embedding, lexical, terminology, and LLM scoring.
- Teacher correction logging, with human corrections overriding live mappings.
- Historical assessment emphasis scoring with normalized components.
- OR-Tools CP-SAT scheduling prototype with hard constraints and churn
  minimization.
- Grounded generation pipeline:
  retrieve evidence, generate claims, verify with a separate provider, persist
  verification status and evidence links.
- Basic end-to-end teacher workspace UI for the ten-stage pipeline.

## Recent Completed Commits

- `782aefc` - Fix scheduler prerequisite date ordering
- `2f69b53` - Fix inverted calendar slot durations
- `f66b0a3` - Sanitize uploaded document filenames
- `cde4091` - Update existing machine mappings on rerun
- `2ab2565` - Parse wrapped LLM mapping scores
- `e757599` - Remove stale machine mappings on rerun
- `621ee01` - Create database sessions lazily
- `83fabef` - Handle mapping shortlist embedding failures
- `14076ce` - Validate assessment generation count
- `d5e82e1` - Validate correction mapping weights
- `baee326` - Add plan-diff API and replan UI comparison table

## Important Fixes Already Made

- Scheduler prerequisite constraints now compare actual calendar dates, not
  sorted window positions. This prevents same-day prerequisite/dependent
  scheduling when multiple windows exist on one day.
- Calendar slot duration now uses signed `total_seconds()` so inverted slots
  are rejected instead of becoming near-24-hour windows.
- Uploaded filenames are reduced to a safe basename before writing into
  `uploads/`.
- Re-running machine mapping updates existing rows instead of duplicating them.
- Stale machine mappings are removed when a later run falls below the
  confidence threshold.
- Human-corrected mappings are preserved across mapper reruns.
- LLM mapping-score parsing now uses the shared `loads_llm_json` helper, so
  fenced or prose-wrapped JSON works.
- Database engine/session creation is lazy, so importing API modules no longer
  requires `DATABASE_URL` immediately.
- Auto-shortlist embedding failures in mapping return an actionable `400`.
- Assessment generation count is constrained to `1..50`.
- Mapping correction weights are validated as numeric values in `0..1`.
- Optional LLM and parser provider modules are imported lazily, so missing
  optional packages do not break app startup.
- Heavy dependencies were moved out of the default install into extras:
  `parsing`, `cloud`, `workers`, and `full`.

## Verification Status

- `compileall` passes for `app` and `tests`.
- Local Docker services and migrations were verified.
- Local HTTP checks passed:
  - `/health` returned `{"status":"ok"}`
  - `/` returned the teacher workspace HTML
  - `/docs` returned the OpenAPI UI
  - `/stats` returned DB-backed counts
- Full lightweight test suite passes with `143 passed, 1 skipped`.
- Python 3.14 local environment verified; tests pass despite project docs
  saying 3.11+.

## Known Gaps / Next Work

Highest priority:

1. Run the full test suite in a proper Python 3.11+ environment.
   - The bundled runtime is Python 3.12.
   - `pyproject.toml` allows Python `>=3.11`, so this may be fine, but the
     project docs say Python 3.11+ and should be tested intentionally.

2. Add endpoint/service tests for DB orchestration.
   - Current tests are mostly pure logic and fake-session tests.
   - Live Postgres coverage is intentionally sparse.

3. Improve the "why is this scheduled here?" acceptance criterion.
   - The UI can show a schedule, but a complete justification should include:
     prerequisite dependency, objective, source pages, emphasis weight, and
     time-to-exam.

4. ~~Add class-level mastery signal endpoints/UI.~~ ✅ Done.
   - `app/api/mastery.py` with list, create, and summary endpoints.
   - Teacher workspace UI in stage 05: mark objectives as mastered /
     needs reinforcement / reteach with summary figures.
   - Tests in `tests/test_mastery.py` pass.

5. ~~Add plan-diff endpoint.~~ ✅ Done.
   - Pure `diff_schedules()` helper in `app/planning/service.py`.
   - `GET /planning/plans/{id}/diff` endpoint returns per-unit change details.
   - Replan UI shows previous date → new date, minutes, and change type.
   - Tests in `tests/test_planning_diff.py` pass.

6. Add real demo seeding / one-command demo path.
   - A sample syllabus exists under `demo/`, and one document was present in
     the local database during verification, but the repo needs a robust demo
     script that can seed enough data to exercise all ten stages.

## Things Not To Add Silently

- Do not add student-level data. V1 is class-level only.
- Do not bypass provider abstractions with direct SDK calls outside
  `app/providers/`.
- Do not treat unsupported or unverified claims as facts.
- Do not remove provenance requirements to make demo data easier.
- Do not make the scheduler optimize churn only in reports; churn belongs in
  the solver objective.

## Suggested Next Task

Add real demo seeding / one-command demo path. A sample syllabus exists
under `demo/`, but the repo needs a robust demo script that can seed
enough data to exercise all ten stages without manual clicking.
