.PHONY: up down install migrate seed run worker test lint bootstrap-key

UV ?= uv

.PHONY: setup dev check web-install web be fe

up:
	docker compose up -d --wait postgres

down:
	docker compose down

install:
	$(UV) sync --directory apps/backend

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
