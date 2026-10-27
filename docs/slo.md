# Service level objective (declared 2026-10-26, before any load test)

SLI: time from POST /petitions to a terminal run status (done or failed), measured end to end.
SLO: p95 <= 60 seconds for a complete run, measured with the LLM replaced by a stub that
responds after a realistic delay.

Justification: petitions are processed asynchronously and an examination officer reviews the
result later, so the caller is not waiting on the response. A run that takes longer than a
minute at p95 would still be acceptable, but it must stay well inside the agent's own 90 second
wall-clock limit, otherwise runs would be cut off. The target will be revised only by adding a
dated note, never by editing this line after measuring.