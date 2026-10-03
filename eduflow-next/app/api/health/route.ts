import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { checkSupabaseHealth } from "@/lib/supabase";

export async function GET() {
  try {
    const db = getDb();
    const result = db.prepare("SELECT 1 as healthy").get() as any;

    const tables = ["portal_users", "portal_sessions", "teacher_enrollments", "class_outlines"];
    const counts: Record<string, number> = {};
    for (const table of tables) {
      const res = db.prepare(`SELECT count(1) as count FROM ${table}`).get() as any;
      counts[table] = res.count;
    }

    const supabase = await checkSupabaseHealth();

    return NextResponse.json({
      status: "healthy",
      timestamp: new Date().toISOString(),
      database: result.healthy === 1 ? "connected" : "disconnected",
      counts,
      supabase: {
        status: supabase.connected ? "connected" : "unavailable",
        url: supabase.url,
      },
    });
  } catch (err: any) {
    return NextResponse.json(
      { status: "unhealthy", error: err.message },
      { status: 500 }
    );
  }
}
