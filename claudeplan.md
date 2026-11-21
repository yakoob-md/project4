# claudeplan.md — PaperLens: Quality-First Research Copilot (Free, Local-First)

**Prepared:** 21 November 2026
**Audience:** Codex (or any coding agent). Self-sufficient.
**Authority:** Supersedes `plan.md`, `plan2.md`, `CODEX_IMPLEMENTATION_GUIDE.md` and the archived `claudeplan_v1_gcp_archived.md` / `claudeplan_v2_free_archived.md` where they conflict. Those remain rationale only.
**Hard constraints:** (1) USD 0: no billing accounts, no paid tiers, no card. User supplies only a **Groq API key**. (2) **Deployment is deferred.** Everything must work completely and produce good results on a Windows PC with Docker Compose first. A short deployment phase at the end is optional.
**Goal:** A research copilot that a researcher, or an AI assistant such as Claude, can rely on to **critique a paper, explore a research idea, build a verified literature picture, and help write a paper**, where every claim traces to exact evidence and every check that can be made deterministic is made deterministic.

---

## 0. Operating rules

1. Inspect the repo first; preserve working code; never reset user work.
2. Follow phase order (§12). A phase's gate must pass before the next starts. From Phase 3 on, every phase must also pass `scripts/quality.ps1` (§11) with no regression.
3. **No task is done without evidence**: commands run + real output saved in `docs/evidence/<phase>.md`. Fixtures/mocks are not live evidence.
4. Never fake an integration. CrewAI → official A2A → ADK → MCP must be real; if incompatible, isolate environments. No direct import, no custom `/retrieve`.
5. Never commit secrets, `.env`, private papers, DB dumps. Never invent metrics, traces, citations, screenshots or contribution claims.
6. No other agent framework (no LangGraph/AutoGen/PydanticAI/OpenAI Agents SDK). LiteLLM is only a model connector.
7. **Zero-cost guard:** never add a payment method; a step needing a card is `blocked` with an alternative.
8. Generate all secrets yourself (`scripts/bootstrap.ps1` writes `.env`); ask the user only for `GROQ_API_KEY`.
9. Update `docs/implementation_status.md` after each phase (`pending | in_progress | implemented_unverified | verified | blocked | deferred`); log design changes in `docs/decisions.md`.
10. **Precision over volume.** A review with 5 verified, ranked issues beats 25 plausible ones. Never present an LLM guess as a verified fact. Never say "fabricated" when the correct word is "could not verify".

---

## 1. Current state: not complete (~25%)

**Works:** local single-user prototype: FastAPI + static HTML/JS, SQLite history, PDF/text → locatable passages (`paperlens/core.py`), arXiv search, exact-quote citation gate, three Groq reviewers + one critique pass (`service.py`, `critique.py`), refine-and-rerun, JSON/Markdown export. Live model run never verified.
**Stubs, unverified:** `services/tools.py` (FastMCP), `services/literature.py` (ADK `to_a2a`).
**Missing:** everything in §§4–11: CrewAI Flow, A2A client, audit engine, Postgres/pgvector, library, writing tools, claim ledger, scoring, auth, quota governor, React UI, assistant interfaces, tracing, benchmark.

**Defects to fix first:**
1. `critique.py`: `revise` with `finding=None` silently becomes a retraction (must be `unresolved`); no closure pass; challenges by index not stable id.
2. `core.py::validate_review`: substring match accepts tiny/repeated quotes → require ≥20 chars (or whole short chunk) and an exact `char_start/char_end` span.
3. `core.py::search`: unquoted `all:` query from raw text, no rate limit/`Retry-After`, no dedup, no exclusion of the submission's own preprint, ignores first-version date.
4. `service.py::create`: 4+ sequential model calls in one HTTP request; will time out and hit Groq free limits.
5. `services/*`: not a package, stdio only, missing deps, ADK agent LLM-passes-through tool output.
6. Tests depend on `material/Final_Project_Report_Template.pdf` → replace with generated synthetic PDFs.
7. `app.js`: stray `' ? '` encoding damage, no polling/cancel/auth.
8. `docs/compatibility.md` pairs FastAPI 0.110.0 with Pydantic 2.13.4; verify resolution.
9. `docs/implementation_status.md` marks mock-only items `verified`; relabel.
10. `.gitignore`: add `node_modules/ dist/ .pytest_cache/ var/ docs/evidence/private/ *.env`.

---

## 2. Who uses it and for what

Primary user: a researcher (you) **and an AI assistant working for you** (Claude, Codex) that calls PaperLens through MCP, CLI or HTTP. PaperLens is the **grounding and verification layer**: it reads papers exactly, checks what can be checked mechanically, retrieves real literature, remembers a project's library, and refuses to cite what it cannot quote. It is deliberately **not** a replacement for a frontier model's judgment, because free Groq models are weaker. So every result comes in two layers:

1. **Evidence Pack** (always available, mostly deterministic, no or little LLM): parsed structure, claim ledger candidates, extracted numbers/tables, reference verification, statistical/arithmetic consistency checks, reproducibility checklist, uncited-close-work candidates, retraction flags. Delivered even when free LLM quota is exhausted.
2. **Full Review** (LLM-assisted): specialist assessments, critique round, scores, ranked issues, questions to authors, suggested experiments. Built *on top of* the Evidence Pack, never contradicting it.

A stronger external assistant can read the Evidence Pack JSON and write its own synthesis; the built-in review is the standalone path.

---

## 3. Quality philosophy (design rules that drive results)

1. **Deterministic first.** Anything checkable by code (reference existence, p-value recomputation, percentage sums, number-in-text vs number-in-table, checklist keywords, retraction flags, dates) is done by code and reported as `verified_by_code`.
2. **Small, well-posed LLM tasks.** Map-reduce, never "read the whole paper": per-section claim extraction on a small model; reasoning only over (claim, evidence snippets) pairs on a larger model.
3. **Every sentence earns its citation.** Findings carry exact spans; unverifiable findings are shown as `unverified` and never influence scores.
4. **Calibrated language.** Confidence and severity on every finding; separate *observed in submission*, *supported comparison*, *inference*, *unverified*, *not assessed*. Always list what was **not** checked (figures, equations, inaccessible full texts).
5. **Noise budget.** Max 8 findings in the Review Card, ranked by severity × confidence × evidence strength; duplicates merged; lower-ranked ones go to an expandable appendix.
6. **Graceful degradation.** Quota exhausted → deliver the Evidence Pack now, mark Full Review `quota_wait`, resume later.
7. **Measured, not claimed.** Quality is tracked by an automatic benchmark (§11) from Phase 3 onward.
8. **Privacy by default.** Only Groq is used unless the user opts into another provider in `MODEL_POOL` (some free providers may train on prompts); `PRIVATE_SAFE=true` blocks anything else.

