import { getDb } from "../lib/db";
import { getSupabaseAdmin } from "../lib/supabase";

async function migrate() {
  console.log("🚀 Starting SQLite -> Supabase Migration...\n");

  const db = getDb();
  const supabase = getSupabaseAdmin();

  // Test Supabase connection
  const { error: testErr } = await supabase.from("portal_users").select("id").limit(1);
  if (testErr) throw new Error(`Supabase is not ready: ${testErr.message}`);

  // 1. Migrate Users
  const users = db.prepare("SELECT * FROM portal_users").all() as any[];
  console.log(`Found ${users.length} users in SQLite.`);
  if (users.length > 0) {
    const { error } = await supabase.from("portal_users").upsert(
      users.map((u) => ({
        id: u.id,
        name: u.name,
        email: u.email,
        password_hash: u.password_hash,
        role: u.role,
        enrollment_code: u.enrollment_code,
        created_at: u.created_at,
      }))
    );
    if (error) throw new Error(`Error migrating users: ${error.message}`);
    console.log(`✓ Migrated ${users.length} users to Supabase.`);
  }

  // 2. Migrate Class Outlines
  const outlines = db.prepare("SELECT * FROM class_outlines").all() as any[];
  console.log(`Found ${outlines.length} outlines in SQLite.`);
  if (outlines.length > 0) {
    const { error } = await supabase.from("class_outlines").upsert(
      outlines.map((o) => ({
        id: o.id,
        teacher_id: o.teacher_id,
        title: o.title,
        subject: o.subject,
        content: o.content,
        source_text: o.source_text,
        published: Boolean(o.published),
        notes: o.notes,
        study_plan: o.study_plan ? JSON.parse(o.study_plan) : null,
        generated_by: o.generated_by,
        created_at: o.created_at,
      }))
    );
    if (error) throw new Error(`Error migrating outlines: ${error.message}`);
    console.log(`✓ Migrated ${outlines.length} outlines to Supabase.`);
  }

  // 3. Migrate Teacher Enrollments
  const enrollments = db.prepare("SELECT * FROM teacher_enrollments").all() as any[];
  if (enrollments.length > 0) {
    const { error } = await supabase.from("teacher_enrollments").upsert(
      enrollments.map((e) => ({
        teacher_id: e.teacher_id,
        student_id: e.student_id,
      }))
    );
    if (error) throw new Error(`Error migrating enrollments: ${error.message}`);
    console.log(`✓ Migrated ${enrollments.length} enrollments to Supabase.`);
  }

  console.log("\n🎉 Migration to Supabase complete!");
}

migrate().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
