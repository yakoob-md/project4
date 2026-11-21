import json
import os
from contextlib import contextmanager
from sqlite3 import connect as sqlite_connect


def uses_postgres() -> bool:
    return bool(os.getenv("DATABASE_URL"))


@contextmanager
def connection():
    if uses_postgres():
        import psycopg
        database = psycopg.connect(os.environ["DATABASE_URL"])
    else:
        database = sqlite_connect(os.getenv("PAPERLENS_DB", "paperlens.sqlite"))
    try:
        initialize(database)
        yield database
    finally:
        database.close()


def initialize(database):
    if uses_postgres():
        database.execute("CREATE EXTENSION IF NOT EXISTS vector")
        database.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        database.execute("CREATE TABLE IF NOT EXISTS audit_events(id BIGSERIAL PRIMARY KEY, run_id TEXT, event_type TEXT NOT NULL, payload JSONB NOT NULL DEFAULT '{}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        database.execute("CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        database.execute("CREATE TABLE IF NOT EXISTS api_tokens(id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), token_hash TEXT UNIQUE NOT NULL, label TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        database.execute("CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), name TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        database.execute("CREATE TABLE IF NOT EXISTS library_papers(id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id), project_id TEXT REFERENCES projects(id), title TEXT NOT NULL, content TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        for table in ("submissions","review_runs","run_checkpoints","documents","document_chunks","run_sources","evidence_bundles","evidence_packs","claims","findings","finding_versions","challenges","responses","reports","drafts","run_diffs","provider_cache","a2a_tasks","model_calls","quota_usage","llm_cache","dispatch_outbox"):
            database.execute(f"CREATE TABLE IF NOT EXISTS {table}(id TEXT PRIMARY KEY, owner_id TEXT, run_id TEXT, payload JSONB NOT NULL DEFAULT '{{}}'::jsonb, created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        database.execute("CREATE INDEX IF NOT EXISTS document_chunks_owner_run ON document_chunks(owner_id,run_id)")
        database.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS text_content TEXT")
        database.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS search_vector TSVECTOR")
        database.execute("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding VECTOR(384)")
        database.execute("CREATE INDEX IF NOT EXISTS audit_events_run ON audit_events(run_id,created_at)")
    else:
        database.execute("CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
    database.commit()


def save_run(run_id: str, payload: dict):
    encoded = json.dumps(payload)
    with connection() as database:
        if uses_postgres():
            database.execute("INSERT INTO runs(id,payload) VALUES (%s,%s::jsonb)", (run_id, encoded))
            database.execute("INSERT INTO audit_events(run_id,event_type,payload) VALUES (%s,'run_saved',%s::jsonb)", (run_id, json.dumps({"status": payload["status"]})))
        else:
            database.execute("INSERT INTO runs VALUES (?,?)", (run_id, encoded))
        database.commit()


def load_run(run_id: str):
    with connection() as database:
        marker = "%s" if uses_postgres() else "?"
        row = database.execute(f"SELECT payload FROM runs WHERE id={marker}", (run_id,)).fetchone()
    if row is None:
        return None
    return row[0] if isinstance(row[0], dict) else json.loads(row[0])


def list_runs():
    with connection() as database:
        if uses_postgres():
            rows = database.execute("SELECT id,payload->>'mode',payload->>'question' FROM runs ORDER BY created_at DESC LIMIT 100").fetchall()
        else:
            rows = database.execute("SELECT id,json_extract(payload,'$.mode'),json_extract(payload,'$.question') FROM runs ORDER BY rowid DESC LIMIT 100").fetchall()
    return [dict(id=run_id, mode=mode, question=question) for run_id, mode, question in rows]

def update_run_status(run_id:str,status:str):
    payload=load_run(run_id)
    if payload is None:return False
    payload["status"]=status
    encoded=json.dumps(payload)
    with connection() as database:
        if uses_postgres(): database.execute("UPDATE runs SET payload=%s::jsonb WHERE id=%s",(encoded,run_id))
        else: database.execute("UPDATE runs SET payload=? WHERE id=?",(encoded,run_id))
        database.commit()
    return True

def assign_run_owner(run_id: str, owner_id: str) -> bool:
    payload = load_run(run_id)
    if payload is None:
        return False
    payload["owner_id"] = owner_id
    encoded = json.dumps(payload)
    with connection() as database:
        if uses_postgres():
            database.execute("UPDATE runs SET payload=%s::jsonb WHERE id=%s", (encoded, run_id))
        else:
            database.execute("UPDATE runs SET payload=? WHERE id=?", (encoded, run_id))
        database.commit()
    return True

def load_owned_run(run_id: str, owner_id: str):
    payload = load_run(run_id)
    if payload is None or payload.get("owner_id") != owner_id:
        return None
    return payload

def list_owned_runs(owner_id: str):
    return [item for item in list_runs() if (load_run(item["id"]) or {}).get("owner_id") == owner_id]
