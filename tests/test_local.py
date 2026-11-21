import os
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from datetime import date
from fastapi import UploadFile
from paperlens.service import create, history, markdown, get_run
from paperlens.critique import Batch, Challenge, Replies, Response, critique


class LocalWorkflow(unittest.TestCase):
    def setUp(self):
        path = Path.cwd()/(uuid4().hex+".sqlite")
        self.addCleanup(path.unlink,missing_ok=True)
        env=patch.dict(os.environ,{"PAPERLENS_DB":str(path),"GROQ_API_KEY":""})
        env.start()
        self.addCleanup(env.stop)

    @patch("paperlens.service.search",return_value=[])
    def test_refine(self,search):
        a=create("idea","Grade short answers","agreement",date.today(),"",None)
        b=create("idea","Grade short answers","rubric variation",date.today(),a["id"],None)
        self.assertEqual(b["parent"],a["id"])
        self.assertEqual(get_run(a["id"]),a)
        self.assertEqual(len(history()),2)
        self.assertIn("rubric variation",markdown(b["id"]))

    @patch("paperlens.service.search",side_effect=TimeoutError)
    def test_pdf(self,search):
        with Path("material/Final_Project_Report_Template.pdf").open("rb") as f:
            r=create("paper","","test",date.today(),"",UploadFile(f))
        self.assertEqual(r["sources"][0]["locator"],"Page 1")
        self.assertIn("unavailable",r["warnings"][0])

    def test_retraction(self):
        def generate(schema,prompt,ctx):
            if schema is Batch:
                return Batch(items=[Challenge(owner="data",index=0,concern="unsupported")])
            return Replies(responses=[Response(decision="retract",reason="unsupported")])
        revised,log=critique({"data":{"findings":[{"assessment":"example"}],"unknowns":[]}},[],generate)
        self.assertEqual(revised["data"]["findings"],[])
        self.assertEqual(log[0]["response"]["decision"],"retract")
