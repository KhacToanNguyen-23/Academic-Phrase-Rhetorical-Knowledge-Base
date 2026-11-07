# AP-RKB Backend

Python 3.12 modular monolith using FastAPI, Pydantic v2, SQLAlchemy async, Alembic, and PostgreSQL 16 with pgvector. The API and worker share the `aprkb` package. The worker polls the PostgreSQL `jobs` table; Redis and Celery are not runtime dependencies.

## Package layout

```text
src/aprkb/
  api/          FastAPI app and /v1 route mounting
  core/         settings, database, auth, and shared dependencies
  modules/      domain models, schemas, repositories, services, and routers
    discipline/ optional adapter only; no API router or public endpoints
  policies/     versioned YAML policies and validators
  seeds/        idempotent local reference/taxonomy/pattern loader
  worker/       PostgreSQL polling runner and job handlers
migrations/     Alembic revision(s)
tests/
  unit/         grouped by domain (identity, mining, recommendation, validation, ...)
  integration/  grouped by domain (API, identity, corpus, core, ...)
  acceptance/   covered AT cases and explicit TODO skips
```

## Local workflow

Run commands from the repository root through `make`, or from this directory with the equivalent `uv run` command. Copy the root `.env.example` to `.env` first.

```powershell
uv sync
uv run alembic -c alembic.ini upgrade head
uv run python -m aprkb.seeds.load
uv run uvicorn aprkb.api.main:app --reload
uv run python -m aprkb.worker.runner
```

The worker command runs continuously and polls for queued jobs. Use a separate terminal from the API. `BLOB_DIR` defaults to `./data/blobs`. Plain UTF-8 `.txt` files use the working parser. Text-layer PDF is parsed locally with pypdf; image-only/encrypted PDFs return actionable errors. JATS/XML remains a stub. See [PDF import and metadata](../../doc/pdf-import.md).

