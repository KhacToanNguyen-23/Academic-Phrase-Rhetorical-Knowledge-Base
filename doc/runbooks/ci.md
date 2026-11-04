# Continuous Integration Runbook

## Ownership and required checks

`@KhacToanNguyen-23` is the initial delivery owner. Phase 02 will establish stable required check names before branch protection is enabled.

The handle and repository access were verified through the GitHub API on 2026-11-04: the account is a user, the private repository default branch is `main`, and the account has repository admin access. CODEOWNER routing still requires a draft-PR proof before enforcement.

## Baseline recorded on 2026-11-04

- Current GitHub job names are `backend` and `frontend`. The latest observed run took 75 seconds for backend and 28 seconds for frontend; the latest 10 workflow runs all succeeded with end-to-end durations of 75–126 seconds (average about 91 seconds). Push and pull-request triggers can create duplicate runs for the same branch.
- Local backend verification ran without the dedicated PostgreSQL integration environment and collected 493 tests: 421 passed and 72 skipped. The skipped set includes environment-dependent tests and intentional scaffold TODO skips; GitHub CI provides `aprkb_test`, so Phase 02 must report and reject environment-caused integration skips while preserving intentional scaffold TODO skips.
- No flaky test is currently registered. A future retry does not establish a flake until evidence and the quarantine process below are recorded.
- Current Docker behavior is local-only: `aprkb-backend:latest`, `aprkb-worker:latest`, and `aprkb-frontend:latest` exist without a registry namespace or verified remote digest. The checked-in backend Dockerfile has no production image contract yet.
- Deployment owner is `@KhacToanNguyen-23`; target runtime is Docker Compose on a homeserver. No automated production deploy actor exists in the repository.
- No container registry is configured. GHCR is recommended but remains a Phase 04 decision.
- Migrations are currently applied with Alembic through `make migrate`; there is no serialized production migrator or implemented advisory release lock.
- `BLOB_DIR` defaults to `./data/blobs`. The checked-in Compose file only defines PostgreSQL, so no shared production API/worker blob mount is established. The proposed homeserver mapping `/srv/aprkb/blobs:/data/blobs` remains unverified until the production Compose artifact exists.

These names are planned contracts, not active ruleset entries. Do not configure branch protection from this table until Phase 02 proves the corresponding jobs on a disposable PR.

| Planned check contract | Local equivalent | Owner |
| --- | --- | --- |
| Backend quality and tests | `make lint` then `make test` | backend owner |
| Frontend quality and build | `pnpm --dir apps/web lint`, `pnpm --dir apps/web typecheck`, `pnpm --dir apps/web build` | frontend owner |
| Frontend smoke E2E | `pnpm --dir apps/web test:e2e` | frontend owner |
| Backend image contract (Phase 03) | `docker build -f apps/backend/Dockerfile -t aprkb-backend:ci apps/backend` then `docker image inspect aprkb-backend:ci` | delivery owner |

Backend database tests require `TEST_DATABASE_URL` to target a dedicated PostgreSQL database named `aprkb_test`. Never substitute a production database.

## Failure handling

1. Read the first failing step and reproduce its documented local command.
2. Fix the cause in a new commit; do not rerun until green without explaining an infrastructure-only failure.
3. If a third-party service is unavailable, record the service, timestamp, error, and the unrun check in the PR.
4. Escalate workflow, migration, secret, or persistent-storage failures to the delivery owner.

## Flaky tests

A retry that passes does not erase the original failure. Quarantine requires a linked issue, named owner, expiry date, failure evidence, and an explicit non-blocking check. An expired quarantine becomes blocking. Deterministic smoke tests graduate to required status only under the thresholds in the CI/CD plan.

## Required-check rename procedure

Change the workflow job name, this runbook, and the GitHub ruleset in one reviewed change. Stage the new check on a disposable PR, confirm it reports, replace the old ruleset entry, then confirm a failing check blocks merge.

## Break glass

Only the smallest configured bypass group may act. Record actor, independent approver, incident/change reference, reason, start/end time, affected commit, checks bypassed, and evidence that normal protection was restored. Review the event after service recovery.
