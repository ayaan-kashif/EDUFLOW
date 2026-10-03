# EduFlow

EduFlow is a Next.js classroom app. Teachers write outlines, add approved source text,
generate notes and a seven-day study plan, and publish them to students who join with
the teacher's enrollment code. The app uses Supabase PostgreSQL through server-only
API routes. It uses its own teacher/student accounts and sessions, not Supabase Auth.

## Run locally

Requires Node.js 22 or later and a Supabase project.

```powershell
npm ci --prefix eduflow-next
Copy-Item eduflow-next/.env.example eduflow-next/.env.local
# Edit eduflow-next/.env.local with your real values
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The teacher and student
portals are at `/teacher` and `/student`.

Required variables in `eduflow-next/.env.local` and Vercel:

| Variable | Purpose |
| --- | --- |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SECRET_KEY` | Complete server-side key; never add `NEXT_PUBLIC_` |
| `GEMINI_API_KEY` | AI draft generation |
| `GROQ_API_KEY` | Independent AI review |

Set `GEMINI_MODEL` and `GROQ_MODEL` only if the configured keys can access those
models. The `gsk_` key is for **Groq**, not xAI's Grok. The app does not query
Google Scholar or a research API; it uses the teacher-approved source text.
Teacher review remains necessary because AI verification cannot guarantee accuracy.

Run `eduflow-next/supabase-schema.sql` in the Supabase SQL Editor before using
the portals. **If an older version of this SQL file was applied, run the current
version again:** the old version granted public access to classroom tables, and
the current version removes those grants and policies. The script preserves data.

`DATABASE_URL=file:...` is used only by the optional one-time SQLite migration
script. The running web app does not use SQLite. The secret key must be complete;
a masked `sb_secret_...` value cannot authenticate.

## Deploy to Vercel

Use the repository root as the project root and the `build` script, or set
`eduflow-next` as the Vercel Root Directory and use its default Next.js build.
Set the four required variables for Production, redeploy, then check
`/api/health`. It returns HTTP 200 only when the classroom table is reachable.
The Vercel environment does not read your local `.env.local`.

## Checks

```powershell
npm run build
npm --prefix eduflow-next run lint
```

See [eduflow-next/README.md](eduflow-next/README.md) for the route map and
[AUDIT.md](AUDIT.md) for the latest review and remaining limits.
