# Continuous Integration Runbook

## Ownership and required checks

`@KhacToanNguyen-23` is the initial delivery owner. Phase 02/03 implemented the stable required check names below (2026-11-04); branch protection itself is not yet enabled — see "Still pending" at the end of this section.

The handle and repository access were verified through the GitHub API on 2026-11-04: the account is a user, the private repository default branch is `main`, and the account has repository admin access. CODEOWNER routing still requires a draft-PR proof before enforcement.

## Baseline recorded on 2026-11-04

- Current GitHub job names are `backend` and `frontend`. The latest observed run took 75 seconds for backend and 28 seconds for frontend; the latest 10 workflow runs all succeeded with end-to-end durations of 75–126 seconds (average about 91 seconds). Push and pull-request triggers can create duplicate runs for the same branch.
- Local backend verification ran without the dedicated PostgreSQL integration environment and collected 493 tests: 421 passed and 72 skipped. The skipped set includes environment-dependent tests and intentional scaffold TODO skips; GitHub CI provides `aprkb_test`, so Phase 02 must report and reject environment-caused integration skips while preserving intentional scaffold TODO skips.
- No flaky test is currently registered. A future retry does not establish a flake until evidence and the quarantine process below are recorded.
- As of 2026-11-04, `apps/backend/Dockerfile` is a multi-stage, non-root, digest-pinned-base image that runs both the API (default `CMD`) and worker (`python -m aprkb.worker.runner`) from one build; `scripts/ci/container-smoke-api.sh`/`container-smoke-worker.sh`/`container-canary.sh` verify this locally and in CI. It is still local-only: no registry push exists yet (Phase 04 decision).
- Deployment owner is `@KhacToanNguyen-23`; target runtime is Docker Compose on a homeserver. No automated production deploy actor exists in the repository.
- No container registry is configured. GHCR is recommended but remains a Phase 04 decision.
- Migrations are currently applied with Alembic through `make migrate`; there is no serialized production migrator or implemented advisory release lock.
- `BLOB_DIR` defaults to `./data/blobs`. The checked-in Compose file only defines PostgreSQL, so no shared production API/worker blob mount is established. The proposed homeserver mapping `/srv/aprkb/blobs:/data/blobs` remains unverified until the production Compose artifact exists.

## Required check names (Phase 02, implemented 2026-11-04)

These are the exact GitHub job names in `.github/workflows/ci.yml`. Configure branch
protection with the first two; the other two exist and run on every push/PR but are
**not required yet** pending the stability evidence Phase 02/03 call for.

| Check name | Required? | Local equivalent | Owner |
| --- | --- | --- | --- |
| `CI / backend-quality-and-tests` | Yes | `make lint && bash scripts/ci/require-db-tests.sh && make test` (needs `TEST_DATABASE_URL=...aprkb_test`) | backend owner |
| `CI / frontend-quality-and-build` | Yes | `pnpm --dir apps/web lint`, `pnpm --dir apps/web typecheck`, `pnpm --dir apps/web build` | frontend owner |
| `CI / backend-image-contract` | Not yet — needs default-branch green runs + a disposable-PR ruleset test first | `make container-build && make container-audit`, then `make container-smoke-api`/`container-smoke-worker` on a shared Docker network aliased `pg` | delivery owner |
| `CI / frontend-e2e-smoke` | Not yet — Stage A observability only (`continue-on-error: true`); promotes per the stability window in `plans/ci-cd-team-standard/phase-02-enforced-ci.md` | `pnpm --dir apps/web test:e2e` against a migrated+seeded `aprkb_test` and a running API | frontend owner |

Backend database tests require `TEST_DATABASE_URL` to target a dedicated PostgreSQL database named `aprkb_test`. Never substitute a production database. `scripts/ci/require-db-tests.sh` fails the run if `tests/integration` collects zero tests or any test in it skips, instead of silently shrinking; intentional TODO/scaffold skips remain confined to `tests/acceptance` and are reported, not gated, there.

### Container checks

`scripts/ci/container-smoke-api.sh`, `container-smoke-worker.sh`, and `container-canary.sh`
are the source of truth for the image contract — CI and `make container-*` targets both
call them, so a local reproduction never drifts from what CI runs. The canary plants
unique sentinel strings in every build-context path category that must be excluded
(`.env.canary`, a cache file, test output, a local blob) and fails if the built image's
filesystem contains them.

### Still pending before branch protection is enabled

The ruleset itself is not yet configured. Per `plans/ci-cd-team-standard/phase-01-governance-and-baseline.md` and `phase-02-enforced-ci.md`, enabling it still needs:

1. A disposable branch/PR proving the staged ruleset: required-check failure blocks merge, stale approvals get dismissed, CODEOWNER review is enforced, and a renamed/missing check is recoverable.
2. The repository administrator's sign-off on the settings proven in step 1.
3. Confirmation that fork-origin PRs run `backend-quality-and-tests`/`frontend-quality-and-build` without access to any deployment secret (none exist yet, so this is currently true by construction — re-check once Phase 04/05 add any).

`backend-image-contract` and `frontend-e2e-smoke` are deliberately excluded from the first ruleset activation; add them as required only after their own promotion criteria in the table above are met.

### Known package-manager ambiguity (tracked, not yet resolved)

`apps/web` has both `pnpm-lock.yaml` (canonical, used by CI) and an unused
`package-lock.json`. Removing the stray lockfile is deferred to its own reviewed change
per `plans/ci-cd-team-standard/phase-02-enforced-ci.md` item 5, so a lockfile removal
PR doesn't get bundled with unrelated CI changes. `CODEOWNERS` covers
`package-lock.json` in the meantime so it can't be reintroduced unreviewed.

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
