# PaperLens implementation status

## Current checkpoint ? Paper critique and recovery, 22 November 2026

PostgreSQL fixtures verified one revised closure, zero-challenge completion, resume after a worker process was killed, single publication, and rejection of a late A2A fixture response after cancellation. A live public-PDF run saved six closure dispositions, including one changed finding marked revised, and published report v1. The React fixture verified the before-and-after finding. The [critique and recovery checkpoint](evidence/paper_critique_recovery.md) records commands, results, and live verification status.

## Previous checkpoint — Live paper review progress, 22 November 2026

The dashboard shows the active stage, provider waits, and the saved report when ready. [Progress checkpoint](evidence/paper_review.md#review-progress-follow-up-22-november-2026)

## Previous checkpoint — Paper review through FastAPI, 21 November 2026

| Evidence class | Exact command | Observed outcome and evidence |
| --- | --- | --- |
| Live | `python scripts/test_paper_review.py "$env:TEMP/paperlens-dpr.pdf"` | Exit 0. Public PDF upload completed. Three independent CrewAI specialist records share one frozen bundle and input digest. Report v1 has six cited findings, one explicit uncertainty and four prioritized revisions. Both exports loaded v1. A page 2 citation was checked visually against the original PDF. [Paper review evidence](evidence/paper_review.md) |
| Fixture | `python -m unittest discover -s tests -v`, `powershell -NoProfile -File scripts/test_m1_ingestion.ps1`, and `npm test` from `apps/web` | 16 Python, 10 ingestion, and one React DOM check passed. [Paper review evidence](evidence/paper_review.md) |
| Unverified | Interactive live browser, Langfuse and release | React assets served successfully, and the DOM fixture verified polling, versioned links and citation view. Browser automation was unavailable. The full Langfuse and release checks remain open. |

The paper path stops at publication. The [paper review record](evidence/paper_review.md) includes the two diagnostic attempts, the manual source check, and known extraction gaps.

## Previous checkpoint — M1 storage and ingestion, 21 November 2026

| Evidence class | Exact command | Observed outcome and evidence |
| --- | --- | --- |
| Fixture | `powershell -NoProfile -File scripts/test_m1_ingestion.ps1` | Exit 0. Migration and 10 focused checks passed against PostgreSQL/pgvector and MCP, including corrupt PDF, blank text, deduplication, provider timeout and forged citation. [M1 evidence](evidence/m1.md#checkpoint) |
| Live | `powershell -NoProfile -File scripts/test_m1_ingestion.ps1 -Live` | Exit 0. MCP parsed 51 passages and ADK returned 2 arXiv abstracts over A2A. A separate process reloaded the same frozen bundle by ID and matched its SHA-256. [M1 evidence](evidence/m1.md#checkpoint) |
| Fixture | `python -m unittest discover -s tests -v` | Exit 0. All 13 legacy tests passed. [M1 evidence](evidence/m1.md#checkpoint) |
| Unverified | Full M1 and Langfuse acceptance | Semantic ranking passed with fixture vectors. Live embedding model integration and the remaining M1 tasks are open. M0 Langfuse verification still needs project credentials. |

The [human-labelling template](../evaluation/human_labelling_template.md) is ready for independent pre-output review. Reference labels remain blank. Continue with the remaining M1 tasks in plan order.

## Previous checkpoint — M0 live interoperability, 21 November 2026

The M0 live protocol smoke passed with a correlated Jaeger trace. M0's Langfuse verification is open. Paper review comes first. Release requires both paper review and idea exploration with refinement in one authenticated deployment.

| Evidence class | Exact command or record | Observed outcome and evidence |
| --- | --- | --- |
| Live | `powershell -NoProfile -File scripts/test_m0_spike.ps1` | Exit 0 twice. First run `21fd9d7b-5551-4e39-86d2-4496b9d64234` extracted 51 PDF passages with `parse_pdf`, retrieved 2 arXiv records with `search_literature`, and passed a typed A2A bundle to one CrewAI task. Groq reported 265 tokens. Repeat run `79f35a32-d1b4-4e19-a6dc-68470f127292` reported 403 tokens. The script verified 10 linked Jaeger spans per run. [M0 evidence](evidence/m0.md) |
| Fixture | `docker compose run --no-deps --rm review-worker python -m unittest services.review_worker.test_artifact -v` | 3/3 passed, including Pydantic rejection of a malformed A2A SDK artifact. [M0 evidence](evidence/m0.md#fixture-checks) |
| Fixture | `python -m unittest discover -s tests -v` | 13/13 passed. [Phase 0 baseline](evidence/phase0.md) · [PostgreSQL and audit baseline](evidence/postgres_audit.md) |
| Dependency check | `docker compose exec -T <service> python -m pip check` | No broken requirements in the three M0 service images. [Tested pins](compatibility.md#m0-protocol-images) |
| Unverified | `powershell -NoProfile -File scripts/test_m0_spike.ps1 -VerifyLangfuse` | Langfuse project credentials are missing. The remaining check is to query the remote observations by the live trace ID and verify the parent links and trace URL. [Open check](evidence/m0.md#open-acceptance-check) |

M0 uses an ADK custom agent for deterministic retrieval and one Groq-backed CrewAI task. The worker removed raw A2A event logging and exports content-free spans. The prior Groq model-ID failure and resolution are recorded with the live evidence.

## Plan selection

- [plan.md](../plan.md) §5 governs the order. M0 interoperability → M1 ingestion and retrieval → M2 paper specialists and reports → M3 critique and recovery → M4 idea exploration and refinement → M5 authenticated Cloud Run release. Its M6 describes evaluation and academic deliverables. Requirement 10 still applies.
- [plan2.md](../plan2.md) and the [architecture reference](../PaperLens_Architecture_and_Methodology.md) describe a paper-only core with proposal assessment as an extension. They place cloud/UI at M4 and evaluation at M5. The [implementation guide](../CODEX_IMPLEMENTATION_GUIDE.md) is a supporting runbook and also describes proposal mode as optional.
- [claudeplan.md](../claudeplan.md) uses a local-first phase sequence, expands the audit engine and optional library, writing, and assistant interfaces, allows Jaeger, and defers cloud deployment. The grading contract requires Langfuse and a two-mode Cloud Run demonstration.

## Grading contract

| # | Expected examiner evidence | Existing evidence and gaps |
| --- | --- | --- |
| 1 | One PostgreSQL run with an ADK evidence bundle, its ID in all three CrewAI specialist inputs, and the same finding before and after critique | The public paper run persisted three specialist records with the same bundle ID and evidence digest. A later live run saved one finding before and after revision with the same finding ID. |
| 2 | One real PDF upload with separate successful MCP document-parser and live literature-provider calls | The normal FastAPI multipart upload completed through MCP PDF extraction and ADK/A2A live arXiv retrieval. |
| 3 | Pydantic validation before publication for each mode, JSON and Markdown from the same saved report version, and one malformed report rejected | Paper validation and v1 exports verified. Fixtures reject invalid priorities and missing evidence or uncertainty. Idea-mode publication remains open. |
| 4 | Three independent orchestrated reviews and one challenge with a defend-or-revise response and visible before/after findings | Three independent CrewAI specialist outputs verified for paper review. The live CrewAI critique saved six challenges and one revised closure. The React fixture verified the visible before-and-after panel. |
| 5 | Actual CrewAI and ADK success and failure callbacks with run ID, stage, duration, outcome, and sanitized artifact reference | PostgreSQL audit table reported. Required callback evidence unverified. |
| 6 | Official A2A Agent Card discovery, retrieval request, and typed artifact returned across processes | Verified live in M0, with the card, task and bundle IDs recorded. |
| 7 | Dependencies and runtime evidence showing CrewAI owns workflow/review and Google ADK owns retrieval/session, with only those agent runtimes | Verified within the M0 spike. Complete ownership through both workflows is unverified. |
| 8 | Input safeguard, tool callback rejecting invalid output, and publication rejection of a mismatched quote, with a normal academic paper as control | Legacy fixture citation checks exist. Full guardrail and control demonstration unverified. |
| 9 | One Langfuse trace spanning worker, A2A, and MCP, plus report citation resolution to the exact passage and locator | The live report citation resolved through FastAPI and matched the original PDF page. Langfuse remains open. |
| 10 | Human-labelled public-paper evaluation with quality, completion rate, wall time, tokens, estimated model cost, cloud cost assumptions, failures, and sample sizes | [Synthetic audit benchmark](../evaluation/benchmark.py) exists. Human-labelled end-to-end results unverified. |
| 11 | One authenticated Cloud Run URL completing paper review and idea exploration with refinement, with deployed revision, run IDs, and sanitized trace references | Local UI, refinement fixture, and containers exist. Cloud acceptance unverified. |

**Next M0 command** after configuring the Langfuse shell variables in [M0 evidence](evidence/m0.md#open-acceptance-check)

```powershell
powershell -NoProfile -File scripts/test_m0_spike.ps1 -VerifyLangfuse
```
