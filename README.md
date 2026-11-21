# PaperLens

This local, single-user prototype accepts empirical research papers and rough research ideas. It extracts locatable passages, queries arXiv, and saves runs and refinements in SQLite. Configuring a Groq model enables three specialist assessments with exact-quote validation and one bounded critique pass. The browser displays findings, objections, source passages, previous runs and export links.

## Run locally

Use Python 3.12 in the project folder. Keep the server bound to loopback because this prototype uses a shared local history.

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    .\.venv\Scripts\python.exe -m uvicorn paperlens.service:app --host 127.0.0.1 --port 8000

Open http://127.0.0.1:8000. Set GROQ_API_KEY and PAPERLENS_MODEL in the server process environment before launch for live assessments. Choose an accessible model supporting JSON output. Set PAPERLENS_DB to change the SQLite file location. The search field is sent to arXiv. When it is empty, the app uses up to 160 opening characters. Use public research material for demonstrations.

## Check the implementation

    python -m unittest discover -s tests -p test_local.py -v
    python -m unittest discover -s tests -v
    node --check paperlens/web/app.js

The first command runs directly against the application handlers. The full suite also exercises FastAPI over its test client. In the managed Windows environment, asyncio blocked while creating its loopback socket pair before HTTP requests reached the application.

## Release status

The local handler checks passed for PDF extraction with a literature-provider outage, saving and refining an idea, reading its original record, Markdown export, and critic retraction. The separate citation test rejected an invented quote. Model and provider calls still need a live run. Missing keys give an explicitly labelled evidence-only result.

The web app currently uses direct provider calls, a synchronous request and a lightweight browser UI. The MCP tool server and ADK A2A service entry points under services/ are initial, unverified integration code. The required CrewAI Flow and A2A client, authenticated shared dashboard, PostgreSQL/pgvector, durable jobs, Langfuse traces and cloud release are pending. The Dockerfile packages only the local web application. The scientific evaluation and cloud acceptance runs for both modes remain open.
