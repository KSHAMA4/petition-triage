import os, time, json, re
import requests
from dotenv import load_dotenv

load_dotenv()


def _models():
    primary = os.environ["LLM_MODEL"]
    extra = [m.strip() for m in os.environ.get("LLM_FALLBACK_MODELS", "").split(",") if m.strip()]
    return [primary] + [m for m in extra if m != primary]


def _one_model(model, prompt, timeout, retries):
    key = os.environ["LLM_API_KEY"]
    base = os.environ["LLM_BASE_URL"]
    url = f"{base}/models/{model}:generateContent"
    gen = {"temperature": 0, "responseMimeType": "application/json"}
    if "2.5" in model and "pro" not in model:
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
    delay = 3
    for attempt in range(retries):
        try:
            r = requests.post(url, json=body, headers={"x-goog-api-key": key}, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:150]}")
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text, data.get("usageMetadata", {})
        except Exception as e:
            print(f"[llm {model} attempt {attempt + 1}/{retries}] {type(e).__name__}: {str(e)[:150]}")
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2


def call_llm(prompt, timeout=40, retries=2):
    last = None
    for model in _models():
        try:
            text, usage = _one_model(model, prompt, timeout, retries)
            usage = dict(usage)
            usage["model_used"] = model
            return text, usage
        except Exception as e:
            last = e
            print(f"[llm] {model} failed, trying next model")
    raise last


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    data = json.loads(text)
    if isinstance(data, list):
        data = next((x for x in data if isinstance(x, dict)), {})
    if not isinstance(data, dict):
        raise ValueError("model did not return a JSON object")
    return data