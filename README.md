# AP-RKB — Academic Phrase & Rhetorical Knowledge Base

AP-RKB is an academic writing assistant scaffold. The backend recommends rhetorical phrase frames, validates claim strength against evidence, and lets curators upload licensed text for traceable mining candidates. Phase-6 syntax mining consumes stored spaCy token features when `NLP_ENGINE=spacy` and accepts only closed, reviewed frame content; the Tier 2 hybrid fallback retains approved fixed leads and rejects split modifiers, heading joins, and frames below its provisional fixed-content threshold. NER, production classifiers and taxonomy publishing remain out of scope. The `/writer` web route uses the real API and PostgreSQL; other prototype screens still use local mock data.

## Architecture

Phrasebank data initialization uses one [JSON manifest workflow](doc/phrasebank-initialization.md) for AP-RKB patterns, Manchester references, and their filter mappings. It reuses the existing import formats and preserves the current runtime APIs.

```text
apps/web (React + TypeScript SPA; Vite runs locally by default)
               │ REST /v1 + OpenAPI
apps/backend (FastAPI modular monolith)
  API ── domain services ── PostgreSQL 16 + pgvector
  worker ── PostgreSQL jobs table (FOR UPDATE SKIP LOCKED)
  corpus blobs ── local ./data/blobs via BlobStore
```

The scaffold keeps the existing `apps/backend/src/aprkb` package and module boundaries. PostgreSQL is the sole database and job queue. The worker is started separately with `make worker`; no Redis or Celery service is used. Text and Markdown ingestion are implemented; JATS and PDF parsers remain explicit stubs. SLR imports use curator-managed profiles in `/import`: saving a profile and choosing “Lấy bài báo” creates a queued job whose filters are snapshotted in its payload. Job results report listed, imported and skipped counts. Set `ARTICLE_SOURCE=slr`, `SLR_API_BASE_URL` (default `https://slr-api.hyperdatalab.org/api`) and `SLR_API_KEY`; timeout, retry count and maximum download size use `SLR_TIMEOUT_SECONDS`, `SLR_MAX_RETRIES` and `SLR_MAX_DOWNLOAD_BYTES`. SLR enforces a limit of 120 requests per minute, handled through `Retry-After`. Imports fail closed: missing, unknown or non-mining licenses are skipped before download. The real SLR API currently returns no license data, so for development only `SLR_DEV_FALLBACK_LICENSE=DEV-UNVERIFIED` assigns that placeholder license to works whose license is missing or unknown; works with a known non-mining license stay blocked. The setting is rejected unless `APP_ENV` is `local` or `test`, and articles under `DEV-UNVERIFIED` must be deleted before production. PDF files can be stored, but the PDF parser remains a stub, so they cannot be mined yet. License aliases and rights are defined in `apps/backend/src/aprkb/policies/licenses.yaml`. OpenAlex is not queried. Ingest uses the shared character-level boundary rules from `policies/sentence_rules.yaml`; `NLP_ENGINE=regex` is the default and `NLP_ENGINE=spacy` stores token features with the selected model. The mining `sentence_filter` drops table rows, captions, math and numeric noise and non-rhetorical sections (thresholds in `policies/mining_filter.yaml`, provisional). After changing these rules, run `uv run --directory apps/backend python -m aprkb.cli reingest --source slr`; it replaces sentences and their pending candidates, and skips articles that have reviewed candidates. See [ADR-0001](doc/adr/0001-modular-monolith.md), [ADR-0005](doc/adr/0005-external-article-source.md), [ADR-0006](doc/adr/0006-slr-repository-import.md), [ADR-0010](doc/adr/0010-spacy-ingest-token-features.md) and [the scaffold PRD](SCAFFOLD_PRD.md).

The development pipeline uses the existing upload/import → ingest → `mine_article` worker → pending candidate → two reviewer rounds flow. Rule-based slot extraction stores typed public slot schemas and private provenance offsets; it does not write patterns or versions. Syntax reporting frames preserve the whole sentence around typed slots, the ROOT verb group and only approved lead-ins; unlisted surrounding content is rejected. Tense and modality remain separate, and modality is not persisted yet. Ownership uses determiner+noun tiers: unconditional own, guarded own, prior, or literal unclear; the tier lists are provisional. Epistemic tagging runs after extraction on masked frames; `show` is neutral with no strength, and the status field is in-memory only. A small, versioned closed-world registry adds author-action, relation/role, and performance/evaluation frames from stored token features; the reporting-verb path keeps precedence. The `/extract` page works on top of that flow: it groups articles by import batch, queues mining for one or more batches, shows each article's text beside its mined phrases, and lets one reviewer accept or reject each phrase; accepted phrases are stored in `approved_phrases` (not as patterns), see [ADR-0009](doc/adr/0009-phrase-extraction-page.md). The read-only `phrase-stats` CLI contrasts frame document frequency across batches or journals; results are descriptive and show no sentence text. Gold labels are a separate development/evaluation path: Groq can draft labels behind explicit runtime settings, and one human reviewer makes the final decision. Only human-approved, current gold items are scored by `eval-mining`; NER, synonym expansion and production AI assistance remain deferred. See [ADR-0007](doc/adr/0007-rule-based-slot-abstraction.md), [ADR-0010](doc/adr/0010-spacy-ingest-token-features.md), [ADR-0011](doc/adr/0011-construction-registry-and-frame-statistics.md), [ADR-0012](doc/adr/0012-slot-abstractor-frames-and-ownership.md), [ADR-0008](doc/adr/0008-gold-dev-labeling.md), and the [knowledge enrichment flow](doc/knowledge-enrichment-flow.md).

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

