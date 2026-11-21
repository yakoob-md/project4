from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"] = "1"


class Locator(StrictModel):
    kind: Literal["page", "paragraph"]
    number: int = Field(ge=1)
    section: str = ""
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    @model_validator(mode="after")
    def ordered_span(self):
        if self.char_end <= self.char_start:
            raise ValueError("char_end must follow char_start")
        return self


class EvidenceRef(StrictModel):
    source_id: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)


class AuditResult(StrictModel):
    check_id: str
    status: Literal["pass", "fail", "inconclusive", "not_applicable"]
    details: str
    evidence: list[EvidenceRef] = []
    confidence: float = Field(ge=0, le=1)
    method: str


class Finding(StrictModel):
    finding_id: str
    owner: str
    dimension: Literal["novelty", "methodology", "evidence", "reproducibility", "feasibility"]
    claim: str
    status: Literal["supported", "inference", "unverified"]
    severity: Literal["info", "minor", "major"]
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRef] = []
    suggested_action: str

    @model_validator(mode="after")
    def evidence_required(self):
        if self.status in {"supported", "inference"} and not self.evidence:
            raise ValueError("supported findings and inferences require evidence")
        return self


def validate_evidence(reference: EvidenceRef, source_id: str, normalized_chunk: str) -> None:
    if reference.source_id != source_id:
        raise ValueError("evidence source does not match chunk")
    if reference.char_end > len(normalized_chunk):
        raise ValueError("evidence span exceeds chunk")
    if normalized_chunk[reference.char_start:reference.char_end] != reference.quote:
        raise ValueError("evidence quote does not match exact span")
    if len(reference.quote.strip()) < 20 and reference.quote.strip() != normalized_chunk.strip():
        raise ValueError("evidence quote is too short")
