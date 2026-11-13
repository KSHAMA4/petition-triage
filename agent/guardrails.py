import re

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|system)\s+prompts?",
    r"system\s*:\s*you\s+are",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"override\s+all\s+rules",
    r"say\s+route\s+is\s+grant",
    r"approve\s+this\s+petition\s+immediately",
    r"bypass\s+verification",
    r"format\s+c:",
    r"<script.*?>",
]

def check_prompt_injection(text: str) -> tuple[bool, str]:
    """Inspects student input for jailbreak / prompt injection attacks (L4)."""
    if not text:
        return False, ""
    lower = text.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, lower):
            return True, f"Prompt injection detected matching pattern: {pat}"
    return False, ""

def filter_output(decision: dict) -> dict:
    """Enforces that the agent never issues an unauthorized final determination (L4)."""
    disallowed_keywords = ["granted officially", "binding decision", "approved by ai", "i hereby approve"]
    pos = decision.get("position", "")
    for kw in disallowed_keywords:
        if kw in pos.lower():
            decision["position"] = "Eligibility recommendation only. Examination officer must decide."
            decision["route"] = "refer-to-committee"
    return decision
