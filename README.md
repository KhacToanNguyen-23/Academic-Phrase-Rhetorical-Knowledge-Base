# AP-RKB — Academic Phrase & Rhetorical Knowledge Base

AP-RKB is an academic writing assistant scaffold. The backend recommends rhetorical phrase frames, validates claim strength against evidence, and lets curators upload licensed text for traceable mining candidates. It does not implement the excluded admin console, production NLP extraction, or taxonomy publishing. The existing web app is a prototype UI that uses local mock data; its admin screen is not a production admin console and is outside this scaffold's backend scope.

## Architecture

```text
apps/web (existing React + TypeScript SPA; outside this scaffold runtime)
               │ REST /v1 + OpenAPI
apps/backend (FastAPI modular monolith)
  API ── domain services ── PostgreSQL 16 + pgvector
  worker ── PostgreSQL jobs table (FOR UPDATE SKIP LOCKED)
  corpus blobs ── local ./data/blobs via BlobStore
```

The scaffold keeps the existing `apps/backend/src/aprkb` package and module boundaries. PostgreSQL is the sole database and job queue. The worker is started separately with `make worker`; no Redis or Celery service is used. Text and Markdown ingestion are implemented; JATS and PDF parsers remain explicit stubs. Articles can also be imported from an external article API through the `import_articles` worker job (`POST /v1/admin/corpus/imports`); mining rights are checked on listed metadata before any content is downloaded. Only the `null` source is registered until the real HTTP adapter is written (`ARTICLE_SOURCE`). OpenAlex is not used. See [ADR-0001](doc/adr/0001-modular-monolith.md), [ADR-0005](doc/adr/0005-external-article-source.md) and [the scaffold PRD](SCAFFOLD_PRD.md).

The owner approved runtime rule-based slot extraction on 2026-10-31. Its implementation is in progress; production classifiers, spaCy, NER, embeddings and live LLM remain deferred. Real-article gold and quality evaluation await the external article API. See [ADR-0006](doc/adr/0006-rule-based-slot-abstraction.md).

## Quick start

Requirements: Python 3.12, `uv`, Docker Desktop, and GNU Make. Before starting Postgres, replace the example `POSTGRES_PASSWORD` and keep `DATABASE_URL` in sync. Compose binds Postgres to `127.0.0.1` only.

```powershell
Copy-Item .env.example .env
make up
make install
make migrate
make seed
make bootstrap-key
make lint
$env:TEST_DATABASE_URL = "postgresql+asyncpg://aprkb:<your-local-password>@localhost:5432/aprkb_test"
make test
make run
```

`make bootstrap-key` prints the initial admin API key once. Keep it private. The test fixture requires a dedicated database named `aprkb_test`; it creates and removes isolated schemas there and never migrates the application's public schema. Set `TEST_DATABASE_URL` to that database before running tests, using the same local password and host port as `DATABASE_URL`. Replace `<your-local-password>` with the password you configured. `make down` stops the PostgreSQL service and preserves its named volume.

OpenAPI is available at <http://localhost:8000/docs>. To process uploaded articles, run `make worker` in another terminal. Uploads require a curator API key and a seeded license. The sample `CC-BY` license permits mining; `PROPRIETARY` is rejected by the worker.

## Commands

| Command | Purpose |
| --- | --- |
| `make up` / `make down` | Start or stop PostgreSQL |
| `make install` | Sync backend dependencies with `uv` |
| `make migrate` | Apply the Alembic migration |
| `make seed` | Idempotently load reference enums, taxonomy, and self-authored patterns |
| `make bootstrap-key` | Create the first admin API key and print it once |
| `make run` | Start FastAPI with reload |
| `make worker` | Poll PostgreSQL jobs and process ingestion/mining |
| `make test` | Run backend unit, integration, and scaffold acceptance tests |
| `make lint` | Run Ruff, format verification, and mypy |

## PRD traceability

| Requirement | Implementation | Verification |
| --- | --- | --- |
| BR-01: approved patterns only | `apps/backend/src/aprkb/modules/recommendation/gates/` | `tests/unit/recommendation/test_recommendation_pipeline.py`; `tests/integration/api/test_routes.py` |
| BR-10: license-aware corpus use | `apps/backend/src/aprkb/modules/corpus/`; `apps/backend/src/aprkb/worker/handlers.py` | `tests/integration/corpus/test_ingestion_jobs.py` |
| Claim strength does not exceed evidence | `apps/backend/src/aprkb/policies/evidence.py`; `modules/validation/rules/` | `tests/unit/validation/test_validation_pipeline.py`; API integration |
| Journal guidance remains distinct from observations | `modules/journals/guideline_policy.py`; recommendation gates | `tests/unit/recommendation/test_recommendation_pipeline.py`; API integration |
| Explainable weighted ranking and fallback | `apps/backend/src/aprkb/modules/recommendation/`; versioned YAML under `apps/backend/src/aprkb/policies/` | `tests/unit/recommendation/test_recommendation_pipeline.py`; API integration |
| Human review requires two rounds | `modules/review/service.py` | `tests/integration/api/test_routes.py` |
| RBAC and transactional audit | `modules/identity/`; `modules/audit/` | Phase 02 and Phase 04 integration tests |
| Mining creates sourced candidates only | `modules/mining/`; `worker/handlers.py` | `tests/integration/corpus/test_ingestion_jobs.py` |
| Database migration and seed bootstrap | `apps/backend/migrations/`; `apps/backend/src/aprkb/seeds/` | `tests/integration/core/test_database_setup.py`; Phase 02 integration tests |
| Discipline data remains an optional P2 adapter | `apps/backend/src/aprkb/modules/discipline/null_source.py` | `tests/unit/discipline/test_null_source.py`; null source returns no classification |

The original acceptance cases that depend on excluded product behavior remain skipped with `TODO(owner)` in `apps/backend/tests/acceptance/`. Cases already covered by scaffold behavior reuse the Phase 04/05 integration tests.