For PostgreSQL integration tests, set `TEST_DATABASE_URL` to a dedicated database named `aprkb_test`, for example:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://aprkb:<your-local-password>@localhost:5432/aprkb_test"
uv run pytest
```

Replace `<your-local-password>` and the port with the same local values used by `DATABASE_URL`. Tests create an isolated schema per run, apply migrations in that schema, and drop only that schema. Never point `TEST_DATABASE_URL` at a production database.

## API and permissions

OpenAPI is served at `/docs`. Routes are mounted below `/v1`; corpus upload, mining enqueue, review, API-key administration, and taxonomy administration are grouped below `/v1/admin`. Curator and admin roles can upload; workers require no API key. Every successful state-changing API operation records an audit event in the same transaction. Full article text and API secrets are excluded from audit snapshots and worker error messages.

System integrations continue to authenticate with `X-API-Key`. `GET /v1/auth/me` identifies the authenticated key without returning it. Client and reviewer keys can list only approved patterns whose current version has one displayable provenance; detail and version-history reads apply the same rule. Recommendation applies the versioned `license_policy.yaml`: approved `PROPRIETARY` patterns may be displayed internally with `license_flag=true`; missing or ambiguous provenance/license is still excluded. Curator and admin keys can inspect drafts and historical versions. `POST /v1/auth/demo-session` is restricted to loopback requests while `APP_ENV=local`; it idempotently seeds the self-authored sample data, rotates the prior local demo curator key, and returns the new key once. It is unavailable in other environments.

`modules/discipline/` contains an optional classification adapter interface and a null implementation. It does not define an API router or expose endpoints.

## Policy and data notes

- YAML policies live in `src/aprkb/policies/` and are validated at app startup.
- Seeds are self-authored and safe to rerun.
- Corpus processing checks `License.allows_mining` before reading/parsing a blob.
- The mining pipeline writes pending `Candidate` rows with `source_sentence_ids`; it never writes phrase patterns or versions.
- Recommendation filtering fails closed on unknown or missing provenance.

## Current recommendation search

`POST /v1/recommendations` accepts optional `intent`, `section`, `query`, `move`,
`claim_type`, `genre`, `journal_id`, and evidence filters. An empty context returns
approved, renderable examples. Evidence strength is not filtered until an evidence
level is selected; rejected examples are counted under `excluded.GATE_EVIDENCE`.
Recommendation retrieval filters status (`approved`) and genre in SQL before
building read views. Empty genre restrictions or absent usage constraints allow
all genres. Approval and retired gates remain as defensive checks, but SQL-filtered
draft/retired rows no longer contribute to `excluded.GATE_APPROVAL` or
`excluded.GATE_RETIRED`. These counts describe candidates seen by the pipeline,
not all rows in the database; the writer currently displays only the evidence count.

Blank intent, move and section values are treated as absent. Requests lacking
intent, move and a nonblank query receive
`Không có intent/move/query; kết quả là toàn bộ pattern được duyệt`;
requests lacking section receive `Section không được lọc`.
The first warning describes the broad candidate scope: other supplied filters,
hard gates and the result limit still apply. No request fields became mandatory.

`query` is split into
case-insensitive word terms, searches for any matching term, and ranks by
matched-term coverage; punctuation-only queries return no results. Recommendation
logs keep only a SHA-256 hash of the query, never its raw text.

The published taxonomy returns section `compatible_genres`. `/v1/recommendations`
rejects genre/section pairs absent from that relation. The seed relation is a
self-authored draft pending taxonomy-owner review (`TODO(owner)`).

When a journal is selected, recommendations are restricted to approved mined
patterns whose evidence provenance points to an article assigned to that journal.
The response labels these results `selected_journal_phrasebank`; an empty mapping
returns no candidates and does not use a generic fallback. Without a selected
journal, the configured generic fallback tiers still apply. This source association
does not claim journal style support or fingerprint-based ranking. The response
includes versioned score breakdowns and gate exclusion counts. Intent and evidence
eligibility remain hard gates; only eligible candidates receive an evidence
proximity score. Keyword match uses query term coverage, and criteria without data
remain null (`—` in the writer). The writer shows each criterion once in a
horizontal cell. Provisional formulas and weights are recorded in
`ranking_weights.yaml` with `TODO(owner)`.

`GET /v1/taxonomy/reference-options` returns DB-backed claim/evidence/strength choices.
`GET /v1/patterns/versions/{version_id}` returns slots only for the current approved
version with display rights. `POST /v1/render` requires its `recommendation_id` and
`pattern_version_id` from the same client, and preserves unfilled placeholders.
Slot definitions may include `type`, `label`, `instruction`, `example`, `required`,
and `min_length`. Render returns HTTP 422 with `error.details.field_errors` for
required empty or too-short values. Legacy type-string definitions use required
and one-character defaults; optional empty slots remain placeholders.
`POST /v1/validate` runs V02, a deterministic V03 check for numbers, DOI, and
parenthetical citations absent from the supplied supporting context/slots, and a limited V06
phrase screen that warns on configured informal wording. V06 is not a grammar checker.
V05 is marked `not_applicable` because journal-guideline compliance is outside the
current sentence-validation flow. Other unfinished in-scope checks remain listed as
unavailable, so `complete` remains false.
Validation returns text/context hashes and policy versions; it does not store the raw
sentence. Feedback accepts only a SHA-256 context hash in its optional metadata and
requires a version actually issued in that client's recommendation. The MVP does not
mount `/v1/overrides`.

See [the root README](../../README.md) for the PRD traceability table and command list. See [SCAFFOLD_PRD.md](../../SCAFFOLD_PRD.md) for the scope boundary and acceptance criteria.

## Internal reference library

## Offline data packs

For both Phrasebank sources and their filter mappings, use the shared [Phrasebank initialization workflow](../../doc/phrasebank-initialization.md): `uv run python -m aprkb.cli init-phrasebank --file <data_init.json> --dry-run`, then the same command without `--dry-run` in the configured staging/test destination. One manifest names the existing pattern pack, Manchester collection, and reviewed mappings. Both imports commit together or roll back together. Existing individual pack/reference commands keep their behavior.

`modules/pack/` transfers only the PhrasePattern graph. The `approved_phrases` store from ADR-0009 is intentionally out of scope for pack v0.1; pack tooling does not read it. Offline self-check: `uv run python -m aprkb.cli validate-pack <pack-dir>`. On a separate Offline/staging/test destination, run `uv run python -m aprkb.cli init-reference`, then `uv run python -m aprkb.cli import-pack <pack-dir>` (preview with `--dry-run`). These commands write data; do not run them against the active query-only Online database. Export with `uv run python -m aprkb.cli export-pack --out <pack-dir> --only-approved`; it reads the database and reports excluded approved patterns by ID/code/path. See [data pack spec](../../doc/data-pack-spec.md).

The `/v1/reference-library` GET routes serve a quarantined external reference collection from its own tables. They return 404 unless `REFERENCE_LIBRARY_ENABLED=true`. Import and purge are CLI-only (`uv run python -m aprkb.cli import-reference-library --file <path>` and `uv run python -m aprkb.cli purge-reference-library`). Import replacement and its content-free audit event commit together. Imported entries are disconnected from patterns, recommendations, render, and validation. Keep the source notice in the UI and do not treat these entries as approved or redistributable patterns.

## Bounded worker retry

Import, ingestion and mining jobs now schedule bounded retries for transient failures.
Defaults: four total attempts, 10s exponential backoff capped at 300s with jitter,
30s heartbeat, 300s lease and 900s asynchronous attempt timeout. `Retry-After` is
respected as a minimum. See [ADR-0013](../../doc/adr/0013-bounded-job-retry.md) for
configuration, transaction guarantees and rollout requirements. Drain all old workers
before applying migration `0012_job_retry`; do not run mixed worker versions.
Job inspection exposes `max_attempts`, `next_attempt_at` and `error_code`.

## Job operations

See [ADR-0014](../../doc/adr/0014-job-operations.md). Migration `0013_job_operations`
adds per-attempt history and repeated-failure alerts. Curator/admin users open
`/jobs` (also linked from Import) for live progress, errors, acknowledgement and
manual retry after fixing the cause. Manual retry grants one additional attempt,
preserves history, and defaults to at most three manual retries per job. In-app
alerts default to three observed failed/interrupted attempts and resolve on success.
Configure `JOB_MANUAL_RETRY_LIMIT` and `JOB_FAILURE_ALERT_THRESHOLD` if required.
