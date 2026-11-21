import hashlib, hmac, os, secrets, time
from uuid import uuid4
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from .storage import connection

hasher = PasswordHasher()

class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=200)
    invite_code: str = ""

def _signature(value: str) -> str:
    return hmac.new(os.environ.get("JWT_SECRET", "local-development-only").encode(), value.encode(), hashlib.sha256).hexdigest()

def session_value(owner_id: str) -> str:
    payload = f"{owner_id}.{int(time.time())}"
    return f"{payload}.{_signature(payload)}"

def owner_from_session(value: str) -> str | None:
    try:
        owner, issued, signature = value.split(".")
        payload = f"{owner}.{issued}"
        if not hmac.compare_digest(signature, _signature(payload)) or time.time()-int(issued) > 86400*7: return None
        return owner
    except (ValueError, TypeError): return None

def current_owner(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer pl_"):
        token_hash = hashlib.sha256(authorization[7:].encode()).hexdigest()
        with connection() as database: row=database.execute("SELECT owner_id FROM api_tokens WHERE token_hash=%s",(token_hash,)).fetchone()
        if not row: raise HTTPException(401,"Invalid API token")
        return row[0]
    if os.getenv("AUTH_MODE") == "dev" and os.getenv("PAPERLENS_ENV", "local") == "local":
        owner = request.cookies.get("paperlens_session") and owner_from_session(request.cookies["paperlens_session"]) or "dev-user"
        if owner == "dev-user" and os.getenv("DATABASE_URL"):
            with connection() as database:
                database.execute("INSERT INTO users(id,email,password_hash) VALUES ('dev-user','dev@paperlens.local','disabled') ON CONFLICT (id) DO NOTHING"); database.commit()
        return owner
    owner = owner_from_session(request.cookies.get("paperlens_session", ""))
    if not owner: raise HTTPException(401, "Authentication required")
    return owner

def set_session(response: Response, owner_id: str):
    response.set_cookie("paperlens_session", session_value(owner_id), httponly=True, samesite="strict", secure=os.getenv("COOKIE_SECURE", "false").lower()=="true", max_age=604800)

def register(credentials: Credentials) -> str:
    if os.getenv("INVITE_CODE") and not secrets.compare_digest(credentials.invite_code, os.environ["INVITE_CODE"]): raise HTTPException(403,"Invalid invite code")
    owner = uuid4().hex
    try:
        with connection() as database:
            database.execute("INSERT INTO users(id,email,password_hash) VALUES (%s,%s,%s)",(owner,credentials.email.lower(),hasher.hash(credentials.password))); database.commit()
    except Exception as exc: raise HTTPException(409,"Account already exists") from exc
    return owner

def authenticate(credentials: Credentials) -> str:
    with connection() as database: row=database.execute("SELECT id,password_hash FROM users WHERE email=%s",(credentials.email.lower(),)).fetchone()
    if not row:
        raise HTTPException(401,"Invalid credentials")
    try: hasher.verify(row[1],credentials.password)
    except Exception as exc: raise HTTPException(401,"Invalid credentials") from exc
    return row[0]
