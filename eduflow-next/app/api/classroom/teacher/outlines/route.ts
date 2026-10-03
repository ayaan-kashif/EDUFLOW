import { NextRequest, NextResponse } from "next/server";
import { getCurrentUser } from "@/lib/auth/session";
import { createOutline, getTeacherOutlines } from "@/lib/data";

export async function GET() {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Sign in to continue" }, { status: 401 });
  }
  if (user.role !== "teacher") {
    return NextResponse.json({ error: "Teacher account required" }, { status: 403 });
  }

  const outlines = await getTeacherOutlines(user.id);
  return NextResponse.json(outlines);
}

export async function POST(req: NextRequest) {
  const user = await getCurrentUser();
  if (!user) {
    return NextResponse.json({ error: "Sign in to continue" }, { status: 401 });
  }
  if (user.role !== "teacher") {
    return NextResponse.json({ error: "Teacher account required" }, { status: 403 });
  }

  try {
    const body = await req.json();
    const { title, subject, content, source_text } = body;

    if (!title || title.trim().length < 3) {
      return NextResponse.json({ error: "Title must be at least 3 characters" }, { status: 422 });
    }
    if (!subject || subject.trim().length < 2) {
      return NextResponse.json({ error: "Subject must be at least 2 characters" }, { status: 422 });
    }
    if (!content || content.trim().length < 20) {
      return NextResponse.json({ error: "Content must be at least 20 characters" }, { status: 422 });
    }

    const outline = await createOutline({
      teacherId: user.id,
      title: title.trim(),
      subject: subject.trim(),
      content: content.trim(),
      sourceText: (source_text || "").trim() || null,
    });

    return NextResponse.json(outline, { status: 201 });
  } catch (err: any) {
    console.error("Create outline error:", err);
    return NextResponse.json({ error: err.message || "Failed to create outline" }, { status: 500 });
  }
}
