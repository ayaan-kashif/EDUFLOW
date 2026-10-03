import crypto from "node:crypto";
import { getDb } from "./db";
import { getSupabaseAdmin, isSupabaseReady } from "./supabase";
import {
  PortalUser,
  ClassOutline,
  CurriculumNode,
  CurriculumEdge,
  PlanVersion,
  ScheduledUnit,
  Claim,
  TeachingUnit,
  CalendarDay,
} from "./types";

// User queries
export async function getUserByEmail(
  email: string
): Promise<(PortalUser & { password_hash: string }) | null> {
  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    const { data } = await supabase
      .from("portal_users")
      .select("*")
      .ilike("email", email.trim())
      .single();
    if (data) return data as any;
  }

  const db = getDb();
  const row = db
    .prepare("SELECT * FROM portal_users WHERE lower(email) = lower(?)")
    .get(email) as any;
  if (!row) return null;
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    role: row.role,
    enrollment_code: row.enrollment_code,
    password_hash: row.password_hash,
    created_at: row.created_at,
  };
}

export async function getUserById(id: string): Promise<PortalUser | null> {
  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    const { data } = await supabase.from("portal_users").select("*").eq("id", id).single();
    if (data) return data as any;
  }

  const db = getDb();
  const row = db.prepare("SELECT * FROM portal_users WHERE id = ?").get(id) as any;
  if (!row) return null;
  return {
    id: row.id,
    name: row.name,
    email: row.email,
    role: row.role,
    enrollment_code: row.enrollment_code,
    created_at: row.created_at,
  };
}

