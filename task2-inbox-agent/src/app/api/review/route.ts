import { NextRequest, NextResponse } from "next/server";
import { recordHumanReview, listInteractions } from "@/lib/feedback-store";
import { HumanReviewRequestSchema } from "@/lib/schemas";

export async function GET() {
  try {
    const list = listInteractions(50);
    return NextResponse.json({ interactions: list });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const raw = await req.json();
    const parsed = HumanReviewRequestSchema.parse(raw);

    const result = recordHumanReview(
      parsed.interaction_id,
      parsed.action,
      parsed.edited_text,
      parsed.correction_reason,
    );

    return NextResponse.json({
      success: true,
      message: `Action '${parsed.action}' applied successfully (simulated send).`,
      ...result,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 400 });
  }
}
