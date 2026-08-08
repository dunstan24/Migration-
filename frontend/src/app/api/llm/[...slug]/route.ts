import { NextRequest, NextResponse } from "next/server";
import { getMockChatResponseStream } from "@/lib/mockData";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const resolvedParams = await params;
  const body = await req.json().catch(() => ({ message: "" }));
  const message = body?.message || "Tell me about Subclass 190 visa";
  const tokens = getMockChatResponseStream(message);

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      for (const token of tokens) {
        const payload = `data: ${JSON.stringify({ token: token + " ", text: token + " " })}\n\n`;
        controller.enqueue(encoder.encode(payload));
        await new Promise((resolve) => setTimeout(resolve, 35));
      }
      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}

export async function GET() {
  return NextResponse.json({ status: "ok", mode: "demo", model: "claude-3-5-sonnet-mock" });
}
