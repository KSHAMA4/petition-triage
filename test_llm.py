from agent.llm import call_llm, parse_json
text, usage = call_llm('Reply with JSON only: {"ok": true}')
print(parse_json(text), usage)