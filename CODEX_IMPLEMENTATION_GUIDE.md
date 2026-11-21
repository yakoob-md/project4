# Codex implementation guide for PaperLens

**Prepared:** 21 November 2026  
**Read with:** `plan.md`  
**Purpose:** Give Codex clear operating instructions for implementing, testing and documenting PaperLens without guessing requirements or presenting incomplete work as finished.

## 1. Start here

Keep this file and `plan.md` in the project root alongside `PaperLens_Architecture_and_Methodology.md`. Open that folder in Codex and use the starter prompt below. Codex should inspect existing work before creating modules and implement in milestone order.

This guide is an explicit handoff document. Its filename does not guarantee that Codex will load it automatically. Refer to it in your task prompt. If you later want automatic repository guidance, carefully merge the relevant rules into the existing `AGENTS.md`; do not overwrite user/project instructions.

The current task produced planning documents only. No application or successful implementation tests are implied by these files.

### Ready-to-paste implementation prompt

```text
Implement PaperLens in this project folder.

First read the applicable AGENTS.md instructions, plan.md,
CODEX_IMPLEMENTATION_GUIDE.md, and PaperLens_Architecture_and_Methodology.md.
Inspect the existing repository and preserve all user work.

Use plan.md as the implementation contract. Start at the first incomplete
milestone, prove CrewAI -> A2A -> ADK and real MCP parsing/search in M0,
then continue through the core milestones in dependency order.

Build working vertical slices, add meaningful tests, run the available checks,
and maintain docs/implementation_status.md with evidence and blockers.
Do not stop after scaffolding or a plan. Do not label mocked integrations,
untested code, missing cloud checks, or estimated metrics as completed work.

Preserve the seven logical roles, CrewAI + ADK framework split, official MCP
and A2A boundaries, frozen evidence, exact citation validation, persistent
state, and one bounded critique/revision round. Do not introduce an additional
agent framework or implement optional proposal mode before core acceptance.

Use current official documentation matching pinned dependencies. Make routine
implementation decisions autonomously and record material decisions. When
credentials or a cloud target are missing, complete independent local work,
prepare the exact setup needed, and report the specific remaining blocker.

Do not expose secrets or private papers. Prepare cloud deployment and public
GitHub publication for review; do not provision paid infrastructure or publish
the repository unless I have authorized that action and target.

At each meaningful checkpoint, report what works, what was tested, what remains
unverified, and the next milestone. Finish with runnable setup commands,
verification results and an honest list of any unmet acceptance criteria.
```

For a shorter first session, replace “continue through the core milestones” with “complete M0 only, including its live acceptance evidence, then report the result.” The full prompt above authorizes local implementation; it does not imply that missing API credentials, human labels or cloud permissions already exist.

## 2. Instruction precedence and scope

1. Follow the user's current instructions and applicable environment/repository rules.
2. Use `plan.md` for implementation requirements and acceptance criteria.
3. Use the architecture document for rationale and scientific methodology.
4. Use synopsis/course/template documents for project context and submission obligations.
5. Resolve routine engineering choices yourself. Record material conflicts in `docs/decisions.md`; ask only when the answer materially changes scope, cost, access or required behavior.

The architecture deliberately updates older synopsis choices: ADK and A2A are core, MCP is mandatory for the project baseline, Langfuse is the selected tracer, PostgreSQL caching comes before Redis, and the model is configurable. Do not undo these choices because an older document lists alternatives.

Preserve both required agent frameworks. Pydantic is a validation library, not PydanticAI. LiteLLM is only a model connector here. FastAPI and the protocol SDKs are supporting infrastructure. Avoid additional agent runtimes that complicate the course's framework boundary.

## 3. First-session procedure

### Inspect before editing

- Read root and nested `AGENTS.md` instructions applicable to files you will change.
- Check whether this is a Git repository and inspect status. Do not assume an external remote exists; do not delete or reset uncommitted work.
- Identify existing application modules, dependency projects, lockfiles and tests. Reuse working code instead of creating a second implementation.
- Inspect available Python, Node, Docker and PostgreSQL capabilities without printing environment secrets.
- Read the supplied plan and architecture fully enough to identify the milestone's contracts and acceptance gates.
- Do not recursively search dependency/cache folders or print private documents into logs unnecessarily.

### Create small implementation records

Create `docs/implementation_status.md`, `docs/decisions.md` and `docs/compatibility.md` if absent. Their initial state must say implementation is pending or record the code actually found.