---

## 4. Workflows (what the product does)

| # | Workflow | Input | Output | Priority |
|---|---|---|---|---|
| W1 | **Critique a paper** | PDF, pasted text, or arXiv ID/DOI (fetched from allowlisted hosts) | Evidence Pack + Review Card + conference-style review letter + JSON/Markdown | Must |
| W2 | **Explore a research idea** | Idea text, constraints (compute, time, data), cutoff | Formalized falsifiable question, assumptions, closest prior work, gaps, baselines, metrics, ablations, threats to validity, smallest viable study, feasibility; empirical results `not_applicable` | Must |
| W3 | **Project library + cited Q&A** | Papers added to a project (ingested once, chunked, embedded, reused across runs) + a question | Answer built only from quoted passages with exact locators; "not found in library" when unsupported | Must |
| W4 | **Draft related work with verified citations** | Topic/outline + library or search results | Section where every citation sentence is tied to a quote from a verified source; BibTeX of verified metadata only; unverified candidates listed separately | Must |
| W5 | **Revision loop / review diff** | New version of a paper or draft | Findings classified resolved / persisting / new vs previous run; change summary | Must |
| W6 | **Rebuttal helper** | Reviewer comment + paper | Relevant passages with locators + draft response skeleton (no invented results) | Stretch |

All run under one authenticated app with shared history, exports and cancel/retry.

---

## 5. Architecture (course invariants preserved)

```
React UI / CLI / PaperLens-MCP (for assistants)
        │ REST /api/v1
     FastAPI ── Postgres+pgvector (state, library, vectors, audit, quota)
        │ outbox
  CrewAI Flow worker ──A2A──▶ ADK Literature agent ──MCP──▶ MCP Tool Server
        │ (MCP client)                                         ▲
        └──────────────────────────MCP──────────────────────────┘
```

- **Seven logical roles** (exactly): Orchestrator, Novelty & Gap, Methodology & Feasibility, Dataset & Evidence (CrewAI), Limitations & Critique (CrewAI), Communication (CrewAI), Literature Retrieval (ADK). The **Audit Engine is deterministic code behind MCP tools, not an eighth agent.**
- **Framework split:** CrewAI Flow = orchestration/review/critique/synthesis; ADK = literature retrieval only; A2A between them (official SDKs, Agent Card discovery, typed artifacts); Streamable-HTTP MCP for tools. Separate Python projects/lockfiles/images per service.
- **Internal MCP tools** (`services/mcp_tools`): `parse_document`, `extract_tables`, `search_literature`, `fetch_paper_evidence`, `lookup_paper_metadata`, `search_evidence`, `verify_references`, `check_statistics`, `check_numeric_claims`, `reproducibility_checklist`, `find_uncited_close_work`. Orchestrator/specialists call checker tools; ADK calls retrieval tools. Authorized object ids only, never paths/URLs.
- **PaperLens as an MCP server for assistants** (`apps/assistant_mcp`, Streamable HTTP + stdio): tools `review_paper`, `explore_idea`, `get_run`, `get_evidence_pack`, `ask_library`, `add_to_library`, `check_references`, `draft_related_work`, `diff_runs`. Uses per-user API tokens (hashed in DB) that the user creates in the UI. Also a CLI: `paperlens review paper.pdf --depth standard --out review.md`, `paperlens ask "<q>" --project X`. Same API underneath.
- **Database:** Postgres 16 + pgvector in Compose. Embeddings: `fastembed` ONNX `BAAI/bge-small-en-v1.5` (384-d) baked into the MCP image (log deviation from MiniLM in ADR).
- **Auth:** built-in email+password (argon2id), invite-code registration (`INVITE_CODE` generated by bootstrap), signed HttpOnly session cookie + CSRF header, per-user API tokens for CLI/MCP, owner scoping on every row. `AUTH_MODE=dev` only when `PAPERLENS_ENV=local`.
- **Service-to-service:** Compose-internal network, no published ports except the API; `SERVICE_TOKEN` bearer between services.
- **Observability:** OpenTelemetry W3C trace context across API→worker→A2A→ADK→MCP; `audit_events` table always on; Langfuse Cloud Hobby (free) if keys given, else local Jaeger.

---

## 6. Deterministic Audit Engine (the quality backbone; build before the LLM pipeline)

All implemented in `services/mcp_tools/audit/`, pure Python, unit-tested on known cases. Each check returns `{check_id, status: pass|fail|inconclusive|not_applicable, details, evidence_refs, confidence, method}`. Inconclusive is a first-class result; the engine must never guess.

1. **Structure parsing:** sections, headings, abstract, reference list, captions, table regions (pdfplumber tables with confidence; unparseable tables flagged "not assessed"), page/char locators. Detect low-text/scanned PDFs → `needs_input`.
2. **Reference verification:** parse the bibliography; resolve each entry by DOI → arXiv ID → Crossref/OpenAlex title+year+author fuzzy match. Classify `verified | ambiguous | not_found | year_mismatch | retracted` (OpenAlex retraction flag). Output wording: "could not verify", never "fabricated". Also in-text citation ↔ reference-list integrity (cited key missing from list, listed but never cited).
3. **Statistical consistency (statcheck-style):** regex-extract APA/ML-style test reports (`t(28)=2.10, p=.045`, `F`, `χ²`, `z`, `r`); recompute p with SciPy; flag mismatches beyond rounding tolerance; flag "p<.05" claims with no test reported; GRIM test for means of integer data when n is known; percentage vs count consistency; table column sums/percent totals.
4. **Numeric claim ↔ table check:** extract numeric claims in text ("improves by 2.3 points", "reduces error by 15%") and recompute from parsed table cells; flag "best" bolding vs numbers; abstract numbers vs results numbers. Report match/mismatch/not-locatable.
5. **Reproducibility checklist** (keyword/regex + LLM confirmation only where ambiguous): code/data link, license, hyperparameters, seeds, number of runs, variance/CI/significance test, compute/hardware, dataset splits and selection procedure, baselines' tuning, ablations. Each item `present | absent | not_reported | not_assessable` with locators. "Not reported in the provided sections", never "not done".
6. **Hygiene heuristics:** text mentions of tuning/selection on test data, single-seed claims of superiority, missing statistical test next to "significant/significantly", overclaim terms without evidence ("state-of-the-art", "robust", "generalizes") flagged for the specialists.
7. **Uncited close work:** retrieve eligible literature (ADK, A2A), compare to the paper's reference list by normalized id/title; list high-similarity works **not** cited, labeled `candidate_missing_comparison` (a prompt for the author, not an accusation).
8. **Dates/cutoff:** first-availability vs assessment cutoff; own-preprint/version exclusion from prior-work.

