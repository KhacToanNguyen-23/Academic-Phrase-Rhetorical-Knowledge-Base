#!/usr/bin/env bash
# One-command manual deploy of a main commit (see deploy/README.md).
#
#   ./deploy/deploy.sh <git-commit-sha>              update an existing deployment
#   ./deploy/deploy.sh <git-commit-sha> --first-deploy   first deployment (no database yet)
#
# Steps: check project/volume -> checkout -> validate compose -> pg_dump backup ->
# build -> migrate + seed in a one-shot `init` container -> only then replace
# api/worker/web -> wait for /v1/health -> print the seed summary.
# It never runs `down -v`, never downgrades the schema, and stops at the first error.
#
# Everything lives in main() so bash has read the whole file before `git checkout`
# can replace it on disk.

main() {
  set -euo pipefail

  local sha="${1:-}"
  local first_deploy="false"
  [[ "${2:-}" == "--first-deploy" ]] && first_deploy="true"
  if [[ -z "$sha" ]]; then
    echo "usage: $0 <git-commit-sha> [--first-deploy]" >&2
    exit 2
  fi

  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  cd "$root"

  local project="${COMPOSE_PROJECT_NAME:-aprkb}"
  local volume="${project}_pgdata"
  local backup_dir="${BACKUP_DIR:-$HOME/aprkb-backups}"
  local -a dc=(docker compose -p "$project" --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml)

  step() { printf '\n== %s\n' "$*"; }
  fail() { printf '\nDEPLOY STOPPED: %s\n' "$*" >&2; exit 1; }

  [[ -f runtime.conf ]] || fail "runtime.conf is missing (see deploy/README.md step 3)."
  # Read the ports from runtime.conf without sourcing it (values may contain shell characters).
  local api_port
  api_port="$(sed -n 's/^API_HOST_PORT=//p' runtime.conf | tail -1)"
  api_port="${api_port:-18080}"

  step "Checking the Compose project and database volume"
  if docker volume inspect "$volume" >/dev/null 2>&1; then
    echo "volume $volume found"
  elif [[ "$first_deploy" == "true" ]]; then
    echo "volume $volume not found; --first-deploy creates it"
  else
    fail "volume $volume not found. Identify the real database volume before deploying; pass --first-deploy only for a brand-new server."
  fi
  if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
    fail "the checkout has local changes to tracked files; commit or discard them first."
  fi

  local previous_tag=""
  previous_tag="$(docker inspect --format '{{.Config.Image}}' "${project}-api-1" 2>/dev/null | sed -n 's/^aprkb-backend://p' || true)"
  echo "currently running: ${previous_tag:-<none>}"

  step "Checking out $sha"
  git fetch --quiet origin
  git checkout --quiet --detach "$sha"
  local full_sha
  full_sha="$(git rev-parse HEAD)"
  export IMAGE_TAG="$full_sha"
  echo "IMAGE_TAG=$IMAGE_TAG"

  step "Validating the Compose configuration"
  "${dc[@]}" config --quiet

  if [[ "$first_deploy" != "true" ]]; then
    step "Backing up the database"
    mkdir -p "$backup_dir"
    local backup
    backup="$backup_dir/aprkb_$(date +%Y%m%d_%H%M%S)_before_${full_sha:0:12}.dump"
    "${dc[@]}" up -d --wait postgres
    "${dc[@]}" exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' >"$backup"
    [[ -s "$backup" ]] || fail "backup $backup is empty."
    "${dc[@]}" exec -T postgres pg_restore --list <"$backup" >/dev/null \
      || fail "backup $backup cannot be read by pg_restore."
    echo "backup: $backup ($(du -h "$backup" | cut -f1))"
  fi

  step "Building images"
  "${dc[@]}" build

  # Migrate and seed in a throwaway container first. Only when that succeeds are the
  # running api/worker/web replaced, so a failed migration or seed leaves the live site
  # exactly as it was. (A plain `up -d` would stop the old api before init finishes.)
  step "Migrating and seeding (the running site is not touched yet)"
  "${dc[@]}" up -d --wait postgres
  local init_log
  init_log="$(mktemp)"
  if ! "${dc[@]}" run --rm --no-deps init 2>&1 | tee "$init_log"; then
    fail "migration or seed failed (log above). The running site was not changed. Fix the cause and run the script again; restore $backup_dir only if data was damaged."
  fi

  step "Starting the new version"
  "${dc[@]}" up -d --no-deps api worker web

  step "Waiting for the API health check"
  local healthy="false"
  for _ in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${api_port}/v1/health" >/dev/null 2>&1; then
      healthy="true"
      break
    fi
    sleep 2
  done
  if [[ "$healthy" != "true" ]]; then
    "${dc[@]}" logs --no-color --tail 60 api || true
    [[ -n "$previous_tag" ]] && echo "Roll back: IMAGE_TAG=$previous_tag ${dc[*]} up -d --no-deps api worker web"
    fail "API did not become healthy on 127.0.0.1:${api_port}."
  fi

  step "Seed summary"
  grep -E "Measurement catalog|Running upgrade" "$init_log" | tail -5 || true
  rm -f "$init_log"

  step "Containers"
  "${dc[@]}" ps

  printf '\nDeployed %s.\n' "$full_sha"
  if [[ -n "$previous_tag" ]]; then
    echo "Rollback (application only; never downgrade the schema):"
    echo "  IMAGE_TAG=$previous_tag ${dc[*]} up -d --no-deps api worker web"
  fi
}

main "$@"
