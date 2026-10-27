import json, os, time
import redis
from agent.graph import run

r = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True,socket_timeout=30, socket_connect_timeout=10, health_check_interval=15)
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
        for i, t in enumerate(out["trace"]):
            jlog("agent_step", run_id=run_id, idx=i, detail=json.dumps(t)[:400])
        r.hset(key, mapping={"status": "done", "result": json.dumps(out["final"]),
                             "trace": json.dumps(out["trace"]), "elapsed_s": out["elapsed_s"]})
        r.hincrby("stats", "completed", 1)
        jlog("run_done", run_id=run_id, route=out["final"]["route"], elapsed_s=out["elapsed_s"])
    except Exception as e:
        r.hset(key, mapping={"status": "failed", "error": type(e).__name__})
        r.hincrby("stats", "failed", 1)
        jlog("run_failed", run_id=run_id, error=str(e)[:200])