The Evidence Pack = outputs of 1–8 + claim-ledger candidates (§7 step 2).

---

## 7. LLM pipeline: token-tiered, quota-aware

**Free Groq reality (checked 21 Nov 2026; re-verify from `x-ratelimit-*` headers):** per-model, org-wide limits; `openai/gpt-oss-120b` and `gpt-oss-20b` ≈ 8K tokens/min, 200K/day, 30 req/min, 1K req/day; `llama-3.3-70b-versatile` ≈ 12K TPM/100K TPD; `llama-3.1-8b-instant` has a much larger daily request allowance. Quotas are independent per model, so work is **spread across models**.

**Model pool (`MODEL_POOL`, verified in Phase 1, configurable, ladder fallback on 429):**
- Map/extraction (claims per section, checklist confirmation, query planning): `llama-3.1-8b-instant`
- Specialists: Novelty → `openai/gpt-oss-120b`; Methodology → `llama-3.3-70b-versatile`; Dataset & Evidence → `openai/gpt-oss-20b`
- Critic, closure, synthesis, writing tasks: `openai/gpt-oss-120b`
- Additional OpenAI-compatible providers may be added to the pool by config but are disabled by default (`PRIVATE_SAFE=true`).

**Pipeline stages (Review, standard depth):**
1. Parse + Audit Engine (0 tokens) → Evidence Pack v1 published immediately.
2. **Claim ledger extraction (map step, small model):** per section (~1.5k tokens each), extract claims `{claim_id, text, locator, type: contribution|empirical|method|limitation}`; merge duplicates deterministically; keep ≤25. Then **claim↔evidence linking** by hybrid retrieval over the paper's own chunks (tables/results) → each claim gets candidate supporting passages and any audit-check hits.
3. Orchestrator builds `ReviewPlan` (claims, questions, ≤3 queries, cutoff) and delegates literature to ADK over A2A → frozen `EvidenceBundle`.
4. Three specialists work independently on **(claim, evidence-snippet, audit-result)** pairs, not full text; each returns an `AgentReviewBundle`.
5. Critic: ≤6 challenges (≤2/owner; empty is valid) → one owner response each → closure (no new challenges). Hard round guard in code and DB.
6. Validation gate (schema, spans, dimension uniqueness, score consistency) → code-computed scores/recommendation.
7. Communication agent writes the Review Card + review letter from validated material only; post-validation rejects invented ids, altered quotes, dropped critical objections, changed scores.

**Depth levels** (user-selectable; the UI shows estimated tokens and waiting time):

| Depth | What changes | Approx. tokens |
|---|---|---|
| quick | Audit Engine + claim ledger from abstract/intro/conclusion; one generalist pass; no critique | ~20k |
| standard (default) | Full pipeline above | ~60–70k, ≤28 model attempts |
| deep | More chunks per specialist, up to 5 full-text prior works, second pass on top issues; may span a day via `quota_wait` | ~120k |

**Quota Governor** (`packages/paperlens_core/quota.py`, used by every model call from CrewAI, ADK and the benchmark): persistent counters in Postgres (`quota_usage`, shared by all containers); calibrate from response headers; atomic pre-call reservation (prompt estimate + `max_tokens`); sleep ≤60 s for minute buckets; try next model in the ladder; if all exhausted set run status `quota_wait` with `resume_after`, release the lease, resume at the last checkpoint. Framework retries disabled (`max_retry_limit=0`, LiteLLM `num_retries=0`); honor `Retry-After`; count format repairs. LLM response cache keyed by hash(model, params, messages) scoped per owner (dev/tests/benchmark rerun savings). Compact prompts: no schema dump, JSON mode + Pydantic + one repair, `reasoning_effort=low`, strict `max_tokens`. Admission: 1 active run per user, 1 running globally; UI shows queue position.

---

## 8. Specs (condensed contracts, rubric, limits, states, persistence)

