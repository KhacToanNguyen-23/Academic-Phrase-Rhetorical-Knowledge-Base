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

The worker command runs continuously and polls for queued jobs. Use a separate terminal from the API. `BLOB_DIR` defaults to `./data/blobs`. Plain UTF-8 `.txt` files use the working parser. PDF and JATS/XML parser adapters deliberately raise `NotImplementedError` with `TODO(owner)` markers.

For PostgreSQL integration tests, set `TEST_DATABASE_URL` to a dedicated database named `aprkb_test`, for example:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://aprkb:<your-local-password>@localhost:5432/aprkb_test"
uv run pytest
```

Replace `<your-local-password>` and the port with the same local values used by `DATABASE_URL`. Tests create an isolated schema per run, apply migrations in that schema, and drop only that schema. Never point `TEST_DATABASE_URL` at a production database.

## API and permissions

OpenAPI is served at `/docs`. Routes are mounted below `/v1`; corpus upload, mining enqueue, review, API-key administration, and taxonomy administration are grouped below `/v1/admin`. Curator and admin roles can upload; workers require no API key. Every successful state-changing API operation records an audit event in the same transaction. Full article text and API secrets are excluded from audit snapshots and worker error messages.

System integrations continue to authenticate with `X-API-Key`. `GET /v1/auth/me` identifies the authenticated key without returning it. Client and reviewer keys can list only approved patterns whose current version has one displayable provenance; detail and version-history reads apply the same rule. Curator and admin keys can inspect drafts and historical versions. `POST /v1/auth/demo-session` is restricted to loopback requests while `APP_ENV=local`; it idempotently seeds the self-authored sample data, rotates the prior local demo curator key, and returns the new key once. It is unavailable in other environments.

`modules/discipline/` contains an optional classification adapter interface and a null implementation. It does not define an API router or expose endpoints.

## Policy and data notes

- YAML policies live in `src/aprkb/policies/` and are validated at app startup.
- Seeds are self-authored and safe to rerun.
- Corpus processing checks `License.allows_mining` before reading/parsing a blob.
- The mining pipeline writes pending `Candidate` rows with `source_sentence_ids`; it never writes phrase patterns or versions.
- Recommendation filtering fails closed on unknown or missing provenance.

## Current recommendation search

`POST /v1/recommendations` accepts `intent`, `section`, optional `query`, `move`,
`claim_type`, `genre`, `journal_id`, and evidence fields. `query` performs a
case-insensitive literal substring search of canonical frames; `%` and `_`
are treated as search characters, not SQL wildcards. Recommendation logs keep
only a SHA-256 hash of the query, never its raw text.

Until reviewed journal guidelines and fingerprint data have a usable runtime
contract, matches are reported as `generic_genre`. A selected journal receives
an explicit `fallback_reason`; matching genre alone does not establish journal
suitability. The response includes versioned score breakdowns and gate exclusion
counts. This is the current API behavior, not a claim of journal style support.

`GET /v1/taxonomy/reference-options` returns DB-backed claim/evidence/strength choices.
`GET /v1/patterns/versions/{version_id}` returns slots only for the current approved
version with display rights. `POST /v1/render` requires its `recommendation_id` and
`pattern_version_id` from the same client, and preserves unfilled placeholders.
`POST /v1/validate` reports V02 and lists V01/V03–V08 as unavailable, with `complete=false`.
Validation returns text/context hashes and policy versions; it does not store the raw
sentence. Feedback accepts only a SHA-256 context hash in its optional metadata and
requires a version actually issued in that client's recommendation. The MVP does not
mount `/v1/overrides`.

See [the root README](../../README.md) for the PRD traceability table and command list. See [SCAFFOLD_PRD.md](../../SCAFFOLD_PRD.md) for the scope boundary and acceptance criteria.
