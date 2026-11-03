# Phase 01 - Infrastructure and data

Stories: P1 startup. Dependencies: none.

## Tasks

1. Compare apps/backend/pyproject.toml, compose, .env.example and core/config.py with the PRD; configure Python 3.12, uv, async SQLAlchemy, Alembic, Pydantic, Ruff, mypy strict, pytest and pytest-asyncio, plus required minimal dependencies. Add root Makefile commands that run from the correct directory.
2. Configure PostgreSQL pgvector/pgvector:pg16, named volume and port 5432. Remove Redis/Celery and NLP services from the scaffold runtime path without deleting existing data or volumes.
3. Implement async session and base/mixins; model every entity in PRD section 4 with UUID, UTC, foreign keys, JSONB, vector, nullability and constraints. Business enums are reference tables, grouped under existing modules.
4. Create initial Alembic migration including CREATE EXTENSION IF NOT EXISTS vector, and handle cyclic foreign keys through explicit ordering. Enforce version append-only and do not provide update/delete version routes. Specify vector dimensions as a documented technical choice without fabricating fingerprint logic.
5. Set up isolated PostgreSQL test database/schema and migration fixture; update .env.example and up/down/install/migrate commands.

## Verification

- Migrate clean PostgreSQL and inspect extension, tables and constraints; check downgrade/upgrade if supported and test isolation.
- Run uv sync and verify async connectivity and lint/type checks for new code.
- Check every entity and field against PRD section 4; do not delete external resources.
