"""Owner-scoped paper report and citation endpoints."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response

from paperlens.auth import current_owner
from paperlens.storage import uses_postgres
from services.m1_contracts import PaperReport
from services.m1_storage import load_bundle, load_report
from services.paper_jobs import cancel, read_job, retry_review

router = APIRouter(prefix="/api/v1/reviews")


@router.post("/{run_id}/retry", status_code=202)
def retry_paper_review(run_id: UUID, owner: str = Depends(current_owner)):
    if not uses_postgres() or read_job(owner, run_id) is None:
        raise HTTPException(404, "Paper review not found")
    if not retry_review(owner, run_id):
        raise HTTPException(409, "This review cannot be retried from saved evidence.")
    return read_job(owner, run_id)


@router.post("/{run_id}/cancel")
def cancel_paper_review(run_id: UUID, owner: str = Depends(current_owner)):
    if not uses_postgres() or read_job(owner, run_id) is None:
        raise HTTPException(404, "Paper review not found")
    if not cancel(owner, run_id):
        raise HTTPException(409, "This review has already finished.")
    return read_job(owner, run_id)


def stored_report(owner, run_id, version):
    job = read_job(owner, run_id) if uses_postgres() else None
    if job is None or job["status"] != "completed":
        raise HTTPException(404, "Published paper report not found")
    report = load_report(owner, job["bundle_id"], version if version is not None else job["report_version"])
    if not isinstance(report, PaperReport) or report.run_id != run_id:
        raise HTTPException(404, "Paper report version not found")
    return report


def render_markdown(report: PaperReport):
    lines = [
        "# Paper review", "",
        f"Report version {report.version} · Run `{report.run_id}` · Bundle `{report.bundle_id}`", "",
        report.summary, "", f"Literature coverage: {report.coverage.replace('_', ' ')}", "",
    ]
    for category, heading in (("strength", "Strengths"), ("limitation", "Limitations"), ("closest_work", "Closest work")):
        lines.extend([f"## {heading}", ""])
        findings = [item for item in report.findings if item.category == category]
        if not findings:
            lines.extend(["No findings recorded in this section.", ""])
        for item in findings:
            lines.extend([f"- **{item.role} · {item.status}** — {item.assessment}", ""])
            if item.uncertainty:
                lines.extend([f"  Uncertainty: {item.uncertainty}", ""])
            for c in item.citations:
                link = f"/api/v1/reviews/{report.run_id}/passages/{c.passage_id}?version={report.version}"
                lines.extend([f"  [{c.locator}, characters {c.char_start}–{c.char_end}]({link})", ""])
                lines.extend(f"  > {line}" for line in c.quote.split("\n"))
                lines.append("")
    if report.critique:
        lines.extend(["## Critique", ""])
        for entry in report.critique:
            lines.extend([
                f"- **{entry.original.role} ({entry.disposition})**", "",
                f"  Before: {entry.original.assessment}", "",
                f"  Challenge: {entry.challenge}", "",
                f"  Specialist response ({entry.reply_action}): {entry.reply_reason}", "",
                f"  After: {entry.final.assessment}", "",
            ])
    lines.extend(["## Prioritized revisions", ""])
    by_id = {item.id: item for item in report.findings}
    if not report.prioritized_revisions:
        lines.append("No revisions proposed.")
    for index, finding_id in enumerate(report.prioritized_revisions, 1):
        item = by_id[finding_id]
        lines.append(f"{index}. {item.revision} ({item.role}, {item.status})")
    return "\n".join(lines) + "\n"


@router.get("/{run_id}/report", response_model=PaperReport)
def read_paper_report(run_id: UUID, version: int | None = Query(None, ge=1), owner: str = Depends(current_owner)):
    return stored_report(owner, run_id, version)


@router.get("/{run_id}/report.{extension}")
def download_paper_report(run_id: UUID, extension: str, version: int = Query(ge=1), owner: str = Depends(current_owner)):
    report = stored_report(owner, run_id, version)
    headers = {"Content-Disposition": f'attachment; filename="paper-review-v{report.version}.{extension}"'}
    if extension == "json":
        return Response(report.model_dump_json(indent=2), media_type="application/json", headers=headers)
    if extension == "md":
        return PlainTextResponse(render_markdown(report), media_type="text/markdown", headers=headers)
    raise HTTPException(404, "Report format not found")


@router.get("/{run_id}/passages/{passage_id}")
def read_cited_passage(run_id: UUID, passage_id: UUID, version: int = Query(ge=1), owner: str = Depends(current_owner)):
    report = stored_report(owner, run_id, version)
    citations = [c for item in report.findings for c in item.citations if c.passage_id == passage_id]
    if not citations:
        raise HTTPException(404, "Cited passage not found")
    bundle = load_bundle(owner, report.bundle_id)
    for passage in bundle.passages:
        if passage.id == passage_id:
            for citation in citations:
                citation.verify(passage)
            return {"passage": passage, "citations": citations}
    raise HTTPException(404, "Cited passage not found")

