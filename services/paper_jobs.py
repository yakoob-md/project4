"""Durable paper queue, fenced stage writes and owner-scoped reads."""
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from services.m1_contracts import SpecialistReview
from services.m1_storage import _connect, _json, freeze, save_report

ACTIVE = ("queued", "ingesting", "reviewing", "synthesizing")


class LeaseLost(RuntimeError):
    pass


class DispatchConflict(ValueError):
    pass


@dataclass(frozen=True)
class Job:
    owner: str
    id: UUID
    question: str
    cutoff: date
    text: str | None
    pdf: bytes | None
    bundle_id: UUID | None
    token: UUID


def enqueue(owner, question, cutoff, text, pdf, dispatch_key=None):
    digest = None
    if dispatch_key is not None:
        content = pdf if pdf is not None else text.encode()
        digest = hashlib.sha256(json.dumps([
            question, cutoff.isoformat(), pdf is not None, hashlib.sha256(content).hexdigest(),
        ]).encode()).hexdigest()
    with _connect() as db:
        row = db.execute(
            """INSERT INTO paperlens_m1.paper_jobs
                   (owner_id, id, question, cutoff, status, paper_text, pdf, dispatch_key, input_digest)
               VALUES (%s, %s, %s, %s, 'queued', %s, %s, %s, %s)
               ON CONFLICT (owner_id, dispatch_key) DO NOTHING
               RETURNING id, input_digest""",
            (owner, uuid4(), question, cutoff, text, pdf, dispatch_key, digest),
        ).fetchone()
        if row is None:
            row = db.execute(
                """SELECT id, input_digest FROM paperlens_m1.paper_jobs
                   WHERE owner_id=%s AND dispatch_key=%s""", (owner, dispatch_key),
            ).fetchone()
            if row[1] != digest:
                raise DispatchConflict("This idempotency key already identifies a different submission.")
    return read_job(owner, row[0])


def claim():
    with _connect() as db:
        db.execute(
            """UPDATE paperlens_m1.paper_jobs SET status='failed', stage='failed', activity=NULL,
                   error=CASE WHEN deadline <= clock_timestamp() THEN 'Review deadline exceeded.'
                              ELSE 'Review attempts exhausted.' END,
                   lease_token=NULL, lease_until=NULL, paper_text=NULL, pdf=NULL
               WHERE status = ANY(%s) AND
                   (deadline <= clock_timestamp() OR
                    (attempts >= 3 AND (lease_until IS NULL OR lease_until <= clock_timestamp())))""",
            (list(ACTIVE),),
        )
        row = db.execute(
            """WITH next_job AS (
                   SELECT owner_id, id FROM paperlens_m1.paper_jobs
                   WHERE status = ANY(%s) AND deadline > clock_timestamp() AND attempts < 3
                       AND (lease_until IS NULL OR lease_until <= clock_timestamp())
                   ORDER BY created_at, id LIMIT 1 FOR UPDATE SKIP LOCKED
               )
               UPDATE paperlens_m1.paper_jobs j SET status='ingesting', stage='extract',
                   stage_started_at=now(), activity=NULL, error=NULL, attempts=attempts+1,
                   lease_token=%s, lease_until=clock_timestamp() + interval '30 seconds'
               FROM next_job n WHERE j.owner_id=n.owner_id AND j.id=n.id
               RETURNING j.owner_id, j.id, j.question, j.cutoff, j.paper_text, j.pdf, j.bundle_id, j.lease_token""",
            (list(ACTIVE), uuid4()),
        ).fetchone()
    return Job(*row) if row else None


def _lock(db, job):
    row = db.execute(
        """SELECT bundle_id, attempts FROM paperlens_m1.paper_jobs
           WHERE owner_id=%s AND id=%s AND lease_token=%s
               AND lease_until > clock_timestamp() AND deadline > clock_timestamp()
               AND status = ANY(%s) FOR UPDATE""",
        (job.owner, job.id, job.token, list(ACTIVE)),
    ).fetchone()
    if row is None:
        raise LeaseLost()
    return row


def renew(job):
    with _connect() as db:
        _lock(db, job)
        db.execute(
            """UPDATE paperlens_m1.paper_jobs SET lease_until=clock_timestamp() + interval '30 seconds'
               WHERE owner_id=%s AND id=%s""", (job.owner, job.id),
        )


def progress(job, status, *, stage=None, activity=None):
    with _connect() as db:
        _lock(db, job)
        db.execute(
            """UPDATE paperlens_m1.paper_jobs SET status=%s, activity=%s,
                   stage_started_at=CASE WHEN %s::text IS NOT NULL AND stage IS DISTINCT FROM %s
                                         THEN now() ELSE stage_started_at END,
                   stage=COALESCE(%s, stage)
               WHERE owner_id=%s AND id=%s""",
            (status, activity, stage, stage, stage, job.owner, job.id),
        )


def save_evidence(job, run, revision, bundle, embeddings):
    with _connect() as db:
        previous, _ = _lock(db, job)
        if previous is not None or run.id != job.id or run.owner_id != job.owner:
            raise ValueError("Invalid evidence checkpoint")
        freeze(run, revision, bundle, embeddings, db=db)
        _lock(db, job)
        db.execute(
            """UPDATE paperlens_m1.paper_jobs SET bundle_id=%s, paper_text=NULL, pdf=NULL
               WHERE owner_id=%s AND id=%s""", (bundle.id, job.owner, job.id),
        )


