# ADR-0014: operating and inspecting background jobs

Status: local implementation. Follows bounded retry in ADR-0013; no production rollout.

## Operator workflow

`/jobs` is available to curator/admin. The existing Import screen links to
`/jobs?job=<id>`. The page lists jobs with status/type filters and pagination,
shows the selected job's current stage, counters, last heartbeat, next retry time,
and paginated attempt history. It polls at 3–5 second intervals while visible.
Client/reviewer roles cannot fetch these APIs or operate jobs.

Manual retry requires a terminal `failed` job, an unchanged attempt count, and a
10–1000 character rationale after correcting the cause. It supports only import,
ingest and mining. It preserves payload, source checks and all previous attempts.
It increments `max_attempts` to `attempts + 1`, never resets `attempts`, and grants
exactly one execution, rather than a new automatic retry cycle. Repeated concurrent
requests return one success and one conflict. No running, queued, successful, gold
labeling or unknown job can be manually retried through this endpoint.

`JOB_MANUAL_RETRY_LIMIT` defaults to 3 manual retries per job. This limit is enforced
server-side and displayed in the UI. Operator actions are audited with actor and
job identifiers. Only a SHA-256 rationale digest is stored in the audit snapshot;
operators must not put article/manuscript text or credentials in the reason field.

## Attempt history and progress

`job_attempts` has a unique `(job_id, attempt_no)` and is created in the claim
transaction. It stores start/end time, processing/succeeded/failed/interrupted
outcome, last stage/counters, redacted error code/message, and retry schedule.
Successful output, terminal state, attempt completion, and alert resolution commit
atomically. Failure history is written after the failed output transaction rolls
back, conditional on the current ownership token. Repeated completion is idempotent.

A reclaimed lease closes its earlier attempt as interrupted before starting the
next attempt. Cancellation itself leaves it processing until lease recovery,
matching the queue protocol. Historical jobs are not backfilled with fabricated
attempts or inferred timestamps.

An attempt-scoped progress reporter uses a separate short transaction so the UI
can observe stages before the output commits, and diagnostics survive rollback.
Both job and attempt updates check current job ownership. Stage codes are a fixed
allowlist and counters are validated; source text, URLs, keys and payloads are not
accepted as progress labels. Failed progress delivery logs a redacted warning;
ownership loss rolls back the handler through the existing final fence.

Stages cover input checks, source listing, duplicate/rights checks, download,
import-page persistence, content reading, parsing, sentence persistence, sentence
loading, phrase extraction and candidate persistence. Gold exposes its coarse
labeling stage without changing the labeler's provider/quota semantics.

Counters describe items examined in a particular step, not an estimated percentage
of the full pipeline, durable checkpoints, or newly inserted row counts. An import
page is not the whole batch: its ingest and continuation jobs finish separately.
The terminal job state remains the source of truth for committed output.

## Repeated failure alerts

`JOB_FAILURE_ALERT_THRESHOLD` defaults to 3 recorded failed/interrupted attempts
for a job. This is an in-app persistent alert, not email/Slack notification or a
cross-job failure-rate detector. One alert per job accumulates the observed count.

- Acknowledge records the operator/time but does not resolve an active failure.
- The API checks the expected last-failure timestamp, preventing an old screen
  from acknowledging a newer failure.
- A subsequent failure reopens acknowledgement without creating duplicate alerts.
- A successful retry resolves the alert; history remains queryable with
  `active_only=false`.
- The job row serializes failure accounting; alert acknowledgement locks its own
  row, and both transitions have database-backed tests.

## API additions

- `GET /v1/admin/jobs`: status/type filters, `limit<=200`, offset pagination.
- `GET /v1/admin/jobs/{id}`: adds progress, manual budget and last heartbeat.
- `GET /v1/admin/jobs/{id}/attempts`: paginated history, newest attempt first.
- `POST /v1/admin/jobs/{id}/retry`: `expected_attempts`, `rationale`.
- `GET /v1/admin/job-alerts`: paginated, active alerts by default.
- `POST /v1/admin/job-alerts/{id}/acknowledge`: `expected_last_failed_at`.

Job payloads, ownership tokens and raw exception messages are not exposed by these
new endpoints. OpenAPI and frontend types are generated from the same contracts.

## Migration and acceptance

Drain old workers, back up and migrate through `0013_job_operations` before
starting the new API/worker pair. Mixed old/new workers do not produce consistent
history/progress. Downgrade refuses to drop recorded operations data; use a forward
fix. Existing ignored `.env` and application data are not changed by implementation
tests, which use isolated PostgreSQL schemas.

Manual acceptance on a disposable database:

1. Create an import job against an intentionally unavailable local source. Observe
   automatic attempts in Jobs and a repeated-failure alert at the configured threshold.
2. Acknowledge the alert. Correct the source configuration, restart the worker if
   its environment changed, enter a reason and click **Retry once**.
3. Verify cumulative attempts and old errors remain. A success resolves the alert;
   another failure makes it need attention again. Two clicks cannot queue two attempts.
4. With a deliberately slow source, observe processing progress before the output
   commits. Terminate its worker; after recovery the earlier attempt is interrupted.
5. Repeat with reviewer/client credentials: operational reads/writes return 403.

Tests cover these contracts with real PostgreSQL and UI fixtures. UI fixtures do
not replace a deployment test against an external SLR service. Progress history
stores the last observed step per attempt, not a full timeline of every step event.
