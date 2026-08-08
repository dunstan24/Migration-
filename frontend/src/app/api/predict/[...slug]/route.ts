import { NextRequest, NextResponse } from "next/server";
import { getMockPathwayPrediction, getMockApprovalPrediction } from "@/lib/mockData";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const resolvedParams = await params;
  const path = resolvedParams.slug ? resolvedParams.slug.join("/") : "";
  const body = await req.json().catch(() => ({}));

  if (path === "pathway") {
    const result = getMockPathwayPrediction(body);
    return NextResponse.json(result);
  }

  if (path === "approval") {
    const result = getMockApprovalPrediction(body);
    return NextResponse.json(result);
  }

  return NextResponse.json(getMockPathwayPrediction(body));
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const resolvedParams = await params;
  const path = resolvedParams.slug ? resolvedParams.slug.join("/") : "";
  if (path === "approval") {
    return NextResponse.json(getMockApprovalPrediction({ points: 80 }));
  }
  return NextResponse.json(getMockPathwayPrediction({ points: 85 }));
}
