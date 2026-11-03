# AP-RKB — Academic Phrase & Rhetorical Knowledge Base

AP-RKB is an academic writing assistant scaffold. The backend recommends rhetorical phrase frames, validates claim strength against evidence, and lets curators upload licensed text for traceable mining candidates. It does not implement the excluded admin console, production NLP extraction, or taxonomy publishing. The `/writer` web route uses the real API and PostgreSQL; other prototype screens still use local mock data.

## Architecture

```text
apps/web (React + TypeScript SPA; Vite runs locally by default)
               │ REST /v1 + OpenAPI
apps/backend (FastAPI modular monolith)
  API ── domain services ── PostgreSQL 16 + pgvector
  worker ── PostgreSQL jobs table (FOR UPDATE SKIP LOCKED)
  corpus blobs ── local ./data/blobs via BlobStore
```

The scaffold keeps the existing `apps/backend/src/aprkb` package and module boundaries. PostgreSQL is the sole database and job queue. The worker is started separately with `make worker`; no Redis or Celery service is used. Text and Markdown ingestion are implemented; JATS and PDF parsers remain explicit stubs. SLR imports use curator-managed profiles in `/import`: saving a profile and choosing “Lấy bài báo” creates a queued job whose filters are snapshotted in its payload. Job results report listed, imported and skipped counts. Set `ARTICLE_SOURCE=slr`, `SLR_API_BASE_URL` (default `https://slr-api.hyperdatalab.org/api`) and `SLR_API_KEY`; timeout, retry count and maximum download size use `SLR_TIMEOUT_SECONDS`, `SLR_MAX_RETRIES` and `SLR_MAX_DOWNLOAD_BYTES`. SLR enforces a limit of 120 requests per minute, handled through `Retry-After`. Imports fail closed: missing, unknown or non-mining licenses are skipped before download. The real SLR API currently returns no license data, so for development only `SLR_DEV_FALLBACK_LICENSE=DEV-UNVERIFIED` assigns that placeholder license to works whose license is missing or unknown; works with a known non-mining license stay blocked. The setting is rejected unless `APP_ENV` is `local` or `test`, and articles under `DEV-UNVERIFIED` must be deleted before production. PDF files can be stored, but the PDF parser remains a stub, so they cannot be mined yet. License aliases and rights are defined in `apps/backend/src/aprkb/policies/licenses.yaml`. OpenAlex is not queried. Ingest splits sentences with an abbreviation list (`policies/lexicon/abbreviations.yaml`), maps headings to section codes (`policies/section_headings.yaml`), and the mining `sentence_filter` drops table rows, captions, math and numeric noise and non-rhetorical sections (thresholds in `policies/mining_filter.yaml`, provisional). After changing these rules, run `uv run --directory apps/backend python -m aprkb.cli reingest --source slr`; it replaces sentences and their pending candidates, and skips articles that have reviewed candidates. See [ADR-0001](doc/adr/0001-modular-monolith.md), [ADR-0005](doc/adr/0005-external-article-source.md), [ADR-0006](doc/adr/0006-slr-repository-import.md) and [the scaffold PRD](SCAFFOLD_PRD.md).

The development pipeline uses the existing upload/import → ingest → `mine_article` worker → pending candidate → two reviewer rounds flow. Rule-based slot extraction stores typed public slot schemas and private provenance offsets; it does not write patterns or versions. The `/extract` page works on top of that flow: it groups articles by import batch, queues mining for one or more batches, shows each article's text beside its mined phrases, and lets one reviewer accept or reject each phrase; accepted phrases are stored in `approved_phrases` (not as patterns), see [ADR-0009](doc/adr/0009-phrase-extraction-page.md). Gold labels are a separate development/evaluation path: Groq can draft labels behind explicit runtime settings, and one human reviewer makes the final decision. Only human-approved, current gold items are scored by `eval-mining`; classifier, spaCy/NER, synonym expansion and production AI assistance remain deferred. See [ADR-0007](doc/adr/0007-rule-based-slot-abstraction.md), [ADR-0008](doc/adr/0008-gold-dev-labeling.md), and the [knowledge enrichment flow](doc/knowledge-enrichment-flow.md).

## Quick start

