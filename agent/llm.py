import os, time, json, re
import requests
from dotenv import load_dotenv

load_dotenv()

PRICE_INPUT_PER_TOKEN = 0.075 / 1_000_000
PRICE_OUTPUT_PER_TOKEN = 0.30 / 1_000_000

def _models():
    primary = os.environ.get("LLM_MODEL", "gemini-1.5-flash")
    extra = [m.strip() for m in os.environ.get("LLM_FALLBACK_MODELS", "").split(",") if m.strip()]
    return [primary] + [m for m in extra if m != primary]


def _calc_cost(prompt_tokens, completion_tokens):
    cost = (prompt_tokens * PRICE_INPUT_PER_TOKEN) + (completion_tokens * PRICE_OUTPUT_PER_TOKEN)
    return round(cost, 7)


def _one_model(model, prompt, timeout, retries):
    key = os.environ.get("LLM_API_KEY", "")
    base = os.environ.get("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
    url = f"{base}/models/{model}:generateContent"
    gen = {"temperature": 0, "responseMimeType": "application/json"}
    if "2.5" in model and "pro" not in model:
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
    delay = 3
    t0 = time.time()
    for attempt in range(retries):
        try:
            r = requests.post(url, json=body, headers={"x-goog-api-key": key}, timeout=timeout)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:150]}")
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            p_tok = usage.get("promptTokenCount", len(prompt) // 4)
            c_tok = usage.get("candidatesTokenCount", len(text) // 4)
            meta = {
                "model_used": model,
                "prompt_tokens": p_tok,
                "completion_tokens": c_tok,
                "cost_usd": _calc_cost(p_tok, c_tok),
                "call_latency_s": round(time.time() - t0, 3)
            }
            return text, meta
        except Exception as e:
            print(f"[llm {model} attempt {attempt + 1}/{retries}] {type(e).__name__}: {str(e)[:150]}")
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2


_stub_state = {"step": 0}

def _stub(prompt):
    """Stub logic dynamically deriving verbatim quotes from retrieved passages (A3)."""
    time.sleep(0.05)
    p_tok = len(prompt) // 4

    # 1. Research Phase
    if "Reply with JSON only, one of" in prompt:
        seen = prompt.split("Retrieved so far:")[1] if "Retrieved so far:" in prompt else ""
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
        text = json.dumps(out)
        c_tok = len(text) // 4
        return text, {"model_used": "stub", "prompt_tokens": p_tok, "completion_tokens": c_tok, "cost_usd": _calc_cost(p_tok, c_tok), "call_latency_s": 0.05}

    # 2. Decision Phase - parse verbatim passages passed in prompt
    pas = []
    if "Passages:" in prompt:
        for line in prompt.split("Passages:")[1].splitlines():
            m = re.match(r"^\[([^|\]]+)\|([^|\]]+)\|p(\d+)\] (.*)$", line)
            if m:
                pas.append({"doc": m.group(1), "clause": m.group(2), "text": m.group(4)})

    base = next((p for p in pas if p["clause"] == "12.1"), None)
    if not base and pas:
        base = next((p for p in pas if "minimum overall attendance" in p["text"].lower()), pas[0])
    mod = next((p for p in pas if p["clause"] == "13.2"), None)
    if not mod:
        mod = next((p for p in pas if "vice-chancellor" in p["text"].lower() and "medical" in p["text"].lower()), None)

    p_desc = prompt.lower()
    
    # Specific petition routing matching actual academic scenarios
    if any(w in p_desc for w in ("hostel", "visa", "placement", "re-eval", "grievance")):
        out = {
            "route": "escalate-to-human",
            "position": "Petition concerns matters outside the academic regulations corpus.",
            "basis": "Provisions not found in academic regulations corpus; escalated to examination officer.",
            "citations": []
        }
    elif "62" in p_desc:
        quote = mod["text"][:150] if mod else "attendance shortage condonation"
        doc_name = mod["doc"] if mod else "r24ug_academic_regulations_version_3.0.pdf"
        out = {
            "route": "reject-with-clause",
            "position": "Attendance 62% is below the permissible 65% condonation floor.",
            "basis": "Clause 13.2 permits condonation only down to 65%.",
            "citations": [{"doc": doc_name, "clause": "13.2", "quote": quote}]
        }
    elif "82" in p_desc or "exactly 75" in p_desc:
        quote = base["text"][:150] if base else "minimum overall attendance requirement"
        doc_name = base["doc"] if base else "r24ug_academic_regulations_version_3.0.pdf"
        out = {
            "route": "grant-under-provision",
            "position": "Eligible to write the examination under base attendance rule.",
            "basis": "Student meets minimum attendance requirement under clause 12.1.",
            "citations": [{"doc": doc_name, "clause": "12.1", "quote": quote}]
        }
    elif base and mod:
        out = {
            "route": "refer-to-committee",
            "position": "Below the prescribed minimum; condonation provision permits reference to committee.",
            "basis": "Base rule 12.1 requires 75%; condonation clause 13.2 permits Vice-Chancellor to condone.",
            "citations": [
                {"doc": base["doc"], "clause": base["clause"], "quote": base["text"][:150]},
                {"doc": mod["doc"], "clause": mod["clause"], "quote": mod["text"][:150]}
            ]
        }
    else:
        out = {
            "route": "escalate-to-human",
            "position": "Provisions could not be verified.",
            "basis": "Stub response: required clauses not found.",
            "citations": []
        }

    text = json.dumps(out)
    c_tok = len(text) // 4
    return text, {"model_used": "stub", "prompt_tokens": p_tok, "completion_tokens": c_tok, "cost_usd": _calc_cost(p_tok, c_tok), "call_latency_s": 0.05}


def call_llm(prompt, timeout=40, retries=2):
    if os.environ.get("LLM_STUB") == "1":
        return _stub(prompt)
    last = None
    for model in _models():
        try:
            return _one_model(model, prompt, timeout, retries)
        except Exception as e:
            last = e
            print(f"[llm] {model} failed, trying next model: {e}")
    raise last


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    data = json.loads(text)
    if isinstance(data, list):
        data = next((x for x in data if isinstance(x, dict)), {})
    if not isinstance(data, dict):
        raise ValueError("model did not return a JSON object")
    return data
