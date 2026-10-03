import { NextResponse } from "next/server";
import { PROVIDER_EVENTS } from "@/lib/providers/router";
import { getCurrentUser } from "@/lib/auth/session";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Sign in to continue" }, { status: 401 });
  if (user.role !== "teacher") {
    return NextResponse.json({ error: "Teacher account required" }, { status: 403 });
  }
  const providersConfig = [
    {
      name: "gemini",
      role: "primary",
      model: process.env.GEMINI_MODEL || "gemini-1.5-flash",
      configured: Boolean(process.env.GEMINI_API_KEY?.trim()),
    },
    {
      name: "groq",
      role: "backup",
      model: process.env.GROQ_MODEL || "llama-3.3-70b-versatile",
      configured: Boolean(process.env.GROQ_API_KEY?.trim()),
    },
  ];

  return NextResponse.json({
    providers: providersConfig,
    recentEvents: PROVIDER_EVENTS.slice(0, 50),
    totalEvents: PROVIDER_EVENTS.length,
  });
}
