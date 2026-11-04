# Database Migration Runbook

## Safety contract

PostgreSQL is both the database and job queue. Run Alembic exactly once per release, never independently in every API or worker replica. Prefer expand/migrate/contract changes so the previous image remains compatible during rollout. `alembic downgrade` is not automatically safe; use it only when that exact downgrade has been tested with representative data.

## Preflight

1. Confirm the target is not production when running CI tests; CI must use `aprkb_test`.
2. Record the current revision and target revision.
3. Verify there is exactly one Alembic head.
4. Classify the release as N-1 compatible or roll-forward-only using the compatibility matrix in the CI/CD plan.
5. Confirm the database backup owner, latest successful backup, restore procedure, recovery objective, and maintenance window.
6. Decide whether worker drain is required. As of 2026-11-04, `apps/backend/src/aprkb/worker/runner.py` handles SIGTERM/SIGINT gracefully: it stops claiming new jobs, lets the in-flight job finish, then exits cleanly (`docker stop` on the production worker container triggers this; verified by `scripts/ci/container-smoke-worker.sh`). This is a real drain primitive, but it does not yet log a reconciled queued/in-flight/completed count at drain time (`TODO(owner)`); inspect `jobs` table status counts manually if that evidence is needed. `scripts/cd/deploy.sh` stops the worker container (triggering this drain) before migrating.

## Execution

`scripts/cd/deploy.sh` (Phase 05) serializes release-time work through `concurrency: group: production-deploy, cancel-in-progress: false` in `.github/workflows/cd-deploy.yml`, so two deploy workflow runs cannot execute concurrently. An **independent PostgreSQL advisory/release lock** around the migration step itself — required so a manual `alembic upgrade head` run outside the workflow can't race a deploy — is not yet implemented (`TODO(owner)`); until it exists, only the named operator running `scripts/cd/deploy.sh` (or the workflow) may run migrations, and no one should run `alembic upgrade head` by hand against production outside that script. Run the migration once, record the result, and end the maintenance lock only after post-migration verification. Do not run seeds or bootstrap-key as an implicit migration step.

## Recovery

Prefer a forward fix. Application rollback is allowed only when the previous image is compatible with the migrated schema. If neither is safe, stop rollout, keep the Docker Compose worker stopped until a tested drain control exists, preserve evidence, and invoke the approved database restore procedure. Never log API keys, article text, manuscript text, or job payload contents.
