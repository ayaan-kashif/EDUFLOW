import { NextResponse } from "next/server";
import { checkSupabaseHealth } from "@/lib/supabase";

export async function GET() {
  const database = await checkSupabaseHealth();
  return NextResponse.json(
    {
      status: database.tablesReady ? "healthy" : "unhealthy",
      database: database.tablesReady ? "connected" : "unavailable",
    },
    { status: database.tablesReady ? 200 : 503 }
  );
}
