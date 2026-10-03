import { NextResponse } from "next/server";
import { getWorkspaceData } from "@/lib/data";

export async function GET() {
  try {
    const data = await getWorkspaceData();
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
