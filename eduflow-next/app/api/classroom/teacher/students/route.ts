import { NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth/session";
import { getTeacherStudents } from "@/lib/data";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Sign in to continue" }, { status: 401 });
  }
  if (user.role !== "teacher") {
    return NextResponse.json({ error: "Teacher account required" }, { status: 403 });
  }

  const students = await getTeacherStudents(user.id);
  return NextResponse.json(students);
}
