from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aprkb.core.config import Settings
from aprkb.core.db import Base, create_session_factory
from aprkb.modules import load_models


def test_database_url_is_async_for_postgres() -> None:
    settings = Settings(database_url="postgresql+asyncpg://user:pass@localhost/db")
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_settings_loads_root_env_file_independent_of_working_directory() -> None:
    expected = Path(__file__).resolve().parents[5] / ".env"
    assert Settings.model_config["env_file"] == expected


def test_all_prd_entities_are_registered() -> None:
    load_models()
    expected = {
        "taxonomy_releases",
        "sections",
        "moves",
        "steps",
        "intents",
        "article_genres",
        "phrase_patterns",
        "pattern_versions",
        "phrase_variants",
        "usage_constraints",
        "evidence_provenances",
        "discipline_affinities",
        "review_decisions",
        "journal_profiles",
        "guideline_rules",
        "journal_fingerprints",
        "licenses",
        "articles",
        "article_sections",
        "sentences",
        "candidates",
        "api_clients",
        "audit_events",
        "feedback",
        "overrides",
        "recommendation_logs",
        "jobs",
        "ref_enums",
    }
    assert expected <= set(Base.metadata.tables)


async def test_session_factory_is_async() -> None:
    factory = create_session_factory("postgresql+asyncpg://user:pass@localhost/db")
    assert isinstance(factory, async_sessionmaker)
    assert factory.class_ is AsyncSession
    await factory.kw["bind"].dispose()


async def test_initial_migration_creates_isolated_schema(postgres_test_engine) -> None:
    async with postgres_test_engine.connect() as connection:
        current_schema = await connection.scalar(text("SELECT current_schema()"))
        assert current_schema is not None and current_schema.startswith("test_")
        revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
        tables = await connection.run_sync(
            lambda sync: set(inspect(sync).get_table_names(schema=current_schema))
        )
    alembic_config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    assert revision == ScriptDirectory.from_config(alembic_config).get_current_head()
    assert {"alembic_version", "api_clients", "pattern_versions", "jobs"} <= tables