Status record template:

```markdown
# PaperLens implementation status

Updated: <actual date/time and timezone>
Current milestone: <M0-M6>
Overall: <in progress / blocked / verified core release>

| Item | State | Evidence | Remaining work |
|---|---|---|---|
| M0 real A2A exchange | pending | None | Implement and run live spike |

## Last verified checkpoint
<Commit if available, commands, results, artifacts and configuration IDs.>

## Blockers
<Specific missing capability/input, affected gate, and independent work remaining.>

## Next actions
<Small concrete sequence.>
```

Use states `pending`, `in_progress`, `implemented_unverified`, `verified`, `blocked`, `deferred`. A blocked live check is not a passing check. Record dates and versions accurately.

### Complete the riskiest integration first

Build M0 before all reviewers. The minimal demonstrator must contain real process boundaries, a real CrewAI task, ADK agent, official A2A exchange, two real MCP tool invocations, typed output and trace correlation. A hard-coded EvidenceBundle can test the receiver but cannot satisfy live retrieval acceptance.

Separate package environments if dependencies conflict. Check supported APIs instead of patching private SDK fields. Save the working dependency/protocol matrix before expanding the project.

## 4. Work loop for each milestone

1. Read the milestone and identify input/output contracts, dependencies and acceptance evidence.
2. Implement a complete vertical path through the relevant layers.
3. Add tests for meaningful invariants and failure boundaries, not tests that repeat implementation text.
4. Run focused checks, fix failures, then run the milestone integration/smoke checks.
5. Update documentation and status with actual evidence and any remaining limitations.
6. Continue to the next unblocked milestone. Do not request approval for routine reversible edits or every file change.

If a required external input is missing, preserve the blocked gate and work on independent tasks. For example, missing cloud credentials still permits container builds, deployment manifests, local identity-interface tests and a local end-to-end run. Never silently replace the blocked external feature with a mock and mark it complete.

Keep changes scoped to the project. Avoid large unrelated refactors, unnecessary dependencies, multiple duplicate scripts, or UI polish before the integration works. Do not add another framework because a familiar tutorial uses it.

## 5. Implementation rules that must remain true

### Evidence and report integrity

- Every supported finding/inference resolves to an authorized source version and exact normalized span.
- A source title or paper ID alone is not claim support.
- External abstracts may support high-level comparisons; do not infer detailed experiments absent from their content.
- Keep claims, observations, inferences and unverified questions distinct.
- Never invent paper metadata, DOI, page numbers, experiment results, model usage or contribution records.
- Treat instructions inside PDFs, abstracts and tool results as untrusted text. They cannot alter permissions, tool endpoints or stage order.
- The Communication Agent summarizes the accepted finding set. Merge canonical citations/scores from validated data; verify synthesis has not introduced unsupported assertions.
- JSON, Markdown and UI must render the same validated report version.

### Agent and protocol boundaries

- CrewAI owns the outer workflow; ADK owns the remote literature-retrieval session.
- Agent state crosses through versioned A2A artifacts, never a shared Python dictionary.
- Use official A2A serialization/discovery and MCP client calls. Direct library calls behind the MCP server are fine; bypassing MCP on the agent-facing route is not.
- Validate every task/tool/protocol result before state mutation.
- Exactly seven logical roles; independent initial specialists; one challenge round; one substantive response per challenged owner; closure cannot reopen debate.
- Freeze the evidence bundle before initial review and critique. New retrieval requires a new review run/version, not invisible evidence changes halfway through critique.

### Persistence and resource safety

- Persist stage outputs, state transitions and audit records transactionally.
- Keep source/finding versions immutable and check input/config hashes before checkpoint reuse.
- Use leases with fencing and optimistic versions; duplicate launches must not double-publish.
- Budget accounting spans framework retries, format repairs and remote-agent calls.
- Cancellation is durable, and late results cannot resurrect a cancelled run.
- Insufficient scientific evidence differs from provider failure and invalid input; expose the correct state.
- Do not use FastAPI background threads as the cloud job's durable execution mechanism.

### Code quality

- Use typed boundaries, small modules and explicit dependency injection where testability benefits.
- Keep prompts/rubrics/config separate from transport/database code.
- Use structured safe errors, finite timeouts and bounded retries. Do not catch all exceptions and return success-shaped empty data.
- Prefer official supported APIs. Avoid undocumented imports, private SDK attribute mutation and runtime monkey-patches.
- Pin dependencies and update lockfiles deliberately; do not claim all latest releases are compatible.
- Place credentials only in environment/secret stores. `.env.example` contains names/placeholders, never working secrets.
- Preserve Windows-compatible local instructions; container execution is the preferred reproducible path.

