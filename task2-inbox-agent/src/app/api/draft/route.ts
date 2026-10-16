import { NextRequest, NextResponse } from "next/server";
import { classifyEmail } from "@/lib/classifier";
import { processEmailPipeline } from "@/lib/drafter";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    if (!body.subject || !body.body) {
      return NextResponse.json({ error: "Missing subject or body" }, { status: 400 });
    }

    // Run classification
    const classification = body.classification || (await classifyEmail(body));

    // Run drafting pipeline with Knowledge Brain client & guardrails
    const result = await processEmailPipeline(body, classification);

    return NextResponse.json(result);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
