"""Run as python -m services.tools with an authorized PDF directory."""
import os
import re
from datetime import date
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from paperlens.core import passages, search

server = FastMCP("PaperLens")


@server.tool()
def search_literature(query: str, cutoff: date) -> list[dict]:
    if not 1 <= len(query.strip()) <= 500:
        raise ValueError("Invalid query length")
    return [p.model_dump() for p in search(query, cutoff)]


@server.tool()
def parse_document(document_id: str) -> list[dict]:
    if not re.fullmatch(r"[0-9a-f]{32}", document_id):
        raise ValueError("Invalid document ID")
    root = Path(os.environ["PAPERLENS_DOCUMENT_ROOT"]).resolve(strict=True)
    path = (root / (document_id + ".pdf")).resolve(strict=True)
    if path.parent != root:
        raise ValueError("Invalid document location")
    with path.open("rb") as stream:
        return [p.model_dump() for p in passages(pdf=stream.read(20_000_001))]


if __name__ == "__main__":
    server.run()
