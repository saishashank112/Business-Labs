import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export async function GET() {
  try {
    const emailsPath = path.resolve(process.cwd(), "data", "emails.json");
    if (!fs.existsSync(emailsPath)) {
      return NextResponse.json({ emails: [] });
    }
    const data = JSON.parse(fs.readFileSync(emailsPath, "utf-8"));
    return NextResponse.json({ emails: data, total: data.length });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
