"""Recovery fixtures with real PostgreSQL and CrewAI Flow scheduling."""
import asyncio
import json
import multiprocessing
import os
import unittest
from datetime import date
from unittest.mock import patch
from uuid import uuid4

from psycopg import connect, errors, sql
from psycopg.conninfo import make_conninfo
from pydantic import ValidationError

from services.m1_contracts import PaperFinding, PaperReport
from services.m1_storage import _connect, load_report, migrate
from services.paper_jobs import (
    DispatchConflict, LeaseLost, cancel, checkpoint, claim, enqueue, fail_attempt,
    load_checkpoint, publish, read_job, renew,
)
from services.review_worker.paper_critique import Challenges, Closure, ProposedChallenges, ProposedReplies, Replies
from services.review_worker.paper_review import DraftReview, Orchestrator, Priorities, run_claimed
from services.review_worker.test_ingestion import evidence


OWNER = "recovery-fixture"
TEXT = "The study reports measurements on two datasets.\n\nThe experiments use the same evaluation metric."
BEFORE = "The experiment establishes broad generalization."
AFTER = "The experiment reports measurements on two datasets."


def run_interrupted_worker(job, ready):
    fixture = RecoveryTests()
    fixture.calls = []
    with (
        patch("services.review_worker.ingestion.delegate", side_effect=evidence),
        patch("services.review_worker.paper_review.ask", fixture.fixture_ask(challenge=True, pause=ready)),
    ):
        asyncio.run(run_claimed(job))


