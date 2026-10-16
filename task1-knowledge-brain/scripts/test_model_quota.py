import os
import json
import re
from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

load_dotenv(dotenv_path="../.env")
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

models_to_test = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
]

print("Running exact 1 call per model test:")
for model in models_to_test:
    print(f"\n==========================================")
    print(f"Testing model: {model}")
    try:
        resp = client.models.generate_content(
            model=model,
            contents="Say 'OK' in one word.",
        )
        print(f"RESULT: SUCCESS")
        print(f"Output text: {resp.text.strip() if resp.text else 'EMPTY'}")
        print(f"Model Version: {getattr(resp, 'model_version', 'None')}")
        # Check usage metadata
        if hasattr(resp, "usage_metadata") and resp.usage_metadata:
            print(f"Prompt tokens: {resp.usage_metadata.prompt_token_count}, candidates tokens: {resp.usage_metadata.candidates_token_count}")
    except APIError as e:
        print(f"RESULT: APIError (code={e.code})")
        print(f"Message: {e.message}")
        print(f"Raw Details: {getattr(e, 'details', None)}")
        # Check for QuotaId
        msg = str(e.message)
        qid_m = re.search(r"QuotaId:\s*([A-Za-z0-9_-]+)", msg)
        if not qid_m and hasattr(e, "details") and e.details:
            qid_m = re.search(r'"quotaId":\s*"([^"]+)"', str(e.details))
        if qid_m:
            print(f"Found QuotaId: {qid_m.group(1)}")
        else:
            print("QuotaId: None in response")
    except Exception as e:
        print(f"RESULT: Exception ({type(e).__name__}): {e}")
