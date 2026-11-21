"""Paper report publication contract fixtures."""
import unittest
from uuid import uuid4

from pydantic import ValidationError

from paperlens.paper_api import render_markdown
from services.m1_contracts import Citation, PaperFinding, PaperReport


class PaperReportTests(unittest.TestCase):
    def setUp(self):
        self.bundle = uuid4()
        self.citation = Citation(
            passage_id=uuid4(), locator="Page 1", quote="A supplied quotation.",
            char_start=20, char_end=41,
        )
        self.findings = [
            PaperFinding(
                id=uuid4(), bundle_id=self.bundle, role="Novelty & Gap", category="strength",
                assessment="A documented contribution.", citations=(self.citation,),
            ),
            PaperFinding(
                id=uuid4(), bundle_id=self.bundle, role="Methodology & Feasibility", category="limitation",
                assessment="Comparison conditions need clarification.", citations=(), status="uncertain",
                uncertainty="The excerpts do not show the protocol.", revision="Explain the comparison protocol.",
            ),
            PaperFinding(
                id=uuid4(), bundle_id=self.bundle, role="Dataset & Evidence", category="limitation",
                assessment="The test scope is unclear.", citations=(), status="uncertain",
                uncertainty="The excerpts do not establish dataset coverage.", revision="List the test datasets.",
            ),
        ]
        self.data = dict(
            id=uuid4(), run_id=uuid4(), bundle_id=self.bundle, version=1, coverage="no_results",
            summary="Fixture report", findings=self.findings,
            prioritized_revisions=(self.findings[2].id, self.findings[1].id),
        )

    def test_findings_require_evidence_or_explicit_uncertainty(self):
        supported = self.findings[0].model_dump()
        with self.assertRaisesRegex(ValidationError, "Supported findings require citations"):
            PaperFinding.model_validate(supported | {"citations": []})
        uncertain = self.findings[1].model_dump()
        with self.assertRaisesRegex(ValidationError, "Uncertain findings require a reason"):
            PaperFinding.model_validate(uncertain | {"uncertainty": ""})

    def test_report_requires_three_roles_and_valid_revision_references(self):
        with self.assertRaisesRegex(ValidationError, "Revision priorities"):
            PaperReport.model_validate(self.data | {"prioritized_revisions": (uuid4(),)})
        with self.assertRaisesRegex(ValidationError, "requires all three specialists"):
            PaperReport.model_validate(self.data | {"findings": [self.findings[0]] * 3})

    def test_markdown_uses_the_saved_version_and_revision_order(self):
        report = PaperReport.model_validate(self.data)
        text = render_markdown(PaperReport.model_validate_json(report.model_dump_json()))
        self.assertIn(f"/passages/{self.citation.passage_id}?version=1", text)
        self.assertIn(self.citation.quote, text)
        self.assertLess(text.index("1. List the test datasets."), text.index("2. Explain the comparison protocol."))

