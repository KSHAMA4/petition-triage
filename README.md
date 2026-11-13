# Academic Petition Triage Service
**Course:** UE24AM342AA5 — ML System Design and AgentOps  
**Project:** Mini Project 15 (Academic Regulation and Student Petition Triage Service)  
**Domain:** Higher Education Administration  

---

## 1. Problem Statement
Academic bye-laws separate base rules (Clause 12.1: minimum 75% attendance) and condonation provisions (Clause 13.2: condonation down to 65% for medical emergencies decided by the Vice-Chancellor). Standard single-pass retrieval fails on medical petitions because petitions never use the word "condonation".

This multi-agent service:
1. Validates and quarantines malformed requests at the ingestion boundary.
2. Uses an agentic loop (LangGraph) to iteratively retrieve base and modifier provisions.
3. Self-verifies citations and verbatim quotes before routing.
4. Generates an eligibility recommendation without issuing autonomous binding decisions.

---

## 2. Architecture & Services
The application runs as 4 containerized services under Docker Compose:
- **`redis`**: Task queue (`triage_queue`, `petition_runs`), heartbeat monitor, and retrieval cache.
- **`ingest`**: Idempotent PDF parser, clause chunker, and ChromaDB vector indexer (`all-MiniLM-L6-v2`).
- **`api`**: FastAPI service handling schema validation, rate-limiting (10 req/min), feedback endpoints, and the Web UI.
- **`triage`**: Agent 1 classifying petition grounds (medical, sports, personal) and extracting attendance figures.
- **`worker`**: Agent 2 running LangGraph multi-step reasoning, Chroma retrieval, and self-verification.

---

## 3. Quickstart: Clean-Clone Setup
```bash
# 1. Clone the repository
git clone https://github.com/KSHAMA4/petition-triage.git
cd petition-triage

# 2. Configure environment
cp .env.example .env

# 3. Launch with Docker Compose (Stub mode for offline testing)
LLM_STUB=1 docker compose up --build

# 4. Access Web UI
# Open in browser: http://127.0.0.1:8001
```

---

## 4. Evaluation Suite & Benchmark (L2, L3)
Run the 20-scenario benchmark suite:
```bash
docker compose exec worker python -m eval.run_eval
```
**Results:**
- **Groundedness:** 0.95 (95%)
- **Context Relevance:** 0.85 (85%)
- **Faithfulness:** 0.65 (65%)
- **Hallucination Rate:** 0.15 (15%)

---

## 5. Performance & Load Testing (D6, A7)
- **Declared SLO:** $p95 \le 3.5\text{s}$ at 10 concurrent users.
- **Locust Benchmark:**
  ```bash
  locust -f locustfile.py --headless -u 10 -r 2 --run-time 30s --host http://127.0.0.1:8001
  ```
  - **Measured p95:** 17 ms
  - **Throughput:** 6.72 RPS
  - **Bottleneck Identified:** Rate limiter (10 req/min) returning HTTP 429 under sustained concurrency.

---

## 6. Repository Structure & Deliverables
- `agent/`: LangGraph orchestration, tools, guardrails, and resilience modules.
- `contracts/`: Pydantic data contract and quarantine handler.
- `corpus/`: University academic regulation PDFs.
- `docs/`:
  - [`final_report.md`](docs/final_report.md): Evaluation report and architecture description.
  - [`runbook.md`](docs/runbook.md): Production runbook for failure modes and recovery.
  - [`incident_log.md`](docs/incident_log.md): Incident records from development.
  - [`slo.md`](docs/slo.md): Justified p95 service level objective.
- `eval/`: 20-scenario test suite (`scenarios.json`) and benchmark runner.
- `services/`: API gateway, Triage agent, and Worker service.
