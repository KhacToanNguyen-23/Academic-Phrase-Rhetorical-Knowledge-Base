# Repository instructions

## Project state and source of truth

AP-RKB is a runnable backend scaffold, not an empty architecture prototype. Preserve the current repository layout: the Python package is `apps/backend/src/aprkb`; unit, integration, and acceptance tests are under `apps/backend/tests`. `SCAFFOLD_PRD.md` defines this scaffold's scope and overrides older product documents where they differ. Keep the API and worker behavior within that scope; do not add the admin console, general-purpose NLP extraction, taxonomy publishing, or excluded evaluation algorithms. Owner-approved exceptions are the versioned, closed-world construction registry in ADR-0011 and the read-only frame-statistics CLI; keep both within their documented limits.

## Commands

From the repository root, use the Makefile:

```bash
make up
make install
make migrate
make seed
make bootstrap-key
make lint
make test
make run
make worker       # separate terminal
```

PostgreSQL integration tests require `TEST_DATABASE_URL` pointing to a dedicated database named `aprkb_test`. The fixture creates and drops per-run schemas there. Never point it at a production database. The worker uses PostgreSQL polling and `FOR UPDATE SKIP LOCKED`; it does not use Redis or Celery. The default upload blob store is local (`BLOB_DIR=./data/blobs`).

## Architecture and invariants

- Keep module layers clear: router → service → repository/model. Keep gate, scorer, rule, parser, and mining-stage logic independently testable where practical.
- PostgreSQL is the only database and job queue. Preserve append-only pattern versions and transactional audit writes.
- Check mining rights before reading or parsing corpus blobs. Do not put API keys, full article text, or manuscript contents in logs or audit snapshots.
- Recommendations fail closed for unknown/missing provenance. EvidenceGate and V02 use the shared `EvidencePolicy`.
- Keep business weights, filter thresholds, and vocabularies in versioned YAML under `apps/backend/src/aprkb/policies/`; identify provisional values with `TODO(owner)`.
- Every incomplete parser or algorithm stub has a `TODO(owner)` and requirement identifier. Do not imply that an unimplemented adapter is active.
- Keep seed text self-authored. Do not add copied Academic Phrasebank or copyrighted corpus content.
- Keep frontend changes outside this scaffold unless specifically requested.

## Verification

Run the backend checks before reporting completion:

```bash
make lint
make test
```

If PostgreSQL, Docker, or an optional external service is unavailable, report the exact checks that could not be run instead of claiming full verification. Update `README.md` and module documentation when implementation decisions change.
