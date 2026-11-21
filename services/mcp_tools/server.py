import base64
import binascii
import hashlib
import logging
import os
from datetime import UTC, date, datetime

import httpx

from mcp.server.mcpserver import MCPServer

from paperlens.core import passages, search
from services.m0_contracts import LiteratureResult, PdfEvidence
from services.m0_trace import stage, tracer
from services.mcp_tools.audit import check_percentages, hygiene_checks, reproducibility_checklist

mcp = MCPServer("PaperLens evidence tools")
telemetry = tracer("paperlens-mcp")
logging.getLogger("pypdf").setLevel(logging.CRITICAL)


@mcp.tool()
def parse_pdf(pdf_base64: str, run_id: str, traceparent: str = "") -> PdfEvidence:
    """Extract locatable evidence from a small machine-readable PDF."""
    with stage(telemetry, "mcp.parse_pdf", run_id, traceparent):
        if len(pdf_base64) > 26_666_668:
            raise ValueError("PDF exceeds 20 MB")
        try:
            pdf = base64.b64decode(pdf_base64, validate=True)
        except binascii.Error:
            raise ValueError("Invalid PDF encoding") from None
        if len(pdf) > 20_000_000:
            raise ValueError("PDF exceeds 20 MB")
        try:
            extracted = passages(pdf=pdf, include_offsets=True)
            return PdfEvidence(
                passages=[item.model_dump() for item in extracted],
                sha256=hashlib.sha256(pdf).hexdigest(),
            )
        except Exception:
            raise ValueError("PDF extraction failed") from None


@mcp.tool()
def parse_document_text(text: str) -> list[dict]:
    """Parse authorized submitted text into locatable evidence passages."""
    if not 1 <= len(text) <= 150_000:
        raise ValueError("text must contain 1 to 150000 characters")
    return [item.model_dump() for item in passages(text=text)]


@mcp.tool()
def search_literature(query: str, cutoff: str, run_id: str = "", traceparent: str = "") -> LiteratureResult:
    """Search live arXiv for literature available by the supplied ISO date."""
    with stage(telemetry, "mcp.search_literature", run_id, traceparent):
        if not 1 <= len(query.strip()) <= 500:
            raise ValueError("Invalid query")
        try:
            records = search(query, date.fromisoformat(cutoff))
        except httpx.HTTPError:
            return LiteratureResult(
                provider="arXiv", passages=[], outcome="provider_unavailable",
                retrieved_at=datetime.now(UTC),
            )
        except Exception:
            raise ValueError("Invalid arXiv response") from None
        return LiteratureResult(
            provider="arXiv", passages=[item.model_dump() for item in records],
            outcome="ok" if records else "no_results", retrieved_at=datetime.now(UTC),
        )


@mcp.tool()
def audit_text(text: str, percentages: list[float] | None = None) -> dict:
    """Run deterministic reproducibility, hygiene and percentage checks."""
    return {
        "checklist": [item.model_dump() for item in reproducibility_checklist(text)],
        "hygiene": [item.model_dump() for item in hygiene_checks(text)],
        "percentages": check_percentages(percentages or []).model_dump(),
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.getenv("PORT", "9000")), stateless_http=True, json_response=True)
