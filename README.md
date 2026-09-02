# CurriculumOS

> CurriculumOS ingests textbooks, past papers, mark schemes, and academic calendars to build a grounded, citable term plan — and automatically replans it when the calendar changes, while minimizing disruption to what's already been taught.

## What it actually does

Most AI lesson planners generate plausible-looking lesson text and staple a citation on afterwards. The hard part isn't the prose — LLMs made that commodity. The hard part is the structured system around the LLM: provenance you can mechanically check, question→objective mapping you can correct, and a scheduler that respects how much a teacher's term plan is allowed to move.

The pipeline, end to end:

```
upload sources          PDF / DOCX / scanned book
      ↓                 anydoc (no ML model) → vision-LLM OCR for scanned pages
provenance store        every paragraph → document + page + bbox + content hash
      ↓
curriculum extraction   LLM proposes topics / objectives / prerequisites
      ↓                 tagged machine_extracted, confidence < 1.0, always
question parsing        exam question ↔ mark scheme entry as ONE linked entity
      ↓
ensemble mapping        embedding + lexical + terminology + LLM → multi-label
      ↓                 weighted mappings with confidence, not classification
teacher correction      logged verbatim; overwrites the live mapping; always wins
      ↓
emphasis scoring        frequency × recency decay × marks × syllabus × structure
      ↓
CP-SAT scheduling       teaching units → calendar capacity, hard constraints first
      ↓
disruption & replan     churn minimisation is an objective, not a report
      ↓
grounded generation     retrieve → generate claims → verify with a DIFFERENT model
                        → reject unsupported → render
```

A teacher workspace at `/` walks all ten stages in order.

## Ground rules

1. Every generated instructional claim carries provenance — a mechanically checkable span reference, not "page 47".
2. No student-level data. Class-level, teacher-entered mastery signals only.
3. Every external API (LLM, embeddings, parsing) goes through the provider abstraction in `app/providers/` — never call an SDK directly elsewhere.
4. Verification must use a different provider/model than generation. A model does not grade its own homework; this is enforced at call time, not just in config.
5. Minimizing replan churn is a first-class scheduling objective, not an afterthought.

## Quick start (hackathon demo)

Requires Docker and Python 3.11+.

```bash
cp .env.example .env          # fill in at least DATABASE_URL
docker compose up -d db
pip install -e ".[dev]"       # lightweight: app + tests + linting
alembic upgrade head
uvicorn app.main:app --reload
```

Then run the self-contained demo (generates PDFs in memory, no external files needed):

```bash
python scripts/demo_seed.py   # exercises all 10 pipeline stages
```

Or open <http://localhost:8000> and walk the workspace manually.

Optional integrations are split out so a fresh setup does not download every
OCR, worker, and cloud-provider dependency before the app can boot:

```bash
pip install -e ".[parsing]"   # docling + anydoc for richer document parsing
pip install -e ".[cloud]"     # Anthropic provider support
pip install -e ".[workers]"   # Celery + Redis worker dependencies
pip install -e ".[full]"      # everything above plus dev tools
```

The default install still includes local/Ollama-compatible LLM support through
the OpenAI-compatible SDK, Postgres/pgvector support, pypdf text-layer parsing,
and the OR-Tools scheduler.

## Providers

Everything external is a swappable provider behind `app/providers/`, routed by
[`config/providers.yaml`](config/providers.yaml) with retry + circuit breaker + ordered fallback.

| Capability | Chain | Notes |
|---|---|---|
| Parsing | `anydoc` → `vision_llm_ocr` | anydoc is pure Rust, no ML weights, <5ms/doc; OCR only reached when a PDF genuinely has no text layer. `docling` is available but kept out of the default chain because its layout model downloads on first use. |
| LLM generation | `ollama` → cloud providers | Any of Anthropic / OpenAI / Groq / OpenRouter / Together / Fireworks; unconfigured providers are skipped, not failed. |
| LLM verification | `ollama_verify` → cloud | First entry must differ from generation's — checked at call time. |
| Embeddings | `qwen3-embedding:0.6b` via Ollama | 1024-dim, stored in pgvector on `curriculum_nodes.embedding`. |

Only `DATABASE_URL` is strictly required. Every provider key is optional — the chains skip what isn't configured, so the app runs with a local Ollama and no cloud keys at all.

## Testing

```bash
python -m pytest -q            # 164 tests, <6 seconds
python -m ruff check app/ tests/   # lint
python -m mypy app/api/planning.py app/planning/service.py --ignore-missing-imports  # type check
```

Tests cover: pure logic (scheduler, signals, claim parsing, question-ref, emphasis, curriculum extraction), service orchestration (FakeSession with real SQLAlchemy queries), and API endpoints (Starlette TestClient). No database or provider keys required to run the full suite.

## Repo layout

```
app/
  providers/    # LLM, embedding, and parsing abstractions — the only place SDKs are called
  ingestion/    # parsing → source_documents/source_spans, question parsing, curriculum extraction
  domain/       # curriculum graph, calendar, and ORM models
  mapping/      # question → objective ensemble mapper
  emphasis/     # historical assessment emphasis scoring
  planning/     # OR-Tools CP-SAT scheduler / replanner
  generation/   # verify-then-render lesson & assessment generation
  api/          # FastAPI routes
  static/       # teacher workspace UI
  workers/      # Celery tasks
migrations/     # Alembic
config/         # provider routing config (no secrets)
eval/           # retrieval/extraction benchmarks
```

Design docs live in [`CurriculumOS_Handoff/`](CurriculumOS_Handoff/) — start with [`00_README.md`](CurriculumOS_Handoff/00_README.md).

## Deliberate shortcuts

Marked in code with `# ponytail:` comments naming the ceiling and the upgrade path — page-level (not paragraph-level) provenance on OCR'd documents, single-session scheduling for splittable units, hard constraints plus churn minimisation without the full soft-constraint set. `grep -rn "ponytail:" app/` lists them.
