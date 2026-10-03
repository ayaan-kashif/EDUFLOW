import { NextRequest, NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth/session";
import { getOutlineById, updateOutline } from "@/lib/data";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Sign in to continue" }, { status: 401 });
  }
  if (user.role !== "teacher") {
    return NextResponse.json({ error: "Teacher account required" }, { status: 403 });
  }

  const outline = await getOutlineById(id);
  if (!outline || outline.teacher_id !== user.id) {
    return NextResponse.json({ error: "Outline not found" }, { status: 404 });
  }

  await updateOutline(id, {
    title: outline.title,
    subject: outline.subject,
    content: outline.content,
    sourceText: outline.source_text,
    published: true,
    notes: outline.notes,
    studyPlan: outline.study_plan,
    generatedBy: outline.generated_by,
  });

  const updated = await getOutlineById(id);
  return NextResponse.json(updated);
}
