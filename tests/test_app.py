import os
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi.testclient import TestClient
from paperlens.service import app
from paperlens.core import Passage, Finding, Review, validate_review


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
        with Path("material/Final_Project_Report_Template.pdf").open("rb") as pdf:
            result = self.client.post("/runs",data=dict(mode="paper",cutoff="2026-01-01"),files={"pdf":("test.pdf",pdf,"application/pdf")})
        self.assertEqual(result.status_code,201)
        self.assertEqual(result.json()["sources"][0]["locator"],"Page 1")
        self.assertIn("unavailable",result.json()["warnings"][0])
        bad = self.client.post("/runs",data=dict(mode="paper",cutoff="2026-01-01"))
        self.assertEqual(bad.status_code,422)

    def test_citation_gate(self):
        source = Passage(id="S1",text="Documented finding",locator="Page 1",title="Submission")
        review = Review(findings=[Finding(assessment="result",action="verify",source="S1",quote="fabricated")],unknowns=[])
        with self.assertRaises(ValueError):
            validate_review(review,[source])
