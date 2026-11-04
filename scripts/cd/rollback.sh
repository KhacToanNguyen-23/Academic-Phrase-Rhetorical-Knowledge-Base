#!/usr/bin/env bash
# Roll the API/worker back to a previous image digest/tag. Never runs a database
# downgrade automatically (doc/runbooks/migrations.md: forward-fix first, downgrade
# is not assumed safe). If the failed release included a migration, a schema-aware
# human decision is required before or instead of running this script.
#
# Usage: BACKEND_IMAGE=<previous-ghcr-ref> DATABASE_URL=... APP_SECRET_KEY=... \
#        scripts/cd/rollback.sh
#
# Phase 05 of plans/ci-cd-team-standard/plan.md.
set -euo pipefail

compose_file="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/docker-compose.prod.yml"
image="${BACKEND_IMAGE:?Set BACKEND_IMAGE to the previous ghcr.io tag or digest to roll back to}"

echo "Rolling back to ${image}"
docker pull "$image"
target_digest="$(docker image inspect --format '{{.Id}}' "$image")"
echo "Target digest: ${target_digest}"

echo "::warning::This restarts api/worker on the previous image only. It does not" >&2
echo "::warning::run any migration. If the release being rolled back included a" >&2
echo "::warning::migration, confirm the previous image is schema-compatible with the" >&2
echo "::warning::CURRENT database before proceeding, per doc/runbooks/migrations.md." >&2

BACKEND_IMAGE="$image" docker compose -f "$compose_file" up -d api worker

for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${API_PORT:-8000}/v1/health"; then
    echo
    running_digest="$(docker compose -f "$compose_file" ps -q api | xargs -r docker inspect --format '{{.Image}}')"
    if [ "$running_digest" != "$target_digest" ]; then
      echo "::error::Running API image (${running_digest}) does not match the rollback target (${target_digest})" >&2
      exit 1
    fi
    echo "Rollback complete: ${image} (${target_digest})"
    exit 0
  fi
  sleep 2
done

echo "::error::API never became healthy after rollback" >&2
exit 1
