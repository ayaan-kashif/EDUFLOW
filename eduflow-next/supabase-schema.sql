-- ==============================================================================
-- EduFlow Complete PostgreSQL Schema for Supabase
-- Run this script in your Supabase SQL Editor (https://supabase.com/dashboard/project/hswzqcusplgwlnorvtcq/sql)
-- ==============================================================================

-- 1. Portal Users (Teachers & Students)
CREATE TABLE IF NOT EXISTS public.portal_users (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('teacher', 'student', 'admin')),
  enrollment_code TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Portal Sessions (Cookie Authentication)
CREATE TABLE IF NOT EXISTS public.portal_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES public.portal_users(id) ON DELETE CASCADE,
  token_hash TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);

-- 3. Teacher Enrollments (Classroom Mapping)
CREATE TABLE IF NOT EXISTS public.teacher_enrollments (
  teacher_id TEXT NOT NULL REFERENCES public.portal_users(id) ON DELETE CASCADE,
  student_id TEXT NOT NULL REFERENCES public.portal_users(id) ON DELETE CASCADE,
  PRIMARY KEY (teacher_id, student_id)
);

-- 4. Class Outlines (Lesson Plans, Notes & Study Guides)
CREATE TABLE IF NOT EXISTS public.class_outlines (
  id TEXT PRIMARY KEY,
  teacher_id TEXT NOT NULL REFERENCES public.portal_users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  subject TEXT NOT NULL,
  content TEXT NOT NULL,
  source_text TEXT,
  published BOOLEAN NOT NULL DEFAULT FALSE,
  notes TEXT,
  study_plan JSONB,
  generated_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Curriculum Nodes (Atomic Objectives & Topics)
CREATE TABLE IF NOT EXISTS public.curriculum_nodes (
  id TEXT PRIMARY KEY,
  node_type TEXT NOT NULL,
  label TEXT NOT NULL,
  description TEXT,
  syllabus_ref TEXT,
  origin TEXT NOT NULL,
  confidence DOUBLE PRECISION NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Curriculum Edges (DAG Prerequisites)
CREATE TABLE IF NOT EXISTS public.curriculum_edges (
  id TEXT PRIMARY KEY,
  from_node_id TEXT NOT NULL REFERENCES public.curriculum_nodes(id) ON DELETE CASCADE,
  to_node_id TEXT NOT NULL REFERENCES public.curriculum_nodes(id) ON DELETE CASCADE,
  edge_type TEXT NOT NULL,
  confidence DOUBLE PRECISION NOT NULL
);

-- 7. Source Documents
CREATE TABLE IF NOT EXISTS public.source_documents (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  doc_type TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  page_count INTEGER NOT NULL,
  uri TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Source Spans
CREATE TABLE IF NOT EXISTS public.source_spans (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES public.source_documents(id) ON DELETE CASCADE,
  page_number INTEGER NOT NULL,
  start_char INTEGER NOT NULL,
  end_char INTEGER NOT NULL,
  text_snippet TEXT NOT NULL
);

-- 9. Academic Calendars
CREATE TABLE IF NOT EXISTS public.academic_calendars (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  academic_year TEXT NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL
);

-- 10. Calendar Days
CREATE TABLE IF NOT EXISTS public.calendar_days (
  id TEXT PRIMARY KEY,
  calendar_id TEXT NOT NULL REFERENCES public.academic_calendars(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  day_type TEXT NOT NULL,
  notes TEXT
);

-- 11. Teaching Units
CREATE TABLE IF NOT EXISTS public.teaching_units (
  id TEXT PRIMARY KEY,
  node_id TEXT NOT NULL REFERENCES public.curriculum_nodes(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  duration_minutes INTEGER NOT NULL,
  order_index INTEGER NOT NULL
);

-- 12. Plan Versions
CREATE TABLE IF NOT EXISTS public.plan_versions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  version_number INTEGER NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 13. Scheduled Units
CREATE TABLE IF NOT EXISTS public.scheduled_units (
  id TEXT PRIMARY KEY,
  plan_version_id TEXT NOT NULL REFERENCES public.plan_versions(id) ON DELETE CASCADE,
  unit_id TEXT NOT NULL REFERENCES public.teaching_units(id) ON DELETE CASCADE,
  calendar_day_id TEXT NOT NULL REFERENCES public.calendar_days(id) ON DELETE CASCADE,
  order_index INTEGER NOT NULL,
  status TEXT NOT NULL,
  notes TEXT
);

-- 14. Claims (Grounding & Verification Ledger)
CREATE TABLE IF NOT EXISTS public.claims (
  id TEXT PRIMARY KEY,
  unit_id TEXT REFERENCES public.teaching_units(id) ON DELETE SET NULL,
  claim_text TEXT NOT NULL,
  verification_status TEXT NOT NULL,
  confidence DOUBLE PRECISION NOT NULL,
  source_page INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 15. Claim Evidence
CREATE TABLE IF NOT EXISTS public.claim_evidence (
  claim_id TEXT NOT NULL REFERENCES public.claims(id) ON DELETE CASCADE,
  source_span_id TEXT NOT NULL REFERENCES public.source_spans(id) ON DELETE CASCADE,
  PRIMARY KEY (claim_id, source_span_id)
);

-- Enable RLS for Defense-in-Depth
ALTER TABLE public.portal_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portal_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teacher_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.class_outlines ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.curriculum_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.curriculum_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_spans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.academic_calendars ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.calendar_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teaching_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.plan_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scheduled_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.claim_evidence ENABLE ROW LEVEL SECURITY;

-- The app uses its own teacher/student sessions in server-only Next.js routes.
-- Browser keys must not access these tables, especially password hashes and sessions.
-- These statements also remove access if an earlier version of this script was run.
DO $$
DECLARE
  table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'portal_users', 'portal_sessions', 'teacher_enrollments', 'class_outlines',
    'curriculum_nodes', 'curriculum_edges', 'source_documents', 'source_spans',
    'academic_calendars', 'calendar_days', 'teaching_units', 'plan_versions',
    'scheduled_units', 'claims', 'claim_evidence'
  ] LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I',
                   'service_role_' || table_name, table_name);
    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC, anon, authenticated', table_name);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.%I TO service_role',
                   table_name);
  END LOOP;
END $$;
