# Paper review checkpoint

21 November 2026. This checkpoint covers the Docker paper-review path through the normal FastAPI review endpoints. The public input was [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401), downloaded from the arXiv PDF endpoint. The search phrase was `dense passage retrieval` with cutoff `2020-05-21`.

| Class | Exact command or action | Observed result |
| --- | --- | --- |
| Build | `docker compose up -d --build web` | Exit 0. Docker started the web, PostgreSQL, CrewAI worker, ADK and MCP services. The worker applied migration 002. The 1.15.44 CrewAI task schema and async kickoff were also checked in the installed image. [CrewAI task reference](https://docs.crewai.com/v1.15.44/en/concepts/tasks) |
| Live input | `curl.exe -fsSL --max-time 35 https://arxiv.org/pdf/2005.11401 -o "$env:TEMP/paperlens-dpr.pdf"` | Exit 0. PDF SHA-256 `23e3249e9a1e75418d82efecab0ea8c4d033b89c93742f63208d47ce01f21233`. |
| Live | `python scripts/test_paper_review.py "$env:TEMP/paperlens-dpr.pdf"` | Exit 0 on the final run. The multipart upload returned 202, then polling observed queued, ingesting, reviewing, synthesizing and completed. Report v1 had three strengths, three limitations and one uncertain closest-work finding. Communication ranked four revisions. JSON matched the report endpoint, and Markdown contained the same report version and exact cited span. |
| Live persistence | `docker compose exec -T postgres psql -U paperlens -d paperlens -Atc "SELECT j.status,count(s.role),count(DISTINCT s.payload->>'input_sha256'), count(DISTINCT s.payload->>'bundle_id') FROM paperlens_m1.paper_jobs j JOIN paperlens_m1.specialist_reviews s ON s.bundle_id=j.bundle_id AND s.owner_id=j.owner_id WHERE j.id='2a29a26f-70fc-4bba-926f-25d63b4fb649' GROUP BY j.status;"` | Exit 0, `completed\|3\|1\|1`. Each specialist saved an independent record with the same frozen bundle ID and identical bounded evidence input digest. |
| Live restart read | `docker compose build web`, `docker compose up -d --no-deps web`, then `python scripts/test_paper_review.py "$env:TEMP/paperlens-dpr.pdf" --run-id 2a29a26f-70fc-4bba-926f-25d63b4fb649` | Exit 0. Both export formats and the cited passage still resolved to v1 after the web container was recreated. The new React JS and CSS assets each returned HTTP 200. |
| Fixture | `python -m unittest discover -s tests -v` | 16 passed, including required evidence or uncertainty, invalid revision references, and versioned Markdown. |
| Fixture | `powershell -NoProfile -File scripts/test_m1_ingestion.ps1` | 10 passed, including the exact-quote and locator gate. |
| Fixture | `npm test` in `apps/web` | One React DOM test passed. It submitted pasted text, polled completion, displayed the two v1 download links, and opened and highlighted a cited passage. |
| Unverified | Live interactive browser session | The computer-use browser host was unavailable, and the Windows browser fallback could not validate the current URL. Live API smoke and the React DOM fixture cover the underlying calls and controls. |

Run `2a29a26f-70fc-4bba-926f-25d63b4fb649`, bundle `bef9270f-dc87-457a-8a05-e861685e3af0`, version 1, coverage `abstracts_only`. Passage `a3f8e8d8-ea6a-4612-b02c-44f96b73a968` resolved to PDF page 2, extracted offsets `[1721, 1818)`. The quote digest was `4dbea308b41599e433197a9f8debafa4c59ca1f0abd76e6df8e41af245356526`.

For the manual check, the saved citation was fetched from `GET /api/v1/reviews/2a29a26f-70fc-4bba-926f-25d63b4fb649/passages/a3f8e8d8-ea6a-4612-b02c-44f96b73a968?version=1`. A local Python check used PyMuPDF `doc[1].search_for(citation["quote"])` and found one match. I rendered the original page at 144 dpi with that line highlighted and visually compared it with a rendered copy of the report quotation. The text matched in the body paragraph below Figure 1. Only digests and locators are retained here.

Two earlier submissions of the same public PDF informed the fixes. Run `f1c2d9a7-feea-47df-8046-dd1ff54d74dc` stopped during review after a Groq rate limit with two specialist records saved. The worker now retries rate-limit responses with a bounded delay. Run `898617f0-e629-4772-872a-8e87575a6059` published a report but failed the live citation check because model-copied quotations did not match verbatim. The worker now supplies numbered source spans and constructs citations directly from their stored offsets.

### Known extraction gaps

- PDF ingestion reads the text layer. Scans without usable text need OCR. Figures such as the diagram on page 2 have visual relationships that the text stream does not capture. Tables, equations, multi-column layout, ligatures, and line breaks can lose structure during extraction.
- All three specialists receive the same bounded excerpts. Findings can miss material outside the excerpts, and a source span may cross only part of a sentence. A resolvable citation proves text and location. The single manual check did not evaluate whether every finding is justified by its cited text.
- Literature coverage was arXiv abstracts. The closest-work assessment remained explicitly uncertain on this paper. Semantic retrieval has fixture evidence only.

The paper checkpoint is complete. Worker restart recovery, critique, broader literature and extraction work, Langfuse acceptance, and the two-mode release remain open under the plan.

### Review progress follow-up, 22 November 2026

The dashboard now shows eight stages and elapsed time for the active stage. The worker publishes specialist and rate-limit states. Finishing the review opens the saved report automatically, and the run URL and History can reopen it. If the saved report fetch fails, the dashboard offers a reload. A running review has a five-minute worker deadline.

The previously submitted run `40749f60-153d-456c-9983-11e8857b87af` progressed from reviewing to completed without resubmission. Owner-scoped GET requests to `/api/v1/reviews/40749f60-153d-456c-9983-11e8857b87af` and its `/report` subroute returned completed and version 1 with six findings.

| Class | Exact command | Observed outcome |
| --- | --- | --- |
| Build | `docker compose up -d --build --wait web` | Exit 0. PostgreSQL, worker, ADK, MCP and web were healthy. |
| Fixture | `npm test` in `apps/web` | Exit 0. The React test observed a queued run, active methodology stage and retry message, then opened the completed report and citation. |
| Fixture | `python -m unittest discover -s tests -v` | Exit 0, 16 passed. |
| Live | `python scripts/test_paper_review.py "$env:TEMP/paperlens-dpr.pdf"` | Exit 0. Run `3d4bdf62-350b-4146-a289-7211481d088f` showed extraction, retrieval, each of the three specialists, provider retry notices, synthesis and completion. The polling interval skipped the brief publish stage. Report v1 and both exports resolved. |
| Deploy | `docker compose build web` and `docker compose up -d --no-deps --wait web` | Exit 0. The updated dashboard is running locally. |

The interactive browser and forced five-minute deadline were not exercised in this follow-up. The live rate-limit waits resolved and the review completed within the deadline.

### Novelty-stage connection failure, 22 November 2026

- Live `docker compose exec -T review-worker python -c "import httpx; print(httpx.get('https://api.groq.com/openai/v1/models',timeout=5).status_code)"` failed TLS certificate verification. The URL probe used no credentials. The worker logs showed both user attempts failed with a provider connection error at novelty.
- Live `POST /api/v1/reviews/7a008c8f-df3f-470e-83e4-0bb872f4091d/retry` queued the run with bundle `30eeab67-fdd4-4eed-a6d4-a42cd336c868`. The worker reused the bundle and exhausted bounded connection retries. The run returned to failed with a Groq connection message and remained eligible to retry.
- `docker compose build web review-worker` was blocked by an untrusted certificate at the Docker registry. `npm run build` succeeded in `apps/web`. The updated source files and React build were copied to the running containers with `docker compose cp`, then activated with `docker compose restart review-worker web`. The served JavaScript contained the retry control. A full image rebuild remains unverified.
- Fixture `python -m unittest discover -s tests -q` and `npm test` from `apps/web` passed. The next action is to restore trusted connectivity to Groq, retry from saved evidence, and rebuild the images once Docker registry access returns.

The follow-up examined `docker compose logs --tail 220 review-worker`. The latest run (`18517841-607d-4328-856c-b287040ed6e2`) failed with `ConnectionError`. An unauthenticated HTTPX request to Groq from the worker failed TLS validation with and without environment proxy settings. A certificate-only handshake showed the same Sophos issuer on Groq, Docker Hub, and a public control domain. `Get-ChildItem Cert:\LocalMachine\Root,Cert:\CurrentUser\Root` found no Sophos root. The credential was never sent by the diagnostic and the account quota remains unverified. Restoring connectivity requires a trusted network path or the approved organizational certificate chain.

