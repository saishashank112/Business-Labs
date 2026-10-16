import sqlite3
import json

conn = sqlite3.connect("task3.db")
c = conn.cursor()

print("--- ROWS IN REQUIREMENTS TABLE ---")
for r in c.execute("SELECT id, transcript_id, project_id, description, source_quote, status FROM requirements").fetchall():
    print(f"ID: {r[0]} | Trans: {r[1]} | Proj: {r[2]}")
    print(f"  Description: {r[3]}")
    print(f"  Source Quote: {r[4]}")

print("\n--- ROWS IN SCOPE_VERSIONS TABLE ---")
for sv in c.execute("SELECT id, project_id, version, status, approved_by, content FROM scope_versions").fetchall():
    print(f"Scope Version ID: {sv[0]} | Proj: {sv[1]} | v{sv[2]} | Status: {sv[3]} | ApprovedBy: {sv[4]}")
    try:
        content = json.loads(sv[5])
        reqs = content.get("agreed_requirements", [])
        print(f"  Agreed Requirements in Scope Content ({len(reqs)} items):")
        for req in reqs:
            print(f"    - [{req.get('id')}] {req.get('description')}")
            print(f"        Quote: {req.get('source_quote')}")
    except Exception as e:
        print("  Error parsing content:", e)
