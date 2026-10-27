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

_stub_state = {"step": 0}


def _stub(prompt):
    time.sleep(1)
    meta = {"model_used": "stub", "promptTokenCount": 0, "candidatesTokenCount": 0}
    if "Reply with JSON only, one of" in prompt:
        seen = prompt.split("Retrieved so far:")[1]
        if "(none yet)" in seen:
            _stub_state["step"] = 1
            out = {"action": "search", "query": "minimum overall attendance requirement"}
        else:
            _stub_state["step"] += 1
            have_mod = "vice-chancellor" in seen.lower() and "medical" in seen.lower()
            if _stub_state["step"] == 2:
                out = {"action": "search", "query": "condonation of attendance shortage medical emergency"}
            elif _stub_state["step"] == 3 and not have_mod:
                out = {"action": "get_clause", "doc": "", "clause": "13.2"}
            else:
                out = {"action": "finish"}
        return json.dumps(out), meta
    pas = []
    for line in prompt.split("Passages:")[1].splitlines():
        m = re.match(r"^\[([^|\]]+)\|([^|\]]+)\|p(\d+)\] (.*)$", line)
        if m:
            pas.append({"doc": m.group(1), "clause": m.group(2), "text": m.group(4)})
    bases = [p for p in pas if "minimum overall attendance" in p["text"].lower()]
    base = next((p for p in bases if p["clause"] == "12.1"), bases[0] if bases else None)
    mod = next((p for p in pas if "vice-chancellor" in p["text"].lower() and "medical" in p["text"].lower()), None)
    if base and mod:
        out = {"route": "refer-to-committee",
               "position": "Below the minimum; the Vice-Chancellor may condone on medical grounds.",
               "basis": "Stub response: base rule plus condonation provision.",
               "citations": [{"doc": base["doc"], "clause": base["clause"], "quote": base["text"][:150]},
                             {"doc": mod["doc"], "clause": mod["clause"], "quote": mod["text"][:150]}]}
    else:
        out = {"route": "escalate-to-human", "position": "Stub could not find the provisions.",
               "basis": "Stub response.", "citations": []}
    return json.dumps(out), meta


def call_llm(prompt, timeout=40, retries=2):
    if os.environ.get("LLM_STUB") == "1":
        return _stub(prompt)
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