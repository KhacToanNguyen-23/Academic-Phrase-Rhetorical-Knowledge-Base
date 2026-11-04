#!/usr/bin/env bash
# Promote one GHCR digest/tag to production on the homeserver. Run on the
# self-hosted runner (same host as docker-compose.prod.yml). Accepts short
# downtime per ADR-0010: stop -> migrate once -> start -> health check.
#
# Required env: BACKEND_IMAGE (full ghcr.io ref), POSTGRES_PASSWORD, APP_SECRET_KEY,
# DATABASE_URL. Optional: API_CORS_ORIGINS, ARTICLE_SOURCE, API_PORT.
#
# Phase 05 of plans/ci-cd-team-standard/plan.md.
set -euo pipefail

compose_file="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/docker-compose.prod.yml"
image="${BACKEND_IMAGE:?Set BACKEND_IMAGE to a ghcr.io tag or digest, e.g. ghcr.io/<owner>/aprkb-backend:sha-<commit>}"

echo "Deploying ${image}"
docker pull "$image"
resolved_digest="$(docker image inspect --format '{{.Id}}' "$image")"
echo "Resolved digest: ${resolved_digest}"

docker compose -f "$compose_file" up -d postgres
for i in $(seq 1 30); do
  docker compose -f "$compose_file" exec -T postgres pg_isready -U "${POSTGRES_USER:-aprkb}" && break
  sleep 1
done

# docker-compose.prod.yml sets `name: aprkb-prod`; Compose v2 names the shared
# network "<project>_<network>" deterministically from that.
compose_network="aprkb-prod_aprkb"

echo "Running migration once (serialized, not inside API/worker replicas)"
docker run --rm \
  -e DATABASE_URL="$DATABASE_URL" \
  --network "$compose_network" \
  "$image" python -m alembic -c alembic.ini upgrade head

echo "Starting api/worker on the resolved digest"
BACKEND_IMAGE="$image" docker compose -f "$compose_file" up -d api worker

echo "Waiting for API health"
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${API_PORT:-8000}/v1/health" | tee /tmp/aprkb-health.json; then
    echo
    running_digest="$(docker compose -f "$compose_file" ps -q api | xargs -r docker inspect --format '{{.Image}}')"
    echo "Running API image id: ${running_digest}"
    if [ "$running_digest" != "$resolved_digest" ]; then
      echo "::error::Running API image (${running_digest}) does not match the resolved digest (${resolved_digest})" >&2
      exit 1
    fi
    echo "Deploy complete: ${image} (${resolved_digest})"
    exit 0
  fi
  sleep 2
done

echo "::error::API never became healthy after deploy; see rollback.sh" >&2
exit 1
