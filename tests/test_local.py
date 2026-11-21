import os
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from datetime import date
from fastapi import UploadFile
from paperlens.service import create, history, markdown, get_run
from paperlens.critique import Batch, Challenge, Replies, Response, critique
from paperlens.critique import Closure
from pdf_fixture import text_pdf


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
        from io import BytesIO
        r=create("paper","","test",date.today(),"",UploadFile(BytesIO(text_pdf())))
        self.assertEqual(r["sources"][0]["locator"],"Page 1")
        self.assertIn("unavailable",r["warnings"][0])

    def test_retraction(self):
        def generate(schema,prompt,ctx):
            if schema is Batch:
                return Batch(items=[Challenge(owner="data",index=0,concern="unsupported")])
            if schema is Closure:
                return Closure(dispositions=["accepted"])
            return Replies(responses=[Response(decision="retract",reason="unsupported")])
        revised,log=critique({"data":{"findings":[{"assessment":"example"}],"unknowns":[]}},[],generate)
        self.assertEqual(revised["data"]["findings"],[])
        self.assertEqual(log[0]["response"]["decision"],"retract")
        self.assertEqual(log[0]["disposition"],"accepted")

    def test_missing_revision_is_unresolved(self):
        def generate(schema,prompt,ctx):
            if schema is Batch:
                return Batch(items=[Challenge(owner="data",index=0,concern="unsupported")])
            if schema is Closure:
                return Closure(dispositions=["unresolved"])
            return Replies(responses=[Response(decision="revise",reason="changed")])
        source = {"assessment":"A sufficiently long evidence-backed assessment","action":"Verify with another experiment","source":"S1","quote":"A sufficiently long source quotation","char_start":0,"char_end":34}
        revised,log=critique({"data":{"findings":[source],"unknowns":[]}},[],generate)
        self.assertEqual(log[0]["response"]["decision"],"unresolved")
        self.assertEqual(revised["data"]["findings"],[source])
