# Phase 0 evidence

Updated 21 November 2026 IST.

## Implemented

- Exact citation spans and a minimum useful quotation length are enforced in the legacy validator.
- A missing replacement for a `revise` response becomes `unresolved`.
- Critique closure covers every challenge once, with an unresolved fallback.
- Tests generate their own synthetic PDF and no longer read course material.
- Windows bootstrap, check, development, migration, smoke and quality entry points exist.
- Docker Compose binds the UI to `127.0.0.1`, keeps SQLite in a named volume and includes a health check.
- The browser encoding defects were removed and external source links use safe new-tab attributes.

## Verification

- `python -m unittest discover -s tests -v` passed 8/8 tests on Python 3.12 using an isolated dependency directory.
- `node --check paperlens/web/app.js` passed.
- `docker compose config --quiet` passed with the host Docker CLI.
- A native Uvicorn smoke run returned HTTP 200 from `/health` and `/`; the health payload was `ok` and the HTML contained `PaperLens`.
- Every PowerShell script parsed successfully with the PowerShell script parser.

## Open gate

The Phase 0 local gate is verified. The Compose image built, PostgreSQL and the web service became healthy, and the health/UI smoke checks passed. Phase 1 interoperability remains pending.
