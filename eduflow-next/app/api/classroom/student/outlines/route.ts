import { NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth/session";
import { getStudentOutlines } from "@/lib/data";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Sign in to continue" }, { status: 401 });
  }
  if (user.role !== "student") {
    return NextResponse.json({ error: "Student account required" }, { status: 403 });
  }

  const outlines = await getStudentOutlines(user.id);
  return NextResponse.json(outlines);
}