export async function createUser(data: {
  name: string;
  email: string;
  passwordHash: string;
  role: "teacher" | "student";
}): Promise<PortalUser> {
  const id = crypto.randomUUID();
  const enrollmentCode =
    data.role === "teacher" ? crypto.randomBytes(3).toString("hex").toUpperCase() : null;
  const now = new Date().toISOString();

  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    const { error } = await supabase.from("portal_users").insert({
      id,
      name: data.name.trim(),
      email: data.email.toLowerCase().trim(),
      password_hash: data.passwordHash,
      role: data.role,
      enrollment_code: enrollmentCode,
      created_at: now,
    });
    if (!error) {
      return {
        id,
        name: data.name.trim(),
        email: data.email.toLowerCase().trim(),
        role: data.role,
        enrollment_code: enrollmentCode,
        created_at: now,
      };
    }
    console.warn("Supabase insert failed, falling back to local SQLite:", error.message);
  }

  const db = getDb();
  db.prepare(`
    INSERT INTO portal_users (id, name, email, password_hash, role, enrollment_code)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(
    id,
    data.name.trim(),
    data.email.toLowerCase().trim(),
    data.passwordHash,
    data.role,
    enrollmentCode
  );

  return {
    id,
    name: data.name.trim(),
    email: data.email.toLowerCase().trim(),
    role: data.role,
    enrollment_code: enrollmentCode,
    created_at: now,
  };
}

// Teacher Outline queries
export async function getTeacherOutlines(teacherId: string): Promise<ClassOutline[]> {
  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    const { data } = await supabase
      .from("class_outlines")
      .select("*")
      .eq("teacher_id", teacherId)
      .order("created_at", { ascending: false });
    if (data) {
      return data.map((r: any) => ({
        id: r.id,
        teacher_id: r.teacher_id,
        title: r.title,
        subject: r.subject,
        content: r.content,
        source_text: r.source_text,
        published: Boolean(r.published),
        notes: r.notes,
        study_plan: typeof r.study_plan === "string" ? JSON.parse(r.study_plan) : r.study_plan,
        generated_by: r.generated_by,
        created_at: r.created_at,
      }));
    }
  }

  const db = getDb();
  const rows = db
    .prepare("SELECT * FROM class_outlines WHERE teacher_id = ? ORDER BY created_at DESC")
    .all(teacherId) as any[];

  return rows.map((r) => ({
    id: r.id,
    teacher_id: r.teacher_id,
    title: r.title,
    subject: r.subject,
    content: r.content,
    source_text: r.source_text,
    published: Boolean(r.published),
    notes: r.notes,
    study_plan: r.study_plan ? JSON.parse(r.study_plan) : null,
    generated_by: r.generated_by,
    created_at: r.created_at,
  }));
}

export async function getOutlineById(id: string): Promise<ClassOutline | null> {
  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    const { data } = await supabase.from("class_outlines").select("*").eq("id", id).single();
    if (data) {
      return {
        id: data.id,
        teacher_id: data.teacher_id,
        title: data.title,
        subject: data.subject,
        content: data.content,
        source_text: data.source_text,
        published: Boolean(data.published),
        notes: data.notes,
        study_plan:
          typeof data.study_plan === "string" ? JSON.parse(data.study_plan) : data.study_plan,
        generated_by: data.generated_by,
        created_at: data.created_at,
      };
    }
  }

  const db = getDb();
  const r = db.prepare("SELECT * FROM class_outlines WHERE id = ?").get(id) as any;
  if (!r) return null;
  return {
    id: r.id,
    teacher_id: r.teacher_id,
    title: r.title,
    subject: r.subject,
    content: r.content,
    source_text: r.source_text,
    published: Boolean(r.published),
    notes: r.notes,
    study_plan: r.study_plan ? JSON.parse(r.study_plan) : null,
    generated_by: r.generated_by,
    created_at: r.created_at,
  };
}

export async function createOutline(data: {
  teacherId: string;
  title: string;
  subject: string;
  content: string;
  sourceText?: string | null;
}): Promise<ClassOutline> {
  const id = crypto.randomUUID();
  const now = new Date().toISOString();

  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    await supabase.from("class_outlines").insert({
      id,
      teacher_id: data.teacherId,
      title: data.title,
      subject: data.subject,
      content: data.content,
      source_text: data.sourceText || null,
      published: false,
      created_at: now,
    });
  }

  const db = getDb();
  db.prepare(`
    INSERT INTO class_outlines (id, teacher_id, title, subject, content, source_text, published, created_at)
    VALUES (?, ?, ?, ?, ?, ?, 0, ?)
  `).run(id, data.teacherId, data.title, data.subject, data.content, data.sourceText || null, now);

  return {
    id,
    teacher_id: data.teacherId,
    title: data.title,
    subject: data.subject,
    content: data.content,
    source_text: data.sourceText || null,
    published: false,
    created_at: now,
  };
}

export async function updateOutline(
  id: string,
  data: {
    title: string;
    subject: string;
    content: string;
    sourceText?: string | null;
    published?: boolean;
    notes?: string | null;
    studyPlan?: any;
    generatedBy?: string | null;
  }
) {
  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    await supabase
      .from("class_outlines")
      .update({
        title: data.title,
        subject: data.subject,
        content: data.content,
        source_text: data.sourceText || null,
        published: Boolean(data.published),
        notes: data.notes || null,
        study_plan: data.studyPlan || null,
        generated_by: data.generatedBy || null,
      })
      .eq("id", id);
  }

  const db = getDb();
  db.prepare(`
    UPDATE class_outlines
    SET title = ?, subject = ?, content = ?, source_text = ?, published = ?, notes = ?, study_plan = ?, generated_by = ?
    WHERE id = ?
  `).run(
    data.title,
    data.subject,
    data.content,
    data.sourceText || null,
    data.published ? 1 : 0,
    data.notes || null,
    data.studyPlan ? JSON.stringify(data.studyPlan) : null,
    data.generatedBy || null,
    id
  );
}

// Student queries
export async function enrollStudentByCode(
  code: string,
  studentId: string
): Promise<{ id: string; name: string }> {
  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    const { data: teacher } = await supabase
      .from("portal_users")
      .select("id, name")
      .eq("enrollment_code", code.toUpperCase().trim())
      .eq("role", "teacher")
      .single();

    if (teacher) {
      await supabase.from("teacher_enrollments").upsert({
        teacher_id: teacher.id,
        student_id: studentId,
      });
      return { id: teacher.id, name: teacher.name };
    }
  }

  const db = getDb();
  const teacher = db
    .prepare("SELECT id, name FROM portal_users WHERE enrollment_code = ? AND role = 'teacher'")
    .get(code.toUpperCase().trim()) as any;

  if (!teacher) {
    throw new Error("No teacher found with this enrollment code");
  }

  db.prepare(`
    INSERT OR IGNORE INTO teacher_enrollments (teacher_id, student_id)
    VALUES (?, ?)
  `).run(teacher.id, studentId);

  return { id: teacher.id, name: teacher.name };
}

export async function getTeacherStudents(
  teacherId: string
): Promise<{ id: string; name: string }[]> {
  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    const { data } = await supabase
      .from("teacher_enrollments")
      .select("student:portal_users!teacher_enrollments_student_id_fkey(id, name)")
      .eq("teacher_id", teacherId);
    if (data && data.length > 0) {
      return data.map((d: any) => ({ id: d.student.id, name: d.student.name }));
    }
  }

  const db = getDb();
  const rows = db
    .prepare(`
      SELECT u.id, u.name
      FROM teacher_enrollments te
      JOIN portal_users u ON te.student_id = u.id
      WHERE te.teacher_id = ?
      ORDER BY u.name ASC
    `)
    .all(teacherId) as any[];

  return rows.map((r) => ({ id: r.id, name: r.name }));
}

export async function getStudentTeachers(
  studentId: string
): Promise<{ id: string; name: string }[]> {
  if (await isSupabaseReady()) {
    const supabase = getSupabaseAdmin();
    const { data } = await supabase
      .from("teacher_enrollments")
      .select("teacher:portal_users!teacher_enrollments_teacher_id_fkey(id, name)")
      .eq("student_id", studentId);
    if (data && data.length > 0) {
      return data.map((d: any) => ({ id: d.teacher.id, name: d.teacher.name }));
    }
  }

  const db = getDb();
  const rows = db
    .prepare(`
      SELECT u.id, u.name
      FROM teacher_enrollments te
      JOIN portal_users u ON te.teacher_id = u.id
      WHERE te.student_id = ?
      ORDER BY u.name ASC
    `)
    .all(studentId) as any[];

  return rows.map((r) => ({ id: r.id, name: r.name }));
}

export async function getStudentOutlines(
  studentId: string
): Promise<(ClassOutline & { teacher_name: string })[]> {
  const db = getDb();
  const rows = db
    .prepare(`
      SELECT o.*, u.name as teacher_name
      FROM class_outlines o
      JOIN teacher_enrollments te ON te.teacher_id = o.teacher_id
      JOIN portal_users u ON u.id = o.teacher_id
      WHERE te.student_id = ? AND o.published = 1
      ORDER BY o.created_at DESC
    `)
    .all(studentId) as any[];

  return rows.map((r) => ({
    id: r.id,
    teacher_id: r.teacher_id,
    teacher_name: r.teacher_name,
    title: r.title,
    subject: r.subject,
    content: r.content,
    source_text: r.source_text,
    published: Boolean(r.published),
    notes: r.notes,
    study_plan: r.study_plan ? JSON.parse(r.study_plan) : null,
    generated_by: r.generated_by,
    created_at: r.created_at,
  }));
}

// Curriculum, Planning & Workspace Data
export async function getWorkspaceData() {
  const db = getDb();

  const nodes = db.prepare("SELECT * FROM curriculum_nodes ORDER BY created_at ASC").all() as any[];
  const edges = db.prepare("SELECT * FROM curriculum_edges").all() as any[];
  const documents = db.prepare("SELECT * FROM source_documents ORDER BY created_at DESC").all() as any[];
  const planVersions = db.prepare("SELECT * FROM plan_versions ORDER BY version_number DESC").all() as any[];
  const scheduledUnits = db.prepare(`
    SELECT su.*, tu.title as unit_title, tu.duration_minutes, cd.date as calendar_date
    FROM scheduled_units su
    JOIN teaching_units tu ON su.unit_id = tu.id
    JOIN calendar_days cd ON su.calendar_day_id = cd.id
    ORDER BY cd.date ASC, su.order_index ASC
  `).all() as any[];
  const claims = db.prepare("SELECT * FROM claims ORDER BY created_at DESC").all() as any[];

  return {
    nodes,
    edges,
    documents,
    planVersions,
    scheduledUnits,
    claims,
    stats: {
      nodeCount: nodes.length,
      edgeCount: edges.length,
      docCount: documents.length,
      planCount: planVersions.length,
      claimCount: claims.length,
    },
  };
}