def load_specialist(job, bundle_id, role):
    with _connect() as db:
        row = db.execute(
            """SELECT payload FROM paperlens_m1.specialist_reviews
               WHERE owner_id=%s AND bundle_id=%s AND role=%s""", (job.owner, bundle_id, role),
        ).fetchone()
    return SpecialistReview.model_validate(row[0]) if row else None


def save_specialist(job, review):
    with _connect() as db:
        bundle_id, _ = _lock(db, job)
        if bundle_id != review.bundle_id:
            raise ValueError("Specialist checkpoint belongs to another bundle")
        db.execute(
            "INSERT INTO paperlens_m1.specialist_reviews VALUES (%s, %s, %s, %s)",
            (job.owner, review.bundle_id, review.role, _json(review)),
        )


def load_checkpoint(job, step, schema):
    with _connect() as db:
        row = db.execute(
            "SELECT payload FROM paperlens_m1.paper_checkpoints WHERE owner_id=%s AND run_id=%s AND step=%s",
            (job.owner, job.id, step),
        ).fetchone()
    return schema.model_validate(row[0]) if row else None


def checkpoint(job, step, record):
    with _connect() as db:
        _lock(db, job)
        db.execute(
            "INSERT INTO paperlens_m1.paper_checkpoints (owner_id, run_id, step, payload) VALUES (%s, %s, %s, %s)",
            (job.owner, job.id, step, _json(record)),
        )


def publish(job, report):
    with _connect() as db:
        bundle_id, _ = _lock(db, job)
        if report.run_id != job.id or report.bundle_id != bundle_id:
            raise ValueError("Report belongs to another review")
        saved = db.execute(
            """SELECT payload FROM paperlens_m1.paper_checkpoints
               WHERE owner_id=%s AND run_id=%s AND step='synthesis'""",
            (job.owner, job.id),
        ).fetchone()
        if saved is None or saved[0] != report.model_dump(mode="json"):
            raise ValueError("Publication requires the saved synthesis")
        save_report(job.owner, report, db=db)
        _lock(db, job)
        db.execute(
            """UPDATE paperlens_m1.paper_jobs SET status='completed', report_version=%s,
                   stage='complete', stage_started_at=now(), activity=NULL, lease_token=NULL, lease_until=NULL
               WHERE owner_id=%s AND id=%s""", (report.version, job.owner, job.id),
        )


def fail_attempt(job, message, *, retryable):
    with _connect() as db:
        _, attempts = _lock(db, job)
        retry = retryable and attempts < 3
        db.execute(
            """UPDATE paperlens_m1.paper_jobs SET status=%s, stage=%s, error=%s, activity=NULL,
                   stage_started_at=now(), lease_token=NULL,
                   lease_until=CASE WHEN %s THEN clock_timestamp() + interval '5 seconds' END,
                   paper_text=CASE WHEN %s THEN paper_text END, pdf=CASE WHEN %s THEN pdf END
               WHERE owner_id=%s AND id=%s""",
            ("queued" if retry else "failed", "queue" if retry else "failed", None if retry else message,
             retry, retry, retry, job.owner, job.id),
        )


def cancel(owner, run_id):
    with _connect() as db:
        return db.execute(
            """UPDATE paperlens_m1.paper_jobs SET status='cancelled', stage='cancelled',
                   stage_started_at=now(), activity=NULL, error=NULL, lease_token=NULL, lease_until=NULL,
                   paper_text=NULL, pdf=NULL
               WHERE owner_id=%s AND id=%s AND status = ANY(%s) RETURNING id""",
            (owner, run_id, [*ACTIVE, "cancelled"]),
        ).fetchone() is not None


def read_job(owner, run_id):
    try:
        run_id = UUID(str(run_id))
    except ValueError:
        return None
    with _connect() as db:
        row = db.execute(
            """SELECT id, question, status, bundle_id, report_version, error, stage, stage_started_at, activity, created_at,
                      status='failed' AND bundle_id IS NOT NULL AND attempts < 3 AND deadline > clock_timestamp()
               FROM paperlens_m1.paper_jobs WHERE owner_id=%s AND id=%s""", (owner, run_id),
        ).fetchone()
    if row:
        fields = ("id", "question", "status", "bundle_id", "report_version", "error", "stage",
                  "stage_started_at", "activity", "created_at", "can_retry")
        return dict(zip(fields, row)) | {"mode": "paper"}
    return None


def list_jobs(owner):
    with _connect() as db:
        rows = db.execute(
            """SELECT id, question, status FROM paperlens_m1.paper_jobs WHERE owner_id = %s
               ORDER BY created_at DESC, id DESC LIMIT 100""", (owner,),
        ).fetchall()
    return [{"id": row[0], "question": row[1], "status": row[2], "mode": "paper"} for row in rows]

def retry_review(owner, run_id):
    with _connect() as db:
        return db.execute(
            """UPDATE paperlens_m1.paper_jobs SET status='queued', stage='queue',
                   stage_started_at=now(), error=NULL
               WHERE owner_id=%s AND id=%s AND status='failed' AND bundle_id IS NOT NULL
                   AND attempts < 3 AND deadline > clock_timestamp() RETURNING id""",
            (owner, run_id),
        ).fetchone() is not None
