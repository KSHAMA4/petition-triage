import json, time, uuid, logging, threading
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import ValidationError
from contracts.petition import Petition, quarantine
from agent.graph import run as run_agent

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("api")
app = FastAPI(title="Petition Triage")

RUNS = {}
STATS = {"submitted": 0, "rejected": 0, "completed": 0, "failed": 0}
LOCK = threading.Lock()


def jlog(event, **kw):
    log.info(json.dumps({"ts": round(time.time(), 3), "event": event, **kw}))


def execute(run_id, petition):
    RUNS[run_id]["status"] = "running"
    jlog("run_started", run_id=run_id)
    try:
        result = run_agent(petition)
        for i, t in enumerate(result["trace"]):
            jlog("agent_step", run_id=run_id, idx=i, detail=json.dumps(t)[:400])
        RUNS[run_id].update(status="done", result=result["final"],
                            trace=result["trace"], elapsed_s=result["elapsed_s"])
        with LOCK:
            STATS["completed"] += 1
        jlog("run_done", run_id=run_id, route=result["final"]["route"],
             verified=result["final"].get("verified"), elapsed_s=result["elapsed_s"])
    except Exception as e:
        RUNS[run_id].update(status="failed", error=type(e).__name__)
        with LOCK:
            STATS["failed"] += 1
        jlog("run_failed", run_id=run_id, error=str(e)[:200])


@app.post("/petitions", status_code=202)
def submit(raw: dict, background: BackgroundTasks):
    try:
        petition = Petition(**raw).model_dump(mode="json")
    except ValidationError as e:
        quarantine(raw, e)
        with LOCK:
            STATS["rejected"] += 1
        jlog("petition_rejected", errors=len(e.errors()))
        return JSONResponse(status_code=422, content={
            "status": "rejected", "agent_started": False,
            "errors": [{"field": ".".join(map(str, x["loc"])), "msg": x["msg"]} for x in e.errors()]})
    run_id = str(uuid.uuid4())
    RUNS[run_id] = {"run_id": run_id, "status": "queued", "submitted_at": time.time()}
    with LOCK:
        STATS["submitted"] += 1
    jlog("petition_accepted", run_id=run_id, petition_id=petition["petition_id"])
    background.add_task(execute, run_id, petition)
    return {"run_id": run_id, "status": "queued", "poll": f"/runs/{run_id}"}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    return RUNS.get(run_id) or JSONResponse(status_code=404, content={"error": "unknown run_id"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return "\n".join(f"petitions_{k}_total {v}" for k, v in STATS.items()) + "\n"