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
`query` is split into
case-insensitive word terms, searches for any matching term, and ranks by
matched-term coverage; punctuation-only queries return no results. Recommendation
logs keep only a SHA-256 hash of the query, never its raw text.

The published taxonomy returns section `compatible_genres`. `/v1/recommendations`
rejects genre/section pairs absent from that relation. The seed relation is a
self-authored draft pending taxonomy-owner review (`TODO(owner)`).

Until reviewed journal guidelines and fingerprint data have a usable runtime
contract, matches are reported as `generic_genre`. A selected journal receives
an explicit `fallback_reason`; matching genre alone does not establish journal
suitability. The response includes versioned score breakdowns and gate exclusion
counts. Intent and evidence eligibility remain hard gates; only eligible candidates
receive an evidence proximity score. Keyword match uses query term coverage, and
criteria without data remain null (`—` in the writer). The writer shows each
criterion once in a horizontal cell. Provisional formulas and
weights are recorded in `ranking_weights.yaml` with `TODO(owner)`. This is the
current API behavior, not a claim of journal style support.

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
V05 remains unavailable pending verified Offline guideline data; other unfinished checks
are also listed as unavailable, so `complete` remains false.
Validation returns text/context hashes and policy versions; it does not store the raw
sentence. Feedback accepts only a SHA-256 context hash in its optional metadata and
requires a version actually issued in that client's recommendation. The MVP does not
mount `/v1/overrides`.

See [the root README](../../README.md) for the PRD traceability table and command list. See [SCAFFOLD_PRD.md](../../SCAFFOLD_PRD.md) for the scope boundary and acceptance criteria.

## Internal reference library

## Offline data packs

`modules/pack/` transfers only the PhrasePattern graph. The `approved_phrases` store from ADR-0009 is intentionally out of scope for pack v0.1; pack tooling does not read it. Offline self-check: `uv run python -m aprkb.cli validate-pack <pack-dir>`. On a separate Offline/staging/test destination, run `uv run python -m aprkb.cli init-reference`, then `uv run python -m aprkb.cli import-pack <pack-dir>` (preview with `--dry-run`). These commands write data; do not run them against the active query-only Online database. Export with `uv run python -m aprkb.cli export-pack --out <pack-dir> --only-approved`; it reads the database and reports excluded approved patterns by ID/code/path. See [data pack spec](../../doc/data-pack-spec.md).

The `/v1/reference-library` GET routes remain a separate, disabled integration and are not used by the Online Phrasebank Basic flow.

## Online Phrasebank Basic

`src/aprkb/seeds/phrasebank_basic.json` is the canonical phrase content source for Online display and recommendations. Its `section_title` names the Methods move/step, each category maps to a taxonomy intent in release `taxonomy_version` (`0.2.0`), and each example maps to `PatternVersion.canonical_frame` and `slots`. The base `0.1.0` taxonomy remains unchanged for Offline packs. The seed also fills `PhrasePattern.intent_id`, `UsageConstraint.allowed_sections`/`allowed_genres`, and authored `EvidenceProvenance`. X/Y/Z become named text slots, ellipses become a completion slot, and illustrative author/year references become citation slots. The scaffold labels these procedural frames `claim_type=descriptive` and `epistemic_strength=low`; evidence minimum remains unset because the examples are templates, not study evidence. Stable IDs and append-only version numbers make reseeding idempotent while preserving prior versions. Bump `taxonomy_version` when category or taxonomy labels change.

The Online initializer does not read the old `data/seed/patterns.json`; all Phrasebank Basic examples come from the packaged JSON in every environment. The deployment runbook runs the initializer after migrations so the JSON is available inside the backend image.
