"""Print only IDs, counts and a digest for the live ingestion restart check."""
import argparse
import asyncio
import hashlib
import json
from datetime import date
from uuid import UUID, uuid4

import httpx

from services.m1_contracts import Citation
from services.m1_storage import load_bundle, search_passages
from services.review_worker.app import PUBLIC_PDF
from services.review_worker.ingestion import ingest


OWNER = "m1-live-smoke"
QUERY = "dense passage retrieval"


async def write():
    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.get(PUBLIC_PDF)
        response.raise_for_status()
    return await ingest(OWNER, uuid4(), QUERY, date(2020, 5, 21), pdf=response.content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read", type=UUID)
    args = parser.parse_args()
    if args.read:
        bundle = load_bundle(OWNER, args.read)
        if bundle is None:
            raise RuntimeError("Frozen bundle unavailable")
        results = search_passages(OWNER, bundle.id, QUERY)
        passage = next((p for p in results if p.access_level == "submitted" and p.locator.startswith("Page ")), None)
        if passage is None:
            raise RuntimeError("Expected a searchable PDF page passage")
        Citation(
            passage_id=passage.id, locator=passage.locator, quote=passage.text,
            char_start=passage.char_start, char_end=passage.char_end,
        ).verify(next(p for p in bundle.passages if p.id == passage.id))
    else:
        bundle = asyncio.run(write())
        if bundle.coverage != "abstracts_only":
            raise RuntimeError("Live check requires arXiv records")
    print(json.dumps({
        "bundle_id": str(bundle.id),
        "sha256": hashlib.sha256(bundle.model_dump_json().encode()).hexdigest(),
        "submission_passages": sum(p.access_level == "submitted" for p in bundle.passages),
        "literature_passages": sum(p.access_level == "abstract" for p in bundle.passages),
        "coverage": bundle.coverage,
    }))


if __name__ == "__main__":
    main()

