#!/usr/bin/env bash
# Back up the aprkb_blobs named volume to a tarball on the host. ADR-0010 flags volume
# backup as TODO(owner): this script produces the archive; copying it off the
# homeserver (offsite retention) is still a manual/TODO(owner) step.
#
# Usage: scripts/cd/backup-blobs.sh [output-dir]
set -euo pipefail

out_dir="${1:-./backups}"
mkdir -p "$out_dir"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="aprkb-blobs-${stamp}.tar.gz"

docker run --rm \
  -v aprkb-prod_aprkb_blobs:/data:ro \
  -v "$(cd "$out_dir" && pwd)":/backup \
  alpine tar czf "/backup/${archive}" -C / data

echo "Wrote ${out_dir}/${archive}"
echo "TODO(owner): copy this archive off the homeserver per the agreed retention policy."
