# EduFlow audit — 2026-10-03

## Stack and status

- Current app: Next.js 16 / React 19 in `eduflow-next`, deployed at
  `https://eduflow-beryl-three.vercel.app/`.
- Public `/`, `/teacher`, and `/student` returned HTTP 200 during this review.
- Public `/api/health` returned HTTP 500 on the earlier deployed commit and
  HTTP 503 after the fixes deployed. The local Supabase secret key worked from
  a server-style request. Supabase returned `PGRST205`: `public.portal_users`
  is missing. Apply the schema before a full production classroom test.
- Local `npm run build` passed, including TypeScript. Local `npm run lint`
  passed with warnings from legacy loose types and unused imports.
- Gemini and Groq model-list endpoints returned HTTP 200; both configured
  model IDs were present. Content generation and independent review were not
  exercised because the database is not ready.

## Changes made in this review

- Removed the web app's SQLite fallback and dual writes. Portal accounts,
  sessions, outlines, enrollment, and workspace reads now use Supabase only.
- Changed `/api/health` to report Supabase readiness. It returns 503 when
  credentials or tables are unavailable.
- Replaced permissive Supabase grants and `USING (true)` policies. The current
  SQL revokes browser-role access to classroom tables and grants server-role
  access. **Re-run the current SQL in Supabase if the old script was applied.**
- Restricted workspace and provider telemetry APIs to teacher accounts.
- AI generation now requires a valid second-provider review. Invalid or failed
  verification leaves the draft unsaved. The seven-day plan shape is checked.
- Updated landing and pipeline copy to describe the implemented classroom
  workflow, replacing claims about an active ten-stage planner.
- Replaced the obsolete Python CI workflow with Next.js install, build, and
  lint checks. Updated setup documentation and environment template.
- Inspected teacher and student sign-in screens at phone width in light and
  dark themes. No page-wide horizontal overflow was observed at 390px.

## Remaining verification

1. Keep the complete `SUPABASE_SECRET_KEY` in local `.env.local` and Vercel
   Production. Do not paste it into chat or commit it.
2. Run the current `eduflow-next/supabase-schema.sql` in Supabase SQL Editor.
   Verify `/api/health` returns 200 after redeployment.
3. In the live app, register one real teacher and one student, enroll with the
   code, create an outline with approved source, generate, publish, and confirm
   the student can see the plan. Do not create disposable accounts in production
   unless there is a cleanup path.
4. Address the remaining lint warnings. They do not block the build.
5. AI verification reduces unsupported claims but is not a guarantee of factual
   accuracy. Teachers should review generated material before publishing.
