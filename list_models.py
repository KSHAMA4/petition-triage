import os, requests
from dotenv import load_dotenv

load_dotenv()
r = requests.get(os.environ["LLM_BASE_URL"] + "/models?pageSize=100",
                 headers={"x-goog-api-key": os.environ["LLM_API_KEY"]}, timeout=30)
print(r.status_code)
for m in r.json().get("models", []):
    if "generateContent" in m.get("supportedGenerationMethods", []):
        print(m["name"].replace("models/", ""))