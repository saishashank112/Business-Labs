import sqlite3
import json

conn = sqlite3.connect("task3.db")
c = conn.cursor()

print("\n--- REQUIREMENTS TABLE ---")
rows = c.execute("SELECT id, transcript_id, project_id, description, statement_type, source_quote, status, version FROM requirements WHERE project_id='proj_lawyers_directory'").fetchall()
print(f"Total requirements for proj_lawyers_directory in DB: {len(rows)}")
for r in rows:
    print(f"ID: {r[0]} | TransID: {r[1]} | Type: {r[4]} | Desc: {r[3]}")
    print(f"   Quote: {r[5]}")

print("\n--- SCOPE_VERSIONS TABLE ---")
for sv in c.execute("SELECT id, project_id, version, status, approved_by, target_delivery_date FROM scope_versions WHERE project_id='proj_lawyers_directory'").fetchall():
    print(f"Scope Version: {sv[0]} | v{sv[2]} | Status: {sv[3]} | ApprovedBy: {sv[4]} | TargetDate: {sv[5]}")

print("\n--- ALL REQUIREMENTS IN DB (ANY PROJECT) ---")
all_reqs = c.execute("SELECT id, transcript_id, project_id, description, statement_type FROM requirements").fetchall()
print(f"Total in requirements table: {len(all_reqs)}")
for ar in all_reqs:
    print(f" - {ar[0]} [{ar[1]} / {ar[2]}]: ({ar[4]}) {ar[3]}")
