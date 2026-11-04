# Database Migration Runbook

## Safety contract

PostgreSQL is both the database and job queue. Run Alembic exactly once per release, never independently in every API or worker replica. Prefer expand/migrate/contract changes so the previous image remains compatible during rollout. `alembic downgrade` is not automatically safe; use it only when that exact downgrade has been tested with representative data.

## Preflight

1. Confirm the target is not production when running CI tests; CI must use `aprkb_test`.
2. Record the current revision and target revision.
3. Verify there is exactly one Alembic head.
4. Classify the release as N-1 compatible or roll-forward-only using the compatibility matrix in the CI/CD plan.
5. Confirm the database backup owner, latest successful backup, restore procedure, recovery objective, and maintenance window.
6. Decide whether worker drain is required. The scaffold has no drain command today. Until Phase 05 implements and tests one, stop/scale the Docker Compose worker before the maintenance window, verify no worker container is running, and inspect job-status counts without payload text. Do not claim a graceful drain merely because the container stopped.

## Execution

Phase 05 must implement a defined PostgreSQL advisory/release lock before automated production migration. Until then, allow only one named operator in the maintenance window and record that manual serialization. Run `uv run --directory apps/backend alembic -c alembic.ini upgrade head` once, record the result, and end the maintenance lock only after post-migration verification. Do not run seeds or bootstrap-key as an implicit migration step.

## Recovery

Prefer a forward fix. Application rollback is allowed only when the previous image is compatible with the migrated schema. If neither is safe, stop rollout, keep the Docker Compose worker stopped until a tested drain control exists, preserve evidence, and invoke the approved database restore procedure. Never log API keys, article text, manuscript text, or job payload contents.