### spaCy and Tier 2

`.env.example` enables `NLP_ENGINE=spacy` and `MINING_HYBRID_ENABLED=true`, because Tier 2 (the hybrid slot engine) needs the token features stored at ingest. spaCy and the `en_core_web_sm` model are the locked optional dependency group `spacy` in `apps/backend/pyproject.toml` (the model is a hash-pinned wheel from the spaCy model releases). `make install`, `.\dev.ps1 be`, the CI jobs and the backend Docker image all install it with `--extra spacy`. To install it by hand:

```powershell
uv sync --directory apps/backend --extra spacy
```

Do not install the model with `uv pip install`: a plain `uv sync` removes packages that are not in the lock file. Articles ingested earlier with `regex` have no stored tokens, so re-ingest them (`python -m aprkb.cli reingest --source slr`, replacing `slr` with the article source) before Tier 2 can produce frames. Without spaCy or the model, ingest fails with `NLP_ENGINE=spacy requires spaCy and model ...`; set `NLP_ENGINE=regex` and `MINING_HYBRID_ENABLED=false` for a setup without them. The production deployment (manual, from `main`, see `deploy/README.md` there) must set both variables in its own environment (`TODO(owner)`).

For PostgreSQL-backed backend checks, set `TEST_DATABASE_URL` in the current PowerShell process to a valid connection for the dedicated `aprkb_test` database, then run the PowerShell script below. For example:

```powershell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://aprkb:<current-local-password>@localhost:5432/aprkb_test"
.\scripts\test-backend.ps1
```

Replace the placeholder locally; do not paste credentials into source files or point this variable at `aprkb` or production. The script checks the database name before running pytest. The fixture creates and removes isolated schemas in `aprkb_test` and never migrates the application's public schema.

Uploads require a curator API key and a seeded license. The sample `CC-BY` license permits mining; `PROPRIETARY` is rejected by the worker. In the internal `/writer` flow, an approved pattern with `PROPRIETARY` provenance can be shown with a `license_flag` marking it for internal use only. Missing license or provenance remains excluded. This policy must be changed before any public deployment.

Open the staff prototype at <http://localhost:5173/> and sign in with a curator or admin API key. In Vite development mode, **Quick demo** re-runs the idempotent self-authored seed data and issues a fresh local curator key. This button is restricted to loopback requests with `APP_ENV=local`. System integrations continue using their client API keys; client/reviewer pattern reads expose only approved current versions with display rights.

With `APP_ENV=local`, the writer connects automatically without an API key; the backend grants a local demo client only to requests from loopback addresses. This access is disabled in other environments. The flow uses published taxonomy/reference options, recommendation, approved version detail, render, validation, and feedback APIs. Render requires a `recommendation_id` issued to the same client. When a journal is selected, recommendation queries only approved mined patterns whose provenance article belongs to that journal; an empty mapping returns no candidates and never falls back to another journal or generic patterns. Validation runs V02, a limited V03 check for unsupported numeric/DOI/citation details against slot values and the separate supporting-context field, and a configured phrase screen for V06. Search keywords are not treated as evidence. V06 does not perform grammar analysis. V05 is outside the current sentence-validation scope; the Writer labels journal-guideline compliance separately from unavailable sentence checks. Other unfinished in-scope checks remain unavailable, so the UI labels copied text a draft. The MVP does not expose a validation override route.

Writer recommendation scores show each available criterion in its own horizontal cell with the criterion name and value; unavailable criteria display `—`.

Writer slots include self-authored instructions and examples. Render rejects empty required fields and values below the slot's configured minimum length with field-specific errors; missing optional slots remain as placeholders. Older slot definitions stored as type strings remain renderable with default required/minimum-length behavior.

