"""Prepare an owner-scoped evidence bundle through the existing MCP and A2A clients."""
import hashlib
import re
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from paperlens.core import passages
from services.m0_contracts import RetrievalRequest
from services.m1_contracts import FrozenBundle, InputRevision, Run, SourcePassage
from services.m1_storage import freeze
from services.review_worker.app import delegate, parse_pdf


async def ingest(
    owner_id: str, run_id: UUID, query: str, cutoff: date, *,
    pdf: bytes | None = None, text: str | None = None, embed=None, on_retrieval=None, persist=freeze,
) -> FrozenBundle:
    """Use the authenticated caller's owner ID. An optional batch embedder supplies 384-D vectors."""
    request = RetrievalRequest(run_id=run_id, query=query.strip(), cutoff=cutoff)
    if (pdf is None) == (text is None):
        raise ValueError("Supply exactly one PDF or text input")
    revision_id = uuid4()
    created_at = datetime.now(UTC)
    if pdf is not None:
        if len(pdf) > 20_000_000 or not pdf.startswith(b"%PDF-"):
            raise ValueError("Supply a valid PDF up to 20 MB")
        parsed, _ = await parse_pdf(run_id, pdf)
        submitted = parsed.passages
        sha256 = parsed.sha256
        kind = "pdf"
    else:
        if not text.strip() or len(text) > 150_000 or "\x00" in text:
            raise ValueError("Supply readable text up to 150000 characters")
        submitted = passages(text=text, include_offsets=True)
        sha256 = hashlib.sha256(text.encode()).hexdigest()
        kind = "text"

    sources = [
        SourcePassage(
            id=uuid4(), source_key=str(revision_id), title=p.title, locator=p.locator,
            text=p.text, char_start=p.char_start, char_end=p.char_end, access_level="submitted",
        )
        for p in submitted
    ]
    if on_retrieval:
        on_retrieval()
    remote, _ = await delegate(request)
    seen_ids = set()
    seen_titles = set()
    for entry in remote.passages:
        if not entry.url.startswith("https://arxiv.org/abs/") or entry.locator != "Abstract":
            raise ValueError("Unexpected arXiv source reference")
        family = re.sub(r"v\d+$", "", entry.url.removeprefix("https://arxiv.org/abs/"))
        title = " ".join(re.findall(r"\w+", entry.title.casefold()))
        if family in seen_ids or (title and title in seen_titles):
            continue
        seen_ids.add(family)
        seen_titles.add(title)
        sources.append(SourcePassage(
            id=uuid4(), source_key=f"arxiv:{family}", title=entry.title, url=entry.url,
            locator=entry.locator, text=entry.text, char_start=0, char_end=len(entry.text),
            access_level="abstract",
        ))
    bundle = FrozenBundle(
        id=remote.bundle_id, run_id=run_id, revision_id=revision_id, provider=remote.provider,
        query=request.query, cutoff=cutoff, retrieved_at=remote.retrieved_at or datetime.now(UTC),
        coverage="abstracts_only" if remote.outcome == "ok" else remote.outcome,
        passages=tuple(sources),
    )
    embeddings = None
    if embed is not None:
        vectors = embed([p.text for p in sources])
        embeddings = {p.id: vector for p, vector in zip(sources, vectors, strict=True)}
    persist(
        Run(id=run_id, owner_id=owner_id, created_at=created_at),
        InputRevision(id=revision_id, run_id=run_id, kind=kind, sha256=sha256, created_at=created_at),
        bundle, embeddings,
    )
    return bundle
