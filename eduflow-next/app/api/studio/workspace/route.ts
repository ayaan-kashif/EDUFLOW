import { NextResponse } from "next/server";
import { getWorkspaceData } from "@/lib/data";
import { getCurrentUser } from "@/lib/auth/session";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) return NextResponse.json({ error: "Sign in to continue" }, { status: 401 });
  if (user.role !== "teacher") {
    return NextResponse.json({ error: "Teacher account required" }, { status: 403 });
  }
  try {
    const data = await getWorkspaceData();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
