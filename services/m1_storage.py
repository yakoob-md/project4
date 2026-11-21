"""Owner-scoped PostgreSQL persistence for the M1 worker and downstream consumers."""
import math
import os
from contextlib import nullcontext
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from services.m1_contracts import FrozenBundle, InputRevision, PaperReport, Report, Run, SourcePassage


def _connect():
    import psycopg

    return psycopg.connect(os.environ["DATABASE_URL"])


def migrate():
    with _connect() as db:
        db.execute("SELECT pg_advisory_xact_lock(70241001)")
        db.execute("CREATE SCHEMA IF NOT EXISTS paperlens_m1")
        db.execute("CREATE TABLE IF NOT EXISTS paperlens_m1.migrations (version integer PRIMARY KEY)")
        for script in sorted(Path(__file__).with_name("migrations").glob("*.sql")):
            version = int(script.name.split("_", 1)[0])
            if not db.execute("SELECT 1 FROM paperlens_m1.migrations WHERE version = %s", (version,)).fetchone():
                db.execute(script.read_text(encoding="utf-8-sig"))
                db.execute("INSERT INTO paperlens_m1.migrations VALUES (%s)", (version,))


def _json(record):
    from psycopg.types.json import Jsonb

    return Jsonb(record.model_dump(mode="json"))


def _vector(values: Sequence[float]) -> str:
    if len(values) != 384 or not all(map(math.isfinite, values)) or not any(values):
        raise ValueError("Expected a finite, nonzero 384-dimensional embedding")
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def freeze(run: Run, revision: InputRevision, bundle: FrozenBundle, embeddings=None, *, db=None):
    if revision.run_id != run.id or bundle.run_id != run.id or bundle.revision_id != revision.id:
        raise ValueError("Bundle does not match the run and revision")
    with (_connect() if db is None else nullcontext(db)) as db:
        db.execute(
            "INSERT INTO paperlens_m1.runs VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (run.owner_id, run.id, _json(run)),
        )
        db.execute(
            "INSERT INTO paperlens_m1.input_revisions VALUES (%s, %s, %s, %s)",
            (run.owner_id, run.id, revision.id, _json(revision)),
        )
        db.execute(
            "INSERT INTO paperlens_m1.bundles VALUES (%s, %s, %s, %s, %s)",
            (run.owner_id, run.id, revision.id, bundle.id, _json(bundle)),
        )
        with db.cursor() as cursor:
            cursor.executemany(
                """INSERT INTO paperlens_m1.passages (owner_id, bundle_id, id, payload, embedding)
                   VALUES (%s, %s, %s, %s, %s::vector)""",
                [
                    (run.owner_id, bundle.id, p.id, _json(p), _vector(embeddings[p.id]) if embeddings else None)
                    for p in bundle.passages
                ],
            )


def load_bundle(owner_id: str, bundle_id: UUID) -> FrozenBundle | None:
    with _connect() as db:
        row = db.execute(
            "SELECT payload FROM paperlens_m1.bundles WHERE owner_id = %s AND id = %s",
            (owner_id, bundle_id),
        ).fetchone()
    return FrozenBundle.model_validate(row[0]) if row else None


def save_report(owner_id: str, report: Report, *, db=None):
    bundle = load_bundle(owner_id, report.bundle_id)
    if bundle is None:
        raise ValueError("Bundle is unavailable")
    passages = {p.id: p for p in bundle.passages}
    for finding in report.findings:
        if finding.bundle_id != bundle.id:
            raise ValueError("Finding belongs to a different bundle")
        for citation in finding.citations:
            passage = passages.get(citation.passage_id)
            if passage is None:
                raise ValueError("Citation is outside the frozen bundle")
            citation.verify(passage)
    with (_connect() if db is None else nullcontext(db)) as db:
        for finding in report.findings:
            row = db.execute(
                """INSERT INTO paperlens_m1.findings VALUES (%s, %s, %s, %s)
                   ON CONFLICT DO NOTHING RETURNING id""",
                (owner_id, bundle.id, finding.id, _json(finding)),
            ).fetchone()
            if row is None:
                existing = db.execute(
                    """SELECT payload FROM paperlens_m1.findings
                       WHERE owner_id = %s AND bundle_id = %s AND id = %s""",
                    (owner_id, bundle.id, finding.id),
                ).fetchone()
                if existing[0] != finding.model_dump(mode="json"):
                    raise ValueError("Finding ID already refers to a different finding")
        db.execute(
            "INSERT INTO paperlens_m1.reports VALUES (%s, %s, %s, %s, %s)",
            (owner_id, bundle.id, report.id, report.version, _json(report)),
        )


def load_report(owner_id: str, bundle_id: UUID, version: int) -> Report | None:
    with _connect() as db:
        row = db.execute(
            "SELECT payload FROM paperlens_m1.reports WHERE owner_id = %s AND bundle_id = %s AND version = %s",
            (owner_id, bundle_id, version),
        ).fetchone()
    if row is None:
        return None
    schema = PaperReport if row[0].get("kind") == "paper" else Report
    return schema.model_validate(row[0])


def search_passages(owner_id: str, bundle_id: UUID, query: str, embedding=None, *, limit=10):
    """Fuse up to 50 keyword and 50 cosine candidates and return at most 20 passages."""
    if not query.strip() or len(query) > 500 or not 1 <= limit <= 20:
        raise ValueError("Expected a query of 1 to 500 characters and a limit of 1 to 20")
    query_vector = None if embedding is None else _vector(embedding)
    with _connect() as db:
        rows = db.execute(
            """
            WITH keyword AS (
                SELECT id, ts_rank_cd(search_vector, websearch_to_tsquery('english', %(query)s)) AS rank
                FROM paperlens_m1.passages
                WHERE owner_id = %(owner)s AND bundle_id = %(bundle)s
                    AND search_vector @@ websearch_to_tsquery('english', %(query)s)
                ORDER BY rank DESC, id LIMIT 50
            ), semantic AS (
                SELECT id, embedding <=> %(vector)s::vector AS distance
                FROM paperlens_m1.passages
                WHERE owner_id = %(owner)s AND bundle_id = %(bundle)s
                    AND embedding IS NOT NULL AND %(vector)s::vector IS NOT NULL
                ORDER BY distance, id LIMIT 50
            ), ranks AS (
                SELECT id, row_number() OVER (ORDER BY rank DESC, id) AS position FROM keyword
                UNION ALL
                SELECT id, row_number() OVER (ORDER BY distance, id) AS position FROM semantic
            ), selected AS (
                SELECT id, sum(1.0 / (60 + position)) AS score FROM ranks GROUP BY id
                ORDER BY score DESC, id LIMIT %(limit)s
            )
            SELECT p.payload FROM selected
            JOIN paperlens_m1.passages p ON p.id = selected.id
                AND p.owner_id = %(owner)s AND p.bundle_id = %(bundle)s
            ORDER BY selected.score DESC, selected.id
            """,
            dict(query=query, owner=owner_id, bundle=bundle_id, vector=query_vector, limit=limit),
        ).fetchall()
    return [SourcePassage.model_validate(row[0]) for row in rows]


if __name__ == "__main__":
    migrate()

