"""AT-01: recommendations exclude patterns without approved provenance/state."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.integration.test_phase04_api_contract import (
    test_recommendation_pipeline_filters_seed_and_persists_explainable_log as covered_case,
)


@pytest.mark.asyncio
async def test_at_01(api_client: AsyncClient, session_factory: async_sessionmaker) -> None:
    await covered_case(api_client, session_factory)