The Writer loads approved, renderable samples into a table without requiring a filter. Genre, section, intent, claim type, evidence level, journal, and keywords are optional filters; selecting an evidence level hides stronger samples and reports the hidden count. The Writer selects article genre before section. Published taxonomy compatibility filters section choices, and changing the section refreshes rhetorical intents. Self-authored compatibility seed values remain provisional pending taxonomy-owner review.

The Online read contract combines each current pattern version with its intent name, typed slots, variants, usage constraints, evidence labels, provenance, and discipline affinities. `unknown` evidence or claim labels are returned as `null` with `labelled=false`. Provenance includes the license, DOI when present (otherwise `null`), separate `article_id`, and a source sentence count; it does not return sentence text. Mined bracket placeholders are interpreted as slots on read only when every marker matches the declared slot names.

The entire app is for internal use. Licenses explicitly listed in `license_policy.yaml` under `internal_use_codes` permit recommendations, pattern reads, and rendering even when public-display permission is false. Sources with neither display permission nor configured internal-use permission remain excluded. The response preserves the actual public-display permission and marks the internal-use exception with `license_flag`.

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
| `.\scripts\test-backend.ps1` | Run backend tests after validating `TEST_DATABASE_URL` targets `aprkb_test` |
| `make install` | Sync backend dependencies with `uv` |
| `make migrate` | Apply the Alembic migration |
| `make seed` | Idempotently load reference enums, taxonomy, and self-authored patterns |
| `make bootstrap-key` | Create the first admin API key and print it once |
| `make phrase-stats ARGS="--focal-batch <uuid> --background all-other"` | Contrast masked frame document frequencies (read-only; no sentence text) |
| `make run` | Start FastAPI with reload |
| `make worker` | Poll PostgreSQL jobs and process ingestion/mining |
| `make test` | Run backend unit, integration, and scaffold acceptance tests |
| `make test-db-required` | Fail if `tests/integration` collects zero tests or any test in it skips (needs `TEST_DATABASE_URL`) |
| `make lint` | Run Ruff, format verification, and mypy |
| `make lint-web` | Run the frontend's zero-warning ESLint check |
| `make contracts` | Export OpenAPI and regenerate frontend types |
| `make container-build` | Build the one backend image the API and worker both run from |
| `make container-smoke-api` / `make container-smoke-worker` | Run the image's API/worker command against a disposable PostgreSQL and verify health/graceful shutdown |
| `make container-audit` | Build-context canary: fail if secrets/caches/blobs/test output leak into the image |
| `make web-install` / `make web` / `make fe` | Install frontend dependencies / start the frontend dev server |
| `.\dev.ps1 be` / `fe` / `worker` / `down` | PowerShell shortcuts for the local development workflow |

## Deployment

Production uses Docker Compose for the API, worker, and web app, with persistent PostgreSQL and blob volumes and manually applied migrations. It does not run the development data initializer. Follow the [manual Docker Compose deployment runbook](deploy/README.md) before starting services on the server.

## Continuous integration

GitHub Actions runs on pushes and pull requests, with superseded runs on the same branch cancelled automatically (except `dev`). Third-party actions are pinned to reviewed commit SHAs. Jobs:

- `CI / backend-quality-and-tests` — OpenAPI contract check, Ruff lint/format, mypy, Alembic migration, then PostgreSQL integration tests (which must never silently skip; see `scripts/ci/require-db-tests.sh`), then the full suite.
- `CI / frontend-quality-and-build` — zero-warning ESLint, generated API types drift check, TypeScript, and build.
- `CI / backend-image-contract` — builds the one image the API and worker both run from, runs the build-context canary, then smokes both commands against a disposable PostgreSQL. Exists and runs on every push/PR; not yet a required check (see the CI runbook).
- `CI / frontend-e2e-smoke` — Playwright against a migrated/seeded database and a running API/frontend. Stage A observability only (`continue-on-error: true`); promotes to required only after the stability window in `plans/ci-cd-team-standard/phase-02-enforced-ci.md`.

CI uses a disposable test database and needs no repository secrets.

### Deployment (production)

Production deploys are manual, from `main`, via Docker Compose over Tailscale — see
`deploy/README.md` on `main`. [ADR-0010](doc/adr/0010-ci-cd-platform.md) is
superseded: it proposed a GHCR/self-hosted-runner CD track before that existing
deployment was discovered, and the corresponding scaffolding was removed from
`dev`. CI (this workflow) does not build or publish anything toward production.

Team delivery changes become PR-only once the ruleset is activated — see "Still pending before branch protection is enabled" in [the CI runbook](doc/runbooks/ci.md); only `backend-quality-and-tests` and `frontend-quality-and-build` are candidates for that first activation. Workflow, Docker, migration, policy, lockfile, infrastructure, and runbook changes require CODEOWNER review. Every PR records verification evidence plus migration, rollback, secret/data-handling, and `BLOB_DIR` impact. Required checks may not be bypassed silently; the time-limited break-glass process and check-rename procedure are defined in the CI runbook. Database releases follow [the migration runbook](doc/runbooks/migrations.md), and application/database recovery follows [the rollback runbook](doc/runbooks/rollback.md).

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

