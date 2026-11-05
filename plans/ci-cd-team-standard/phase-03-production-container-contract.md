# Phase 03 — Production Container Contract

## Goal

Produce one controlled, repeatable, non-root backend image whose immutable digest can run either API or worker safely.

## Work

1. Convert `apps/backend/Dockerfile` to a controlled, repeatable multi-stage build with Python base and `uv` source images pinned by digest, locked dependencies (`uv.lock` included), no development dependencies, and a minimal non-root runtime. Do not claim bit-for-bit reproducibility across architectures/build engines; record platform, BuildKit version, source commit, base digests, and dependency lock hash. Update pins only through a reviewed dependency PR that rebuilds, scans, and runs both entrypoint smokes.
2. Add `apps/backend/.dockerignore`, because the build context is `apps/backend`. Exclude `.env*`, local blobs/data, caches, coverage, test output, editor files, and irrelevant artifacts. Do not exclude runtime policy YAML or other package data required by `aprkb`.
3. Keep the image entrypoint neutral enough for command override. Define supported commands:
   - API: `uvicorn aprkb.api.main:app --host 0.0.0.0 --port 8000`
   - Worker: `python -m aprkb.worker.runner`
4. Application metadata may report only the build commit SHA (and safe version metadata), not self-assert an image digest. Deployment verification must compare the registry-resolved digest with the digest in the platform's desired API/worker specs and the digest/status actually running in both workloads.
5. Define liveness/readiness behavior for API and worker. API readiness must include only safe dependencies needed to accept traffic; worker readiness must prove PostgreSQL access and required blob mount/access without consuming a job.
6. Add CI smoke tests that start the same locally built image with each command. Exercise API health and worker startup/shutdown against disposable PostgreSQL.
7. Add a packaging check proving policies, migrations/required runtime files, and configured local blob directory behavior are present while source secrets and developer blobs are absent.
8. Document that production replicas use a shared durable `BLOB_DIR`; do not encode a platform-specific volume until Phase 04.
9. Add a canary build-context test: create unique non-secret sentinel files in paths that must be excluded (for example `apps/backend/.env.canary`, a cache path, test output, and local blob path), build the image, inspect/export its filesystem, and fail if any sentinel appears. Remove canaries after the test even on failure.
10. After the image-contract job exists and passes on the default branch, update the ruleset in a separate staged change to require `CI / backend-image-contract`; prove a failing image-contract PR is blocked and document the exact name.

## Intended Files

- `apps/backend/Dockerfile`
- `apps/backend/.dockerignore` (new)
- `.github/workflows/ci.yml`
- `Makefile`
- `README.md`
- `doc/runbooks/ci.md`
- application health/release-metadata files only if the current API/worker lacks the minimum observable contract; keep router/service/repository boundaries intact

## Acceptance Criteria

- `docker build` succeeds from a clean checkout using locked dependencies and digest-pinned Python/`uv` sources; evidence records the stated build inputs without claiming cross-platform bit identity.
- Container runtime UID is non-zero and the root filesystem can be read-only except explicitly mounted writable locations.
- Image inspection and filesystem checks find no `.env`, Git metadata, local corpus blobs, test artifacts, or package-manager caches containing credentials.
- Canary sentinels placed in every required excluded context category are absent from the final image filesystem.
- One image ID/digest passes both API and worker smoke commands; CI records the same digest for both.
- API health becomes ready against disposable PostgreSQL and fails clearly when its required dependency is unavailable.
- Worker starts, polls PostgreSQL using existing `FOR UPDATE SKIP LOCKED` behavior, handles termination gracefully, and does not require Redis/Celery.
- A cross-process staging smoke test writes/identifies a non-sensitive sentinel through the configured durable blob path and confirms both API and worker can access it.
- Runtime policy YAML and required application resources load successfully.
- The image-contract required check is added only after successful default-branch runs and a disposable ruleset test.

## Verification

```bash
docker build --pull -f apps/backend/Dockerfile -t aprkb-backend:ci apps/backend
docker image inspect aprkb-backend:ci
docker run --rm --entrypoint python aprkb-backend:ci -c "import aprkb; print(aprkb.__name__)"
make lint
make test
```

Implementation must add named Make targets or scripts for `container-smoke-api`, `container-smoke-worker`, and `container-audit`; those commands become the authoritative verification rather than ad-hoc shell snippets.

## Dependencies and Risks

- Depends on stable Phase 02 CI.
- Health endpoints must not disclose configuration, credentials, blob names, article text, or manuscript content.
- A Docker `HEALTHCHECK` alone cannot represent worker readiness; the deployment platform needs a track-specific probe or startup verification.
- Non-root conversion may expose implicit write paths. Inventory and explicitly mount only necessary writable directories.

