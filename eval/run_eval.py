import json, sys, time, pathlib
from pydantic import ValidationError
from contracts.petition import Petition
from agent.graph import run

args = sys.argv[1:]
ids = [a for a in args if a.startswith("S")]
scenarios = json.load(open("eval/scenarios.json"))
if ids:
    scenarios = [s for s in scenarios if s["id"] in ids]

results, ok = [], 0
for s in scenarios:
    t0 = time.time()
    try:
        petition = Petition(**s["petition"]).model_dump(mode="json")
    except ValidationError:
        route, cited, verified = "rejected_at_ingestion", [], True
        basis = "rejected by data contract"
    else:
        out = run(petition)
        final = out["final"]
        route = final["route"]
        cited = [str(c.get("clause")) for c in final.get("citations", [])]
        verified = bool(final.get("verified"))
        basis = final.get("basis", "")
        time.sleep(8)
    want = s["expected_clauses"]
    clauses_ok = all(any(c == w or c.startswith(w + ".") for c in cited) for w in want)
    passed = route == s["expected_route"] and clauses_ok
    ok += passed
    results.append({"id": s["id"], "note": s["note"], "basis": basis, "expected_route": s["expected_route"], "got_route": route,
                    "expected_clauses": want, "cited": cited, "verified": verified,
                    "passed": passed, "seconds": round(time.time() - t0, 1)})
    print(f"{s['id']} {'PASS' if passed else 'FAIL'}  want={s['expected_route']} got={route} cited={cited}")
    if not passed:
        print("   basis:", basis[:300])
print(f"\n{ok}/{len(scenarios)} passed")
pathlib.Path("eval/results.json").write_text(json.dumps(results, indent=2))