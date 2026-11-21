import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from paperlens.service import app
from paperlens.core import Passage, Finding, Review, validate_review
from pdf_fixture import text_pdf


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        path = Path.cwd() / (uuid4().hex+".sqlite")
        self.addCleanup(path.unlink,missing_ok=True)
        env = patch.dict(os.environ,{"PAPERLENS_DB":str(path),"GROQ_API_KEY":""})
        env.start()
        self.addCleanup(env.stop)
        self.client = TestClient(app)

    @patch("paperlens.service.search", return_value=[])
    def test_idea_refinement_and_export(self,search):
        data = dict(mode="idea",text="Compare grading rubrics",cutoff="2026-01-01")
        first = self.client.post("/runs",data=data).json()
        self.assertEqual(first["status"],"Evidence only")
        second = self.client.post("/runs",data={**data,"parent":first["id"],"question":"Which rubric improves agreement?"}).json()
        self.assertEqual(second["parent"],first["id"])
        self.assertEqual(len(self.client.get("/runs").json()),2)
        self.assertIn("Compare grading",self.client.get("/runs/"+first["id"]+"/markdown").text)

    @patch("paperlens.service.search",side_effect=TimeoutError)
    def test_pdf_outage_and_invalid_input(self,search):
        result = self.client.post("/runs",data=dict(mode="paper",cutoff="2026-01-01"),files={"pdf":("test.pdf",text_pdf(),"application/pdf")})
        self.assertEqual(result.status_code,201)
        self.assertEqual(result.json()["sources"][0]["locator"],"Page 1")
        self.assertIn("unavailable",result.json()["warnings"][0])
        bad = self.client.post("/runs",data=dict(mode="paper",cutoff="2026-01-01"))
        self.assertEqual(bad.status_code,422)

    def test_citation_gate(self):
        source = Passage(id="S1",text="Documented finding with enough context for exact validation",locator="Page 1",title="Submission")
        review = Review(findings=[Finding(assessment="result",action="verify",source="S1",quote="fabricated")],unknowns=[])
        with self.assertRaises(ValueError):
            validate_review(review,[source])

    def test_exact_span_and_minimum_quote(self):
        text = "Documented finding with enough context for exact validation"
        source = Passage(id="S1",text=text,locator="Page 1",title="Submission")
        valid = Finding(assessment="result",action="verify",source="S1",quote=text[11:42],char_start=11,char_end=42)
        self.assertEqual(validate_review(Review(findings=[valid],unknowns=[]),[source]).findings[0].char_start,11)
        short = Finding(assessment="result",action="verify",source="S1",quote="finding",char_start=11,char_end=18)
        with self.assertRaises(ValueError):
            validate_review(Review(findings=[short],unknowns=[]),[source])
