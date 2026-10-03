# EduFlow UI redesign progress

Updated: 2026-10-03

## Completed

- [x] Installed the UI/UX Pro Max skill from the repository supplied by the user.
- [x] Generated and saved a project design system in `design-system/eduflow/MASTER.md`.
- [x] Configured the `21st` MCP endpoint in Codex with `API_KEY_21ST` as a persistent Windows user environment variable. `codex mcp list` confirms it is enabled.
- [x] Reviewed public 21st.dev glass card, dashboard, and background component collections for visual direction. The app remains plain HTML/CSS/JavaScript.
- [x] Added shared light and dark color, typography, glass, depth, focus, and motion rules in `app/static/ui-system.css`.
- [x] Redesigned the main planning workspace hero, navigation, cards, and advanced workflow using the shared system.
- [x] Redesigned teacher and student portals with dimensional hero cards, responsive dashboards, clearer forms, and theme controls.
- [x] Kept the theme preference shared across the main workspace, advanced workflow, and both portals.
- [x] Reviewed desktop light and dark screenshots of the main workspace and portals, plus the advanced workflow and signed-in teacher/student dashboards.
- [x] Reviewed mobile screenshots and checked all four pages at 390px, 768px, and 1440px in both themes with reduced motion enabled; no horizontal overflow or browser errors.
- [x] Exercised the local teacher outline publishing and student enrollment flow in a disposable preview database.
- [x] Stored the supplied OpenAI API key in the ignored `.env`, restarted EduFlow, and verified that OpenAI is first in the generation provider chain. The key itself is not stored in tracked files.
- [x] Updated `.gitignore` for nested `.env` files, private keys, local databases, uploads, runtime data, and test/browser output. Verified that 176 files Git would include contain no recognized API key or private-key patterns, and no already-tracked files match the ignore rules.
- [x] Added Vercel build-time PostgreSQL migrations, normalized hosted database URLs for asyncpg, added a portal-schema readiness check, and tested registration from a fresh disposable database. Added clean `/teacher`, `/student`, and `/pipeline` URLs plus a favicon.
- [x] Added Gemini drafting and Groq verification providers; both supplied keys passed live authentication and tiny completion calls. Local `.env` remains ignored by Git.
- [x] Required teacher-approved source text before AI generation. A separate provider checks the draft against that source and rejects unsupported material before students receive it.
- [x] Removed the public demo seeding route, sample entry point, default Biology values, and user-facing demo copy. Moved the synthetic PDF to `tests/fixtures` for internal tests.
- [x] Completed a live Gemini-to-Groq study-material call: notes and seven plan days were generated from source text and independently checked. The full test suite passed (216 passed, 1 skipped); Ruff, JavaScript syntax, and local database health checks passed.
- [x] Added SQLite setup handling for the new source column. PostgreSQL migration 0006 clears older ungrounded notes during upgrade.
- [x] Added the user-specified Supabase MCP server to Codex and completed OAuth login. Kept Supabase as PostgreSQL only; documented its Session pooler `DATABASE_URL` for Vercel and disabled local SQLAlchemy pooling in Vercel functions.

## Remaining verification and integration limits

- [ ] The 21st.dev MCP endpoint returned HTTP 401 for the provided key. Its catalogue tools cannot be called until the key or account access is corrected. Codex configuration itself is present and enabled.
- [ ] OpenAI returned `429 insufficient_quota` during a live test: the key is accepted but the account needs API credits before AI notes and study plans can generate.
- [ ] Vercel needs a persistent PostgreSQL `DATABASE_URL` configured in the project dashboard and a redeploy. The deployment dashboard requires the owner's login, so the live environment and server logs were not available for direct verification.
- [ ] The older source-upload pipeline writes to local disk; durable object storage is still needed for that workflow on Vercel.
- [ ] Gemini web search grounding returned HTTP 429 in a live test, so the portal relies on teacher-provided source material instead of web research. There is no Google Scholar integration.
- [ ] Supabase PostgreSQL still needs its full Session pooler `DATABASE_URL` with the database password in Vercel. The supplied Supabase API keys and JWKS URL cannot authenticate PostgreSQL. Live Vercel registration remains unverified until that variable is configured and the deployment is rebuilt.

## Design sources

- UI/UX Pro Max generated design system: `design-system/eduflow/MASTER.md`
- 21st.dev public glassmorphism sidebar and dashboard component catalogues
- Implemented styles: `app/static/ui-system.css` and `app/static/portal.css`
