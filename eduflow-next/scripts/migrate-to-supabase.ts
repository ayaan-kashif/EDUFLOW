import { getDb } from "../lib/db";
import { getSupabaseAdmin } from "../lib/supabase";

async function migrate() {
  console.log("🚀 Starting SQLite -> Supabase Migration...\n");

  const db = getDb();
  const supabase = getSupabaseAdmin();

  // Test Supabase connection
  const { error: testErr } = await supabase.from("portal_users").select("id").limit(1);
  if (testErr && testErr.message.includes("Could not find the table")) {
    console.error("❌ Supabase tables have not been created yet!");
    console.log("\nPlease execute the SQL script in your Supabase dashboard first:");
    console.log("👉 Go to: https://supabase.com/dashboard/project/hswzqcusplgwlnorvtcq/sql");
    console.log("👉 Copy and paste the contents of: eduflow-next/supabase-schema.sql\n");
    process.exit(1);
  }

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
    if (error) console.error("Error migrating users:", error.message);
    else console.log(`✓ Migrated ${users.length} users to Supabase.`);
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
    if (error) console.error("Error migrating outlines:", error.message);
    else console.log(`✓ Migrated ${outlines.length} outlines to Supabase.`);
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
    if (error) console.error("Error migrating enrollments:", error.message);
    else console.log(`✓ Migrated ${enrollments.length} enrollments to Supabase.`);
  }

  console.log("\n🎉 Migration to Supabase complete!");
}

migrate().catch(console.error);
