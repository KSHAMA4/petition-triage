# Runbook

## Failure 1: LLM provider unavailable or out of quota
Symptom: runs finish as escalate-to-human with a basis starting "System error", or the API/worker
log shows "[llm ...] HTTP 429", "HTTP 503" or "ReadTimeout".
Confirm: run `python test_llm.py`. The printed attempt lines show the status code and which model failed.
Recovery: (1) wait a few minutes for per-minute limits; (2) run `python list_models.py` and put other
available model names in LLM_FALLBACK_MODELS in .env; (3) restart the API or worker, because .env is read at startup.

## Failure 2: Index missing, empty or stale
Symptom: searches return nothing, or the agent escalates every petition, or errors mention a missing collection.
Confirm: `ls index_store` and `cat index_store/manifest.json` (check built_at and the chunk count).
Recovery: `python ingest/ingest.py`. It is safe to re-run; it replaces each document's chunks.