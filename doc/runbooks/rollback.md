# Release Rollback Runbook

## Application rollback

1. Stop new deployment activity and keep production deployment concurrency locked.
2. Record the failing commit, image digest, migration revision, symptoms, actor, and approver.
3. Verify the previous API/worker image digest is compatible with the current schema.
4. If compatible, deploy the previous backend digest to both API and worker, deploy the previous frontend digest when needed, and verify the actual running digests.
5. Check `/v1/health`, frontend loading, PostgreSQL job processing, audit writes, and access to the shared blob sentinel.

API and worker must always use the same backend digest. Do not roll back only one of them.

## Database recovery

Do not infer database rollback from application rollback. Never run an untested `alembic downgrade` automatically. For an incompatible schema, prefer an approved forward fix; otherwise keep workers stopped and invoke the tested backup/restore procedure with the database owner.

## Worker and blob checks

Before an incompatible recovery, stop/scale the Docker Compose worker because the scaffold does not yet expose a graceful drain command. Reconcile queued/processing/completed counts without logging payloads and use the existing lease-recovery semantics only through a tested procedure. Phase 05 must replace this manual stop with a named, verified drain/resume control before automated production CD. Confirm API and worker share the same durable `BLOB_DIR`; verify with a synthetic, release-scoped, non-corpus sentinel and delete it afterward.

## Closeout

Record restoration time, final commit/digests, database revision, health evidence, data impact, temporary bypasses, and proof that branch/deployment protection was restored. Open follow-up work for every manual or missing control.
