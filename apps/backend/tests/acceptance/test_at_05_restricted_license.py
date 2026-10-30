"""AT-05: a restricted license blocks article extraction for mining."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.integration.test_phase05_ingestion import (
    test_non_mining_license_is_recorded_as_rejected_without_sentences as covered_case,
)


@pytest.mark.asyncio
async def test_at_05(
    phase05_client: tuple[AsyncClient, str], phase05_sessions: async_sessionmaker
) -> None:
    await covered_case(phase05_client, phase05_sessions)
