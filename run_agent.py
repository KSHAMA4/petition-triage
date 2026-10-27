import json, sys
from pydantic import ValidationError
from contracts.petition import Petition, quarantine
from agent.graph import run

path = sys.argv[1] if len(sys.argv) > 1 else "eval/petition_4_1.json"
raw = json.load(open(path))
try:
    petition = Petition(**raw).model_dump(mode="json")
except ValidationError as e:
    quarantine(raw, e)
    print("Rejected at ingestion and quarantined. No agent run started.")
    sys.exit(1)
print(json.dumps(run(petition), indent=2))