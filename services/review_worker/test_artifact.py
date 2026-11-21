"""Offline tests for the receiving A2A artifact boundary."""
import unittest
from datetime import date
from uuid import uuid4

from a2a.helpers import new_data_part
from a2a.types import Artifact
from pydantic import ValidationError

from services.m0_contracts import BUNDLE_MEDIA_TYPE, RetrievalRequest
from services.review_worker.artifact import read_bundle


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.request = RetrievalRequest(run_id=uuid4(), query="fixture", cutoff=date(2020, 5, 21))
        self.bundle_id = str(uuid4())
        self.payload = {
            **self.request.model_dump(mode="json"), "bundle_id": self.bundle_id,
            "provider": "arXiv", "tool": "search_literature", "mcp_protocol": "2025-11-25",
            "passages": [{"id": "L1", "locator": "Abstract", "text": "Fixture passage.",
                          "title": "Fixture", "url": "https://arxiv.org/abs/1706.03762"}],
        }

    def artifact(self):
        return Artifact(
            artifact_id=self.bundle_id, name="EvidenceBundle",
            parts=[new_data_part(self.payload, BUNDLE_MEDIA_TYPE)],
        )

    def test_valid_artifact(self):
        self.assertEqual(str(read_bundle(self.artifact(), self.request).bundle_id), self.bundle_id)

    def test_malformed_artifact_is_rejected(self):
        self.payload["passages"] = []
        with self.assertRaises(ValidationError) as thrown:
            read_bundle(self.artifact(), self.request)
        self.assertEqual(thrown.exception.errors(include_input=False)[0]["loc"], ("passages",))

    def test_artifact_from_different_run_is_rejected(self):
        self.payload["run_id"] = str(uuid4())
        with self.assertRaisesRegex(ValueError, "does not match"):
            read_bundle(self.artifact(), self.request)


if __name__ == "__main__":
    unittest.main()
