# Deployment Runbook

Track selected in [ADR-0010](../adr/0010-ci-cd-platform.md): GHCR registry, Docker
Compose on a self-managed homeserver, `aprkb_blobs` named volume, short downtime
accepted per release (no zero-downtime requirement).

## One-time setup (human/admin steps, not automatable from this repo)

1. Install a self-hosted GitHub Actions runner on the homeserver, labeled
   `homeserver` (matches `runs-on: [self-hosted, homeserver]` in
   `.github/workflows/cd-deploy.yml`). This avoids exposing SSH or any inbound port
   for deploys.
2. Repository **Settings → Environments → New environment → `production`** → add at
   least one required reviewer. Without this, `cd-deploy.yml` runs unattended.
3. Add environment secrets scoped to `production` only (never repository/org-wide):
   `POSTGRES_PASSWORD`, `APP_SECRET_KEY`, `DATABASE_URL` (pointing at the `postgres`
   service name on the homeserver, e.g.
   `postgresql+asyncpg://aprkb:<password>@postgres:5432/aprkb`).
4. On the homeserver, create a `.env` alongside `docker-compose.prod.yml` (or export
   the same variables in the runner's environment) with `POSTGRES_PASSWORD`,
   `APP_SECRET_KEY`, `DATABASE_URL`, and optionally `API_CORS_ORIGINS`,
   `ARTICLE_SOURCE`, `API_PORT`.
5. First boot only: `docker compose -f docker-compose.prod.yml up -d postgres` once
   by hand to create the `pgdata`/`aprkb_blobs` named volumes before the first
   `cd-deploy.yml` run.

## Release flow

1. CI (`backend-quality-and-tests`, `frontend-quality-and-build`,
   `backend-image-contract`) runs on every push to `dev`. On success,
   `backend-image-contract` publishes the exact smoke-tested image to
   `ghcr.io/<owner>/aprkb-backend` tagged `sha-<commit>` and `dev`. The image is never
   rebuilt afterward.
2. A human runs **Actions → CD Deploy → Run workflow**, entering the published
   `image_tag` (e.g. `sha-<commit>`). The `production` environment's required
   reviewer must approve before the job starts.
3. The `deploy` job (on the homeserver runner) runs `scripts/cd/deploy.sh`, which:
   pulls the image, starts/health-checks PostgreSQL, runs the migration once from a
   disposable container (not inside the long-running API/worker), starts API and
   worker on the pulled digest, and fails the run if the running API's image ID
   doesn't match the resolved digest.
4. Release evidence (commit, image, actor, timestamp) is written to the workflow's
   job summary.

## Known gaps (do not treat Phase 05 as production-rehearsed until these close)

- No independent PostgreSQL advisory/release lock around the migration step yet —
  only workflow concurrency (`cancel-in-progress: false`) serializes deploys. See
  `doc/runbooks/migrations.md`.
- No automated queued/in-flight/completed job-count reconciliation during worker
  drain. See `doc/runbooks/rollback.md`.
- No synthetic release-scoped blob-sentinel smoke test script yet.
- No staging environment distinct from production exists yet; this flow has only
  been exercised with disposable containers in CI, not on the real homeserver.
- Frontend has no Dockerfile/image contract; frontend deployment is out of this
  scaffold's scope until specifically requested.
- GHCR retention policy and `aprkb_blobs`/PostgreSQL backup-to-offsite policy are
  `TODO(owner)` in ADR-0010.

Per `plans/ci-cd-team-standard/phase-05-track-specific-cd-and-rollout.md`, a staging
rehearsal executed by someone other than the author, and a game day (failed
migration, failed readiness, worker termination, blob unavailability, rollback) are
required before this is considered production-ready — not just scripted.
