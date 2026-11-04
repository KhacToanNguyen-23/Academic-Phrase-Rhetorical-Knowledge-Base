#!/usr/bin/env bash
# Start the production image's default (API) command against a disposable PostgreSQL
# network alias named "pg" and prove /v1/health becomes ready. Phase 03 of
# plans/ci-cd-team-standard/plan.md.
set -euo pipefail

image="${1:-aprkb-backend:ci}"
network="${CONTAINER_SMOKE_NETWORK:-aprkb-ci-net}"
container="aprkb-ci-api-$$"
host_port="${CONTAINER_SMOKE_API_PORT:-18000}"

cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$container" --network "$network" \
  -e DATABASE_URL="postgresql+asyncpg://aprkb:postgres@pg:5432/aprkb_ci" \
  -e APP_SECRET_KEY=ci-smoke-secret \
  -p "${host_port}:8000" \
  "$image" >/dev/null

docker exec "$container" python -m alembic -c alembic.ini upgrade head

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${host_port}/v1/health" >/dev/null 2>&1; then
    echo "API smoke: healthy"
    curl -fsS "http://127.0.0.1:${host_port}/v1/health"
    echo
    exit 0
  fi
  sleep 1
done

echo "::error::API container never became healthy" >&2
docker logs "$container" || true
exit 1