### 8.1 Contracts (`packages/paperlens_core/models.py`)
Pydantic v2, `extra="forbid"`, `schema_version="1"`. Control fields (run_id, owner_id, finding_id, source/chunk ids, scores) are server-assigned/verified, never model-generated.
- `Locator{kind: page|paragraph, number, section, char_start, char_end}`; `Chunk{chunk_id, source_id, parent_id, text, norm_text, locator, content_hash}`; `SourceRecord{source_id, kind: submission|literature|library, provider, provider_id, doi, arxiv_id, title, authors, published, first_available, url, retrieved_at, content_hash, access_status: full_text|abstract_only|user_submission, eligible, ineligible_reason}`.
- `EvidenceBundle{bundle_id, run_id, cutoff, queries, sources, chunks, rankings, provider_errors, coverage: complete|partial|none, bundle_hash, frozen}`; `EvidenceRef{source_id, chunk_id, quote, char_start, char_end}`.
- `AuditResult{check_id, status, details, evidence, confidence, method}`; `EvidencePack{run_id, structure, claim_ledger, audits[], references[], checklist[], candidate_missing_comparisons[], not_assessed[]}`.
- `Claim{claim_id, text, locator, type, linked_evidence[], audit_hits[], verdict: supported|partially_supported|unsupported|not_assessable (set by specialists/code, never by the extractor)}`.
- `Finding{finding_id, owner, dimension, version, claim_ids[], claim, rationale, status: supported|inference|unverified, basis: observed|code_verified|supported_comparison|inference, severity: info|minor|major, confidence 0–1, evidence[], uncertainty, suggested_action, prior_version_id, retracted}`; `supported`/`inference` need ≥1 evidence.
- `DimensionReview{dimension, assessability: assessed|insufficient_evidence|not_applicable, score 1–5 only if assessed else null, findings, uncertainty, rubric_version}`; `AgentReviewBundle{agent, reviews}` (novelty owns novelty; methodology owns methodology+reproducibility; evidence owns evidence; idea mode swaps reproducibility→feasibility, evidence `not_applicable`).
- `Challenge{challenge_id, round=1, owner, target: {finding_id, version} | {omission: text}, concern, required_resolution}`; `CritiqueBatch{≤6, ≤2/owner, may be empty}`; `RevisionResponse{challenge_id, decision: defend|revise|retract|unresolved, reason, revised_finding}` (`revise` without valid finding ⇒ `unresolved`); `CritiqueClosure{dispositions: challenge_id→accepted|rejected|unresolved, unresolved_notes}` covering every challenge exactly once.
- `ReviewReport{run_id, mode, report_version, title, review_card (≤8 ranked findings), executive_assessment, claim_ledger, dimensions, comparison_table, prioritized_actions, questions_for_authors, suggested_experiments, unresolved_objections, critique_history, not_assessed, citations, rubric_index, recommendation, quality: complete|limited_evidence, execution_metadata}`; `ErrorEnvelope{code, message, retryable, correlation_id}`.
- `Draft{draft_id, kind: related_work|brief, sections[{text, sentences[{text, claim_type, evidence: EvidenceRef[], citation_keys[]}]}], bibtex, unverified_candidates[]}`; a sentence with a citation key but no valid evidence is rejected.
- `RunDiff{base_run_id, new_run_id, resolved[], persisting[], new[], changed_scores}` (match by claim similarity + locator + dimension).

### 8.2 Citation validation (deterministic)
Each `EvidenceRef` resolves to a chunk in the run's frozen bundle/submission/library, owned by that user, with `norm_text[char_start:char_end] == normalize(quote)`, quote ≥20 chars (or equals a shorter chunk), matching `source_id`. Reject fabricated ids, altered quotes, cross-owner chunks. Quote existence ≠ semantic support (critic and humans judge support). `unverified` findings cannot drive scores or the executive assessment.

### 8.3 Rubric (`rubrics/paper_v1.md`, `rubrics/idea_v1.md`)
Scores 1–5 only when assessed; null otherwise. Weak retrieval is a coverage problem, not low novelty.

| Dim | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Novelty | Central contribution substantially overlaps eligible prior work, no supported distinction | Overlap, thin distinctions | Some distinction, material overlap | Clear distinction from most close work | Clear supported distinction with adequate coverage |
| Methodology | Documented flaws undermine main conclusion | Major control/baseline gaps | Plausible, material gaps | Sound, minor gaps | Appropriate design/comparisons/assumptions |
| Evidence | Results fail to support central claims | Weak partial support | Partial, material uncertainty | Mostly supported, minor missing checks | Supports scoped claims with uncertainty checks |
| Reproducibility | Omissions prevent reproduction | Key details mostly missing | Procedure clear, key details missing | Minor omissions | Sufficient procedure and artifacts |

Rubric index (only if all four assessed): `20*(0.30*nov+0.30*meth+0.25*evid+0.15*repro)`, range 20–100, "rubric index" not acceptance probability. Recommendation (code only): `insufficient_evidence` if any dimension unassessable or a critical objection blocks assessment; else `revision_recommended` if an unresolved major issue or score ≤2; else `ready_for_further_expert_review`. Idea mode has its own versioned rubric, never compared numerically with paper mode.

### 8.4 Limits (config-driven)
PDF 20 MB/30 pages; pasted text 150,000 chars; 3 initial queries; 6 search tool calls and 18 provider HTTP attempts/run; 30 candidates → ≤12 retained → ≤3 full texts (standard); 1 critique round; ≤6 challenges, ≤2/owner; 1 response per challenged owner; concurrency across different models ≤3, same model 1; standard: ≤28 model attempts and 70k tokens/run; 1 repair per output; app deadline 25 min excluding `quota_wait`; library ≤200 papers/user; Neon-style size concerns not applicable locally but retention default 30 days for private artifacts.

### 8.5 State machine
Stages: `queued → parsing → auditing → claim_extraction → planning → retrieving → reviewing → challenging → revising → closing → validating → synthesizing → publishing → completed`. Status: `queued | running | quota_wait | needs_input | failed | cancelling | cancelled | completed | evidence_pack_ready` (the last is a sub-state shown while the Full Review continues).

| Event | Behavior |
|---|---|
| Empty/unreadable extraction | `needs_input`, zero model calls |
| Search ok, no eligible literature | Continue, `coverage=none`, novelty `insufficient_evidence` |
| All providers fail | Bounded retry, then `failed` (retryable); never claim "no prior work" |
| Quota exhausted for all models | `quota_wait` + `resume_after`; Evidence Pack stays available |
| Specialist fails after repair | Run `failed`, checkpoint kept, no partial-looking report |
| No challenges | Persist empty batch, skip owner calls, deterministic empty closure |
| Owner invalid/timeout | Keep original finding + `unresolved` objection |
| Closure fails | Deterministic all-`unresolved` fallback, disclosed |
| Synthesis adds unsupported content | Reject, one repair, else fail publish (Evidence Pack still delivered) |
| Cancel | Persist first; stop new calls; discard late results |
| Telemetry down | Continue; audit trail remains |
| Worker dies | Another worker reacquires lease after expiry, resumes matching checkpoint |

### 8.6 Persistence (Alembic; every user row has `owner_id`)
`users, api_tokens, projects, project_papers, submissions, review_runs (status, stage, state_version, lease_token, lease_expires_at, fencing, parent_run_id, idempotency_key, request_hash, deadline_at, resume_after, cancel_requested, depth), run_checkpoints (UNIQUE run_id+stage+branch+input_hash+config_version), documents, document_chunks (embedding vector(384), tsvector, parent_id, library flag), run_sources, evidence_bundles, evidence_packs, claims, findings, finding_versions, challenges, responses, critique_rounds (UNIQUE run_id+round, CHECK round=1), reports, drafts, run_diffs, audit_events (append-only), provider_cache (public metadata only), a2a_tasks, model_calls, quota_usage, llm_cache, dispatch_outbox`. Accepted stage output + next state version in **one transaction**. Leases: `UPDATE … SET lease_token, lease_expires_at=now()+90s, fencing=fencing+1 WHERE id=:id AND (lease_expires_at IS NULL OR lease_expires_at<now()) RETURNING fencing`; heartbeat 30 s; every write checks `fencing` and `state_version`. Parallel specialists return separate artifacts; the coordinator merges once after the join. Library papers are ingested once and reused by W1–W5.

