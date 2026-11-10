.PHONY: up down install migrate seed run worker test lint bootstrap-key

UV ?= uv
BACKEND_IMAGE ?= aprkb-backend:ci

.PHONY: setup dev check web-install web be fe
.PHONY: lint-web test-db-required container-build container-smoke-api container-smoke-worker container-audit

up:
	docker compose up -d --wait postgres

down:
	docker compose down

install:
	$(UV) sync --directory apps/backend --extra spacy

migrate:
	$(UV) run --directory apps/backend alembic -c alembic.ini upgrade head

seed:
	$(UV) run --directory apps/backend python -m aprkb.seeds.load



run:
	$(UV) run --directory apps/backend uvicorn aprkb.api.main:app --reload

worker:
	$(UV) run --directory apps/backend python -m aprkb.worker.runner

test:
	$(UV) run --directory apps/backend pytest

lint:
	$(UV) run --directory apps/backend ruff check . && $(UV) run --directory apps/backend ruff format --check . && $(UV) run --directory apps/backend mypy src/aprkb

bootstrap-key:
	$(UV) run --directory apps/backend python -m aprkb.cli bootstrap-key

# DB-required PostgreSQL integration tests: fail if the suite collects zero tests or
# any test in it skips, instead of silently shrinking. Requires TEST_DATABASE_URL.
test-db-required:
	bash scripts/ci/require-db-tests.sh

lint-web:
	pnpm --dir apps/web lint

# Build the one image that must run both the API and worker commands.
container-build:
	docker build -f apps/backend/Dockerfile \
		--build-arg GIT_COMMIT_SHA=$$(git rev-parse HEAD) \
		-t $(BACKEND_IMAGE) .

# Requires a running container network alias "pg" reachable as $(CONTAINER_SMOKE_NETWORK)
# (default aprkb-ci-net); see doc/runbooks/ci.md for the local setup sequence.
container-smoke-api:
	bash scripts/ci/container-smoke-api.sh $(BACKEND_IMAGE)

container-smoke-worker:
	bash scripts/ci/container-smoke-worker.sh $(BACKEND_IMAGE)

# Build-context canary: fails if secrets/caches/blobs/test output leak into the image.
container-audit:
	bash scripts/ci/container-canary.sh

# Short workflows for local development.
setup: up install migrate seed

dev: setup run

be: dev

check: lint test

web-install:
	npm --prefix apps/web install

web:
	npm --prefix apps/web run dev

fe: web

.PHONY: phrase-stats
phrase-stats:
	$(UV) run --directory apps/backend python -m aprkb.cli phrase-stats $(ARGS)

.PHONY: contracts
contracts:
	$(UV) run --directory apps/backend python -m aprkb.cli export-openapi
	npm --prefix apps/web run gen:api
