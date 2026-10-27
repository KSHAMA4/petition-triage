import json, os, time, uuid, logging
import redis
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError
from contracts.petition import Petition, quarantine
from agent.graph import run as run_agent

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("api")
app = FastAPI(title="Petition Triage")
r = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True,socket_timeout=10, socket_connect_timeout=10)
QUEUE = "petition_runs"


def jlog(event, **kw):
    log.info(json.dumps({"ts": round(time.time(), 3), "service": "api", "event": event, **kw}))


@app.post("/petitions", status_code=202)
def submit(raw: dict):
    try:
        petition = Petition(**raw).model_dump(mode="json")
    except ValidationError as e:
        quarantine(raw, e)
        r.hincrby("stats", "rejected", 1)
        jlog("petition_rejected", errors=len(e.errors()))
        return JSONResponse(status_code=422, content={
            "status": "rejected", "agent_started": False,
            "errors": [{"field": ".".join(map(str, x["loc"])), "msg": x["msg"]} for x in e.errors()]})
    run_id = str(uuid.uuid4())
    r.hset(f"run:{run_id}", mapping={"status": "queued", "submitted_at": time.time()})
    r.rpush(QUEUE, json.dumps({"run_id": run_id, "petition": petition}))
    r.hincrby("stats", "submitted", 1)
    jlog("petition_queued", run_id=run_id, petition_id=petition["petition_id"])
    return {"run_id": run_id, "status": "queued", "poll": f"/runs/{run_id}"}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    h = r.hgetall(f"run:{run_id}")
    if not h:
        return JSONResponse(status_code=404, content={"error": "unknown run_id"})
    for k in ("result", "trace"):
        if k in h:
            h[k] = json.loads(h[k])
    return h


@app.get("/health")
def health():
    try:
        r.ping()
        return {"status": "ok", "queue_depth": r.llen(QUEUE)}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "redis unavailable"})


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    lines = [f"petitions_{k}_total {v}" for k, v in r.hgetall("stats").items()]
    lines.append(f"queue_depth {r.llen(QUEUE)}")
    return "\n".join(lines) + "\n"