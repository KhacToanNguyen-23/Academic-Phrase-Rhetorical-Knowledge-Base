# Manual Docker Compose deployment

This runbook deploys the backend on a Linux server. It preserves PostgreSQL's named volume and keeps the API bound to loopback so a host reverse proxy can serve it. Deploy manually from `main`; this setup does not auto-deploy from CI.

## Before connecting

Confirm the server's SSH user, SSH access, public host name, and whether a reverse proxy already serves traffic. Do not paste credentials into repository files or commit them. Use the password only for the interactive server login, then prefer SSH keys for later access.

## First deployment

1. Install Docker Engine and the Docker Compose plugin on the Linux host. Clone this repository and check out the intended commit from `main`.
2. Inspect existing containers, Compose project names, and Docker volumes before starting anything. The current Compose project is `aprkb` and its PostgreSQL volume is `aprkb_pgdata`. If the server already has application data, identify and preserve its actual volume and project name. Stop if the source database is unclear; do not start a second empty database.
3. Create a server-local `runtime.conf` with `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `DATABASE_URL`. Set the URL to the existing database at host `postgres` and URL-encode special characters in its password. Also set `APP_ENV=production`, `APP_SECRET_KEY` to a generated random value, `API_CORS_ORIGINS` as a JSON array (for example, `["https://writer.example.com"]`), and `BLOB_DIR=/app/data/blobs`. Restrict permissions to the deployment account (`chmod 600 runtime.conf`). This file is not part of the repository.
4. Back up the identified database with `pg_dump` and verify the backup file before upgrading.
5. Validate the Compose configuration, then build the selected commit:

   ```sh
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml config --quiet
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml build
   ```

6. Apply migrations and start the services. These commands do not run the development initializer:

   ```sh
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml run --rm api alembic -c alembic.ini upgrade head
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

7. Create the first admin API key once and store it in the approved credential manager. Do not paste or save the printed key in shell history, terminal logs, or the repository:

   ```sh
   IMAGE_TAG=<git-commit-sha> docker compose --env-file runtime.conf -f docker-compose.yml -f docker-compose.prod.yml run --rm api python -m aprkb.cli bootstrap-key
   ```

8. Check service health and logs. Verify `http://127.0.0.1:8000/v1/health` locally on the host. Configure the existing reverse proxy to send HTTPS traffic to that loopback address; do not expose port 8000 publicly.

## Updates and rollback

Before each update, confirm the current volume and take another verified database backup. Deploy an immutable commit SHA as `IMAGE_TAG`, apply migrations, and check API health and worker status. For an application rollback, redeploy the previous image tag. Do not downgrade the schema or remove the PostgreSQL/blob volumes as part of rollback. Review migration compatibility before rolling back application code.

Never use `docker compose down -v` on this deployment. Do not run `make init-dev`, `make seed`, `init-reference`, demo data, or sample content on production. The production deployment creates schema only and leaves reference, taxonomy, and phrase content empty. Although the current pack importer exists, it validates against reference rows already present in PostgreSQL; production pack import therefore remains blocked until those references have an approved production provisioning path. Do not copy development seed JSON into the production image as a workaround.