Requirements: Docker Desktop with Docker Compose v2 `--wait` support, Python 3.12, `uv`, Node.js/npm, and PowerShell on Windows (GNU Make on macOS/Linux). The default workflow runs PostgreSQL in Docker and the backend/frontend on the host. Set `POSTGRES_PASSWORD` and the matching password in `DATABASE_URL` in `.env`; Compose uses the former and the host backend reads the latter. PostgreSQL binds to `127.0.0.1` only.

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
# Set POSTGRES_PASSWORD and use the same password in DATABASE_URL.
.\dev.ps1 be
```

`.\dev.ps1 be` starts PostgreSQL in Docker, applies migrations and seed data, then runs the backend locally with reload and logs in that terminal. In a second terminal, run `.\dev.ps1 fe` to start the frontend locally with Vite logs and hot reload; it installs npm dependencies automatically the first time. Open <http://localhost:5173> for the web app or <http://localhost:8000/docs> for the API. Stop each terminal with `Ctrl+C`; run `.\dev.ps1 down` to stop PostgreSQL while preserving its named volume. `make bootstrap-key` creates the initial admin API key; keep it private.

Vite proxies `/v1` to `http://localhost:8000` by default. If the API runs on another local port, set `VITE_API_PROXY_TARGET` before starting `.\dev.ps1 fe`, for example `http://127.0.0.1:8001`. If port 5173 is already in use, set `VITE_PORT` (for example `5174`) before starting the frontend.

If you need to process uploaded articles, run `.\dev.ps1 worker` in a third terminal.

For backend checks, set `TEST_DATABASE_URL` to a dedicated database named `aprkb_test`. The test fixture creates and removes isolated schemas there and never migrates the application's public schema. Use the same local password and host port as `DATABASE_URL`, then run `make check`.

Uploads require a curator API key and a seeded license. The sample `CC-BY` license permits mining; `PROPRIETARY` is rejected by the worker. In the internal `/writer` flow, an approved pattern with `PROPRIETARY` provenance can be shown with a `license_flag` marking it for internal use only. Missing license or provenance remains excluded. This policy must be changed before any public deployment.

Open the staff prototype at <http://localhost:5173/> and sign in with a curator or admin API key. In Vite development mode, **Quick demo** re-runs the idempotent self-authored seed data and issues a fresh local curator key. This button is restricted to loopback requests with `APP_ENV=local`. System integrations continue using their client API keys; client/reviewer pattern reads expose only approved current versions with display rights.

With `APP_ENV=local`, the writer connects automatically without an API key; the backend grants a local demo client only to requests from loopback addresses. This access is disabled in other environments. The flow uses published taxonomy/reference options, recommendation, approved version detail, render, validation, and feedback APIs. Render requires a `recommendation_id` issued to the same client. Validation runs V02, a limited V03 check for unsupported numeric/DOI/citation details against slot values and the separate supporting-context field, and a configured phrase screen for V06. Search keywords are not treated as evidence. V06 does not perform grammar analysis; V05 remains explicitly not checked until verified Offline guideline data is available. Other unfinished checks remain unavailable, so the UI labels copied text a draft. Journal-specific ranking waits for reviewed Offline guideline/fingerprint data and currently reports generic fallback. The MVP does not expose a validation override route.

Writer recommendation scores show each available criterion in its own horizontal cell with the criterion name and value; unavailable criteria display `—`.

Writer slots include self-authored instructions and examples. Render rejects empty required fields and values below the slot's configured minimum length with field-specific errors; missing optional slots remain as placeholders. Older slot definitions stored as type strings remain renderable with default required/minimum-length behavior.

The Writer loads approved, renderable samples into a table without requiring a filter. Genre, section, intent, claim type, evidence level, journal, and keywords are optional filters; selecting an evidence level hides stronger samples and reports the hidden count. The Writer selects article genre before section. Published taxonomy compatibility filters section choices, and changing the section refreshes rhetorical intents. Self-authored compatibility seed values remain provisional pending taxonomy-owner review.

The Online read contract combines each current pattern version with its intent name, typed slots, variants, usage constraints, evidence labels, provenance, and discipline affinities. `unknown` evidence or claim labels are returned as `null` with `labelled=false`. Provenance includes the license, DOI when present (otherwise `null`), separate `article_id`, and a source sentence count; it does not return sentence text. Mined bracket placeholders are interpreted as slots on read only when every marker matches the declared slot names.

`UsageConstraint.evidence_min` excludes a recommendation when the writer declares a lower evidence level, using the seeded `evidence_level` order through `EvidencePolicy`; without a declared level, table-first results are unchanged. `forbidden_contexts` currently matches literal requested section, genre, or claim type codes and reports `GATE_FORBIDDEN_CONTEXT`. **TODO(owner, FR-02.4):** confirm these matching semantics before treating the field as a broader context vocabulary.

