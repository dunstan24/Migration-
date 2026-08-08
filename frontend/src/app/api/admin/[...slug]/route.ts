import { NextRequest, NextResponse } from "next/server";
import { getMockAdminData } from "@/lib/mockData";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const resolvedParams = await params;
  const admin = getMockAdminData();
  return NextResponse.json({ users: admin.users, tables: admin.tables, logs: admin.logs });
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const resolvedParams = await params;
  const body = await req.json().catch(() => ({}));
  return NextResponse.json({ status: "success", message: "Admin action complete", body });
}
