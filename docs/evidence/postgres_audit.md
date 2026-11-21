# PostgreSQL and audit foundation evidence

Updated 21 November 2026 IST.

- `docker compose up --build --detach --wait` completed with healthy web, PostgreSQL and Jaeger containers.
- PostgreSQL reported the `vector` extension and application tables `runs` and `audit_events`.
- `/api/v1/health/ready` returned `status=ok` and `model_configured=true`.
- Twelve native tests passed, including strict evidence contracts, rubric scoring, percentage consistency, reproducibility checklist and hygiene checks.
- A real Groq models request authenticated successfully. A structured GPT-OSS 20B response validated locally. Subsequent calls returned HTTP 429, now represented as `Quota wait` rather than a false successful review.

This is partial Phase 2 evidence. It does not satisfy the Phase 1 CrewAI/A2A/ADK/MCP gate.
