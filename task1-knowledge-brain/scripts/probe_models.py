import os
import json
import re
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv(dotenv_path="../.env")
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

print("Fetching models from client.models.list()...")
all_models = []
try:
    for m in client.models.list():
        # m.name is usually "models/gemini-..."
        clean_name = m.name.replace("models/", "")
        if "gemini" in clean_name and "embedding" not in clean_name and "aqa" not in clean_name:
            all_models.append(clean_name)
except Exception as e:
    print(f"Error listing models: {e}")

# Add models configured in .env and requested by user
candidates = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]

# Merge while preserving order
test_models = []
for c in candidates:
    if c not in test_models:
        test_models.append(c)

for m in all_models:
    # Pick a few relevant representative models
    if m in ["gemini-2.5-pro", "gemini-2.0-flash-lite", "gemini-1.5-pro"] and m not in test_models:
        test_models.append(m)

print(f"Testing {len(test_models)} models with exactly 1 generation call each:")
print(test_models)

results = []

for model_name in test_models:
    print(f"\n--- Testing model: {model_name} ---")
    entry = {
        "model": model_name,
        "resolved_model": model_name,
        "status": "UNKNOWN",
        "quota_id": "N/A",
        "quota_dimension": "N/A",
        "detail": "",
    }
    try:
        resp = client.models.generate_content(
            model=model_name,
            contents="Say 'hello' in one word.",
        )
        entry["status"] = "SUCCESS"
        entry["detail"] = (resp.text or "").strip()[:50]
        # Check if response metadata reveals actual resolved model
        if hasattr(resp, "model_version") and resp.model_version:
            entry["resolved_model"] = resp.model_version
    except APIError as e:
        entry["status"] = f"ERROR ({e.code})"
        raw_msg = str(e.message)
        entry["detail"] = raw_msg[:120]
        
        # Look for QuotaId
        # pattern: QuotaId: [A-Za-z0-9_-]+ or quotaId: "..."
        qid_match = re.search(r"QuotaId:\s*([A-Za-z0-9_-]+)", raw_msg)
        if not qid_match:
            qid_match = re.search(r'"quotaId":\s*"([^"]+)"', raw_msg)
        
        if qid_match:
            qid = qid_match.group(1)
            entry["quota_id"] = qid
            # Analyze quota dimension from QuotaId
            if "PerProjectPerModel" in qid:
                entry["quota_dimension"] = "PerProjectPerModel"
            elif "PerProject" in qid:
                entry["quota_dimension"] = "PerProject (Shared)"
            elif "PerModel" in qid:
                entry["quota_dimension"] = "PerModel"
            else:
                entry["quota_dimension"] = "Unknown"
        else:
            if "429" in str(e.code) or "RESOURCE_EXHAUSTED" in raw_msg:
                entry["quota_dimension"] = "Resource Exhausted"

        # Check for model resolution in message or error details
        res_match = re.search(r"models/([a-zA-Z0-9.-]+)", raw_msg)
        if res_match:
            entry["resolved_model"] = res_match.group(1)
            
    except Exception as e:
        entry["status"] = "EXCEPTION"
        entry["detail"] = str(e)[:100]

    results.append(entry)

print("\n\n=== RESULTS TABLE ===")
print("| Model | Resolved Model | Result | QuotaId | Quota Model Dimension | Details |")
print("|---|---|---|---|---|---|")
for r in results:
    print(f"| {r['model']} | {r['resolved_model']} | {r['status']} | {r['quota_id']} | {r['quota_dimension']} | {r['detail']} |")

with open("model_probe_results.json", "w") as f:
    json.dump(results, f, indent=2)
