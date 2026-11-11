# Manual Docker Compose deployment

This runbook deploys the API, worker, and web app on a Linux server. It preserves PostgreSQL's named volume, keeps the API bound to loopback, and serves the web app only on the server's Tailscale address. The web container proxies `/v1/` to the API. Deploy manually from `main`; this setup does not auto-deploy from CI.

## Quick deploy (recommended)

`deploy/deploy.sh` runs steps 4-6 below for one `main` commit and stops at the first error:

```sh
git fetch origin && git checkout --detach <git-commit-sha>
./deploy/deploy.sh <git-commit-sha>                  # update an existing deployment
./deploy/deploy.sh <git-commit-sha> --first-deploy   # brand-new server, no database volume yet
```

Check out the commit first so the script you run is the one from that commit.

The script:

1. checks for the `aprkb_pgdata` volume and a clean checkout;
2. validates the Compose files;
3. writes a `pg_dump` backup to `$BACKUP_DIR` (default `~/aprkb-backups`) and verifies it with `pg_restore --list`;
4. builds the images;
5. runs migrations and the production seed in a one-shot `init` container;
6. replaces `api`, `worker` and `web` only if step 5 succeeded;
7. waits for `/v1/health`, then prints the seed summary and the rollback command.

If a migration or the seed fails, the running site is not changed. Steps 1-3 and 7-8 below (server preparation and the first admin key) are still manual.

## Before connecting

Confirm the server's SSH user and Tailscale address. Do not paste credentials into repository files or commit them. Use SSH keys for access.

## First deployment

1. Install Docker Engine and the Docker Compose plugin on the Linux host. Clone this repository and check out the intended commit from `main`.
2. Inspect existing containers, Compose project names, and Docker volumes before starting anything. The current Compose project is `aprkb` and its PostgreSQL volume is `aprkb_pgdata`. If the server already has application data, identify and preserve its actual volume and project name. Stop if the source database is unclear; do not start a second empty database.
3. Create a server-local `runtime.conf` with `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `DATABASE_URL`. Set the URL to the database at host `postgres` and URL-encode special characters in its password. Also set `APP_ENV=production`, `APP_SECRET_KEY` to a generated random value, `API_CORS_ORIGINS` as a JSON array containing the Tailnet web origin, `BLOB_DIR=/app/data/blobs`, and `TAILSCALE_IP` to the server's current Tailscale IPv4 address. The default host ports are `18080` for loopback API and `18081` for Tailnet web; `API_HOST_PORT` and `WEB_HOST_PORT` can override them. Restrict permissions to the deployment account (`chmod 600 runtime.conf`). This file is not part of the repository.
4. Back up the identified database with `pg_dump` and verify the backup file before upgrading.
5. Validate the Compose configuration, then build the selected commit:

   ```sh
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml config --quiet
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml build
   ```

6. Apply migrations and initialize the Online reference/taxonomy data. `deploy/deploy.sh` does this for you; the manual equivalent follows. Production seeding reads the packaged Phrasebank Basic JSON and does not load development examples:

   ```sh
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps init
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

   The `init` service runs `alembic upgrade head` and then `python -m aprkb.seeds.load`. `api` and `worker` also wait for `init` to complete, so a bare `up -d` cannot start them on an unmigrated database. Run `init` on its own first, as above, because `up -d` stops the old containers before `init` has finished. The web container re-resolves the `api` address every 10 seconds, so recreating `api` alone does not break `/v1/`.

7. Create the first admin API key once and store it in the approved credential manager. Do not paste or save the printed key in shell history, terminal logs, or the repository:

   ```sh
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml run --rm api python -m aprkb.cli bootstrap-key
   ```

8. Check service health and logs. Verify `http://127.0.0.1:18080/v1/health` locally on the host and `http://<tailscale-ip>:18081/` from a Tailnet client. The web app sends `/v1/` requests through its Nginx proxy. Do not expose either port on a public interface.

## Metric & Measurement catalog (ADR-0015)

The steps above deploy the catalog. There is no extra command to run.

- `docker-compose.prod.yml` sets `MEASUREMENT_ENABLED=true` for the API. To hide the
  `/measurements` pages and `/v1/measurements` API, put `MEASUREMENT_ENABLED=false` in
  `runtime.conf` and recreate the `api` container.
- The `init` step (step 6) creates the `measurement_*` tables with `alembic upgrade head`.
- The same step's `python -m aprkb.seeds.load` imports the packaged
  `data/seed/measurement_catalog.json` and prints `Measurement catalog <version>: imported`
  (later runs print `unchanged`). It then proposes catalog links for the Academic Phrase Bank
  Methods templates. Proposals stay hidden until a curator approves them on
  `/measurements/<code>` ("Proposed links to review"). Re-running the initializer never
  duplicates links or re-creates rejected ones.
- Check with a curator key that `GET /v1/measurements?limit=1` returns the expected `catalog_version`.
- Rollback: an older image ignores the catalog tables. Do not drop them.

## Updates and rollback

Use `deploy/deploy.sh <git-commit-sha>` for each update. It confirms the volume, takes and verifies a backup, deploys the immutable commit SHA as `IMAGE_TAG`, re-runs the idempotent initializer so new seed versions reach the database, and checks API health. For an application rollback, run the command the script prints, `IMAGE_TAG=<previous-sha> docker compose ... up -d --no-deps api worker web`. It skips `init`, because an older image cannot migrate a newer schema. Do not downgrade the schema or remove the PostgreSQL/blob volumes as part of rollback. Review migration compatibility before rolling back application code.

Never use `docker compose down -v` on this deployment. Do not run `make init-dev` or load local/test fixture patterns on production. The production initializer loads the team-authored Phrasebank Basic, its METHODS taxonomy intents, and reference options from the versioned application assets; it excludes development examples and the development-only license. Offline data packs remain separate and are not imported by this Online initializer.
