import json, os, time
import redis
from agent.graph import run

r = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True,
                         socket_timeout=30, socket_connect_timeout=10, health_check_interval=15)
QUEUE = "petition_runs"

def jlog(event, **kw):
    print(json.dumps({"ts": round(time.time(), 3), "service": "worker", "event": event, **kw}), flush=True)

jlog("worker_started")
while True:
    item = r.blpop(QUEUE, timeout=5)
    if not item:
        continue
    job = json.loads(item[1])
    run_id, petition = job["run_id"], job["petition"]
    key = f"run:{run_id}"
    r.hset(key, "status", "running")
    jlog("run_started", run_id=run_id)
    try:
        out = run(petition)
        trace = out["trace"]

        # Calculate totals across steps (A6, L5)
        total_p_tok = 0
        total_c_tok = 0
        total_cost = 0.0
        tool_calls = 0

        for t in trace:
            if not isinstance(t, dict):
                continue
            if t.get("event") == "tool_call" or "action" in t:
                tool_calls += 1
            toks = t.get("tokens") if isinstance(t.get("tokens"), dict) else t
            total_p_tok += toks.get("prompt_tokens", 0)
            total_c_tok += toks.get("completion_tokens", 0)
            total_cost += float(toks.get("cost_usd", 0.0))

        steps_count = len(trace)

        for i, t in enumerate(trace):
            jlog("agent_step", run_id=run_id, idx=i, detail=json.dumps(t)[:400])

        r.hset(key, mapping={
            "status": "done",
            "result": json.dumps(out["final"]),
            "trace": json.dumps(trace),
            "elapsed_s": out["elapsed_s"],
            "prompt_tokens": total_p_tok,
            "completion_tokens": total_c_tok,
            "cost_usd": round(total_cost, 6),
            "tool_calls": tool_calls,
            "steps": steps_count
        })

        # Increment global Prometheus counters in Redis
        r.hincrby("stats", "completed", 1)
        r.hincrby("stats", "prompt_tokens", total_p_tok)
        r.hincrby("stats", "completion_tokens", total_c_tok)
        r.hincrby("stats", "tool_calls", tool_calls)
        r.hincrbyfloat("stats", "total_cost_usd", total_cost)
        r.hincrbyfloat("stats", "total_latency_s", out["elapsed_s"])

        jlog("run_done", run_id=run_id, route=out["final"]["route"], elapsed_s=out["elapsed_s"],
             cost_usd=round(total_cost, 6), tokens=total_p_tok + total_c_tok)
    except Exception as e:
        r.hset(key, mapping={"status": "failed", "error": type(e).__name__})
        r.hincrby("stats", "failed", 1)
        jlog("run_failed", run_id=run_id, error=str(e)[:200])
