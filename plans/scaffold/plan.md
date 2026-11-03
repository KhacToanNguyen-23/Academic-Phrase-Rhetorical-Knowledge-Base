# Plan: AP-RKB scaffold

Date: 2026-10-30
Mode: hard
Risk: high-risk - authentication, database schema and infrastructure changes.
Sources: spec.md and ../../SCAFFOLD_PRD.md. The user chose to retain the existing repository structure and apply the PRD's functional decisions.

## Objective and scope

Build a runnable, testable backend meeting the PRD definition of done, without implementing excluded algorithms or features. Retain apps/backend/src/aprkb and apps/backend/tests. Replace the Celery/Redis execution path with PostgreSQL polling. Keep the existing frontend outside the scaffold execution path. The scaffold PRD overrides older documents except for the layout decision above.

## Existing state

Backend modules already have router/service/repository/models files, mostly placeholders; migrations are absent. api/routes.py mounts routes that differ from PRD section 7, and health does not check the database. Compose and dependencies currently include Redis, Celery and NLP services. Inspect actual files before modifying them; do not assume placeholder files are safe to delete.

## Phases

| Phase | Scope | Dependencies | Stories |
| --- | --- | --- | --- |
| [01](phase-01-foundation.md) | Infrastructure, configuration, schema, migration | None | P1 startup |
| [02](phase-02-policy-identity-seed.md) | Policy, identity, audit, seeds | 01 | P1 startup and access control |
| [03](phase-03-pipelines.md) | Pure recommendation, validation and mining pipelines | 02 | P1 recommendations and validation; P2 interfaces |
| [04](phase-04-api.md) | Services, API contracts, review | 01-03 | P1 API and permissions |
| [05](phase-05-worker.md) | Blob storage, ingestion, polling and mining | 01-04 | P1 upload to candidate |
| [06](phase-06-verification.md) | Integration, acceptance, lint and documentation | 01-05 | All P1/P2 |

Phases are sequential checkpoints; write meaningful tests alongside each implementation. The user invoked `--hard --tdd` for this execution.

## Progress

- [x] Phase 01: Infrastructure and data — verified; code review approved.
- [x] Phase 02: Policy, identity, audit, seeds — verified; code review approved.
- [x] Phase 03: Recommendation, validation and mining pipelines — verified; code review approved.
- [x] Phase 04: Services, API contracts and review — verified; code review approved.
- [x] Phase 05: Blob storage, ingestion, polling and mining — verified; code review approved.
- [x] Phase 06: Integration, acceptance, lint and documentation — verified; code review approved.

## Layout mapping

- PRD app/core and app/db map to apps/backend/src/aprkb/core and existing module models. Add Alembic in apps/backend.
- PRD app/modules maps to apps/backend/src/aprkb/modules; add policy, discipline and pipeline packages as needed. Preserve router -> service -> repository boundaries.
- PRD app/api/v1 maps to apps/backend/src/aprkb/api and existing module routers, mounted under /v1 with clearly grouped admin routes.
- PRD app/workers maps to apps/backend/src/aprkb/worker, replacing the Celery execution path with polling.
- Place versioned YAML under apps/backend/src/aprkb/policies; retain data/seed for seed data and add a backend entrypoint. Tests live under apps/backend/tests. Root Makefile commands must work regardless of backend working directory.
- Admin console remains a placeholder; do not choose a new frontend stack.

## Decisions and dependencies

- Handle cyclic foreign keys between api_clients/created_by and phrase_patterns/current_version using explicit table and constraint ordering. Use UUID, UTC, JSONB and pgvector per PRD; seed created_by is nullable.
- Audit and data writes share a transaction; do not log keys or complete articles. Apply the exact PRD role hierarchy.
- Validate policies at startup; EvidenceGate and V02 use the same EvidencePolicy. Preserve owner TODOs and identify draft seed and policy content as provisional.
- Provide a minimal text parser for the DoD; PDF parser remains a stub. Any unspecified filter thresholds must be configuration with explicit provisional TODO(owner), not an invented approved business rule.
- Specify minimal fallback behavior and ingest/mine ordering during implementation without inventing journal similarity data.

## Risks and checks

- PRD gives 501 for unimplemented endpoints but specifies real behavior for others: implement each mandated behavior and use 501 only where appropriate.
- Upload-to-candidate spans transactions, license checks, offsets, provenance and job status; exercise the entire path with a real worker and PostgreSQL.
- Original acceptance criteria are not all reproduced in scaffold PRD: preserve TODO/skip except for behavior actually covered under section 10.
- PostgreSQL/pgvector integration tests need isolated test data and migration/seed verification. Report missing infrastructure instead of claiming tests passed.

## Completion

Run the PRD section 12 commands in a clean environment and verify /docs, recommendation, validation and upload-to-mine. Record actual results. Document commands, architecture, stubs and the PRD traceability table. No deployment or admin UI.

## Red-team review

Review verdict: WARN. Accepted findings are incorporated in phases 02-06: fallback gating and deduplication, transaction-aware audit scope, explicit unknown policy and zero-weight handling, deterministic pre-ingest mining behavior, bounded worker recovery, and DB-backed acceptance verification. Decisions unspecified by the PRD remain implementation choices to validate.

## Session Notes
<!-- Updated by cook automatically. -->

**Last active:** 2026-10-30
**Phase in progress:** complete
**Status:** Phases 01-06 are complete and code review approved. Full PostgreSQL-backed suite: 76 passed, 9 out-of-scope/underspecified acceptance cases skipped. Ruff check/format, mypy, diff checks, fresh database setup, live `/docs`, recommendations, validation, and upload-to-candidate verification passed.

### Decisions made this session
- Use asyncpg for SQLAlchemy async PostgreSQL connections and include SQLAlchemy asyncio extras (greenlet), discovered by the project virtual environment.
- Fix the vector placeholder dimension at 384 as a documented storage choice; no fingerprint logic is implied.
- Freeze initial DDL in the Alembic revision instead of generating it from current ORM metadata at migration time.
- Keep ORM entities in the existing domain `models.py` modules; `load_models()` imports each module for Alembic.
- The test fixture targets a dedicated database named `aprkb_test`, creates a per-run schema, and applies the Alembic revision through its command API.

### Next immediate action
- Scaffold implementation and handoff documentation are complete.
