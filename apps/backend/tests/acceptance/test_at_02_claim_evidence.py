"""AT-02: a strong claim with insufficient evidence is blocked by V02."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from tests.integration.test_phase04_api_contract import (
    test_validation_http_runs_v02_and_blocks_prove_with_single_study as covered_case,
)


@pytest.mark.asyncio
async def test_at_02(api_client: AsyncClient, session_factory: async_sessionmaker) -> None:
    await covered_case(api_client, session_factory)
