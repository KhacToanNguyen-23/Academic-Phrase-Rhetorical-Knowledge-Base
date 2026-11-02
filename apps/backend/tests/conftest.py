"""Shared fixtures; PostgreSQL tests use a dedicated schema per test run."""

import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from aprkb.core.config import settings


@pytest.fixture(autouse=True)
def _disable_local_demo_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep keyless loopback demo access off; ASGITransport clients are loopback."""
    monkeypatch.setattr(settings, "app_env", "test")


@pytest_asyncio.fixture
async def postgres_test_engine() -> AsyncIterator[AsyncEngine]:
    """Provide an isolated schema on TEST_DATABASE_URL when integration DB is enabled."""
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to enable PostgreSQL integration tests")
    if "/aprkb_test" not in database_url:
        raise RuntimeError("TEST_DATABASE_URL must target a database named aprkb_test")

    schema = f"test_{uuid4().hex}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        public_version_table_before = bool(
            await connection.scalar(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            )
        )
        public_revision_before = None
        if public_version_table_before:
            public_revision_before = await connection.scalar(
                text("SELECT version_num FROM public.alembic_version LIMIT 1")
            )
    schema_engine = create_async_engine(
        database_url,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
            )
        async with schema_engine.begin() as connection:

            def upgrade(sync_connection) -> None:
                backend_root = Path(__file__).parents[1]
                config = Config(str(backend_root / "alembic.ini"))
                config.set_main_option("script_location", str(backend_root / "migrations"))
                config.attributes["connection"] = sync_connection
                config.attributes["version_table_schema"] = schema
                command.upgrade(config, "head")

            await connection.run_sync(upgrade)
        async with engine.begin() as connection:
            public_version_table_after = bool(
                await connection.scalar(
                    text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
                )
            )
            public_revision_after = None
            if public_version_table_after:
                public_revision_after = await connection.scalar(
                    text("SELECT version_num FROM public.alembic_version LIMIT 1")
                )
        if (public_version_table_after, public_revision_after) != (
            public_version_table_before,
            public_revision_before,
        ):
            raise AssertionError("Isolated migration modified public.alembic_version")
        yield schema_engine
    finally:
        await schema_engine.dispose()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()
