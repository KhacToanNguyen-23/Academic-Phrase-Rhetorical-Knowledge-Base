# Manual Docker Compose deployment

This runbook deploys the API, worker, and web app on a Linux server. It preserves PostgreSQL's named volume, keeps the API bound to loopback, and serves the web app only on the server's Tailscale address. The web container proxies `/v1/` to the API. Deploy manually from `main`; this setup does not auto-deploy from CI.

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

6. Apply migrations and initialize the Online reference/taxonomy data. Production seeding reads the packaged Phrasebank Basic JSON and does not load development examples:

   ```sh
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml run --rm api alembic -c alembic.ini upgrade head
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml run --rm api python -m aprkb.seeds.load
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

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
- Step 6's `alembic upgrade head` creates the `measurement_*` tables.
- Step 6's `python -m aprkb.seeds.load` imports the packaged
  `data/seed/measurement_catalog.json` and prints `Measurement catalog <version>: imported`
  (later runs print `unchanged`). It then proposes catalog links for the Academic Phrase Bank
  Methods templates. Proposals stay hidden until a curator approves them on
  `/measurements/<code>` ("Proposed links to review"). Re-running the initializer never
  duplicates links or re-creates rejected ones.
- Check with a curator key that `GET /v1/measurements?limit=1` returns the expected `catalog_version`.
- Rollback: an older image ignores the catalog tables. Do not drop them.

## Updates and rollback

Before each update, confirm the current volume and take another verified database backup. Deploy an immutable commit SHA as `IMAGE_TAG`, apply migrations, run the idempotent initializer again so new Phrasebank Basic JSON versions reach the database, and check API health and worker status. For an application rollback, redeploy the previous image tag. Do not downgrade the schema or remove the PostgreSQL/blob volumes as part of rollback. Review migration compatibility before rolling back application code.

Never use `docker compose down -v` on this deployment. Do not run `make init-dev` or load local/test fixture patterns on production. The production initializer loads the team-authored Phrasebank Basic, its METHODS taxonomy intents, and reference options from the versioned application assets; it excludes development examples and the development-only license. Offline data packs remain separate and are not imported by this Online initializer.
