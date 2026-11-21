import re
from packages.paperlens_core.models import AuditResult


def check_percentages(values: list[float], tolerance: float = 0.5) -> AuditResult:
    if not values:
        return AuditResult(check_id="percentage_sum", status="not_applicable", details="No percentages supplied.", confidence=1, method="deterministic_sum")
    total = sum(values)
    status = "pass" if abs(total - 100) <= tolerance else "fail"
    return AuditResult(check_id="percentage_sum", status=status, details=f"Percentages sum to {total:.2f}%.", confidence=1, method="deterministic_sum")


def reproducibility_checklist(text: str) -> list[AuditResult]:
    items = {
        "code_link": r"https?://\S*(?:github|gitlab)|\bcode (?:is|at|available)",
        "random_seed": r"\b(?:random )?seed(?:s)?\b",
        "hyperparameters": r"\bhyperparameter(?:s)?\b|learning rate|batch size",
        "variance": r"standard deviation|confidence interval|\bvariance\b|±",
        "hardware": r"\bGPU\b|\bTPU\b|hardware|compute",
        "dataset_split": r"train(?:ing)?[ /-](?:validation|test)|dataset split|held[ -]out",
        "ablation": r"\bablation(?:s| study)?\b",
    }
    lowered = text.lower()
    return [AuditResult(check_id=name, status="pass" if re.search(pattern, lowered, re.I) else "inconclusive", details="Reported in supplied text." if re.search(pattern, lowered, re.I) else "Not reported in the provided text.", confidence=0.9, method="keyword_regex") for name, pattern in items.items()]


def hygiene_checks(text: str) -> list[AuditResult]:
    checks = []
    if re.search(r"tun(?:e|ed|ing).{0,40}\btest (?:set|data)\b", text, re.I):
        checks.append(AuditResult(check_id="test_set_tuning", status="fail", details="Text may describe tuning on test data.", confidence=0.85, method="bounded_regex"))
    for term in ("state-of-the-art", "significantly", "generalizes", "robust"):
        if term in text.lower():
            checks.append(AuditResult(check_id=f"overclaim_{term.replace('-', '_')}", status="inconclusive", details=f"The term '{term}' requires supporting evidence.", confidence=0.7, method="keyword_prompt"))
    return checks
