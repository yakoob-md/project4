from datetime import date
from io import BytesIO
import re
from xml.etree import ElementTree as ET

import httpx
from pydantic import BaseModel, Field
from pypdf import PdfReader


class Passage(BaseModel):
    id: str
    locator: str
    text: str
    title: str
    url: str = ""


class LocatedPassage(Passage):
    char_start: int
    char_end: int


class Finding(BaseModel):
    finding_id: str = ""
    assessment: str = Field(min_length=1)
    action: str = Field(min_length=1)
    source: str
    quote: str = Field(min_length=1)
    char_start: int = Field(default=-1, ge=-1)
    char_end: int = Field(default=-1, ge=-1)


class Review(BaseModel):
    findings: list[Finding] = Field(max_length=6)
    unknowns: list[str] = Field(max_length=6)


def passages(text="", pdf=None, *, include_offsets=False):
    if pdf is None:
        parts = [
            (f"Paragraph {i}", p if include_offsets else p.strip())
            for i, p in enumerate(re.split(r"\n\s*\n", text), 1)
        ]
    else:
        if not pdf.startswith(b"%PDF-") or len(pdf) > 20_000_000:
            raise ValueError("Upload a PDF under 20 MB")
        reader = PdfReader(BytesIO(pdf))
        if reader.is_encrypted or len(reader.pages) > 30:
            raise ValueError("Use an unlocked PDF of up to 30 pages")
        parts = [(f"Page {i}", page.extract_text() or "") for i, page in enumerate(reader.pages, 1)]
    items = []
    for locator, value in parts:
        for start in range(0, len(value), 1600):
            chunk = value[start:start+1600]
            excerpt = chunk.strip()
            if excerpt:
                item = Passage(id=f"S{len(items)+1}", locator=locator, text=excerpt, title="Submission")
                if include_offsets:
                    first = start + len(chunk) - len(chunk.lstrip())
                    item = LocatedPassage(**item.model_dump(), char_start=first, char_end=first + len(excerpt))
                items.append(item)
    if not items:
        raise ValueError("Provide readable text")
    return items


def search(query, cutoff):
    response = httpx.get("https://export.arxiv.org/api/query", params={"search_query":"all:"+query, "max_results":12}, timeout=15)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    ns = "{http://www.w3.org/2005/Atom}"
    if root.tag != ns+"feed":
        raise ValueError("Unexpected literature response")
    results = []
    for entry in root.findall(ns+"entry"):
        url = entry.findtext(ns+"id","").replace("http://arxiv.org/", "https://arxiv.org/")
        if not url.startswith("https://arxiv.org/abs/"):
            raise ValueError("Unexpected arXiv record")
        if date.fromisoformat(entry.findtext(ns+"published")[:10]) <= cutoff:
            results.append(Passage(id=f"L{len(results)+1}", locator="Abstract", title=entry.findtext(ns+"title","").strip(), text=entry.findtext(ns+"summary","").strip(), url=url))
    return results


def validate_review(review, sources):
    by_id = {item.id:item for item in sources}
    for finding in review.findings:
        passage = by_id.get(finding.source)
        if passage is None:
            raise ValueError("Finding has an invalid source or quotation")
        first = passage.text.find(finding.quote)
        if first < 0 or passage.text.find(finding.quote, first + 1) >= 0:
            raise ValueError("Finding quotation must resolve to one exact span")
        finding.char_start, finding.char_end = first, first + len(finding.quote)
        if len(finding.quote.strip()) < 20 and finding.quote.strip() != passage.text.strip():
            raise ValueError("Finding quotation is too short")
    return review
