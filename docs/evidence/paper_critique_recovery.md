# Paper critique and recovery checkpoint

The requested slice follows the paper specialist pipeline. The primary plan labels the critique and recovery section M3.

The CrewAI Flow records the original specialist findings, one challenge batch, a reply batch per challenged specialist, a closure, and the report synthesis. PostgreSQL stores them as append-only records. Finding IDs stay stable across the original and final versions. A supported defense needs an additional eligible citation, and a revision needs verified evidence or explicit uncertainty. Unresolved findings become uncertain in the report. The dashboard displays one closed finding and prefers a revised example when available.

Repeated paper dispatches can supply an owner-scoped `Idempotency-Key`. The queue uses a 30-second fenced lease, renewed every two seconds while a run is active. The run deadline is 15 minutes from submission with at most three claims. A restart can repeat work whose output had yet to reach a checkpoint. The report version and completed status commit together. Cancellation clears the lease and blocks subsequent evidence or report commits.

| Class | Exact command | Observed outcome | Evidence |
| --- | --- | --- | --- |
| Fixture | `docker compose run --build --no-deps --rm review-worker python -m unittest services.review_worker.test_paper_recovery -v` | Exit 0. Five checks passed. A worker subprocess was killed after a specialist reply checkpoint. A replacement lease resumed at closure, produced one revised finding and published one report. The stale lease could not publish. Zero challenges also published. A cancelled run rejected an intentionally delayed A2A fixture response before freezing evidence. The suite also checked concurrent dispatch, challenge caps, expiration and the retry budget. | [PostgreSQL and CrewAI fixtures](../../services/review_worker/test_paper_recovery.py) |
| Fixture | `docker compose run --no-deps --rm review-worker python -m unittest services.review_worker.test_ingestion services.review_worker.test_artifact -v` | Exit 0. Eight ingestion and A2A artifact checks passed, including exact-citation rejection. | [Ingestion fixtures](../../services/review_worker/test_ingestion.py) and [artifact fixtures](../../services/review_worker/test_artifact.py) |
| Fixture | `python -m unittest discover -s tests -v` | Exit 0. Sixteen checks passed. | [Test suite](../../tests) |
| Fixture | `npm test` from `apps/web` | Exit 0. React showed the revised before-and-after example, polled the run, loaded saved exports and opened the cited passage. | [Dashboard fixture](../../apps/web/src/app.test.ts) |
| Local API | `POST /api/v1/reviews` twice with the same `Idempotency-Key`, then with a different body. `POST /api/v1/reviews/{id}/cancel` twice. `GET /api/v1/reviews/{id}/report`. | HTTP 202 with the same run ID twice, 409 on payload conflict, 200 on both cancellations, and 404 for the report. | [Paper API](../../paperlens/paper_api.py) and [dispatch endpoint](../../paperlens/service.py) |

Implementation APIs were checked against the installed worker dependencies and their matching upstream sources. [CrewAI 1.15.44](https://github.com/crewAIInc/crewAI/blob/1.15.44/lib/crewai/src/crewai/crew.py) · [A2A SDK 1.3.1](https://github.com/a2aproject/a2a-python/blob/v1.3.1/src/a2a/client/errors.py)

## Live commands

`docker compose up -d --build web review-worker` built and started the local services. The first invocation of `python scripts/test_paper_review.py "$env:TEMP/paperlens-dpr.pdf" --require-revision` dispatched run `6057ba1f-283f-4c1c-949d-37efb1324806`. Groq throttled requests, and the first critique attempt failed validation before saving a challenge batch. During attempt two, PostgreSQL recorded `challenges` and `reply_novelty`. After `docker compose up -d --no-deps review-worker`, attempt three resumed in critique with both checkpoint records intact. The run exhausted its claim budget when Groq rejected a reply with a missing field and published no report. The reply schema was simplified to return exactly one item per assigned challenge, in assignment order. The worker maps that batch to stable finding IDs and handles provider JSON schema rejection within the attempt budget.

Browser verification stopped when the computer-use tool could not determine the current browser URL. The dashboard's before-and-after presentation passed the DOM fixture.

After `docker compose build review-worker web` and `docker compose up -d --no-deps review-worker web`, the fresh `python scripts/test_paper_review.py "$env:TEMP/paperlens-dpr.pdf" --require-revision` exited 0. Run `61477550-9d60-4684-810a-cb9d503a8789` published report v1 on its first claim. All three original specialist records use frozen bundle `00380106-701b-4094-ac6c-0e8a971a1b7f` and the same digest. Closure recorded six challenges, one revised and five unresolved. The report and JSON export matched exactly. Markdown included the saved report version and the original-to-final critique. A Page 2 citation resolved to passage `e07b3bc6-9875-480b-b6ed-0d055a2ae2e0`, characters 1721–1818.

`docker compose build web` and `docker compose up -d --no-deps web` refreshed the local dashboard. `python scripts/test_paper_review.py "$env:TEMP/paperlens-dpr.pdf" --require-revision --run-id 61477550-9d60-4684-810a-cb9d503a8789` exited 0 against the saved report after that refresh. [Local dashboard run](http://127.0.0.1:8000/?run=61477550-9d60-4684-810a-cb9d503a8789)

The remaining verification gap is the interactive browser check. Open the saved run and look for **Finding before and after critique**. The authenticated release and later workflow remain on the primary plan.