---

## 9. What the outputs look like (UX contract)

**Review Card (top of report):** one-paragraph assessment with explicit confidence; recommendation label; four dimension chips (score or "insufficient evidence"); **Top ≤8 issues**, each with severity, confidence, basis tag (`code-verified` / `observed` / `supported comparison` / `inference`), one-sentence fix, and a clickable quote; "What I did not check" list.
**Below:** Claim ledger table (claim → verdict → evidence → audit hits); Audit panel (references verified x/y with list of unverified, statistics checks, numeric-claim checks, reproducibility checklist matrix); Closest prior work table + `candidate_missing_comparison` list; Critique timeline (original → challenge → response → revision → disposition); Questions for authors; Suggested experiments/ablations; Execution panel (models, tokens, fallbacks, waiting time, cost = "$0 free tier" plus equivalent paid cost for the report).
**Exports:** Markdown, JSON, **Evidence Pack JSON**, conference-style review letter (summary, strengths, weaknesses, questions, minor issues, confidence), BibTeX (verified metadata only), Draft Markdown.

---

## 10. Interfaces

- **Web UI (React + TS + Vite + Tailwind):** sign-in/register; workspace with Projects and Library; New run (W1/W2, depth selector with token/wait estimate, arXiv ID/DOI/PDF/paste, cutoff with explanation, idea constraints); Run view (live stages from `/events`, Evidence Pack appears first, quota-wait banner with resume time, cancel); Report view (§9) with evidence drawer; Ask-the-library (W3); Draft studio (W4: topic/outline → draft with per-sentence citations, BibTeX export); Diff view (W5); History; API tokens page (for CLI/MCP). Accessibility: labels, keyboard, focus, contrast, non-color status. Sanitized Markdown, `rel="noopener noreferrer"`. API types generated from OpenAPI.
- **REST** under `/api/v1`: `auth/*`, `tokens`, `projects`, `library/papers`, `submissions`, `reviews` (Idempotency-Key, 202), `reviews/{id}`, `/events`, `/evidence-pack`, `/report`, `/sources/{sid}/chunks/{cid}`, `/export?format=`, `/cancel`, `/refine`, `reviews/{id}/diff?base=`, `library/ask`, `drafts`, `health/live|ready`. Status codes 401, 403/non-disclosing 404, 409, 413, 422, 429.
- **CLI** (`apps/cli`, `uv tool`-installable) and **assistant MCP** (§5) wrap the same REST API.
- Legacy static UI at `/legacy` until React parity, then deleted.

---

## 11. Quality system (runs from Phase 3 onward; `scripts/quality.ps1`)

Quality is measured automatically, without waiting for human labels, then confirmed by a small human check.

**Q1. Seeded-flaw benchmark (mutation testing).** Take 8–10 open-access empirical CS/AI papers (license/hash in `evaluation/manifest.json`, split dev/held-out). Create mutated variants (text-level, with tables as text; regenerate PDFs from mutated text for a subset) with **known injected flaws**: M1 text number ≠ table number; M2 removed baseline row/sentence; M3 "hyperparameters tuned on the test set"; M4 inflated claim ("significantly outperforms") with no test; M5 fabricated reference (invented title/DOI); M6 p-value inconsistent with reported statistic; M7 removed seeds/code/variance details; M8 removed citation to the closest prior work while claiming novelty; M9 citation of a retracted paper (pick from OpenAlex retraction flag at runtime); M10 percentages that do not sum. Metrics: **recall per flaw type**, **false positives on the unmutated originals**, citation validity. Targets (report actuals): deterministic types M1, M5, M6, M7, M9, M10 ≥90% recall; LLM-dependent types M2, M3, M4, M8 ≥60%; ≤1 high-severity unverified/false finding per clean paper (median); 100% citation validity.
**Q2. Retrospective retrieval benchmark.** For each paper P, set the cutoff just before P's first availability, search with P's abstract only, measure **recall@10 against P's own reference list** (and against its top-cited references). Targets: report actuals; use to tune queries/RRF.
**Q3. Golden regression suite.** Store sanitized outputs for 5 papers; any prompt/model/ranking change must not reduce Q1/Q2 scores or change the Review Card's top issues without an explained diff. Fixture-mode LLM responses (cache) keep this cheap.
**Q4. Self-consistency.** Re-run 2 papers ×3: report the overlap of top-8 issues (Jaccard) and score variance.
**Q5. Ablations (reduced):** B0 single reviewer/no retrieval/no audit; B1 + retrieval; B2 three specialists + audit, no critique; B3 full. 6 held-out papers × 4 conditions × 1 attempt (+ repeats on 2). Report tokens, waiting time, equivalent paid cost, per-paper results, paper-level resampling for uncertainty. State the small sample.
**Q6. Draft quality:** per-sentence citation validity 100% by validator; human spot check of 20 sentences for semantic support.
**Q7. Human check (small, honest):** two team members independently rate 5 reviews each (are top issues valid? anything important missed? any false claim?); record agreement. Optional reference: public OpenReview reviews of the same papers for manual comparison only (respect their terms; no scraping at scale). No LLM-as-ground-truth.

Quota note: the benchmark must be resumable, cache LLM responses, and run over several days through the Quota Governor.

---

## 12. Phases (each: tests green, `docs/evidence/<phase>.md`, status updated)

**Phase 0 — Stabilize + scaffolding (1 day).** `scripts/bootstrap.ps1` (checks Python/uv/Node/Docker; creates `.env` generating `JWT_SECRET`, `INVITE_CODE`, `SERVICE_TOKEN`, `POSTGRES_PASSWORD`; prompts only for `GROQ_API_KEY`), `check.ps1`, `dev.ps1`, `migrate.ps1`, `smoke.ps1`, `quality.ps1`. Fix §1 defects 1,2,6–10 in the prototype; move it to `legacy/` with tests green; add CI (fixtures only, `.github/workflows/ci.yml`). Docker not running ⇒ `blocked`, continue natively.