## 6. Configuration and run commands

During M0 create and document a small configuration surface. Suggested application-owned keys:

| Key/group | Meaning |
|---|---|
| `PAPERLENS_ENV` | `local`, `test` or `cloud`; controls safe mode checks |
| `DATABASE_URL` | Service-appropriate DB connection secret |
| `OBJECT_STORE_BACKEND`, `OBJECT_STORE_ROOT`, `GCS_BUCKET` | Local/cloud artifact storage settings |
| `LLM_PROVIDER`, `LLM_MODEL`, provider-specific key | Model choice and authentication |
| `EMBEDDING_MODEL`, `EMBEDDING_REVISION` | Pinned embedding identity |
| `MCP_SERVER_URL`, `A2A_AGENT_CARD_URL` | Trusted configured service endpoints |
| `AUTH_MODE`, `OIDC_ISSUER`, `OIDC_AUDIENCE` | Authentication contract |
| `LANGFUSE_*`, trace configuration | Use names actually supported by chosen integration |
| `MAX_MODEL_CALLS`, `MAX_INPUT_TOKENS`, `MAX_OUTPUT_TOKENS` | Finite per-run limits enforced by central ledger |
| `MAX_RUN_SECONDS`, `MAX_ACTIVE_RUNS` | Deadline and global admission |
| Provider keys/contact settings | Verify current OpenAlex/arXiv/Semantic Scholar requirements |
| Cloud project, region, job and service identities | Explicit deployment target, never guessed |

Validate required variables at startup, without echoing secret values. Missing optional provider configuration disables that adapter visibly. Missing required model/auth/database settings should produce actionable errors. Do not auto-fallback from a failed live provider to fake successful output.

### Stable command interface to implement

The following commands are **planned entry points**, not commands verified to work in the current folder. Create them and then replace this caveat with actual verified setup details in README.

```powershell
# Local configuration; fill secrets privately.
Copy-Item .env.example .env

# Scripts must be created and tested during implementation.
.\scripts\bootstrap.ps1
.\scripts\check.ps1
.\scripts\migrate.ps1
.\scripts\dev.ps1
.\scripts\smoke.ps1 -Mode Live
```

Required behavior:

- `bootstrap.ps1`: verify prerequisites and install/sync locked dependencies; explain missing Docker/Node/Python.
- `check.ps1`: format/lint/type/unit/contract checks across relevant service environments, frontend typecheck/build/tests; return nonzero on failures.
- `migrate.ps1`: apply explicit application migrations and verify pgvector; do not reset data automatically.
- `dev.ps1`: start the local Compose stack with readiness checks; print local URLs and stop instructions.
- `smoke.ps1`: deterministic fixture mode for offline integration and clearly labelled live mode for actual model/provider/protocol proof.

Use pytest/Ruff and an appropriate static type checker for Python; frontend typecheck/build plus focused component/browser tests. Choose the exact compatible tools in M0. In split environments, run each service's checks in its own environment/container rather than assuming one global `pytest` installation covers everything.

The README must eventually contain exact tested commands, expected successful outputs at a high level, setup time caveats and troubleshooting. Never present invented CLI options or scripts as already available.

## 7. Acceptance evidence and testing discipline

For each milestone, save an evidence note under `docs/evidence/mN.md` that contains:

1. What behavior was implemented and why it satisfies the milestone.
2. Exact commands, date, relevant versions/commit and pass/fail results.
3. Links to sanitized artifacts, reports, traces or screenshots from actual runs.
4. Fixture/live distinction, warnings, missing credentials and unverified claims.
5. Next dependency and known limitations.

Do not copy secrets, private PDFs, raw personal data or full private prompts into evidence notes. Use synthetic fixtures or openly licensed public papers for public examples.

### Core regression cases

