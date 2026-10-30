# AP-RKB Backend

Python 3.12 modular monolith using FastAPI, Pydantic v2, SQLAlchemy async, Alembic, and PostgreSQL 16 with pgvector. The API and worker share the `aprkb` package. The worker polls the PostgreSQL `jobs` table; Redis and Celery are not runtime dependencies.

## Package layout

```text
src/aprkb/
  api/          FastAPI app and /v1 route mounting
  core/         settings, database, auth, and shared dependencies
  modules/      domain models, schemas, repositories, services, and routers
  policies/     versioned YAML policies and validators
  seeds/        idempotent local reference/taxonomy/pattern loader
  worker/       PostgreSQL polling runner and job handlers
migrations/     Alembic revision(s)
tests/
  unit/         pure pipelines and policy behavior
  integration/  PostgreSQL-backed API and worker behavior
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

## Policy and data notes

- YAML policies live in `src/aprkb/policies/` and are validated at app startup.
- Seeds are self-authored and safe to rerun.
- Corpus processing checks `License.allows_mining` before reading/parsing a blob.
- The mining pipeline writes pending `Candidate` rows with `source_sentence_ids`; it never writes phrase patterns or versions.
- Recommendation filtering fails closed on unknown or missing provenance.

See [the root README](../../README.md) for the PRD traceability table and command list. See [SCAFFOLD_PRD.md](../../SCAFFOLD_PRD.md) for the scope boundary and acceptance criteria.