**Phase 1 — Interop spike + Groq verification (3 days).** Real separate processes: CrewAI task → official `a2a-sdk` client → ADK agent → MCP `search_literature`; CrewAI → MCP `parse_document`. ADK uses `McpToolset` (Streamable HTTP, `tool_filter`), captures raw tool output in `after_tool_callback`, assembles `EvidenceBundle` in code (LLM only plans queries/one reformulation, on `llama-3.1-8b-instant`). Thin CrewAI `BaseTool` wraps the A2A client (discover allowlisted card, verify skill/transport, persist task/message ids, validate artifact). Measure per Groq model: tool calling, JSON mode, usage, rate-limit headers, 429 behavior → `docs/compatibility.md`; tune `MODEL_POOL`. Prototype the Quota Governor and use it in both frameworks. OTel `traceparent` across A2A/MCP. Negative tests: malformed A2A payload and malformed MCP result rejected. Per-service `pyproject.toml`+`uv.lock`; exact versions recorded. `scripts/test_m0_spike.ps1`. **Gate:** `docs/evidence/m0.md` with real output and trace. Fixture-only ≠ pass.

**Phase 2 — Audit Engine + ingestion + evidence + DB (6 days).** `packages/paperlens_core` models/validators/rubric/scoring/quota; Alembic migrations (§8.6); object store; MCP tools of §5 including all of §6 (build checkers test-first on synthetic cases: known p-value mismatches, GRIM examples, table sum errors, fake/real references, retracted-record fixtures). Ingestion: `%PDF-` signature, size, encryption, pages, readability, low-text → `needs_input`; section-aware parent chunks (~500–800 tokens) + embedding sub-chunks sized to the tokenizer (no silent truncation); pasted text → paragraph/char locators; arXiv ID/DOI fetch through safe-fetch (allowlist `arxiv.org`, `export.arxiv.org`, `api.openalex.org`, `api.crossref.org`; HTTPS only; no URL credentials; revalidate redirects and resolved IPs; block private/loopback/link-local/metadata; ≤3 redirects; byte/MIME/time caps). Providers: arXiv (rate limit, `Retry-After`, quoted/field-scoped queries) and OpenAlex/Crossref (free; key/mailto per current docs). Dedup DOI → arXiv family → fuzzy title; exclude the submission's own versions; unknown dates ineligible; later work only as labeled retrospective context. Hybrid retrieval: Postgres FTS + pgvector with RRF (k=60, versioned). Library ingestion once, reused. Freeze `EvidenceBundle` with hash; ADK returns it over A2A. **Gate:** Evidence Pack produced for a fixture PDF with zero LLM calls; citation spans resolve exactly; all audit unit tests pass; cross-owner retrieval denied.

**Phase 3 — Review pipeline: claim ledger, specialists, validation, report (6 days).** CrewAI Flow with typed `ReviewState` and transactional per-stage checkpoints (reuse only on exact input-hash/config match). Roles with `output_pydantic`, function guardrails, callbacks → `audit_events` + trace. Claim extraction (map step) and claim↔evidence linking (§7). Orchestrator → `ReviewPlan`; A2A literature delegation (Flow refuses to advance without a validated A2A result). Three independent specialists on (claim, evidence, audit) pairs with different models; Communication agent for Review Card/letter; validators; code scoring; renderers (JSON/Markdown/Evidence Pack/letter) from the same report object; idea-mode prompts/rubric. Versioned `prompts/` (source text is untrusted data). All calls via the Quota Governor; ledger totals reconcile with provider usage. **Gate:** real run on a public arXiv paper → schema-valid report, 100% citation resolution, forged citation rejected, Evidence Pack delivered before the Full Review, and **first `quality.ps1` Q1/Q2 baseline recorded**.

**Phase 4 — Critique, recovery, quota_wait (4 days).** Critic/owner response/closure per §7 with immutable `finding_versions`; round guard in code and DB; leases/fencing; cancellation (late results discarded); `quota_wait` pause/resume; reconciler loop. Fault injection: reviewer failure, owner timeout, malformed closure, 429, telemetry outage, kill worker mid-stage, exhaust quota mid-run then resume. **Gate:** one run shows original→challenged→revised finding with history; empty-challenge run completes; no second round possible; no double-publish; Q1–Q3 do not regress.

**Phase 5 — API, auth, library, writing tools, diff (5 days).** REST of §10; built-in auth, tokens, CSRF, login rate limit; outbox dispatch (local polling worker with `FOR UPDATE SKIP LOCKED`); projects/library; W3 cited Q&A (retrieve → answer from quotes → validator; "not found in library" when unsupported); W4 draft generation (per-sentence evidence, BibTeX from verified metadata, unverified candidates separate); W5 `RunDiff`; W2 idea mode finalized; admission/retention. **Gate:** security tests (cross-owner on every route, forged ids, oversize/corrupt PDF, idempotency, brute force, CSRF); Q6 automatic validity 100%.

**Phase 6 — React UI (5 days).** All views of §10 against the live API; Playwright E2E (register → upload → Evidence Pack appears → Full Review → open drawer → export; idea → refine; Ask-library; Draft; Diff; cancel; quota-wait banner). **Gate:** typecheck + build + Vitest + Playwright green on the local stack.

**Phase 7 — Assistant interfaces (2 days).** CLI and `apps/assistant_mcp` (§5) with API tokens; documented usage snippets for Claude/Codex MCP configuration; contract tests via a real MCP client; `get_evidence_pack` returns compact JSON suited to an LLM context. **Gate:** from a separate process, an MCP client submits a PDF, polls, and retrieves the Evidence Pack and Review Card.

**Phase 8 — Observability + local E2E hardening (2 days).** One instrumentation path per framework; manual spans for A2A/MCP; `traceparent` end to end; audit fields; provenance chain finding→version→prompt version→chunk→source hash→query/time; secret redaction; Langfuse volume sampling (<50k units/month) or Jaeger. Compose healthchecks, named volumes, 127.0.0.1 binding, memory limits fitting a 6 GB Docker VM. **Gate:** fresh clone → `bootstrap.ps1` → `dev.ps1` → full workflows work; kill worker → resume; quota exhaustion → `quota_wait` → resume; run completes with telemetry off.

