# Runbook: Academic Petition Triage Service
**Course:** UE24AM342AA5 (Mini Project 15)  
**System:** Multi-Agent Academic Regulation & Petition Triage Service

---

## 1. System Overview & Deployment Boundaries
- **API Gateway (`api:8000`, external `8001`)**: FastAPI service enforcing the published data contract, input validation, and per-client rate limiting (10 req/min).
- **Triage Agent (`triage`)**: Consumes from `triage_queue`, classifies petition grounds (medical, sports, personal), and extracts numbers before passing to `petition_runs`.
- **Worker Agent (`worker`)**: Consumes from `petition_runs`, executes LangGraph retrieval over ChromaDB, performs multi-clause verification, and logs results.
- **Queue & Cache (`redis:6379`)**: Manages async job queues (`triage_queue`, `petition_runs`), pub/sub heartbeats, retrieval caching, and stats counters.

---

## 2. Failure Mode 1: Upstream LLM Provider Outage / Rate Limit (HTTP 429/503)
### Symptom
- Worker logs show `[circuit_breaker] OPEN!` or repeated `ConnectionError` / `429 Too Many Requests`.
- Petitions stay in `running` status or return `escalate-to-human` with basis: `Provider unavailable`.

### Confirmation
1. Inspect worker logs:
   ```bash
   docker compose logs worker --tail 25
   ```
2. Verify Redis circuit breaker status:
   ```bash
   curl -s http://127.0.0.1:8001/metrics | grep triage_failed_total
   ```

### Recovery
1. **Model Fallback**: The system automatically attempts configured fallback models (`LLM_FALLBACK_MODELS`).
2. **Circuit Breaker Cooldown**: The system fails fast for 30s to prevent worker exhaustion.
3. **Emergency Offline Mode**: Switch the stack to stub mode to keep queue draining without quota:
   ```bash
   LLM_STUB=1 docker compose restart worker triage
   ```

---

## 3. Failure Mode 2: Ingestion Queue Backlog / Worker Starvation
### Symptom
- UI stays on `Status: queued ...` for longer than 30 seconds.
- `/health` endpoint reports `queue_depth > 10`.

### Confirmation
1. Query queue metrics:
   ```bash
   curl -s http://127.0.0.1:8001/health
   ```
2. Check worker container status:
   ```bash
   docker compose ps
   ```

### Recovery
1. **Horizontal Worker Scaling (Requirement A7)**:
   Scale up worker agents to clear the queue:
   ```bash
   docker compose up -d --scale worker=3
   ```
2. **Re-queue stuck jobs**: Restarting the worker triggers safe `rpoplpush` recovery, moving processing items back into the intake queue without message loss.
