# EduFlow upgrade and demo guide

All changes are in the existing project folder. No archive or deployment is required.

## Implemented

| Area | Behavior |
|---|---|
| Workspace | Sources, Plan, Evidence; paper and sage palette, dark mode, responsive layout, command palette, reduced-motion support. Original workflow remains at `/pipeline.html`. |
| Scheduling | CP-SAT chooses session minutes within teacher-selected bounds, splits eligible units, rewards assessment emphasis and coverage, and penalizes changes to prior sessions. An independent validator checks the result. |
| Replanning | Coverage preference preview, date preview before closures, animated timeline changes, aggregated split-session differences, actual scheduled minutes, and taught-session locks. |
| Explanation | Per-session justification, source pages, emphasis, prerequisites, solve time, unscheduled reasons, and a sufficient CP-SAT conflict set where available. |
| Evidence Lens | Original PDF rendered using bundled PDF.js, matching extracted text runs highlighted, source hash and attribution precision displayed. Page-level parsing is identified honestly. |
| Audit | Exact source matches, unknown curriculum references, related passages requiring review, and missing evidence. This is a mechanical audit, not an automated truth verdict. |
| Resilience | Seeded independent whole-day closure simulations, high-emphasis coverage estimate, Wilson sampling interval, at-risk units, and solver-budget disclosure. Days with taught sessions are excluded from future closure sampling. |
| Exports | Saved timetable to RFC 5545 ICS and a paginated PDF. Times are local floating timetable times. |
| Mapping corrections | Question-level train/validation split for local lexical and terminology weight calibration. Requires at least 20 genuine corrected mappings across 10 questions; synthetic demo mappings are excluded. Weights are adopted only if held-out error does not worsen. |
| Grounding | Bounded lexical/embedding retrieval with outage fallback; cited span, hash, and quote validation before a separate-model semantic verifier; document text treated as untrusted input. |
| Ingestion | Upload size/capacity bounds, tracked asynchronous jobs, SSE progress, durable document/span storage, and parser execution off the event loop for text PDFs. |
| Observability | Provider retry/fallback/breaker events, request IDs and timing headers, bounded process-local request limiting. |
| Demo/validation | Original Biology fixtures and PDF, optional public Cambridge syllabus download, reproducible evaluation runner, dependency lock, CI workflow, integration tests, and a Playwright browser walkthrough. |

## Run locally

Use Python 3.11 or newer. The local `.venv` already contains the tested dependencies.

```powershell
$env:DATABASE_URL = 'sqlite+aiosqlite:///./curriculumos.db'
.venv/Scripts/python.exe scripts/setup_sqlite.py
.venv/Scripts/python.exe -m uvicorn app.main:app --reload
```

Open `http://localhost:8000`. For a fresh installation, create a virtual environment,
install `requirements.lock`, then install the project with `pip install -e . --no-deps`.
The setup script does not alter provider keys or `.env`; keep the environment variable
set when launching the server. Existing PostgreSQL installations can retain their usual
Alembic setup. The control-room upgrade adds migration `0004` for source extraction
caches and reviewed recovery scenarios. Run `alembic upgrade head` for PostgreSQL;
for local SQLite, rerun `python scripts/setup_sqlite.py` to create missing tables.

## Three-minute demo

1. **0:00–0:25:** Explain the problem: unexpected closures disrupt prerequisite order,
   coverage, and teacher preparation. Open with the class-level-only data model.
2. **0:25–1:00:** Select **Try the Biology demo**. Show the objective graph and timetable.
   Explain that these are original fixtures, while a separate action loads a public syllabus.
3. **1:00–1:40:** Preview “Snow day Thursday + sports day next Tuesday.” With the fixture
   reference date of October 5, 2026, these resolve to October 8 and 13. Apply and replan.
   Enzymes can shrink from 180 to 120 minutes across fewer sessions while retaining
   coverage. Read the actual displayed move counts rather than promising fixed counts.
4. **1:40–2:10:** Inspect a lesson's explanation. In Evidence, click a claim to open the
   matching passage in the original PDF. Demo claims are visibly unchecked.
5. **2:10–2:35:** Audit the text below. Show the exact match, review-needed claim, and
   unknown code. Explain what the checker establishes.
6. **2:35–3:00:** Show resilience with its interval, export the plan, and present the
   measured offline regression results. A recording of this flow remains useful backup.

```text
Enzymes are biological catalysts.
Enzymes work equally well at every temperature.
BIO.FAKE.99 is an official objective.
```

**Try the Biology demo** restores only its synthetic calendar availability for replay.
It retains previous plan versions and does not reset uploaded documents.

## Reproduce checks and results

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check app tests eval
.venv/Scripts/python.exe -m mypy app/api/planning.py app/planning/service.py --ignore-missing-imports
node --check app/static/studio.js
.venv/Scripts/python.exe -m eval.run
```

`eval/report.json` uses 20 easy original Biology question labels, six citation-integrity
cases, and one disruption scenario. Current results: precision@1 **1.0**, precision@3
**0.3333**, six mechanical checks correct with zero false accepts, and **one** unit moved
against **eight** in the naive rebuilding baseline, with zero hard-constraint violations.
Latency is measured per run and should be read from the report. These numbers are
regression evidence for the supplied fixtures, not broad competitive quality claims.

`scripts/verify_studio.cjs` uses Playwright installed under `.runtime/browser` and a
review server at port 8017. `STUDIO_BROWSER` can point to a Chromium executable;
the default is the locally available Brave. It verifies the real demo, compression,
lesson inspector, source highlights, audit, mobile overflow, and PDF export rendering.
It writes screenshots and a verification report under ignored `.runtime/`.

## Remaining production and research work

- Authentication, tenant-scoped authorization and data migration, department visibility,
  durable Redis/Celery workers, shared rate limiting, and multi-process observability.
- Google Calendar OAuth/synchronization, vector-indexed source retrieval, and additional
  pedagogical constraints such as spacing and per-objective safe compression limits.
- A measured teacher study, expert-labeled exam mapping data, live plain-prompt comparison,
  semantic unsupported-claim rate, and real held-out improvement after teacher corrections.
- Public deployment, QR codes, and a recorded backup. Provider keys must be configured
  locally for live extraction/generation/verification; the offline demo needs no keys.

The forecast assumes independent closures, is bounded to a 15-second run budget, and
may use feasible rather than proven-optimal scenarios. The sampling interval does not
include uncertainty in closure rates or solver quality. It identifies at-risk objectives;
it does not yet optimize placement of additional buffer lessons. Lexical shortlisting
and audit each inspect at most 2,000 stored spans; very large corpora require indexing.
