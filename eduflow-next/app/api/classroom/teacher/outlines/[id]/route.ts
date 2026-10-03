import { NextRequest, NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth/session";
import { getOutlineById, updateOutline } from "@/lib/data";

export async function PUT(
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

  try {
    const body = await req.json();
    const { title, subject, content, source_text } = body;

    if (!title || !subject || !content) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 422 });
    }

    await updateOutline(id, {
      title: title.trim(),
      subject: subject.trim(),
      content: content.trim(),
      sourceText: (source_text || "").trim() || null,
      published: false,
      notes: null,
      studyPlan: null,
      generatedBy: null,
    });

    const updated = await getOutlineById(id);
    return NextResponse.json(updated);
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Failed to update" }, { status: 500 });
  }
}
