# PaperLens

The Docker dashboard accepts research PDFs and pasted paper text. CrewAI orchestrates three independent reviews of frozen evidence in PostgreSQL. Google ADK retrieves arXiv records through A2A and MCP. The dashboard shows run status, findings, cited passages, and versioned JSON and Markdown downloads.

Current verified behavior is recorded in [the implementation status](docs/implementation_status.md).

## Run with Docker

Start Docker Desktop, then run:

    .\scripts\bootstrap.ps1
    docker compose up -d --build web

Open http://127.0.0.1:8000 and choose **Review a paper**. Upload a PDF or paste the paper text, enter a search phrase and literature cutoff, and select **Run analysis**. Open a cited passage or download either report format when the run completes. `bootstrap.ps1` creates `.env` and prompts for the Groq API key. Stop the stack with:

    .\scripts\start.ps1 -Stop

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

The Python-only setup runs the legacy SQLite prototype. Docker runs the PostgreSQL paper path and its worker. The scientific evaluation, Langfuse acceptance, and authenticated two-mode cloud release remain open.
