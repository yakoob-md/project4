"""Submit a public paper via FastAPI and verify the saved report, citation, and both exports."""
import argparse
import hashlib
import os
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--run-id", help="Verify an already-submitted dashboard run")
    parser.add_argument("--require-revision", action="store_true", help="Require a changed finding closed as revised")
    args = parser.parse_args()
    token = os.getenv("PAPERLENS_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(base_url="http://127.0.0.1:8000", headers=headers, timeout=30) as client:
        if args.run_id:
            run_id = args.run_id
        else:
            with args.pdf.open("rb") as pdf:
                response = client.post(
                    "/api/v1/reviews",
                    data={"mode": "paper", "question": "dense passage retrieval", "cutoff": "2020-05-21"},
                    files={"pdf": ("paper.pdf", pdf, "application/pdf")},
                )
            response.raise_for_status()
            assert response.status_code == 202
            run_id = response.json()["id"]
        base = f"/api/v1/reviews/{run_id}"
        print(f"Run {run_id}", flush=True)
        deadline = time.monotonic() + 910
        previous = None
        while time.monotonic() < deadline:
            job = client.get(base).raise_for_status().json()
            status = job["status"]
            snapshot = (status, job.get("stage"), job.get("activity"))
            if snapshot != previous:
                previous = snapshot
                print(" | ".join(field for field in snapshot if field), flush=True)
            if status == "failed":
                raise RuntimeError(job["error"])
            if status == "completed":
                break
            time.sleep(1)
        else:
            raise TimeoutError("Run did not complete within 910 seconds")
        version = job["report_version"]
        params = {"version": version}
        report = client.get(base + "/report", params=params).raise_for_status().json()
        exported = client.get(base + "/report.json", params=params).raise_for_status()
        markdown = client.get(base + "/report.md", params=params).raise_for_status()
        assert report == exported.json()
        assert report["bundle_id"] in markdown.text and f"Report version {version}" in markdown.text
        assert all(f["citations"] or f["uncertainty"] for f in report["findings"])
        assert len({f["role"] for f in report["findings"]}) == 3
        history = report.get("critique", [])
        for entry in history:
            assert entry["final"] in report["findings"]
        revised = [entry for entry in history if entry["disposition"] == "revised"]
        if args.require_revision:
            assert any(entry["original"]["assessment"] != entry["final"]["assessment"] for entry in revised)
        print(f"Critique closures {len(history)}; revised {len(revised)}", flush=True)
        citation = next((
            c for finding in report["findings"] for c in finding["citations"] if c["locator"].startswith("Page ")
        ), None)
        if citation is None:
            raise RuntimeError("The published report did not cite a submission page")
        passage_id = citation["passage_id"]
        source = client.get(f"{base}/passages/{passage_id}", params=params).raise_for_status().json()
        passage = source["passage"]
        start, end = (citation[k] - passage["char_start"] for k in ("char_start", "char_end"))
        assert passage["locator"] == citation["locator"] and passage["text"][start:end] == citation["quote"]
        assert all("> " + line in markdown.text for line in citation["quote"].split("\n"))
        print(f"Bundle {report['bundle_id']} · version {version} · coverage {report['coverage']}")
        counts = {status: sum(f["status"] == status for f in report["findings"]) for status in ("supported", "uncertain")}
        print(f"Findings {counts} · revisions {len(report['prioritized_revisions'])}")
        print(f"Passage {passage_id} · {citation['locator']} · offsets {citation['char_start']}-{citation['char_end']}")
        print(f"Quote SHA-256 {hashlib.sha256(citation['quote'].encode()).hexdigest()}")
        print("PDF SHA-256 " + hashlib.sha256(args.pdf.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()

