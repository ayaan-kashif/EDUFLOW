import crypto from "node:crypto";
import { getSupabaseAdmin } from "./supabase";
import type { ClassOutline, PortalUser } from "./types";

type StoredUser = PortalUser & { password_hash: string };
type OutlineUpdate = {
  title: string;
  subject: string;
  content: string;
  sourceText?: string | null;
  published?: boolean;
  notes?: string | null;
  studyPlan?: ClassOutline["study_plan"];
  generatedBy?: string | null;
};

function fail(error: { message: string } | null): void {
  if (error) throw new Error(error.message);
}

export async function getUserByEmail(email: string): Promise<StoredUser | null> {
  const { data, error } = await getSupabaseAdmin()
    .from("portal_users")
    .select("*")
    .ilike("email", email.trim())
    .maybeSingle();
  fail(error);
  return data as StoredUser | null;
}

export async function getUserById(id: string): Promise<PortalUser | null> {
  const { data, error } = await getSupabaseAdmin()
    .from("portal_users")
    .select("id, name, email, role, enrollment_code, created_at")
    .eq("id", id)
    .maybeSingle();
  fail(error);
  return data as PortalUser | null;
}

export async function createUser(input: {
  name: string;
  email: string;
  passwordHash: string;
  role: "teacher" | "student";
}): Promise<PortalUser> {
  const row = {
    id: crypto.randomUUID(),
    name: input.name.trim(),
    email: input.email.toLowerCase().trim(),
    password_hash: input.passwordHash,
    role: input.role,
    enrollment_code:
      input.role === "teacher" ? crypto.randomBytes(4).toString("hex").toUpperCase() : null,
  };
  const { data, error } = await getSupabaseAdmin()
    .from("portal_users")
    .insert(row)
    .select("id, name, email, role, enrollment_code, created_at")
    .single();
  fail(error);
  return data as PortalUser;
}

export async function getTeacherOutlines(teacherId: string): Promise<ClassOutline[]> {
  const { data, error } = await getSupabaseAdmin()
    .from("class_outlines")
    .select("*")
    .eq("teacher_id", teacherId)
    .order("created_at", { ascending: false });
  fail(error);
  return (data || []) as ClassOutline[];
}

export async function getOutlineById(id: string): Promise<ClassOutline | null> {
  const { data, error } = await getSupabaseAdmin()
    .from("class_outlines")
    .select("*")
    .eq("id", id)
    .maybeSingle();
  fail(error);
  return data as ClassOutline | null;
}

export async function createOutline(input: {
  teacherId: string;
  title: string;
  subject: string;
  content: string;
  sourceText?: string | null;
}): Promise<ClassOutline> {
  const { data, error } = await getSupabaseAdmin()
    .from("class_outlines")
    .insert({
      id: crypto.randomUUID(),
      teacher_id: input.teacherId,
      title: input.title,
      subject: input.subject,
      content: input.content,
      source_text: input.sourceText || null,
      published: false,
    })
    .select("*")
    .single();
  fail(error);
  return data as ClassOutline;
}

export async function updateOutline(id: string, input: OutlineUpdate): Promise<void> {
  const { error } = await getSupabaseAdmin()
    .from("class_outlines")
    .update({
      title: input.title,
      subject: input.subject,
      content: input.content,
      source_text: input.sourceText || null,
      published: Boolean(input.published),
      notes: input.notes || null,
      study_plan: input.studyPlan || null,
      generated_by: input.generatedBy || null,
    })
    .eq("id", id);
  fail(error);
}

export async function enrollStudentByCode(
  code: string,
  studentId: string
): Promise<{ id: string; name: string }> {
  const admin = getSupabaseAdmin();
  const { data: teacher, error: lookupError } = await admin
    .from("portal_users")
    .select("id, name")
    .eq("enrollment_code", code.toUpperCase().trim())
    .eq("role", "teacher")
    .maybeSingle();
  fail(lookupError);
  if (!teacher) throw new Error("No teacher found with this enrollment code");

  const { error } = await admin.from("teacher_enrollments").upsert(
    { teacher_id: teacher.id, student_id: studentId },
    { onConflict: "teacher_id,student_id" }
  );
  fail(error);
  return teacher;
}

