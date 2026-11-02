"""AT-04: an article source outage fails the import job and leaves local search available."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from aprkb.seeds.load import run_seed
from tests.integration.corpus.test_article_import import (
    test_source_outage_fails_the_import_job_without_touching_the_corpus as covered_case,
)


@pytest.mark.asyncio
async def test_at_04(
    phase05_client: tuple[AsyncClient, str],
    phase05_sessions: async_sessionmaker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with phase05_sessions() as session:
        await run_seed(session)
        await session.commit()
    await covered_case(phase05_client, phase05_sessions, tmp_path, monkeypatch)
