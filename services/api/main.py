import json, os, pathlib, time, uuid, logging
import redis
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, ValidationError
from contracts.petition import Petition, quarantine

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("api")
app = FastAPI(title="Petition Triage")

r = redis.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
                         decode_responses=True, socket_timeout=10, socket_connect_timeout=10)
QUEUE = os.environ.get("INTAKE_QUEUE", "petition_runs")
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "10"))
INDEX_HTML = pathlib.Path(__file__).with_name("static") / "index.html"


def jlog(event, **kw):
    log.info(json.dumps({"ts": round(time.time(), 3), "service": "api", "event": event, **kw}))


def bump(name):
    try:
        r.hincrby("stats", name, 1)
    except redis.exceptions.RedisError:
        pass


def unavailable():
    return JSONResponse(status_code=503, content={"error": "queue unavailable, try again shortly"})


def over_limit(request: Request):
    cid = (request.headers.get("x-client-id") or (request.client.host if request.client else "unknown"))[:64]
    key = f"rl:{cid}:{int(time.time() // 60)}"
    n = r.incr(key)
    if n == 1:
        r.expire(key, 120)
    return n > RATE_LIMIT


class Feedback(BaseModel):
    satisfactory: bool
    reason: str = Field(default="", max_length=500)


@app.get("/", response_class=HTMLResponse)
def home():
    if not INDEX_HTML.exists():
        return HTMLResponse("index.html not found at services/api/static/index.html", status_code=500)
    return HTMLResponse(INDEX_HTML.read_text(encoding="utf-8"))


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


@app.post("/petitions", status_code=202)
def submit(raw: dict, request: Request):
    try:
        petition = Petition(**raw).model_dump(mode="json")
    except ValidationError as e:
        quarantine(raw, e)
        bump("rejected")
        jlog("petition_rejected", errors=len(e.errors()))
        return JSONResponse(status_code=422, content={
            "status": "rejected", "agent_started": False,
            "errors": [{"field": ".".join(map(str, x["loc"])), "msg": x["msg"]} for x in e.errors()]})
    try:
        if over_limit(request):
            bump("rate_limited")
            jlog("rate_limited")
            return JSONResponse(status_code=429, headers={"Retry-After": "60"},
                                content={"error": "rate limit exceeded", "limit_per_minute": RATE_LIMIT})
        run_id = str(uuid.uuid4())
        r.hset(f"run:{run_id}", mapping={"status": "queued", "submitted_at": time.time()})
        r.rpush(QUEUE, json.dumps({"run_id": run_id, "petition": petition}))
        bump("submitted")
    except redis.exceptions.RedisError:
        return unavailable()
    jlog("petition_queued", run_id=run_id, petition_id=petition["petition_id"])
    return {"run_id": run_id, "status": "queued", "poll": f"/runs/{run_id}"}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    if len(run_id) > 64:
        return JSONResponse(status_code=404, content={"error": "unknown run_id"})
    try:
        h = r.hgetall(f"run:{run_id}")
        fb = r.hgetall(f"feedback:{run_id}")
    except redis.exceptions.RedisError:
        return unavailable()
    if not h:
        return JSONResponse(status_code=404, content={"error": "unknown run_id"})
    h["run_id"] = run_id
    for k in ("result", "trace", "triage"):
        if k in h:
            try:
                h[k] = json.loads(h[k])
            except ValueError:
                pass
    if fb:
        h["feedback"] = fb
    return h


@app.post("/runs/{run_id}/feedback", status_code=201)
def feedback(run_id: str, fb: Feedback):
    if len(run_id) > 64:
        return JSONResponse(status_code=404, content={"error": "unknown run_id"})
    try:
        if not r.exists(f"run:{run_id}"):
            return JSONResponse(status_code=404, content={"error": "unknown run_id"})
        if r.exists(f"feedback:{run_id}"):
            return JSONResponse(status_code=409, content={"error": "feedback already recorded for this run"})
        rec = {"run_id": run_id, "satisfactory": fb.satisfactory, "reason": fb.reason, "ts": time.time()}
        r.hset(f"feedback:{run_id}", mapping={"satisfactory": str(fb.satisfactory).lower(),
                                              "reason": fb.reason, "ts": rec["ts"]})
        r.rpush("feedback_log", json.dumps(rec))
        bump("feedback_satisfactory" if fb.satisfactory else "feedback_not_satisfactory")
    except redis.exceptions.RedisError:
        return unavailable()
    jlog("feedback_saved", run_id=run_id, satisfactory=fb.satisfactory)
    return {"status": "saved"}


@app.get("/feedback/summary")
def feedback_summary():
    try:
        items = [json.loads(x) for x in r.lrange("feedback_log", 0, -1)]
    except redis.exceptions.RedisError:
        return unavailable()
    good = sum(1 for i in items if i["satisfactory"])
    bad = len(items) - good
    return {"total": len(items), "satisfactory": good, "not_satisfactory": bad,
            "satisfaction_rate": round(good / len(items), 2) if items else None,
            "recent": items[-20:]}


@app.get("/health")
def health():
    try:
        r.ping()
        out = {"status": "ok", "queue_depth": r.llen(QUEUE), "stub": os.environ.get("LLM_STUB") == "1"}
        if QUEUE == "triage_queue":
            out["triage_alive"] = bool(r.exists("hb:triage"))
        return out
    except redis.exceptions.RedisError:
        return JSONResponse(status_code=503, content={"status": "redis unavailable"})


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    try:
        stats = r.hgetall("stats")
        completed = int(stats.get("completed", 0))
        total_lat = float(stats.get("total_latency_s", 0.0))
        avg_lat = round(total_lat / completed, 3) if completed > 0 else 0.0
        
        lines = [
            "# HELP triage_completed_total Total successful runs",
            "# TYPE triage_completed_total counter",
            f"triage_completed_total {completed}",
            "# HELP triage_failed_total Total failed runs",
            "# TYPE triage_failed_total counter",
            f"triage_failed_total {stats.get('failed', 0)}",
            "# HELP triage_rejected_total Total petitions rejected at ingestion boundary",
            "# TYPE triage_rejected_total counter",
            f"triage_rejected_total {stats.get('rejected', 0)}",
            "# HELP triage_queue_depth Current petitions waiting in queue",
            "# TYPE triage_queue_depth gauge",
            f"triage_queue_depth {r.llen(QUEUE)}",
            "# HELP triage_prompt_tokens_total Total prompt tokens used",
            "# TYPE triage_prompt_tokens_total counter",
            f"triage_prompt_tokens_total {stats.get('prompt_tokens', 0)}",
            "# HELP triage_completion_tokens_total Total completion tokens generated",
            "# TYPE triage_completion_tokens_total counter",
            f"triage_completion_tokens_total {stats.get('completion_tokens', 0)}",
            "# HELP triage_cost_usd_total Estimated total LLM cost in USD",
            "# TYPE triage_cost_usd_total counter",
            f"triage_cost_usd_total {stats.get('total_cost_usd', 0.0)}",
            "# HELP triage_avg_latency_seconds Average end-to-end run latency",
            "# TYPE triage_avg_latency_seconds gauge",
            f"triage_avg_latency_seconds {avg_lat}",
        ]
    except redis.exceptions.RedisError:
        return PlainTextResponse("redis unavailable\n", status_code=503)
    return "\n".join(lines) + "\n"