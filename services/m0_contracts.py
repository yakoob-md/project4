"""Strict wire contracts for the M0 protocol spike."""
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationInfo, field_validator


BUNDLE_MEDIA_TYPE = "application/vnd.paperlens.evidence-bundle+json"
PDF_TOOL = "parse_pdf"
SEARCH_TOOL = "search_literature"


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Passage(WireModel):
    id: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    text: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: str = ""


class RetrievalRequest(WireModel):
    run_id: UUID
    query: str = Field(min_length=1, max_length=500)
    cutoff: date


class PdfPassage(Passage):
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)


class PdfEvidence(WireModel):
    passages: list[PdfPassage] = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class LiteratureResult(WireModel):
    provider: Literal["arXiv"]
    outcome: Literal["ok", "no_results", "provider_unavailable"] = "ok"
    retrieved_at: AwareDatetime | None = None
    passages: list[Passage] = Field(max_length=12)

    @field_validator("passages")
    @classmethod
    def check_outcome(cls, passages, info: ValidationInfo):
        if "outcome" in info.data and bool(passages) != (info.data["outcome"] == "ok"):
            raise ValueError("Literature passages do not match the provider outcome")
        return passages


class EvidenceBundle(LiteratureResult):
    run_id: UUID
    bundle_id: UUID
    query: str = Field(min_length=1, max_length=500)
    cutoff: date
    tool: Literal["search_literature"]
    mcp_protocol: str = Field(min_length=1)
