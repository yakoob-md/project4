import unittest
from pydantic import ValidationError
from packages.paperlens_core.models import EvidenceRef, Finding, validate_evidence
from packages.paperlens_core.scoring import recommendation, rubric_index
from services.mcp_tools.audit import check_percentages, hygiene_checks, reproducibility_checklist
from packages.paperlens_core.quota import QuotaGovernor,QuotaWait
from packages.paperlens_core.state import advance


class ContractsAndAuditTests(unittest.TestCase):
    def test_strict_evidence_and_span(self):
        text = "A sufficiently long exact quotation from a frozen chunk."
        ref = EvidenceRef(source_id="S1",chunk_id="C1",quote=text[2:42],char_start=2,char_end=42)
        validate_evidence(ref,"S1",text)
        with self.assertRaises(ValueError): validate_evidence(ref,"S2",text)

    def test_supported_finding_requires_evidence(self):
        with self.assertRaises(ValidationError):
            Finding(finding_id="F1",owner="method",dimension="methodology",claim="Missing controls",status="supported",severity="major",confidence=.8,suggested_action="Add controls")

    def test_scoring(self):
        self.assertEqual(rubric_index(dict(novelty=1,methodology=1,evidence=1,reproducibility=1)),20)
        self.assertEqual(rubric_index(dict(novelty=5,methodology=5,evidence=5,reproducibility=5)),100)
        self.assertIsNone(rubric_index(dict(novelty=5,methodology=None,evidence=5,reproducibility=5)))
        self.assertEqual(recommendation(dict(novelty=3,methodology=3,evidence=3,reproducibility=3)),"ready_for_further_expert_review")

    def test_audits(self):
        self.assertEqual(check_percentages([40,50]).status,"fail")
        self.assertEqual(check_percentages([40,60]).status,"pass")
        checklist = {item.check_id:item.status for item in reproducibility_checklist("Code is available at https://github.com/x/y. Random seed 4.")}
        self.assertEqual(checklist["code_link"],"pass")
        self.assertEqual(checklist["ablation"],"inconclusive")
        self.assertTrue(any(item.check_id=="test_set_tuning" for item in hygiene_checks("We tuned on the test set.")))

    def test_quota_and_state_guards(self):
        governor=QuotaGovernor(max_calls=1,max_tokens=100); reservation=governor.reserve(20,30); governor.release(reservation,25)
        with self.assertRaises(QuotaWait): governor.reserve(20,30)
        self.assertEqual(advance("queued","parsing"),"parsing")
        with self.assertRaises(ValueError): advance("queued","reviewing")


if __name__ == "__main__": unittest.main()
