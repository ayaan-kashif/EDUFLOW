# EduFlow

> EduFlow ingests textbooks, past papers, mark schemes, and academic calendars to build a grounded, citable term plan — and automatically replans it when the calendar changes, while minimizing disruption to what's already been taught.

## What it actually does

Most AI lesson planners generate plausible-looking lesson text and staple a citation on afterwards. The hard part isn't the prose — LLMs made that commodity. The hard part is the structured system around the LLM: provenance you can mechanically check, question→objective mapping you can correct, and a scheduler that respects how much a teacher's term plan is allowed to move.

The pipeline, end to end:

```
upload sources          PDF / DOCX / scanned book
      ↓                 anydoc (no ML model) → vision-LLM OCR for scanned pages
provenance store        source blocks → document + parser-reported page/bbox + content hash
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
CP-SAT scheduling       bounded durations + split sessions + emphasis + taught-session locks
      ↓
disruption & replan     churn minimisation is an objective, not a report
      ↓
grounded generation     retrieve → generate claims → verify with a DIFFERENT model
                        → reject unsupported → render
```

The workspace at `/` has Sources, Plan, and Evidence views. The original ten-stage
workflow remains at `/pipeline.html`. See [the upgrade and demo guide](docs/HACKATHON_UPGRADES.md)
for the implemented features, evaluation results, and remaining production work.

## Ground rules

1. Generated claims undergo citation-resolution, content-hash, and supplied-quote checks before independent semantic verification. Mechanical integrity alone does not establish factual support.
2. No student-level data. Class-level, teacher-entered mastery signals only.
3. Every external API (LLM, embeddings, parsing) goes through the provider abstraction in `app/providers/` — never call an SDK directly elsewhere.
4. Verification must use a different provider/model than generation. A model does not grade its own homework; this is enforced at call time, not just in config.
5. Minimizing replan churn is a first-class scheduling objective, not an afterthought.

## Quick start (hackathon demo — no Docker needed)

Requires Python 3.11+. No Docker, no Postgres — uses SQLite.

```bash
pip install -r requirements.lock
pip install -e . --no-deps
DATABASE_URL=sqlite+aiosqlite:///./curriculumos.db python scripts/setup_sqlite.py
uvicorn app.main:app --reload
```

The original pipeline exercise is also available when its AI providers are configured:

```bash
python scripts/demo_seed.py   # exercises all 10 pipeline stages
```

For the provider-free presentation, open <http://localhost:8000> and select **Try the Biology demo**. This seeds
original synthetic sources, mappings, a timetable, and inspectable claims without
provider keys. The demo claims remain explicitly unchecked; they are not fabricated
verification successes. **Load public syllabus** downloads the official Cambridge
Biology syllabus when the network is available, then stores its extracted sources.

On Windows PowerShell, after creating and installing into a virtual environment:

```powershell
$env:DATABASE_URL = 'sqlite+aiosqlite:///./curriculumos.db'
.venv/Scripts/python.exe scripts/setup_sqlite.py
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

The setup script creates missing tables and does not overwrite `.env`.

### With Docker (PostgreSQL)

```bash
cp .env.example .env          # DATABASE_URL=postgresql+asyncpg://...
docker compose up -d db
alembic upgrade head
uvicorn app.main:app --reload
```

Optional integrations are split out so a fresh setup does not download every
OCR, worker, and cloud-provider dependency before the app can boot:

```bash
pip install -e ".[parsing]"   # docling + anydoc for richer document parsing
pip install -e ".[cloud]"     # Anthropic provider support
pip install -e ".[workers]"   # optional dependencies for a future durable worker deployment
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
| Parsing | `pypdf_text` → `anydoc` → `vision_llm_ocr` | Text PDFs retain page numbers; pypdf boxes cover the page. AnyDoc does not establish page-level provenance. Optional Docling can supply block coordinates. |
| LLM generation | `huggingface` → other cloud providers → `ollama` | Configure `HF_TOKEN` for hosted inference. Unconfigured providers are skipped. |
| LLM verification | `huggingface_verify` → other cloud providers → `ollama_verify` | A distinct model is required; generation cannot verify itself. |
| Embeddings | `qwen3-embedding:0.6b` via Ollama | 1024-dim, stored in pgvector on `curriculum_nodes.embedding`. |

Only `DATABASE_URL` is strictly required. Every provider key is optional — the chains skip what isn't configured, so the app runs with a local Ollama and no cloud keys at all.

For Hugging Face, set `HF_TOKEN` in the ignored `.env` file. `HF_MODEL` defaults to
`Qwen/Qwen3-4B-Instruct-2507:nscale`; `HF_VERIFY_MODEL` uses a different Llama model.
The token needs Inference Providers permission and available inference credits.
Restart the server after changing these settings. Model routing can change; both
model IDs are configurable. Successful objective extraction persists the nodes;
planning and replanning do not call this API again.

## Testing

```bash
python -m pytest -q
python -m ruff check app tests eval
python -m mypy app/api/planning.py app/planning/service.py --ignore-missing-imports  # type check
node --check app/static/studio.js
python -m eval.run             # writes the labeled offline regression report
```

Tests cover pure logic, service orchestration, real temporary SQLite integration,
streamed ingestion, exports, taught-session preservation, and API endpoints. No
running database server or provider keys are required. The synthetic evaluation
does not establish real-world teaching quality or semantic hallucination rates.

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
  workers/      # bounded process-local ingestion jobs and SSE progress
migrations/     # Alembic
config/         # provider routing config (no secrets)
eval/           # labeled synthetic mapping, evidence integrity, and replan regression
```

Design docs live in [`EduFlow_Handoff/`](EduFlow_Handoff/) — start with [`00_README.md`](EduFlow_Handoff/00_README.md).

## Deliberate shortcuts

The [competitive execution blueprint](docs/COMPETITIVE_BLUEPRINT.md) records the
first-party benchmark, implemented control-room workflow, and three-minute pitch.
The workspace now includes a source-to-plan wizard, coverage/evidence ledger,
saved-plan switching, and Recovery Lab comparisons with exact reviewed application.
PostgreSQL installations need migration `0004` (`alembic upgrade head`); rerun the
SQLite setup script for local installations. Existing records are preserved.

This remains a single-tenant prototype. Job metadata, provider breakers, and rate
limits are process-local; a multi-process deployment needs shared state and durable
workers. Source attribution precision depends on the parser. Generation retrieval
uses a bounded hybrid rerank with lexical fallback, rather than an indexed span
vector database. Scheduling supports split sessions and bounded shortening; it
does not infer pedagogically safe minimum durations. Use teacher-approved bounds.
Run `rg "ponytail:" app` to find additional local limitations.