The fallback tier chooser requires verified journal/genre, similar-journal fingerprint, subfield/genre, or field/genre data for the corresponding tier. Those signals are not available to Online yet, so every current recommendation uses `generic_genre`. Provenance scores are provisional values in `ranking_weights.yaml`: authored `1.0`, mined `0.7` (**TODO(owner, CR-06):** approve both values). The API retains the `linguistic` key for compatibility; the UI calls it **Keyword match** because it measures keyword overlap only.

| Ranking criterion | System Design §5.2 | Current Online (`ranking_weights.yaml`) |
| --- | ---: | ---: |
| Intent | 25% | — (gate, not a scorer) |
| Discipline | 20% | 20% |
| Journal and genre | 20% | 20% |
| Evidence | 15% | 30% |
| Keyword match (`linguistic` API key) | 10% | 15% |
| Provenance | 10% | 15% |

CR-06 changed the current weights; they remain provisional pending owner review.

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
| `make contracts` | Export OpenAPI and regenerate frontend types |
| `make web-install` / `make web` / `make fe` | Install frontend dependencies / start the frontend dev server |
| `.\dev.ps1 be` / `fe` / `worker` / `down` | PowerShell shortcuts for the local development workflow |

## Deployment

Production uses the backend Docker image with the existing PostgreSQL Compose volume, a persistent blob volume, and manually applied migrations. It does not run the development data initializer. Follow the [manual Docker Compose deployment runbook](deploy/README.md) after confirming the server's database volume and reverse proxy.

## Continuous integration

GitHub Actions runs on pushes to any branch and pull requests. The backend job checks the generated OpenAPI contract, Ruff lint/format, mypy, and pytest against an ephemeral PostgreSQL/pgvector service. The frontend job installs from the pnpm lockfile, checks generated API types, runs TypeScript checks, and builds the app. CI uses a disposable test database and needs no repository secrets.

### Logs

The API and worker write logs to stderr under the `aprkb.*` loggers; set the level with `LOG_LEVEL` (default `INFO`).

- **API**: one line per request (method, path, status, duration, `request_id`), rejected requests (4xx with error code; 422 lists field names only), import-profile create/update, import, upload, and mining enqueue events.
- **Worker**: job claimed, succeeded or failed with duration, the import page summary (counts per skip reason), and one line per SLR work (license, chosen artifact) or skipped article.
- **Excluded**: API keys, query strings, rejected input values, exception messages (only the type and stack frames are logged), and article or manuscript text. Match a failed response to its log line with the `X-Request-ID` header.

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

## Unified phrasebank reference

Each AP-RKB pattern opens a WB-02 detail view for frame, slots, variants, usage, evidence, provenance, and version. The list uses the full read contract without an extra request per pattern.

`/phrasebank` is a source-aware browser for Manchester reference material and AP-RKB's existing approved patterns. The Manchester collection is stored only in the separate `reference_sources`, `reference_categories`, and `reference_entries` tables; it never enters `phrase_patterns`, recommendations, render, or validate. Its API and UI are off by default (`REFERENCE_LIBRARY_ENABLED=false`). Manchester items always show the notice that reuse rights are unverified and the material must not be redistributed. Treat this as an internal, removable reference collection, not approved patterns. The AP-RKB group reads approved client-visible patterns through `/v1/patterns`; taxonomy sections are not mapped to Manchester categories (`TODO(owner)`).

To enable the local reference browser, set `REFERENCE_LIBRARY_ENABLED=true`, apply migrations from `apps/backend` with `uv run alembic -c alembic.ini upgrade head`, then import the external file with `uv run python -m aprkb.cli import-reference-library --file "D:\Project\FptProject\Academic-Phrase-Rhetorical-Knowledge-Base\data\raw\manchester-diverse\collection.json"`. The input file remains outside git. Remove the imported reference data with `uv run python -m aprkb.cli purge-reference-library`; disable API access again by setting the flag to false.

## Offline-to-Online data packs

The backend modules/pack/ tooling validates and transfers the PhrasePattern graph using natural reference keys and append-only version IDs. It excludes source text and the separate approved phrase store. Offline self-check: uv run --directory apps/backend python -m aprkb.cli validate-pack <pack-dir>. Online import: uv run --directory apps/backend python -m aprkb.cli init-reference, then uv run --directory apps/backend python -m aprkb.cli import-pack <pack-dir>; preview with --dry-run. See [data pack spec](doc/data-pack-spec.md) and [sample pack](data/packs/sample-demo/manifest.json).
