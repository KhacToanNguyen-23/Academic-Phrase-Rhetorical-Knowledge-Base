#!/usr/bin/env bash
# Start the production image with the worker command against a disposable PostgreSQL
# network alias named "pg", confirm it logs startup, then send SIGTERM and confirm it
# drains and exits cleanly. Phase 03 of plans/ci-cd-team-standard/plan.md.
set -euo pipefail

image="${1:-aprkb-backend:ci}"
network="${CONTAINER_SMOKE_NETWORK:-aprkb-ci-net}"
container="aprkb-ci-worker-$$"

cleanup() { docker rm -f "$container" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$container" --network "$network" \
  -e DATABASE_URL="postgresql+asyncpg://aprkb:postgres@pg:5432/aprkb_ci" \
  -e APP_SECRET_KEY=ci-smoke-secret \
  "$image" python -m aprkb.worker.runner >/dev/null

sleep 5
if ! docker ps --filter "name=$container" --filter status=running --format '{{.Names}}' | grep -q "$container"; then
  echo "::error::Worker container exited unexpectedly on startup" >&2
  docker logs "$container" || true
  exit 1
fi
if ! docker logs "$container" 2>&1 | grep -q "Worker started"; then
  echo "::error::Worker did not log its startup confirmation" >&2
  docker logs "$container" || true
  exit 1
fi

docker stop -t 10 "$container" >/dev/null
exit_code="$(docker inspect "$container" --format '{{.State.ExitCode}}')"
if [ "$exit_code" != "0" ]; then
  echo "::error::Worker did not exit cleanly on SIGTERM (exit code $exit_code)" >&2
  docker logs "$container" || true
  exit 1
fi
if ! docker logs "$container" 2>&1 | grep -q "Worker stopped"; then
  echo "::error::Worker did not log a graceful shutdown confirmation" >&2
  docker logs "$container" || true
  exit 1
fi

echo "Worker smoke: started, confirmed PostgreSQL polling, and stopped gracefully."
