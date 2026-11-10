"""Run a live E2E API on port 8016 using an isolated schema in aprkb_test.

Launch from apps/backend with its uv environment. No production data or policy
files are changed. Graceful shutdown drops only the generated test schema.
The API uses the packaged runtime policies without test-only weight overrides.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aprkb.api.main import create_app
from aprkb.core.config import settings
from aprkb.modules.patterns.models import (
    EvidenceProvenance,
    PatternVersion,
    PhrasePattern,
    UsageConstraint,
)
from aprkb.modules.taxonomy.models import Intent
from aprkb.seeds.load import run_seed

settings.app_env = "local"
app = create_app()
original_lifespan = app.router.lifespan_context
backend_root = Path(__file__).resolve().parents[2] / "apps" / "backend"


@asynccontextmanager
async def isolated_lifespan(application):
    database_url = urlunsplit(urlsplit(settings.database_url)._replace(path="/aprkb_test"))
    schema = f"online_ranking_{uuid4().hex}"
    engine = create_async_engine(database_url)
    scoped_engine = create_async_engine(
        database_url, connect_args={"server_settings": {"search_path": f"{schema},public"}}
    )
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        async with scoped_engine.begin() as connection:

            def migrate(sync_connection):
                config = Config(str(backend_root / "alembic.ini"))
                config.set_main_option("script_location", str(backend_root / "migrations"))
                config.attributes["connection"] = sync_connection
                config.attributes["version_table_schema"] = schema
                command.upgrade(config, "head")

            await connection.run_sync(migrate)
        factory = async_sessionmaker(scoped_engine, expire_on_commit=False)
        async with factory() as session:
            await run_seed(session)
            intent = await session.scalar(select(Intent).where(Intent.code == "INTRO_GAP_INDICATE"))
            pattern = PhrasePattern(intent_id=intent.id, status="approved")
            session.add(pattern)
            await session.flush()
            version = PatternVersion(
                pattern_id=pattern.id,
                version_no=1,
                canonical_frame="We suggest {topic}.",
                slots={"topic": "noun_phrase"},
                epistemic_strength="absolute",
                claim_type="descriptive",
            )
            session.add(version)
            await session.flush()
            pattern.current_version_id = version.id
            session.add(
                UsageConstraint(
                    pattern_version_id=version.id,
                    allowed_sections=["INTRO"],
                    allowed_genres=["RESEARCH_ARTICLE"],
                )
            )
            session.add(
                EvidenceProvenance(
                    pattern_version_id=version.id,
                    source_type="authored",
                    sentence_ids=[],
                )
            )

            writer_pattern = PhrasePattern(intent_id=intent.id, status="approved")
            session.add(writer_pattern)
            await session.flush()
            writer_version = PatternVersion(
                pattern_id=writer_pattern.id,
                version_no=1,
                canonical_frame="The role of {topic} in {context} remains underexplored.",
                slots={
                    "topic": {
                        "type": "noun_phrase",
                        "label": "Research topic",
                        "instruction": "Name the specific topic discussed in your evidence.",
                        "example": "language models",
                        "required": True,
                        "min_length": 3,
                    },
                    "context": {
                        "type": "noun_phrase",
                        "label": "Context",
                        "instruction": "Describe the study or setting relevant to the topic.",
                        "example": "higher education",
                        "required": True,
                        "min_length": 3,
                    },
                },
                epistemic_strength="low",
                claim_type="descriptive",
            )
            session.add(writer_version)
            await session.flush()
            writer_pattern.current_version_id = writer_version.id
            session.add(
                UsageConstraint(
                    pattern_version_id=writer_version.id,
                    allowed_sections=["INTRO", "DISCUSSION"],
                    allowed_genres=["RESEARCH_ARTICLE"],
                )
            )
            session.add(
                EvidenceProvenance(
                    pattern_version_id=writer_version.id,
                    source_type="authored",
                    sentence_ids=[],
                )
            )
            await session.commit()
        async with original_lifespan(application):
            application.state.session_factory = factory
            yield
    finally:
        await scoped_engine.dispose()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()


app.router.lifespan_context = isolated_lifespan

if __name__ == "__main__":
    asyncio.run(uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8016)).serve())
