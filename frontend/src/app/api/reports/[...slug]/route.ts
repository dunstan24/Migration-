import { NextRequest, NextResponse } from "next/server";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ slug: string[] }> }
) {
  const resolvedParams = await params;
  const url = new URL(req.url);
  const name = url.searchParams.get("name") || "Applicant";
  const occupation = url.searchParams.get("occupation") || "Software Engineer";
  const state = url.searchParams.get("state") || "NSW";
  const points = url.searchParams.get("points") || "85";

  const pdfHeader = `%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kinds [/PDF] /Count 1 /Kids [3 0 R]>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj
4 0 obj <</Length 240>> stream
BT
/F1 18 Tf
50 720 Td
(Australian Migration Intelligence Assessment) Tj
/F1 12 Tf
0 -30 Td
(Applicant Name: ${name}) Tj
0 -20 Td
(Target Occupation: ${occupation}) Tj
0 -20 Td
(Nominated State: ${state} | Calculated Points: ${points}) Tj
0 -20 Td
(Estimated Subclass 190 Pathway Probability: 84%) Tj
0 -20 Td
(Status: High Invitation Likelihood - Recommended for EOI Submission) Tj
ET
endstream
endobj
5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000062 00000 n 
0000000136 00000 n 
0000000266 00000 n 
0000000557 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
628
%%EOF`;

  return new NextResponse(pdfHeader, {
    status: 200,
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="Inter_Migration_Intelligence_Report_${name.replace(/\s+/g, "_")}.pdf"`,
    },
  });
}
