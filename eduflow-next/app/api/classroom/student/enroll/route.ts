import { NextRequest, NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth/session";
import { enrollStudentByCode } from "@/lib/data";

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Sign in to continue" }, { status: 401 });
  }
  if (user.role !== "student") {
    return NextResponse.json({ error: "Student account required" }, { status: 403 });
  }

  try {
    const body = await req.json();
    const { code } = body;

    if (!code || typeof code !== "string" || code.trim().length < 4) {
      return NextResponse.json({ error: "Please enter a valid teacher code" }, { status: 422 });
    }

    const teacher = await enrollStudentByCode(code, user.id);
    return NextResponse.json(teacher);
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Failed to enroll" }, { status: 404 });
  }
}
