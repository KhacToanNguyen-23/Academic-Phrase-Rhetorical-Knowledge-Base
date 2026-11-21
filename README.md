# AP-RKB

Academic Phrase & Rhetorical Knowledge Base is a runnable backend scaffold. It provides a REST API for approved phrase patterns, recommendations and claim validation, plus PostgreSQL-backed corpus jobs that produce reviewable, traceable candidates.

## Deployed app

Private Tailscale deployment: `http://<TAILSCALE_IP>:18081/` (replace with the server's Tailscale IP). The actual server address is not stored in this repository. See the [deployment runbook](https://github.com/KhacToanNguyen-23/Academic-Phrase-Rhetorical-Knowledge-Base/blob/main/deploy/README.md).

## Scope

- Backend package: `apps/backend/src/aprkb`; tests: `apps/backend/tests`.
- PostgreSQL is the only database and job queue. The worker polls jobs with `FOR UPDATE SKIP LOCKED`; uploads use local `./data/blobs` by default.
- Text and Markdown parsers are implemented. JATS and PDF parsers are stubs. Mining rules and policy values remain provisional where marked `TODO(owner)`.
- No admin console, production NLP extraction, taxonomy publishing, Redis/Celery, or excluded evaluation algorithms.

See [AGENTS.md](AGENTS.md) and [SCAFFOLD_PRD.md](SCAFFOLD_PRD.md) for requirements. Keep rights checks before reading corpus blobs; do not log API keys or article/manuscript text. Pattern versions are append-only and recommendations fail closed when provenance is unknown.

## Run locally

Requirements: Docker Compose, Python 3.12, `uv`, and GNU Make. Copy `.env.example` to `.env`; configure matching local values for `POSTGRES_PASSWORD` and `DATABASE_URL`.

```sh
make up
make install
make migrate
make seed
make bootstrap-key
make run
```

Open API docs at <http://localhost:8000/docs>. Start `make worker` in a separate terminal to process corpus jobs. On Windows, `.\dev.ps1 be` starts the backend; `.\dev.ps1 worker` starts its worker.

## Verify

```sh
make lint
make test
```

Integration tests require `TEST_DATABASE_URL` to target a dedicated PostgreSQL database named `aprkb_test`; never point it at production. See [module documentation](apps/backend/src/aprkb) for implementation details.
