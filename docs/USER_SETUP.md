# PaperLens local setup

1. Install Docker Desktop and start the Linux container engine.
2. Run `scripts/bootstrap.ps1` and enter a Groq API key when prompted.
3. Run `scripts/dev.ps1`.
4. Run `scripts/smoke.ps1`.
5. Open `http://127.0.0.1:8000`. Jaeger is at `http://127.0.0.1:16686`.

The generated `.env` contains secrets and must remain uncommitted. Rotate any key that has appeared in terminal output or a tracked file.

## CLI

Create an API token through `POST /api/v1/tokens`, then set `PAPERLENS_TOKEN` and run:

`python apps/cli/paperlens_cli.py review paper.pdf --out review.json`

## Assistant MCP

Run `python -m apps.assistant_mcp.server` with `PAPERLENS_URL` and `PAPERLENS_TOKEN` set. It exposes `explore_idea`, `get_run`, and `list_library` over stdio MCP.
