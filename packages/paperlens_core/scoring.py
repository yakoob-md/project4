def rubric_index(scores: dict[str, int | None]) -> float | None:
    required = ("novelty", "methodology", "evidence", "reproducibility")
    if any(scores.get(name) is None for name in required):
        return None
    if any(not 1 <= int(scores[name]) <= 5 for name in required):
        raise ValueError("rubric scores must be between 1 and 5")
    return round(20 * (0.30*scores["novelty"] + 0.30*scores["methodology"] + 0.25*scores["evidence"] + 0.15*scores["reproducibility"]), 2)


def recommendation(scores: dict[str, int | None], unresolved_major: bool = False) -> str:
    if rubric_index(scores) is None:
        return "insufficient_evidence"
    if unresolved_major or min(int(value) for value in scores.values()) <= 2:
        return "revision_recommended"
    return "ready_for_further_expert_review"