Phrasebank applies keyword, section, and intent filters on the backend before limiting results to 200 patterns. The Online Phrasebank Basic source is `apps/backend/src/aprkb/seeds/phrasebank_basic.json`: the seed loader maps its categories to METHODS taxonomy intents in release `0.2.0` and each example to an approved `PhrasePattern`/`PatternVersion`, with typed slots for X/Y/Z, continuations, and citation placeholders. The base `0.1.0` taxonomy stays available for Offline packs. The same approved DB rows feed Phrasebank display and `/v1/recommendations`; the frontend does not maintain a second phrase list for this flow.

`/phrasebank` reads the lab-authored Phrasebank Basic patterns from `/v1/patterns`, the same approved records used by recommendation and rendering. Category headings are represented as intents under the METHODS section; example text is stored as a canonical frame, slots, and authored provenance. The former external reference-library backend remains isolated and disabled; it is not a source for this Online flow.

For local or deployed Online initialization, apply migrations and run `python -m aprkb.seeds.load`. Every environment loads Phrasebank Basic from the packaged JSON plus taxonomy and reference options; Online initialization does not read legacy `data/seed/patterns.json` fixtures.

## Metric & Measurement catalog

`/measurements` is a separate, self-authored catalog that answers "how to measure". It has three
kinds of entry: metrics (for example accuracy and Cohen's kappa), measurement methods (for example
a 5-point Likert questionnaire) and data-collection protocols (for example a pre-test/post-test
design). It complements the phrase core, which answers "how to write". The catalog lives in its own
`measurement_*` tables and never enters ranking, render, validate or pack export. The API and UI
are off by default (`MEASUREMENT_ENABLED=false`).

The link to phrases is a curator-reviewed slot link, for example `likert_5_point` for the
`{instrument}` slot of a Methods pattern. Only approved links are shown, and only as
suggestions; a slot is never filled automatically (FR-07.5, AT-08). To enable the catalog locally:

1. Set `MEASUREMENT_ENABLED=true`.
2. Run `uv run alembic -c alembic.ini upgrade head` from `apps/backend`.
3. Import the catalog: `uv run python -m aprkb.cli measurement-import --file ../../data/seed/measurement_catalog.json`.

Re-importing the same file is a no-op. Codes that disappear from a new catalog are reported, not
deleted. Remove everything with `uv run python -m aprkb.cli measurement-purge`.

Academic Phrase Bank Methods templates have no slots, so they use pattern-level links.
`uv run python -m aprkb.cli measurement-propose-links [--dry-run]` proposes them from catalog
terms found in the frames of APB Methods functions. A curator approves or rejects each
proposal on the measurement entry page. Approved links show as "Measurement context" on the
pattern page.

While the flag is on, `/v1/validate` also returns report-only `metric_warnings` (FR-08.2):
catalog metrics that the sentence names but the writer's slots or context do not. They never
change the validation severity. See ADR-0015.

## Offline-to-Online data packs

The backend `modules/pack/` tooling validates and transfers the PhrasePattern graph using natural reference keys and append-only version IDs. It excludes source text and the separate approved phrase store. Offline self-check: `uv run --directory apps/backend python -m aprkb.cli validate-pack <pack-dir>`. Read-only export: `uv run --directory apps/backend python -m aprkb.cli export-pack --out <pack-dir> --only-approved`. Export reports excluded approved patterns by ID/code/path and does not invent missing labels or approvals. Check exported and excluded counts before transfer.

Keep the active Online database query-only. Run the write commands `init-reference` and `import-pack` only on a separate Offline/staging/test destination (`import-pack --dry-run` previews the transfer); provisioning Online data is a separate process. Shared modules do not enforce deployment separation, so use the appropriate database credentials. See [data pack spec](doc/data-pack-spec.md) and [sample pack](data/packs/sample-demo/manifest.json).

Offline reviewers can assign a pending candidate's published-taxonomy intent with `PUT /v1/admin/review-queue/{id}/intent`, body `{"intent_id": "<published-intent-uuid>"}`, before the first approval. This uses the existing candidate field and requires no migration. Once review starts, intent is frozen. For a legacy first approval with no intent, only that original reviewer can assign and confirm the missing intent. This workflow is available through the API (`/docs`); `/extract` continues to approve separate phrases under ADR-0009. Claim type remains unlabelled after normal promotion and is reported as an export exclusion until a separate human-labelling workflow exists.