**Phase 9 — Quality iteration (4–6 days + human check).** Run Q1–Q7; inspect failures; improve extractors, prompts, ranking, query building; re-run until targets or honest plateau; freeze prompts before held-out numbers; write `docs/evidence/quality.md` with per-paper, per-flaw tables, ablations, self-consistency, human-check results, and failure analysis. Do not tune on held-out papers; report contamination if it happens.

**Phase 10 — Docs and packaging (3 days).** README with only tested commands; `docs/USER_SETUP.md`; decisions, compatibility, operations (local), evaluation protocol, evidence per phase, contributions log; Mermaid diagrams (architecture, A2A sequence, MCP, data flow); report material mapped to the course template (Introduction, Problem Statement, Literature Review, Methodology, Technology Stack, Experimental Results, Team Matrix, Conclusions, References, Appendix) without fabricated competitor research/results/contributions; demo script and a genuine recorded demo; secret scan (`gitleaks`); public-repo candidate prepared, **publish only on user authorization**. Contribution matrix filled only from real commits: Mohammad Yakub (230477) Flow/state/API/A2A client; Himanshi Chaturvedi (230474) ADK/MCP/audit engine/ranking; Ananya Pandey (230472) specialists/critic/UI. Respect the course AI-assistance policy.

**Phase 11 — Deployment (DEFERRED; do not start until the user says so).** Prepared options only: Cloudflare quick tunnel to the local stack; Render free + Neon free single-container variant; keep-alive notes. No paid services.

---

## 13. Test inventory

Contracts (extra fields, duplicate/missing dimensions, wrong owner, unknown source, span mismatch, short quote, score/null consistency, all-1⇒20, all-5⇒100, any null⇒no index, round cap, challenge caps, `revise` without finding⇒unresolved, draft sentence without evidence rejected). **Audit Engine** (p-value recompute incl. rounding tolerance, GRIM, table sums, numeric-claim↔table match/mismatch/not-locatable, reference classes verified/ambiguous/not_found/year_mismatch/retracted, in-text↔list integrity, checklist matrix, inconclusive never promoted to fail). Parsing/retrieval (corrupt/encrypted/scanned/oversized PDF, locators, duplicate families, own-preprint exclusion, cutoff, abstract-only, subchunk length, redirect/private-IP blocking). Quota governor (pacing, daily exhaustion→`quota_wait`, ladder fallback, header calibration, shared counters across containers, reservation release on failure). Integration over real transports (MCP, A2A, ADK session, Postgres+pgvector, cache scope). Recovery (duplicate dispatch, expired lease fencing, stale heartbeat, hash mismatch on resume, cancel+late result, 429/timeout, telemetry outage). Security (cross-owner on every route incl. library and tokens, forged ids, PDF prompt injection, malicious Markdown, prohibited fetch targets, secret redaction, dev-auth refused outside local, brute force, CSRF, API token scope). E2E and UI (as Phase 6). Fixtures in CI; live tests need `--live`.

## 13A. Course-guideline compliance matrix (mandatory; Phase 10 report must show proof for each row)

| # | Guideline | Where implemented | Proof to capture |
|---|---|---|---|
| 1 | Context sharing & state | Typed `ReviewState` in the CrewAI Flow (§8.6 checkpoints); `EvidencePack`→`ReviewPlan`→frozen `EvidenceBundle`→specialist inputs→critique→report; ADK keeps its own session and returns state only as a validated A2A artifact | State versions before/after each stage; the EvidenceBundle appearing as specialist input; ADK session record |
| 2 | ≥2 tools via MCP | 11 MCP tools (§5): parser, table extractor, literature search, paper fetch, metadata lookup, evidence search, reference verifier, statistics checker (calculator-style), numeric-claim checker, checklist, uncited-work finder; real Streamable-HTTP client/server calls | MCP discovery output + call logs for `parse_document` and `search_literature` minimum, plus checker calls |
| 3 | Pydantic structured output | All contracts (§8.1) with `extra="forbid"`; `ReviewReport`, `EvidencePack`, `Draft` validated at API, MCP, A2A and task-output boundaries; Markdown/JSON/table renders come from one validated object | JSON schema, a valid report, one deliberately malformed output rejected |
| 4 | Agentic design patterns | See pattern table below | Annotated workflow diagram in the report |
| 5 | Callback monitoring | See callback spec below | `audit_events` rows for a run incl. one real error event |
| 6 | A2A interoperability | CrewAI Orchestrator → official A2A client → ADK Literature agent (Agent Card discovery, typed request/artifact, task/message ids stored in `a2a_tasks`) | Agent Card, message/task ids, validated artifact |
| 7 | Only CrewAI + ADK | CrewAI = Flow/roles; ADK = retrieval agent. FastAPI, Pydantic, MCP SDK, A2A SDK, LiteLLM, SQLAlchemy, OpenTelemetry are libraries, not agent frameworks. The Audit Engine and assistant-MCP/CLI are plain code | Per-service lockfiles/imports showing no other agent framework |
| 8 | Guardrails & validation | See guardrail spec below | Tests: injection in PDF, abusive instruction, malformed tool return, fake citation |
| 9 | Observability / provenance | OpenTelemetry `traceparent` across API→worker→A2A→ADK→MCP→model; Langfuse (free Hobby) or Jaeger; append-only `audit_events`; provenance chain finding→version→prompt version→chunk→source hash→query/time | One correlated trace + lineage query result |
| 10 | End-to-end performance, cost, time | See metrics spec below | Real tables from `scripts/quality.ps1` and `evaluation/perf.md` |

**Pattern table (name these in code docs and the report):** planning (Orchestrator `ReviewPlan`); tool use (MCP checkers/retrieval); agentic retrieval with one bounded reformulation (ADK); routing (mode and depth select the pipeline, deterministic code); parallelization (three independent specialists on different models, joined by the coordinator); orchestrator–workers (Orchestrator → specialists); map–reduce (per-section claim extraction → merged claim ledger); evaluator–optimizer / reflection, bounded (Critic → one owner revision → closure); guarded synthesis (Communication agent + post-validation).

**Callback spec (monitoring):** CrewAI `task_callback`, `step_callback` and event listeners write `audit_events` (start/end, agent, task, tool calls, outputs as hashes + truncated excerpts, durations, tokens, model, attempt, validation outcome); CrewAI task guardrails gate invalid output before downstream use. ADK `before_agent/after_agent`, `before_model/after_model`, `before_tool/after_tool` callbacks record the same fields, validate tool returns, and update retrieval-session state through supported context APIs. Also catch exceptions at execution boundaries (an after-callback alone is not error handling) and store a sanitized `error_code`. Record at least one genuine error event (e.g. provider 429 or malformed tool return) for the report.

