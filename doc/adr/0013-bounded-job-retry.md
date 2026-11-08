# ADR-0013: bounded job retries on PostgreSQL

Status: implemented locally; migration and tests run against an isolated test database.

## Scope and preserved decisions

Keep the modular monolith, PostgreSQL `jobs`, `FOR UPDATE SKIP LOCKED`, and existing
job type/status values. No Redis, Celery, manual retry endpoint, or new management UI.
Migration `0012_job_retry` follows `0010_merge_vocabulary_and_pack` directly.
The retry branch has no dependency on the separate editorial feature.

Automatic exception retries are opted in only for `import_articles`, `ingest_article`,
and `mine_article`. Gold labeling keeps its existing quota/partial-label semantics
and is not automatically retried on provider failures. Its worker call now lets the
runner own the transaction instead of committing its execution lock early; direct
labeling callers retain their existing commit behavior.

## State and retry budget

`queued` (due) -> `processing` -> `succeeded`.

A retryable exception rolls back the attempt's database changes, then conditionally
changes the owned job to `queued` with `next_attempt_at`. A permanent failure or
exhausted budget becomes terminal `failed`. Fixed handler rejection messages are
terminal: they do not trigger retries by parsing strings. Historical failed jobs
are not automatically revived by this migration.

Each job has `max_attempts=4` by default: one initial execution and up to three
additional attempts. Lease recoveries consume this same budget. Claiming an
exhausted job terminalizes it without executing the handler. Every new claim gets
a UUID `lock_token`. The API exposes the budget, next attempt time and redacted
error code, but does not expose ownership tokens.

Retry transport failures, HTTP 408/429/500/502/503/504, invalidated database
connections, serialization failures, deadlocks, and selected PostgreSQL
availability errors. Permission failures, invalid data, unsupported parsers,
other HTTP errors and unclassified errors fail closed.

Backoff uses equal jitter between half and all of
`min(cap, base * 2^(attempts-1))`. A valid `Retry-After` (seconds or HTTP date)
is a minimum, even when larger than the local cap. Retry schedules are persisted;
workers do not sleep while waiting for a retry to become due. Worker-created SLR
adapters disable their inner 429 retry loop, avoiding multiplied retry budgets.
Non-worker SLR usage retains its existing adapter behavior.

## Ownership and recovery

`locked_at` is renewed by a separate heartbeat session, conditional on the token.
The handler transaction holds a PostgreSQL transaction advisory lock for its job.
The claimer must acquire that same lock before replacing a stale token. Thus an
expired heartbeat alone cannot evict a still-live handler transaction. Locks are
automatically released on rollback or connection termination.

The runner checks the token again before committing output and terminal status
in one transaction. Exception handling and heartbeat updates also check the token;
an old owner cannot overwrite a replacement attempt. A handler deadline bounds
asynchronous operations and database-lock waits. Graceful SIGTERM still drains
the current attempt. Cancellation rolls back; subsequent lease recovery is bounded.

## Idempotency and external effects

- Import and upload share `lock_corpus_writes(session)`, a transaction advisory
  lock covering metadata checks, content-hash checks/backfill and insertion.
  Corpus writes serialize for the bounded page, including otherwise unrelated
  papers. This prevents cross-source and import/upload races that source/DOI/title
  locks alone do not cover. Titles are review hints, not confirmed duplicates.
  Retry progress reporting retains the `checking_duplicates` stage.
- A failed import page rolls back articles, ingest jobs and continuation together.
  A retry reruns that page, not already committed earlier pages. No per-article
  checkpoint within a failed page is introduced in this increment.
- Ingest/mining lock the article row. Ingest of a ready article is a no-op after
  the rights check. Explicit reingest retains its provenance checks and intentionally
  resets the ingest state before replacing sentences.
- Mining skips already persisted exact frame/source-sentence sets, preserving
  reviewed candidates. This is retry idempotency, not semantic deduplication.
- Attempt-created blobs are compensated after a confirmed rollback. If COMMIT
  acknowledgement is lost, check the terminal job receipt before deleting blobs.
  If the database is unreachable, retain files rather than risk deleting committed
  content. Hard process kills can leave unreferenced blobs; garbage collection
  remains separate work. This does not promise exactly-once external I/O.

## Configuration and rollout

Defaults (seconds):

| Setting | Default |
| --- | ---: |
| `JOB_LEASE_SECONDS` | 300 |
| `JOB_HEARTBEAT_SECONDS` | 30 |
| `JOB_TIMEOUT_SECONDS` | 900 |
| `JOB_RETRY_BASE_SECONDS` | 10 |
| `JOB_RETRY_CAP_SECONDS` | 300 |

Heartbeat must be less than half the lease, timeout must exceed heartbeat, and
base must not exceed cap. The database budget can be set per job. Start with the
default budget rather than automatically increasing failed historical jobs.

Stop/drain **all old workers** before migration and replacement: mixed worker
versions do not share the new fencing protocol. Back up first, upgrade to head,
start the new workers, then inspect `/v1/admin/jobs/{job_id}` and worker logs.
No production/application database was migrated as part of this local implementation.
Do not downgrade while workers are active or delayed retries remain; downgrading
removes retry schedules and fencing metadata. A forward fix is preferred.

## Verification

Regression tests cover delayed/exhausted retries, redaction, Retry-After, permanent
failures, stale tokens, heartbeat plus live-transaction exclusion, bounded stale
recovery, cancellation/timeout rollback, repeated ingest/mining, partial-page import
recovery, overlapping imports, and lost COMMIT acknowledgement. Integration tests
use isolated PostgreSQL schemas; no external SLR call is needed for these tests.

Long CPU-bound parsers can delay asyncio heartbeat/deadline delivery. The advisory
lock prevents concurrent committed processing, but external worker supervision is
still needed for a wedged process. Moving CPU-heavy parsing into separately bounded
processes is outside this increment.
