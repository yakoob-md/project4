"""Version 1 durable evidence contracts. Offsets are zero-based and end-exclusive."""
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from services.m0_contracts import WireModel


class Versioned(WireModel):
    model_config = ConfigDict(frozen=True)
    schema_version: Literal[1] = 1


class Run(Versioned):
    id: UUID
    owner_id: str = Field(min_length=1)
    created_at: AwareDatetime


class InputRevision(Versioned):
    id: UUID
    run_id: UUID
    kind: Literal["pdf", "text"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: AwareDatetime


class SourcePassage(Versioned):
    id: UUID
    source_key: str = Field(min_length=1)
    title: str
    url: str = ""
    locator: str = Field(min_length=1)
    text: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    access_level: Literal["submitted", "abstract", "full_text"]

    @model_validator(mode="after")
    def check_span(self):
        if self.char_end - self.char_start != len(self.text):
            raise ValueError("Passage offsets must match its text")
        return self


class FrozenBundle(Versioned):
    id: UUID
    run_id: UUID
    revision_id: UUID
    provider: Literal["arXiv"]
    query: str = Field(min_length=1, max_length=500)
    cutoff: date
    retrieved_at: AwareDatetime
    coverage: Literal["abstracts_only", "no_results", "provider_unavailable"]
    passages: tuple[SourcePassage, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_coverage(self):
        if len({p.id for p in self.passages}) != len(self.passages):
            raise ValueError("Bundle passage IDs must be unique")
        literature = [p for p in self.passages if p.access_level != "submitted"]
        if len(literature) > 12 or bool(literature) != (self.coverage == "abstracts_only"):
            raise ValueError("Bundle passages do not match literature coverage")
        if len(literature) == len(self.passages) or any(p.access_level != "abstract" for p in literature):
            raise ValueError("Expected submission passages and optional abstracts")
        return self


class Citation(Versioned):
    passage_id: UUID
    locator: str
    quote: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)

    def verify(self, passage: SourcePassage) -> None:
        start = self.char_start - passage.char_start
        end = self.char_end - passage.char_start
        if (
            passage.id != self.passage_id or self.locator != passage.locator
            or not 0 <= start < end <= len(passage.text)
            or passage.text[start:end] != self.quote
        ):
            raise ValueError("Citation does not resolve to the exact frozen source span")


class Finding(Versioned):
    id: UUID
    bundle_id: UUID
    assessment: str = Field(min_length=1)
    citations: tuple[Citation, ...]
    status: Literal["supported", "uncertain"] = "supported"
    uncertainty: str = ""

    @model_validator(mode="after")
    def check_support(self):
        if self.status == "supported" and (not self.citations or self.uncertainty):
            raise ValueError("Supported findings require citations")
        if self.status == "uncertain" and not self.uncertainty.strip():
            raise ValueError("Uncertain findings require a reason")
        return self


class Report(Versioned):
    id: UUID
    bundle_id: UUID
    version: int = Field(ge=1)
    findings: tuple[Finding, ...]
    summary: str = Field(min_length=1)


SpecialistRole = Literal["Novelty & Gap", "Methodology & Feasibility", "Dataset & Evidence"]


class PaperFinding(Finding):
    role: SpecialistRole
    category: Literal["strength", "limitation", "closest_work"]
    revision: str = Field(default="", max_length=500)


class SpecialistReview(Versioned):
    bundle_id: UUID
    role: SpecialistRole
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    findings: tuple[PaperFinding, ...] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def check_lineage(self):
        if any(f.bundle_id != self.bundle_id or f.role != self.role for f in self.findings):
            raise ValueError("Specialist findings must match the review role and bundle")
        return self


class CritiqueEntry(Versioned):
    original: PaperFinding
    challenge: str = Field(min_length=1, max_length=400)
    reply_action: Literal["defend", "revise"]
    reply_reason: str = Field(min_length=1, max_length=400)
    disposition: Literal["accepted", "revised", "unresolved"]
    final: PaperFinding

    @model_validator(mode="after")
    def check_lineage(self):
        if (self.original.id, self.original.role, self.original.bundle_id) != (
            self.final.id, self.final.role, self.final.bundle_id
        ):
            raise ValueError("Critique must preserve the finding identity")
        if self.disposition == "unresolved" and self.final.status != "uncertain":
            raise ValueError("Unresolved findings must be marked uncertain")
        return self


class PaperReport(Report):
    kind: Literal["paper"] = "paper"
    run_id: UUID
    coverage: Literal["abstracts_only", "no_results", "provider_unavailable"]
    findings: tuple[PaperFinding, ...] = Field(min_length=3, max_length=15)
    prioritized_revisions: tuple[UUID, ...]
    critique: tuple[CritiqueEntry, ...] = Field(default=(), max_length=6)

    @model_validator(mode="after")
    def check_findings(self):
        if any(item.bundle_id != self.bundle_id for item in self.findings):
            raise ValueError("Paper findings must match the report bundle")
        if len({item.role for item in self.findings}) != 3:
            raise ValueError("A paper report requires all three specialists")
        if len({item.id for item in self.findings}) != len(self.findings):
            raise ValueError("Paper finding IDs must be unique")
        findings = {item.id: item for item in self.findings}
        if len({entry.original.id for entry in self.critique}) != len(self.critique):
            raise ValueError("A finding may be challenged only once")
        for role in {item.role for item in self.findings}:
            if sum(entry.original.role == role for entry in self.critique) > 2:
                raise ValueError("A specialist may receive at most two challenges")
        if any(findings.get(entry.final.id) != entry.final for entry in self.critique):
            raise ValueError("Critique closure must match the published finding")
        expected = {item.id for item in self.findings if item.revision.strip()}
        if set(self.prioritized_revisions) != expected or len(self.prioritized_revisions) != len(expected):
            raise ValueError("Revision priorities must reference each proposed revision once")
        return self