class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        url = os.environ["DATABASE_URL"]
        name = "paperlens_recovery_" + uuid4().hex
        with connect(url, autocommit=True) as db:
            db.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

        def drop_database():
            with connect(url, autocommit=True) as db:
                db.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))

        cls.addClassCleanup(drop_database)
        cls.enterClassContext(patch.dict(os.environ, {
            "DATABASE_URL": make_conninfo(url, dbname=name),
            "GROQ_API_KEY": "fixture",
        }))
        migrate()

    def submit(self, key=None, text=TEXT):
        return enqueue(OWNER, "datasets", date(2020, 5, 21), text, None, key)["id"]

    def expire(self, job, field):
        statement = sql.SQL("UPDATE paperlens_m1.paper_jobs SET {}=clock_timestamp() WHERE id=%s")
        with _connect() as db:
            db.execute(statement.format(sql.Identifier(field)), (job.id,))

    def counts(self, job):
        with _connect() as db:
            return db.execute(
                """SELECT
                     (SELECT count(*) FROM paperlens_m1.bundles WHERE run_id=%s),
                     (SELECT count(*) FROM paperlens_m1.reports r JOIN paperlens_m1.bundles b
                      ON (b.owner_id, b.id)=(r.owner_id, r.bundle_id) WHERE b.run_id=%s),
                     (SELECT count(*) FROM paperlens_m1.paper_checkpoints WHERE run_id=%s)""",
                (job.id, job.id, job.id),
            ).fetchone()

    def fixture_ask(self, *, challenge, pause=None):
        async def ask(role, goal, prompt, schema, *, on_activity):
            self.calls.append(schema.__name__)
            on_activity(None)
            if schema == DraftReview:
                return schema(findings=[{
                    "category": "limitation", "assessment": BEFORE,
                    "evidence_id": 1, "revision": "Report per-dataset metrics.",
                }])
            if schema == ProposedChallenges:
                originals = json.loads(prompt.splitlines()[1])
                return schema(challenges=[{
                    "finding_number": originals[0]["finding_number"], "reason": "Coverage of two datasets is narrower.",
                }] if challenge else [])
            if schema == ProposedReplies:
                return schema(replies=[{
                    "action": "revise", "reason": "Narrowed scope.",
                    "assessment": AFTER, "evidence_id": 1, "revision": "Report per-dataset metrics.",
                }])
            if schema == Priorities:
                candidates = json.loads(prompt.splitlines()[1])
                return schema(order=[candidate["number"] for candidate in candidates])
            if pause is not None:
                pause.set()
                await asyncio.Future()
            return schema(decisions=[{"finding_number": 1, "disposition": "revised"}])

        return ask

    async def test_resume_after_reply_and_only_one_worker_publishes(self):
        run_id, duplicate = await asyncio.gather(*(
            asyncio.to_thread(self.submit, key="same-request") for _ in range(2)
        ))
        self.assertEqual(duplicate, run_id)
        with self.assertRaises(DispatchConflict):
            self.submit(key="same-request", text="Different fixture.")
        claims = await asyncio.gather(asyncio.to_thread(claim), asyncio.to_thread(claim))
        self.assertEqual(sum(job is not None for job in claims), 1)
        first = next(job for job in claims if job is not None)
        self.calls = []
        context = multiprocessing.get_context("spawn")
        ready = context.Event()
        worker = context.Process(target=run_interrupted_worker, args=(first, ready))
        worker.start()
        try:
            self.assertTrue(await asyncio.to_thread(ready.wait, 20))
        finally:
            if worker.is_alive():
                worker.kill()
            await asyncio.to_thread(worker.join, 10)
            worker.close()
        self.expire(first, "lease_until")
        replacement = claim()
        self.assertEqual(first.id, replacement.id)
        self.assertNotEqual(first.token, replacement.token)
        with self.assertRaises(LeaseLost):
            renew(first)
        challenges = load_checkpoint(replacement, "challenges", Challenges)
        with self.assertRaises(errors.UniqueViolation):
            checkpoint(replacement, "challenges", challenges)
        reply = load_checkpoint(replacement, "reply_novelty", Replies)
        with self.assertRaises(errors.UniqueViolation):
            checkpoint(replacement, "reply_novelty", reply)

        def check_publication(job, report):
            with self.assertRaises(LeaseLost):
                publish(first, report)
            publish(job, report)

        with (
            patch("services.review_worker.ingestion.delegate", side_effect=evidence) as delegate,
            patch("services.review_worker.paper_review.ask", self.fixture_ask(challenge=True)),
            patch("services.review_worker.paper_review.publish", side_effect=check_publication),
        ):
            await run_claimed(replacement)
            delegate.assert_not_awaited()
        self.assertEqual(self.calls, ["Decisions", "Priorities"])
        job = read_job(OWNER, run_id)
        report = load_report(OWNER, job["bundle_id"], job["report_version"])
        self.assertEqual(job["status"], "completed")
        entry, = report.critique
        self.assertEqual((entry.original.assessment, entry.final.assessment, entry.disposition), (BEFORE, AFTER, "revised"))
        self.assertEqual(entry.original.id, entry.final.id)
        self.assertIn(entry.final, report.findings)
        self.assertEqual(report, load_checkpoint(replacement, "synthesis", PaperReport))
        with self.assertRaises(LeaseLost):
            publish(first, report)
        with self.assertRaises(LeaseLost):
            publish(replacement, report)
        self.assertEqual(self.counts(first), (1, 1, 4))

    async def test_zero_challenges_completes(self):
        self.submit()
        job = claim()
        self.calls = []
        with (
            patch("services.review_worker.ingestion.delegate", side_effect=evidence),
            patch("services.review_worker.paper_review.ask", self.fixture_ask(challenge=False)),
        ):
            await run_claimed(job)
        saved = read_job(OWNER, job.id)
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(load_checkpoint(job, "closure", Closure).entries, ())
        self.assertEqual(load_report(OWNER, saved["bundle_id"], 1).critique, ())
        self.assertEqual(self.calls, ["DraftReview"] * 3 + ["ProposedChallenges", "Priorities"])
        self.assertEqual(self.counts(job), (1, 1, 3))

    async def test_late_a2a_response_after_cancel_cannot_freeze_or_publish(self):
        self.submit()
        job = claim()
        sent = asyncio.Event()
        returned = asyncio.Event()

        async def delegate(request):
            sent.set()
            await returned.wait()
            return evidence(request)

        with patch("services.review_worker.ingestion.delegate", side_effect=delegate):
            # Deliver the late response to the flow itself to exercise the database
            # fence independently of the supervisor's coroutine cancellation.
            flow = asyncio.create_task(Orchestrator(job).kickoff_async())
            await asyncio.wait_for(sent.wait(), 10)
            self.assertFalse(cancel("other-owner", job.id))
            self.assertTrue(cancel(OWNER, job.id))
            self.assertTrue(cancel(OWNER, job.id))
            returned.set()
            with self.assertRaises(LeaseLost):
                await asyncio.wait_for(flow, 10)
        saved = read_job(OWNER, job.id)
        self.assertEqual(saved["status"], "cancelled")
        self.assertIsNone(saved["report_version"])
        self.assertEqual(self.counts(job), (0, 0, 0))

    def test_deadline_and_retry_budget(self):
        self.submit()
        job = claim()
        self.expire(job, "deadline")
        with self.assertRaises(LeaseLost):
            renew(job)
        self.assertIsNone(claim())
        self.assertEqual(read_job(OWNER, job.id)["error"], "Review deadline exceeded.")
        run_id = self.submit()
        for _ in range(3):
            job = claim()
            self.assertEqual(job.id, run_id)
            fail_attempt(job, "Fixture failure.", retryable=True)
            self.expire(job, "lease_until")
        self.assertIsNone(claim())
        self.assertEqual(read_job(OWNER, run_id)["status"], "failed")

    def test_challenge_budget_rejects_seventh_and_third_per_role(self):
        bundle_id = uuid4()
        originals = {
            item.id: item
            for item in (
                PaperFinding(
                    id=uuid4(), bundle_id=bundle_id, role="Novelty & Gap", category="strength",
                    assessment="Fixture", status="uncertain", uncertainty="Fixture", citations=(),
                )
                for _ in range(7)
            )
        }
        targets = [{"finding_id": id, "reason": "Check evidence."} for id in originals]
        with self.assertRaises(ValidationError):
            Challenges(challenges=targets)
        with self.assertRaisesRegex(ValueError, "Too many challenges"):
            Challenges(challenges=targets[:3]).verify_targets(originals)
        Challenges(challenges=targets[:2]).verify_targets(originals)