export async function getTeacherStudents(
  teacherId: string
): Promise<{ id: string; name: string }[]> {
  const admin = getSupabaseAdmin();
  const { data: enrollments, error } = await admin
    .from("teacher_enrollments")
    .select("student_id")
    .eq("teacher_id", teacherId);
  fail(error);
  const ids = (enrollments || []).map((row) => row.student_id);
  if (!ids.length) return [];
  const { data: students, error: userError } = await admin
    .from("portal_users")
    .select("id, name")
    .in("id", ids)
    .order("name");
  fail(userError);
  return students || [];
}

export async function getStudentTeachers(
  studentId: string
): Promise<{ id: string; name: string }[]> {
  const admin = getSupabaseAdmin();
  const { data: enrollments, error } = await admin
    .from("teacher_enrollments")
    .select("teacher_id")
    .eq("student_id", studentId);
  fail(error);
  const ids = (enrollments || []).map((row) => row.teacher_id);
  if (!ids.length) return [];
  const { data: teachers, error: userError } = await admin
    .from("portal_users")
    .select("id, name")
    .in("id", ids)
    .order("name");
  fail(userError);
  return teachers || [];
}

export async function getStudentOutlines(
  studentId: string
): Promise<(ClassOutline & { teacher_name: string })[]> {
  const admin = getSupabaseAdmin();
  const { data: enrollments, error } = await admin
    .from("teacher_enrollments")
    .select("teacher_id")
    .eq("student_id", studentId);
  fail(error);
  const ids = (enrollments || []).map((row) => row.teacher_id);
  if (!ids.length) return [];
  const [outlineResult, teacherResult] = await Promise.all([
    admin.from("class_outlines").select("*").in("teacher_id", ids)
      .eq("published", true).order("created_at", { ascending: false }),
    admin.from("portal_users").select("id, name").in("id", ids),
  ]);
  fail(outlineResult.error);
  fail(teacherResult.error);
  const names = new Map((teacherResult.data || []).map((row) => [row.id, row.name]));
  return (outlineResult.data || []).map((row) => ({
    ...(row as ClassOutline),
    teacher_name: names.get(row.teacher_id) || "Teacher",
  }));
}

export async function getWorkspaceData() {
  const admin = getSupabaseAdmin();
  const [nodeResult, edgeResult, documentResult, planResult, scheduleResult,
    claimResult, unitResult, dayResult] = await Promise.all([
    admin.from("curriculum_nodes").select("*").order("created_at"),
    admin.from("curriculum_edges").select("*"),
    admin.from("source_documents").select("*").order("created_at", { ascending: false }),
    admin.from("plan_versions").select("*").order("version_number", { ascending: false }),
    admin.from("scheduled_units").select("*").order("order_index"),
    admin.from("claims").select("*").order("created_at", { ascending: false }),
    admin.from("teaching_units").select("id, title, duration_minutes"),
    admin.from("calendar_days").select("id, date"),
  ]);
  for (const result of [nodeResult, edgeResult, documentResult, planResult,
    scheduleResult, claimResult, unitResult, dayResult]) fail(result.error);

  const nodes = nodeResult.data || [];
  const edges = edgeResult.data || [];
  const documents = documentResult.data || [];
  const planVersions = planResult.data || [];
  const claims = claimResult.data || [];
  const units = new Map((unitResult.data || []).map((row) => [row.id, row]));
  const days = new Map((dayResult.data || []).map((row) => [row.id, row]));
  const scheduledUnits = (scheduleResult.data || []).map((row) => ({
    ...row,
    unit_title: units.get(row.unit_id)?.title || "",
    duration_minutes: units.get(row.unit_id)?.duration_minutes || 0,
    calendar_date: days.get(row.calendar_day_id)?.date || "",
  })).sort((a, b) => a.calendar_date.localeCompare(b.calendar_date) ||
    a.order_index - b.order_index);
  return {
    nodes, edges, documents, planVersions, scheduledUnits, claims,
    stats: {
      nodeCount: nodes.length,
      edgeCount: edges.length,
      docCount: documents.length,
      planCount: planVersions.length,
      claimCount: claims.length,
    },
  };
}