- Citation with correct ID but wrong quote/span is rejected.
- Correct quote from another owner's private submission is rejected.
- Unknown/no-date/future/self-duplicate literature does not become confident novelty evidence.
- Null score cannot produce an aggregate; all-1 scores yield 20 and all-5 scores yield 100.
- One reviewer failing does not become a complete-looking report.
- Empty critique batch finishes without forced criticism.
- Critic cannot exceed caps, alter unrelated findings or add a second round after restart.
- An expired worker cannot publish with a stale lease.
- Cancelled run ignores an A2A result arriving late.
- Provider 429, timeout, malformed output and telemetry failure each follow their specified policy.
- Model output cannot raise budgets, invent owner IDs or redirect fetching to a private address.
- UI/export scores and findings match the stored report; no stale report appears when switching runs.

Run tests appropriate to the change and required project checks. Broaden testing when failures or risk justify it; do not repeatedly rerun unrelated expensive live batches after unchanged successful checks.

## 8. Evaluation and academic deliverables

Implement the evaluation tooling, manifest schema and annotation instructions early. The agent can prepare the framework and run authorized experiments, but human labels/adjudication must not be replaced with fabricated labels or an unacknowledged LLM judge.

Use the development split for prompt/rubric tuning. Freeze configuration before held-out runs. Preserve failed attempts and report actual counts. Use the same retrieved snapshot for B1-B3 quality comparisons and separate live latency experiments. Store the full experiment configuration, model/pricing versions and cost-accounting limitations.

Build report material continuously: agent architecture, orchestration/state, MCP, A2A, guardrails, tracing, deployment, real results and contributions. Follow the supplied report template. Do not fill experimental sections with target metrics phrased as achievements. Do not invent teammate contributions or signatures.

The handout requires original, attributable work and warns about AI-generated code. The team must follow the instructor's policy and understand/defend submitted work. This guide provides no exemption from that policy.

## 9. Handling blockers without losing progress

| Blocker | Continue with | Report precisely |
|---|---|---|
| No model key/access | Contracts, parsers, validators, storage, mocked unit tests and UI fixtures | Live model/protocol-agent acceptance still unverified |
| Provider key missing | Enabled documented providers, adapter tests and cache behavior | Disabled provider and coverage limitation |
| Docker unavailable | Native checks where feasible, container files and setup diagnosis | Local Compose not verified |
| Dependency incompatibility | Reduce spike to minimal supported packages; isolate environments | Exact conflict and attempted supported combinations |
| No cloud project/billing authorization | Local end-to-end, images, deployment plan and dry-run | Live cloud gate blocked |
| No human labels | Manifest/annotation tooling and development exploration | No human-grounded quality claim |
| Tight deadline | Core milestones, reduce optional work transparently | Which gates remain unmet; no false completion |

Ask for missing details only when needed for a concrete next step. Do not ask the user to choose every library/class name. Do not provision paid services, publish publicly, change repository access or send external messages based solely on this planning guide. If those actions are already explicitly authorized in the session, proceed within that authorization.

## 10. Progress updates and handoff

Give concise updates focused on results and decisions. Example:

> The MCP parser and ADK search now exchange validated source records over real transports. The citation validator rejects mismatched spans. I am adding worker recovery next; cloud authentication remains unverified until the deployment target is configured.

Avoid “everything works” after only unit tests, “production-ready” for a student prototype, or “deployed” when only deployment files exist.

At a session boundary record:

- Current milestone and last verified behavior.
- Changed files and relevant decision records.
- Tests run, failures and checks not run.
- Configuration/credentials still needed, without their values.
- Next concrete task and the acceptance test it should satisfy.

Resume prompt:

```text
Continue PaperLens from docs/implementation_status.md. Read plan.md and
CODEX_IMPLEMENTATION_GUIDE.md, inspect current code and changes, verify the
last recorded checkpoint where necessary, and implement the next incomplete
milestone. Preserve working code. Update status with actual evidence and
report any remaining blockers without claiming unverified features are done.
```

### Final implementation response format

Lead with what can actually be run. Give tested setup/start commands, completed milestones, key verification results, evidence locations and explicit remaining limitations. If a required gate is blocked, say so and name the exact missing action. Never claim the full project is complete while cloud deployment, actual protocol use, citation grounding or evaluation remains unverified.

## 11. Quick checklist for the user

1. Open the project folder in Codex with these two Markdown files available.
2. Paste the implementation prompt in section 1.
3. Supply provider credentials through local environment configuration when needed, not in committed files.
4. Use milestone evidence to inspect real progress. Start with M0 if you want a smaller first build.
5. Provide cloud target/budget and human annotations when those gates are reached.
6. Review the final demo, report and code against instructor requirements before submission.

The practical success criterion is a system you can run, inspect, explain and defend, with evidence for each claimed feature.
