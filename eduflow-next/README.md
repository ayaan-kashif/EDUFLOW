# EduFlow Next.js app

## Routes

- `/`: classroom landing page; signed-in teachers can see stored workspace records.
- `/teacher`: teacher account, enrollment code, outlines, AI notes and study plans.
- `/student`: student account, teacher-code enrollment, published materials.
- `/pipeline`: current classroom workflow and teacher-only provider telemetry.
- `/api/health`: database readiness; 200 means the portal table is accessible.

All classroom reads and writes use the server-only Supabase secret key. Public
Supabase keys are not required by this app. The SQL schema denies browser roles
direct access to classroom tables. Teacher/student authorization is enforced in
the Next.js API routes using an HTTP-only session cookie.

## Setup

1. Run `supabase-schema.sql` in the Supabase SQL Editor. Re-run it if you used
   an older copy because it now removes permissive policies.
2. Copy `.env.example` to `.env.local` and fill in the project URL, complete
   server-side secret key, Gemini key, and Groq key.
3. Run `npm install` and `npm run dev`, then open `http://localhost:3000`.
4. Run `npm run build` to check the production build.

The app does not automatically create Supabase tables at runtime. Missing schema
or credentials make `/api/health` return 503. Never commit `.env.local` or
put `SUPABASE_SECRET_KEY` in a `NEXT_PUBLIC_` variable.

## Optional data migration

`npm run migrate:supabase` copies users, outlines, and enrollments from the old
local SQLite file into Supabase. Use it only when you have existing local data
to keep, after setting `DATABASE_URL=file:...` to that file. It does not
migrate the old session tokens, so users must sign in again.

AI generation uses the teacher's approved source. A second provider checks the
draft; generation fails without a valid independent review. A teacher should
still inspect the result before publishing it.
