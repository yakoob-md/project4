"""M1 fixture checks against PostgreSQL, using the real MCP parser for PDF inputs."""
import unittest
from datetime import UTC, date, datetime
from unittest.mock import patch
from uuid import uuid4

from services.m0_contracts import EvidenceBundle, Passage
from services.m1_contracts import Citation, Finding, Report
from services.m1_storage import load_bundle, load_report, save_report, search_passages
from services.review_worker.ingestion import ingest


OWNER = "m1-fixture"
CUTOFF = date(2020, 5, 21)
VECTOR = [1.0] + [0.0] * 383


def evidence(request, outcome="ok"):
    records = [
        Passage(
            id=f"L{i}", locator="Abstract", title=f"Retrieval study {i}",
            text="Synthetic literature record", url=f"https://arxiv.org/abs/1706.03762v{i}",
        )
        for i in (1, 2)
    ] if outcome == "ok" else []
    return EvidenceBundle(
        **request.model_dump(), bundle_id=uuid4(), provider="arXiv",
        tool="search_literature", mcp_protocol="fixture", retrieved_at=datetime.now(UTC),
        outcome=outcome, passages=records,
    ), {}


class IngestionTests(unittest.IsolatedAsyncioTestCase):
    async def test_corrupt_pdf_rejected_by_mcp(self):
        with patch("services.review_worker.ingestion.delegate") as delegate:
            with self.assertRaises(ExceptionGroup) as error:
                await ingest(OWNER, uuid4(), "retrieval", CUTOFF, pdf=b"%PDF-1.4\nbroken")
            self.assertTrue(error.exception.subgroup(
                lambda exc: isinstance(exc, RuntimeError) and str(exc) == "MCP PDF tool failed"
            ))
        delegate.assert_not_awaited()

    async def test_empty_text_rejected_before_retrieval(self):
        with patch("services.review_worker.ingestion.delegate") as delegate:
            with self.assertRaisesRegex(ValueError, "readable text"):
                await ingest(OWNER, uuid4(), "retrieval", CUTOFF, text=" \n\t")
        delegate.assert_not_awaited()

    async def test_duplicate_source_and_hybrid_query(self):
        with patch("services.review_worker.ingestion.delegate", side_effect=evidence):
            bundle = await ingest(
                OWNER, uuid4(), "retrieval", CUTOFF, text="  Evidence text.\n\nSecond paragraph.",
                embed=lambda texts: [VECTOR] * len(texts),
            )
        first, second, abstract = bundle.passages
        self.assertEqual((first.locator, first.char_start, first.char_end), ("Paragraph 1", 2, 16))
        self.assertEqual(second.locator, "Paragraph 2")
        self.assertEqual(abstract.source_key, "arxiv:1706.03762")
        self.assertEqual(load_bundle(OWNER, bundle.id), bundle)
        self.assertIsNone(load_bundle("other-owner", bundle.id))
        self.assertEqual(search_passages(OWNER, bundle.id, "evidence"), [first])
        self.assertEqual(len(search_passages(OWNER, bundle.id, "unmatched", VECTOR, limit=2)), 2)
        self.assertEqual(search_passages(OWNER, bundle.id, "evidence", VECTOR, limit=1), [first])
        self.assertEqual(search_passages("other-owner", bundle.id, "evidence", VECTOR), [])

    async def test_provider_outage_freezes_submitted_evidence(self):
        def unavailable(request):
            return evidence(request, "provider_unavailable")
        with patch("services.review_worker.ingestion.delegate", side_effect=unavailable):
            bundle = await ingest(OWNER, uuid4(), "retrieval", CUTOFF, text="Submitted evidence.")
        self.assertEqual(bundle.coverage, "provider_unavailable")
        self.assertEqual(load_bundle(OWNER, bundle.id).passages[0].access_level, "submitted")

    async def test_report_rejects_forged_quote_locator_and_offsets(self):
        with patch("services.review_worker.ingestion.delegate", side_effect=evidence):
            bundle = await ingest(OWNER, uuid4(), "retrieval", CUTOFF, text="  Exact quotation.")
        p = bundle.passages[0]
        citation = Citation(
            passage_id=p.id, locator=p.locator, quote=p.text,
            char_start=p.char_start, char_end=p.char_end,
        )
        finding = Finding(id=uuid4(), bundle_id=bundle.id, assessment="Fixture", citations=(citation,))
        report = Report(id=uuid4(), bundle_id=bundle.id, version=1, findings=(finding,), summary="Fixture")
        for change in ({"quote": "Forged quotation."}, {"locator": "Paragraph 2"}, {"char_start": 0}):
            forged = finding.model_copy(update={"citations": (citation.model_copy(update=change),)})
            with self.assertRaisesRegex(ValueError, "exact frozen source span"):
                save_report(OWNER, report.model_copy(update={"findings": (forged,)}))
            self.assertIsNone(load_report(OWNER, bundle.id, 1))
        save_report(OWNER, report)
        self.assertEqual(load_report(OWNER, bundle.id, 1), report)
        self.assertIsNone(load_report("other-owner", bundle.id, 1))

