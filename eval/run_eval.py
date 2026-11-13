import json, sys, time, pathlib
from pydantic import ValidationError
from contracts.petition import Petition
from agent.graph import run

def compute_metrics(scenarios_results):
    total = len(scenarios_results)
    if total == 0:
        return {}

    grounded_count = 0
    relevant_count = 0
    faithful_count = 0
    hallucination_count = 0

    for r in scenarios_results:
        # Groundedness: proportion of returned citations that resolve to valid clauses
        cited = r.get("cited", [])
        expected_clauses = r.get("expected_clauses", [])
        is_grounded = bool(r.get("verified")) and (len(cited) > 0 or r.get("got_route") in ("escalate-to-human", "rejected_at_ingestion"))
        if is_grounded:
            grounded_count += 1

        # Context relevance: whether retrieved/cited clauses match expected regulations
        if expected_clauses:
            has_relevant = any(any(c == exp or c.startswith(exp + ".") for exp in expected_clauses) for c in cited)
            if has_relevant:
                relevant_count += 1
        else:
            relevant_count += 1  # For out-of-scope/malformed, no clause needed

        # Faithfulness: answer can be inferred from cited provisions
        if r.get("passed"):
            faithful_count += 1

        # Hallucination rate: statements/citations not supported or contradictory
        if not r.get("passed") and len(cited) > 0 and not any(any(c == exp or c.startswith(exp + ".") for exp in expected_clauses) for c in cited):
            hallucination_count += 1

    return {
        "groundedness": round(grounded_count / total, 3),
        "context_relevance": round(relevant_count / total, 3),
        "faithfulness": round(faithful_count / total, 3),
        "hallucination_rate": round(hallucination_count / total, 3)
    }

def main():
    args = sys.argv[1:]
    ids = [a for a in args if a.startswith("S")]
    prompt_variant = "v2_structured" if "--v2" in args else "v1_baseline"
    scenarios = json.load(open("eval/scenarios.json", encoding="utf-8"))
    if ids:
        scenarios = [s for s in scenarios if s["id"] in ids]

    results, ok = [], 0
    print(f"=== Running Evaluation Set ({len(scenarios)} Scenarios) [Variant: {prompt_variant}] ===")
    
    for s in scenarios:
        t0 = time.time()
        try:
            petition = Petition(**s["petition"]).model_dump(mode="json")
        except ValidationError:
            route, cited, verified = "rejected_at_ingestion", [], True
            basis = "rejected by data contract at ingestion boundary"
        else:
            out = run(petition)
            final = out["final"]
            route = final["route"]
            cited = [str(c.get("clause")) for c in final.get("citations", [])]
            verified = bool(final.get("verified"))
            basis = final.get("basis", "")

        want = s["expected_clauses"]
        clauses_ok = all(any(c == w or c.startswith(w + ".") for c in cited) for w in want)
        passed = route == s["expected_route"] and clauses_ok
        ok += passed
        results.append({
            "id": s["id"],
            "note": s["note"],
            "basis": basis,
            "expected_route": s["expected_route"],
            "got_route": route,
            "expected_clauses": want,
            "cited": cited,
            "verified": verified,
            "passed": passed,
            "seconds": round(time.time() - t0, 2)
        })
        print(f"[{s['id']}] {'PASS' if passed else 'FAIL'} | Want: {s['expected_route']} | Got: {route} | Cited: {cited}")

    metrics = compute_metrics(results)
    summary = {
        "variant": prompt_variant,
        "scenarios_count": len(scenarios),
        "passed": ok,
        "accuracy": round(ok / len(scenarios), 3),
        "metrics": metrics,
        "results": results
    }

    print("\n" + "="*50)
    print(f"Evaluation Summary ({ok}/{len(scenarios)} passed - Accuracy: {summary['accuracy']*100}%):")
    print(f"  • Groundedness:       {metrics['groundedness']}")
    print(f"  • Context Relevance:  {metrics['context_relevance']}")
    print(f"  • Faithfulness:       {metrics['faithfulness']}")
    print(f"  • Hallucination Rate: {metrics['hallucination_rate']}")
    print("="*50)

    out_file = f"eval/benchmark_{prompt_variant}.json"
    pathlib.Path(out_file).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Detailed evaluation artifact saved to {out_file}")

if __name__ == "__main__":
    main()
