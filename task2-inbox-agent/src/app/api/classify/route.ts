import { NextRequest, NextResponse } from "next/server";
import { classifyEmail } from "@/lib/classifier";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    if (!body.subject || !body.body) {
      return NextResponse.json({ error: "Missing subject or body" }, { status: 400 });
    }
    const classification = await classifyEmail(body);
    return NextResponse.json(classification);
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
