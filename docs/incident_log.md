# Incident Log: Academic Petition Triage Service
**Course:** UE24AM342AA5 (Mini Project 15)  
**Requirement:** D8 (Real Development Incident Records)

---

## Incident 1: Port Collision on Startup (`0.0.0.0:8000`)
- **Date/Time:** 2026-11-13 08:45 IST
- **Severity:** High (Service Outage on Startup)
- **Symptom:** Starting `docker compose up` rendered an unfamiliar page titled *"Agent Pipeline: Researcher → Writer → Reviewer"* instead of the Petition Triage UI.
- **Root Cause:** A lingering container from a prior lab (`pes1ug24am142-orchestrator-1`) had been bound to port `8000` for 12 days, intercepting inbound traffic.
- **Resolution:** Re-mapped external port in `docker-compose.yml` to `8001:8000`, cleanly isolating the service boundary without disrupting host processes.
- **Prevention:** Documented standard port assignment (`8001`) in `README.md` and health check scripts.

---

## Incident 2: Rate Limiting & Hugging Face Hub 429 During Ingestion
- **Date/Time:** 2026-11-13 09:15 IST
- **Severity:** Medium (Pipeline Delay)
- **Symptom:** `ingest-1` blocked on startup displaying `HTTP Error 429 thrown while requesting HEAD https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2`.
- **Root Cause:** SentenceTransformers queried Hugging Face online on every container start, encountering anonymous IP rate limits.
- **Resolution:** Added `HF_HUB_OFFLINE: "1"` to environment configuration in `docker-compose.yml`, forcing the model loader to use weights baked into the image.
- **Prevention:** All embedding models are pre-cached in Docker layers with offline mode forced by default.

---

## Incident 3: Host vs Container SQLite File Lock on Vector Index
- **Date/Time:** 2026-11-13 10:01 IST
- **Severity:** Medium (Evaluation Execution Failure)
- **Symptom:** Running `python -m eval.run_eval` from host Git Bash failed scenario `S01` with `chromadb.errors.NotFoundError: Collection [regulations] does not exist`.
- **Root Cause:** The Docker worker held an active write-lock on `index_store/chroma.sqlite3`. Host Windows processes attempting to query ChromaDB encountered database lock contention.
- **Resolution:** Executed evaluation suite directly within the containerized boundary via `docker compose exec worker python -m eval.run_eval`.
- **Prevention:** Documented container-native evaluation execution in project documentation.
