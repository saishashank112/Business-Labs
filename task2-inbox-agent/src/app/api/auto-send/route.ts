import { NextRequest, NextResponse } from "next/server";
import { getAutoSendRules, setAutoSendEnabled } from "@/lib/auto-send";

export async function GET() {
  try {
    const rules = getAutoSendRules();
    return NextResponse.json({ rules });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    if (!body.kind || typeof body.enabled !== "boolean") {
      return NextResponse.json({ error: "Missing 'kind' or 'enabled'" }, { status: 400 });
    }

    const ok = setAutoSendEnabled(body.kind, body.enabled);
    if (!ok) {
      return NextResponse.json(
        { error: "Cannot enable auto-send: category has not reached 20 consecutive unchanged drafts." },
        { status: 400 },
      );
    }

    return NextResponse.json({
      success: true,
      kind: body.kind,
      enabled: body.enabled,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
