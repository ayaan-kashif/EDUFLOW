# EduFlow

## Teacher and student portals

Open `/teacher` to create a teacher account. The teacher receives an eight-character
enrollment code, can save and edit outlines, publish them to enrolled students, and
generate revision notes plus a seven-day study plan. Open `/student` to create a
student account, enter the teacher's code, and view that teacher's published materials.
Students may join multiple teachers. Edits return an outline to draft and clear its old
AI materials until the teacher republishes and regenerates it.

The **Generate notes and plan** action requires at least 200 characters of teacher-approved
source text. Gemini drafts notes using only that source; Groq independently checks the
draft against it. An unsupported draft is rejected, and no generated material is saved.
Use `GEMINI_API_KEY` and `GROQ_API_KEY` for this two-provider flow. The supplied `gsk_`
key is for **Groq**, which is different from xAI's Grok. The app does not use Google
Scholar or a general research API. Teacher review remains necessary: independent AI
verification reduces errors but cannot prove every statement is correct.

On Windows, a clean local setup is:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env
.venv\Scripts\python.exe scripts/setup_sqlite.py
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then visit <http://localhost:8000/teacher> or
<http://localhost:8000/student>. The older `.html` URLs remain available. For an existing PostgreSQL database, apply
`alembic upgrade head` to create the new portal tables. The original planning workspace
at `/` remains a hackathon prototype and its older API routes are not account scoped;
use the new portals for teacher and student class sharing.

### Deploying on Vercel

Vercel runs this FastAPI app as a Python Function. It does not run the Dockerfile or
`scripts/start_web.py`. Set these variables in the Vercel project's **Settings → Environment
Variables** for each environment you deploy:

| Variable | Needed for | Value |
|---|---|---|
| `DATABASE_URL` | Required for registration, enrollment, and saved materials | Supabase PostgreSQL **Session pooler** connection string, including the database password. Use port 5432 and add `?sslmode=require`. Do not use SQLite on Vercel. |
| `GEMINI_API_KEY` | AI notes and study plans | Google Gemini API key. Used first for drafting. |
| `GROQ_API_KEY` | Independent factual check | Groq inference API key. Used first for verification. |
| `OPENAI_API_KEY` | Optional fallback | A key with API credits. A key with exhausted credits returns `429`. |
| `HF_TOKEN` | Optional alternative AI provider | Hugging Face Inference Providers token with credits. |
| `OPENROUTER_API_KEY` | Optional scanned-document OCR | Only needed for the vision OCR fallback in the older planning pipeline. |

The teacher notes feature generates from the teacher-approved source and outline. It
does not search the web or retrieve academic papers. Add `DATABASE_URL`, `GEMINI_API_KEY`,
and `GROQ_API_KEY` in the Vercel dashboard, then redeploy. Local `.env` is not transferred
to Vercel.

For the linked Supabase project, open **Connect → Session pooler** in its dashboard and
copy the full PostgreSQL URI. Replace `[YOUR-PASSWORD]` with the database password;
percent-encode special characters in that password. Its shape is
`postgresql://postgres.<project-ref>:<password>@<pooler-host>:5432/postgres?sslmode=require`.
Use the actual pooler host shown in Supabase. `SUPABASE_URL`, the publishable key,
the secret key, and the JWKS URL are for Supabase APIs/Auth and are not used when
Supabase supplies PostgreSQL only. The supplied secret key was masked, so it could
not be used. `@supabase/server` is a JavaScript package; this Python FastAPI app
uses SQLAlchemy and does not need it. On Vercel, database connections use no local
SQLAlchemy pool to avoid retaining idle connections in short-lived functions.

The Vercel build script runs `alembic upgrade head` against `DATABASE_URL`, so the
`portal_users` and related tables exist before the deployment becomes live. Leave any
custom Vercel Build Command override unset so `[tool.vercel.scripts]` takes effect. After
adding or changing environment variables, redeploy and check `/health/db`; it returns
`ok` only when the portal table is accessible. The original source-upload pipeline still
writes to local `uploads/` and needs durable object storage before it can work reliably on
Vercel.

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
2. The original planner uses class-level, teacher-entered mastery signals. The new portal stores student accounts and teacher enrollment only for access to shared study materials; it does not add individual mastery tracking.
3. Every external API (LLM, embeddings, parsing) goes through the provider abstraction in `app/providers/` — never call an SDK directly elsewhere.
4. Verification must use a different provider/model than generation. A model does not grade its own homework; this is enforced at call time, not just in config.
5. Minimizing replan churn is a first-class scheduling objective, not an afterthought.

## Quick start (no Docker needed)

Requires Python 3.11+. No Docker, no Postgres — uses SQLite.

```bash
pip install -r requirements.lock
pip install -e . --no-deps
DATABASE_URL=sqlite+aiosqlite:///./curriculumos.db python scripts/setup_sqlite.py
uvicorn app.main:app --reload
```

The public demo seeding route and sample content have been removed. New accounts and
workspaces start empty. The synthetic Biology fixture remains under `tests/fixtures/`
for automated tests only. **Load official syllabus** downloads the Cambridge Biology
syllabus when the network is available and stores its extracted sources.

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

Only `DATABASE_URL` is strictly required. Every provider key is optional — the chains skip what isn't configured, so the app can run with a local Ollama server and no cloud keys at all. Vercel does not provide that local Ollama server.

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
