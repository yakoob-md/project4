"""Fixture checks at the MCP provider boundary."""
import unittest
from unittest.mock import patch

import httpx

from services.mcp_tools.server import search_literature


class ProviderTests(unittest.TestCase):
    def test_timeout_is_reported_as_unavailable(self):
        with patch("services.mcp_tools.server.search", side_effect=httpx.ReadTimeout("fixture")):
            response = search_literature("retrieval", "2020-05-21")
        self.assertEqual(response.outcome, "provider_unavailable")
        self.assertEqual(response.passages, [])
        self.assertIsNotNone(response.retrieved_at)

    def test_empty_success_has_distinct_coverage(self):
        with patch("services.mcp_tools.server.search", return_value=[]):
            response = search_literature("retrieval", "2020-05-21")
        self.assertEqual(response.outcome, "no_results")

