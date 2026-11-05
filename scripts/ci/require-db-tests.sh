#!/usr/bin/env bash
# DB-required PostgreSQL integration tests must never silently skip or collect zero
# tests; a missing TEST_DATABASE_URL must fail loudly instead of producing a smaller,
# green-looking run. Phase 02 of plans/ci-cd-team-standard/plan.md.
set -euo pipefail

backend_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../apps/backend" && pwd)"
cd "$backend_dir"

collected="$(uv run pytest tests/integration --collect-only -q | tail -n 1)"
echo "Collected: $collected"
if ! echo "$collected" | grep -qE '^[1-9][0-9]* tests? collected'; then
  echo "::error::Expected at least one PostgreSQL-backed test under tests/integration, got: $collected" >&2
  exit 1
fi

log="$(mktemp)"
trap 'rm -f "$log"' EXIT
set +e
uv run pytest tests/integration -rs | tee "$log"
status="${PIPESTATUS[0]}"
set -e
if [ "$status" -ne 0 ]; then
  exit "$status"
fi

if grep -qE '[0-9]+ skipped' "$log"; then
  echo "::error::tests/integration must not skip in CI; confirm TEST_DATABASE_URL targets aprkb_test" >&2
  exit 1
fi

echo "DB-required tests: collected and passed with zero skips."
