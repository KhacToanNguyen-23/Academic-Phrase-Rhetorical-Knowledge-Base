# Release Rollback Runbook

## Application rollback

1. Stop new deployment activity and keep production deployment concurrency locked (`.github/workflows/cd-deploy.yml` uses `concurrency: group: production-deploy, cancel-in-progress: false`, so a rollback queues behind any in-progress deploy rather than racing it).
2. Record the failing commit, image digest, migration revision, symptoms, actor, and approver.
3. Verify the previous API/worker image digest is compatible with the current schema.
4. If compatible, run `BACKEND_IMAGE=ghcr.io/<owner>/aprkb-backend:<previous-tag-or-digest> scripts/cd/rollback.sh` on the homeserver (or via a `workflow_dispatch` wired to it). It restarts both API and worker on the same previous digest and fails loudly if the running image doesn't match. Frontend rollback is not yet covered (no frontend image contract exists).
5. Check `/v1/health`, frontend loading, PostgreSQL job processing, audit writes, and access to the shared blob sentinel.

API and worker must always use the same backend digest. Do not roll back only one of them. `scripts/cd/rollback.sh` never runs a migration or downgrade.

## Database recovery

Do not infer database rollback from application rollback. Never run an untested `alembic downgrade` automatically. For an incompatible schema, prefer an approved forward fix; otherwise keep workers stopped and invoke the tested backup/restore procedure with the database owner.

## Worker and blob checks

Before an incompatible recovery, `docker compose -f docker-compose.prod.yml stop worker` triggers the worker's SIGTERM-handled graceful drain (finishes any in-flight job, claims nothing new, exits 0 — `apps/backend/src/aprkb/worker/runner.py`, verified by `scripts/ci/container-smoke-worker.sh`). Reconcile queued/processing/completed counts from the `jobs` table without logging payloads; a reconciled count is not yet automated in the deploy/rollback scripts (`TODO(owner)`). Use the existing lease-recovery semantics only through a tested procedure. Confirm API and worker share the same durable `BLOB_DIR` (the `aprkb_blobs` named volume per ADR-0010); verify with a synthetic, release-scoped, non-corpus sentinel and delete it afterward — this synthetic-sentinel check itself is not yet scripted (`TODO(owner)`).

## Closeout

Record restoration time, final commit/digests, database revision, health evidence, data impact, temporary bypasses, and proof that branch/deployment protection was restored. Open follow-up work for every manual or missing control.
