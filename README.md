# AP-RKB — Academic Phrase & Rhetorical Knowledge Base

AP-RKB is an academic writing assistant scaffold. The backend recommends rhetorical phrase frames, validates claim strength against evidence, and lets curators upload licensed text for traceable mining candidates. It does not implement the excluded admin console, production NLP extraction, or taxonomy publishing. The existing web app is a prototype UI that uses local mock data; its admin screen is not a production admin console and is outside this scaffold's backend scope.

## Architecture

```text
apps/web (React + TypeScript SPA; runs locally by default)
               │ REST /v1 + OpenAPI
apps/backend (FastAPI modular monolith)
  API ── domain services ── PostgreSQL 16 + pgvector
  worker ── PostgreSQL jobs table (FOR UPDATE SKIP LOCKED)
  corpus blobs ── local ./data/blobs via BlobStore
```

The scaffold keeps the existing `apps/backend/src/aprkb` package and module boundaries. PostgreSQL is the sole database and job queue. The default local workflow runs PostgreSQL in Docker and the backend/frontend on the host; run the worker separately with `make worker` when processing jobs. No Redis or Celery service is used. Text and Markdown ingestion are implemented; JATS and PDF parsers remain explicit stubs. Articles can also be imported from an external article API through the `import_articles` worker job (`POST /v1/admin/corpus/imports`); mining rights are checked on listed metadata before any content is downloaded. Only the `null` source is registered until the real HTTP adapter is written (`ARTICLE_SOURCE`). OpenAlex is not used. See [ADR-0001](doc/adr/0001-modular-monolith.md), [ADR-0005](doc/adr/0005-external-article-source.md) and [the scaffold PRD](SCAFFOLD_PRD.md).

## Quick start

Requirements: Docker Desktop with Docker Compose v2 `--wait` support, Python 3.12, `uv`, Node.js/npm, and PowerShell on Windows (GNU Make on macOS/Linux). The default workflow runs PostgreSQL in Docker and the backend/frontend on the host. Set `POSTGRES_PASSWORD` and the matching password in `DATABASE_URL` in `.env`; Compose uses the former and the host backend reads the latter. PostgreSQL binds to `127.0.0.1` only.

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Set POSTGRES_PASSWORD and use the same password in DATABASE_URL.
.\dev.ps1 be
```

`.\dev.ps1 be` starts PostgreSQL in Docker, applies migrations and seed data, then runs the backend locally with reload and logs in that terminal. In a second terminal, run `.\dev.ps1 fe` to start the frontend locally with Vite logs and hot reload; it installs npm dependencies automatically the first time. Open <http://localhost:5173> for the web app or <http://localhost:8000/docs> for the API. Stop each terminal with `Ctrl+C`; run `.\dev.ps1 down` to stop PostgreSQL while preserving its named volume. `make bootstrap-key` creates the initial admin API key; keep it private.

If you need to process uploaded articles, run `.\dev.ps1 worker` in a third terminal.

For backend checks, set `TEST_DATABASE_URL` to a dedicated database named `aprkb_test`. The test fixture creates and removes isolated schemas there and never migrates the application's public schema. Use the same local password and host port as `DATABASE_URL`, then run `make check`.

Uploads require a curator API key and a seeded license. The sample `CC-BY` license permits mining; `PROPRIETARY` is rejected by the worker.

## Commands

| Command | Purpose |
| --- | --- |
| `make up` / `make down` | Start PostgreSQL only / stop the Compose stack |
| `make setup` | Start PostgreSQL, install backend dependencies, migrate, and seed |
| `make dev` / `make be` | Start PostgreSQL, prepare backend, and run the API |
| `make check` | Run lint and backend tests |
| `make install` | Sync backend dependencies with `uv` |
| `make migrate` | Apply the Alembic migration |
| `make seed` | Idempotently load reference enums, taxonomy, and self-authored patterns |
| `make bootstrap-key` | Create the first admin API key and print it once |
| `make run` | Start FastAPI with reload |
| `make worker` | Poll PostgreSQL jobs and process ingestion/mining |
| `make test` | Run backend unit, integration, and scaffold acceptance tests |
| `make lint` | Run Ruff, format verification, and mypy |
| `make web-install` / `make web` / `make fe` | Install frontend dependencies / start the frontend dev server |
| `.\dev.ps1 be` / `fe` / `worker` / `down` | PowerShell shortcuts for the local development workflow |

## Continuous integration

GitHub Actions runs on pushes to any branch and pull requests. The backend job checks the generated OpenAPI contract, Ruff lint/format, mypy, and pytest against an ephemeral PostgreSQL/pgvector service. The frontend job installs from the pnpm lockfile, checks generated API types, runs TypeScript checks, and builds the app. CI uses a disposable test database and needs no repository secrets.

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
