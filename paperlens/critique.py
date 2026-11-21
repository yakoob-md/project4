"""Bounded review revision over a frozen passage set."""
from typing import Literal
from pydantic import BaseModel, Field
from .core import Review, validate_review


class Challenge(BaseModel):
    owner: str
    index: int = Field(ge=0)
    concern: str = Field(min_length=1)


class Batch(BaseModel):
    items: list[Challenge] = Field(max_length=6)


class Response(BaseModel):
    decision: Literal["defend","revise","retract","unresolved"]
    reason: str = Field(min_length=1)
    finding: dict | None = None


class Replies(BaseModel):
    responses: list[Response] = Field(max_length=2)


def critique(reviews, sources, generate):
    original = {k:v.copy() for k,v in reviews.items()}
    batch = generate(Batch,"Challenge weak or unsupported findings. Use zero-based indices, at most two per owner.", original)
    grouped = {}
    seen = set()
    for c in batch.items:
        key = (c.owner,c.index)
        if c.owner not in original or c.index >= len(original[c.owner]["findings"]) or key in seen:
            raise ValueError("Invalid critique target")
        seen.add(key)
        grouped.setdefault(c.owner,[]).append(c)
        if len(grouped[c.owner])>2:
            raise ValueError("Too many challenges for one reviewer")
    revised = dict(original)
    history = []
    for owner, challenges in grouped.items():
        findings = list(original[owner]["findings"])
        context = {"initial":original[owner],"challenges":[c.model_dump() for c in challenges]}
        try:
            replies = generate(Replies,"Respond once per challenge in order. For revise supply a complete replacement finding with a valid quote.",context)
            if len(replies.responses)!=len(challenges):
                raise ValueError("Incomplete response")
            candidate = list(findings)
            for c,r in zip(challenges,replies.responses):
                if r.decision=="revise":
                    candidate[c.index]=r.finding
                elif r.decision=="retract":
                    candidate[c.index]=None
            review = Review(findings=[f for f in candidate if f is not None],unknowns=original[owner]["unknowns"])
            revised[owner]=validate_review(review,sources).model_dump()
        except (ValueError,RuntimeError):
            replies=Replies(responses=[Response(decision="unresolved",reason="No valid owner response") for _ in challenges])
        for c,r in zip(challenges,replies.responses):
            history.append({"challenge":c.model_dump(),"response":r.model_dump(),"original":findings[c.index]})
    return revised,history
