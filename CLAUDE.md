# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

AP-RKB (Academic Phrase & Rhetorical Knowledge Base / "Academic Wordbank") is at the **scaffold stage**: the architecture, configs and module boundaries exist, but there is no business logic, DB schema or Alembic setup yet. The source of truth for requirements is the two Vietnamese PDFs in `doc/` (PRD and System Design). Code comments and docs reference requirement IDs from them (`FR-xx.x`, `BR-xx`, `NFR-xx`, `AT-xx`, `WB-xx`, `V01–V08`). Keep using those IDs when adding code. Architecture decisions live in `doc/adr/`.

Roadmap order: M0 (taxonomy, schema, rights policy, editor workflow) → M1 (patterns, search/recommendation, composer, validator, journal profile) → M2 (corpus, mining, fingerprint) → M3 (OpenAlex affinity, ablation).

## Commands

Infra (from repo root, after `cp .env.example .env`):
```bash
docker compose up -d postgres redis
docker compose up api worker
docker compose --profile nlp up -d      # GROBID + LanguageTool, only needed from M2
```

Backend (`apps/backend`, Python 3.12, managed with uv):
```bash
uv sync                                  # add --extra nlp for spaCy/sentence-transformers (M2)
uv run uvicorn aprkb.api.main:app --reload
uv run celery -A aprkb.worker.app worker -l info
uv run ruff check .
uv run pyright
uv run pytest
uv run pytest tests/acceptance/test_at_01_x.py::test_name   # single test
uv run alembic init migrations           # not done yet; first step of M0
```

Frontend (`apps/web`, pnpm):
```bash
pnpm install
pnpm dev                 # Vite on :5173, proxies /v1 → localhost:8000
pnpm typecheck
pnpm build
pnpm gen:api             # regenerate types from packages/contracts/openapi/openapi.json
pnpm test:e2e            # Playwright
```

CI (`.github/workflows/ci.yml`) runs ruff, pyright and pytest with `OPENALEX_ENABLED=false`, then typecheck and build for the web app.

## Architecture

**Modular monolith.** One Python package `aprkb` (`apps/backend/src/aprkb`) with two entrypoints that share the same domain modules:
- `api/main.py` is the FastAPI app. `api/routes.py` mounts every module's `router` under `/v1/<prefix>`.
- `worker/app.py` is the Celery app (Redis broker). It runs ingest, OpenAlex sync, phrase mining and fingerprint computation. Tasks must be idempotent and must retry on HTTP 429 (NFR-10).

Each domain in `modules/<name>/` has the same layers: `models.py` (SQLAlchemy), `schemas.py` (Pydantic contracts), `repository.py`, `service.py`, `router.py`. The `mining` module has no router because it runs only in the worker. Modules map to PRD sections; the table is in `apps/backend/README.md`.

**Module dependency rules. These are the core of the design, so do not break them:**
- A module may call another module only through that module's `service.py`. It never imports another module's `models` or `repository`.
- `taxonomy` depends on nothing. `patterns` depends on `taxonomy`. `recommendation` depends on `patterns`, `taxonomy`, `journals` and `validation`.
- **No core module imports `openalex`.** OpenAlex is an optional adapter (BR-06, NFR-01, ADR-0003). The worker writes its data into local tables with `synced_at` and `classifier_version`, and core modules read only those local tables. Search, recommendation and validation must keep working when `OPENALEX_ENABLED=false`; Gate D tests the end-to-end flow WB-01→WB-08 in that mode.
- A state change that affects output must write an `audit` event in the same transaction (NFR-03).

**Data (ADR-0002).** PostgreSQL 16 is the only store. `infra/postgres/init.sql` enables these extensions:
- `ltree`: taxonomy tree
- `pg_trgm` and full-text search: search
- `pgvector`: near-duplicate detection, clustering and diversification
- `pgcrypto`

Flexible fields such as `slots_schema`, `constraints` and fingerprint `features` are JSONB.

Rules for versions and identifiers:
- Approved versions are immutable. Version tables are append-only, and editing an approved pattern creates a new draft version (AT-09).
- OpenAlex IDs are never primary keys for patterns.

**Recommendation pipeline (PRD-07).** Hard gates run before ranking, and a high score never compensates for a violation. The gates are approval, permission/license, intent/section, mandatory guideline and claim strength vs evidence. After the gates come soft ranking with a score breakdown, then an explicit fallback chain: journal+genre → similar journal → subfield → field → generic. Every result returns its `fallback_tier`.

**Domain invariants that shape code and UI:**
- Journal guideline (verified rule) and journal fingerprint (corpus observation) are separate entities. The UI must label data as "Required by journal" / "Observed in corpus" / "Model suggestion" and must never claim "journal requires" based only on corpus statistics (BR-04, BR-09).
- Never fabricate DOIs, citations, numbers or research gaps. Unfilled slots stay as placeholders (BR-02, AT-08).
- Corpus with license `unknown` or `restricted` is quarantined, and its text is never exported or published (BR-10).
- Seed patterns in `data/seed/` must be self-authored (`own_authored`). Never copy text from the Manchester Academic Phrasebank. Real corpus files go in `data/corpus/`, which is gitignored.
- Raw manuscripts are not stored by default (`STORE_MANUSCRIPT_RAW=false`).

**Frontend (ADR-0004).** React SPA. Each PRD screen WB-01…WB-09 is a folder under `src/features/`. Features must not import each other and share code only through `src/shared/`. API types are generated from the backend OpenAPI export in `packages/contracts/openapi/`; do not hand-write them. The `@/` alias maps to `src/`.