**Guardrail spec (security):**
- *Input:* API and Orchestrator validate type/length/MIME/page limits; screen the **user's own instruction fields** (question, constraints, draft outline) for prompt-injection patterns and abusive/toxic language with a documented heuristic or small-model classifier; flag or reject with an actionable message. Quoted toxic or offensive text *inside a paper* must never block an otherwise legitimate review.
- *Untrusted content:* paper text, abstracts and tool results are data only; they can never change tools, endpoints, stage order, budgets or auth. Injection heuristics are an extra layer, not the defense.
- *Tool-return validation callbacks:* every MCP result and A2A artifact is Pydantic-validated (schema, types, byte cap, expected fields) before an agent sees it; malformed results are rejected and logged.
- *Output:* citation/span validator, score/assessability checks, post-synthesis validation, sanitized Markdown, escaped citations, protected external links.
- *System:* ownership checks, safe-fetch allowlist, token/call budgets, secret redaction, rate limits (§5, §8).

**Performance, cost and time spec (guideline 10):** collect per run and aggregate (median, p95, n): wall time per stage; **separate** queue time, `quota_wait` time and active compute time; model calls and tokens per stage/model/fallback; retries and repairs; Evidence Pack latency vs Full Review latency; quality-vs-cost across depths and B0–B3. Cost = actual spend **$0** (free tiers, local infrastructure) plus **equivalent paid cost** = tokens × dated Groq list prices (`LLM_PRICING_JSON`, with date) and an electricity/infrastructure note. Pre-measurement planning estimate, to be replaced by measurements: Evidence Pack under 1–2 min; standard Full Review roughly 6–15 min dominated by free-tier tokens-per-minute pacing; deep may span hours. Frozen-retrieval benchmark latency must never be reported as live end-to-end latency. Results go in `evaluation/perf.md` and the report.

## 14. `.env.example` (names only; bootstrap generates values)

`PAPERLENS_ENV`, `DATABASE_URL`, `POSTGRES_PASSWORD`, `OBJECT_STORE_BACKEND`, `OBJECT_STORE_ROOT`, `GROQ_API_KEY` (**user**), `MODEL_POOL`, `MODEL_LIMITS_JSON`, `LLM_PRICING_JSON` (equivalent-cost reporting only), `PRIVATE_SAFE`, `EMBEDDING_MODEL`, `EMBEDDING_REVISION`, `MCP_SERVER_URL`, `A2A_AGENT_CARD_URL`, `SERVICE_TOKEN`, `JWT_SECRET`, `INVITE_CODE`, `AUTH_MODE`, `COOKIE_SECURE`, `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST` (optional), `OTEL_EXPORTER_OTLP_ENDPOINT`, `MAX_RUN_TOKENS`, `MAX_RUN_MODEL_CALLS`, `MAX_RUN_SECONDS`, `OPENALEX_API_KEY`/`OPENALEX_MAILTO` (optional), `CROSSREF_MAILTO` (optional), `RETENTION_DAYS`. Validate at startup without echoing values; never fall back to fake successful output.

## 15. What the user provides

**Required:** (1) Docker Desktop running (WSL2 backend, ≥6 GB RAM via `%UserProfile%\.wslconfig` `[wsl2] memory=6GB`, then `wsl --shutdown`; ≥15 GB disk; verify `docker version`, `docker compose version`, `docker run --rm hello-world`; no Docker Hub login needed; Codex must run on the same PC or the user runs `scripts\dev.ps1` and pastes output). (2) `GROQ_API_KEY` from a free Groq account with **no payment method**.
**Optional (free, no card):** Langfuse Cloud Hobby keys; OpenAlex key if current docs require one; a few open-access papers for the benchmark manifest (Codex proposes candidates); two teammates for the Q7 human check.
**Never needed:** credit card, cloud account, domain, OAuth client.

## 16. Blockers

| Blocker | Continue with | Report |
|---|---|---|
| Docker not running | Native checks, container files | Compose unverified |
| Groq 429/daily cap | `quota_wait`, cache, fixtures; Evidence Pack still works | Live gate pending reset time |
| Groq model lacks tool calling/JSON | Change `MODEL_POOL` | Measured capability matrix |
| Dependency conflict | Separate envs/images | Exact conflict + attempts |
| Table extraction fails on a PDF | Mark tables `not_assessed`; text checks continue | Which checks were skipped |
| No human raters | Q1–Q6 automatic metrics only | No human-grounded claim |

## 17. Definition of done (each item needs linked evidence)

- [ ] Fresh clone → `bootstrap.ps1` → `dev.ps1` → all workflows W1–W5 work through UI, CLI and assistant MCP at zero cost.
- [ ] Real CrewAI → A2A → ADK → MCP retrieval; real MCP parsing and audit tools.
- [ ] Evidence Pack delivered without LLM; Full Review built on it; quota exhaustion degrades gracefully.
- [ ] Seven roles execute; specialists independent; evidence frozen; one critique round with closure survives retry/restart/cancel.
- [ ] Every published citation/draft sentence resolves to an exact span; "could not verify" wording enforced; not-assessed items always listed.
- [ ] Quality benchmark (Q1–Q7) run, with honest per-flaw, per-paper results and failure analysis; no regressions vs recorded baseline.
- [ ] Built-in auth, owner isolation, safe fetch, quota governor, secret handling tested.
- [ ] Correlated trace and audit trail; provenance from report finding to source hash.
- [ ] React UI covers success, failure, cancel, limited evidence, quota wait, diff, library, drafts, accessibility.
- [ ] README, USER_SETUP, report material, demo + recording, contribution log; secret scan clean; total cost USD 0.
- [ ] All ten course guidelines in §13A have captured proof; the matrix appears in the final report.
- [ ] Deployment either explicitly deferred or done under the zero-cost rules.

## 18. Final response format for Codex

Lead with what can be run now: tested commands, completed phases, verification and quality-benchmark numbers (actual, with denominators), evidence paths, and an explicit list of unmet gates with the exact missing user action. Never say "complete", "production-ready" or "deployed" without live evidence for that gate.
