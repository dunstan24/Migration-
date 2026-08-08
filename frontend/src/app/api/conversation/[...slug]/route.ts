import { NextRequest, NextResponse } from "next/server";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const resolvedParams = await params;
  const path = resolvedParams.slug ? resolvedParams.slug.join("/") : "";

  if (path.includes("history")) {
    return NextResponse.json({
      session_id: "demo-session-1",
      messages: [
        { role: "assistant", content: "Hello! I am your AI Migration Intelligence Assistant. How can I help you today?" },
      ],
    });
  }

  return NextResponse.json({ session_id: "demo-session-1" });
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const resolvedParams = await params;
  return NextResponse.json({
    session_id: "demo-session-" + Math.random().toString(36).substring(7),
    status: "created",
  });
}

export async function DELETE() {
  return NextResponse.json({ status: "deleted" });
}
