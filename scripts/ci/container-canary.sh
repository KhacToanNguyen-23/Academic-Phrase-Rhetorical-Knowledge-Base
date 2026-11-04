#!/usr/bin/env bash
# Prove the .dockerignore build-context exclusions hold: plant unique, non-secret
# sentinel strings in every path category that must never reach the runtime image
# (.env, cache, test output, local blobs), build, and grep the built image's own
# filesystem for the sentinel. Removes the canaries even on failure.
# Phase 03 of plans/ci-cd-team-standard/plan.md.
set -euo pipefail

backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../apps/backend" && pwd)"
cd "$backend_dir"

sentinel="CANARY_$$_$(date +%s)"
canary_env=".env.canary"
canary_blob="data/blobs/canary.bin"
canary_cache="__pycache__/canary.pyc"
canary_test_output=".pytest_cache/canary.txt"

mkdir -p "$(dirname "$canary_blob")" "$(dirname "$canary_cache")" "$(dirname "$canary_test_output")"
for path in "$canary_env" "$canary_blob" "$canary_cache" "$canary_test_output"; do
  echo "$sentinel" > "$path"
done

canary_image="aprkb-backend:canary-$$"

cleanup() {
  rm -f "$canary_env" "$canary_blob" "$canary_cache" "$canary_test_output"
  docker rmi "$canary_image" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build -f Dockerfile -t "$canary_image" .

# Search /app only: everything this build copies in lands there, and recursing from
# "/" would walk /proc (e.g. /proc/kcore reads as unbounded) and can hang forever.
set +e
found="$(docker run --rm --entrypoint sh "$canary_image" -c "grep -rl '$sentinel' /app 2>/dev/null")"
set -e

if [ -n "$found" ]; then
  echo "::error::Canary sentinel leaked into the built image filesystem:" >&2
  echo "$found" >&2
  exit 1
fi

echo "Container canary: excluded build-context paths are absent from the image."
