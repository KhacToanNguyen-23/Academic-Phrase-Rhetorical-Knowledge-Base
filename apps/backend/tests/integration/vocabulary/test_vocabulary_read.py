"""Public vocabulary read API tests use invented rows only."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.deps import get_db_session
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.vocabulary.models import (
    VocabFamily,
    VocabFamilyMember,
    VocabLemma,
    VocabLemmaDomainStat,
)


@pytest_asyncio.fixture
async def session_factory(
    postgres_test_engine: AsyncEngine,
) -> AsyncIterator[async_sessionmaker]:
    yield async_sessionmaker(postgres_test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def api_client(
    session_factory: async_sessionmaker,
) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client,
    ):
        yield client


async def _client_key(session_factory: async_sessionmaker) -> str:
    async with session_factory() as session:
        _, key = await create_api_key(session, name="vocabulary reader", role="client")
        await session.commit()
    return key


async def _seed_vocabulary(session_factory: async_sessionmaker) -> str:
    async with session_factory() as session:
        alpha = VocabLemma(
            word="alpha", pos="n", rank=2, band=1, status="y", is_core=True, domains=["HIS"]
        )
        beta = VocabLemma(word="beta", pos="n", rank=1, band=2, status="x", is_core=False)
        numeric = VocabLemma(word="9lives", pos="n", rank=3, is_core=True)
        family = VocabFamily(headword="alpha", rank=1, family_freq=14)
        session.add_all([alpha, beta, numeric, family])
        await session.flush()
        session.add_all(
            [
                VocabLemmaDomainStat(lemma_id=alpha.id, domain="SCI", freq=3, relative_ratio=0.3),
                VocabLemmaDomainStat(lemma_id=alpha.id, domain="HIS", freq=5, relative_ratio=0.5),
                VocabFamilyMember(
                    family_id=family.id,
                    lemma_id=alpha.id,
                    freq=10,
                    category="y",
                ),
                VocabFamilyMember(
                    family_id=family.id,
                    lemma_id=beta.id,
                    freq=4,
                    category="x",
                ),
            ]
        )
        await session.commit()
        return str(alpha.id)


@pytest.mark.asyncio
async def test_vocabulary_filters_pagination_and_detail(
    api_client: AsyncClient,
    session_factory: async_sessionmaker,
) -> None:
    alpha_id = await _seed_vocabulary(session_factory)
    key = await _client_key(session_factory)
    headers = {"X-API-Key": key}

    assert (await api_client.get("/v1/vocabulary/lemmas")).status_code == 401

    letter = await api_client.get(
        "/v1/vocabulary/lemmas", params={"letter": "a", "limit": 1}, headers=headers
    )
    assert letter.status_code == 200
    assert letter.json()["total"] == 1
    assert letter.json()["items"][0]["word"] == "alpha"

    ranked = await api_client.get(
        "/v1/vocabulary/lemmas",
        params={"core_only": True, "sort": "rank", "offset": 1},
        headers=headers,
    )
    assert ranked.status_code == 200
    assert ranked.json()["total"] == 2
    assert ranked.json()["items"][0]["word"] == "9lives"

    numeric = await api_client.get("/v1/vocabulary/lemmas", params={"letter": "#"}, headers=headers)
    assert numeric.status_code == 200
    assert [item["word"] for item in numeric.json()["items"]] == ["9lives"]

    escaped = await api_client.get("/v1/vocabulary/lemmas", params={"q": "%"}, headers=headers)
    assert escaped.status_code == 200
    assert escaped.json()["total"] == 0

    letters = await api_client.get("/v1/vocabulary/letters", headers=headers)
    assert letters.status_code == 200
    assert next(item["count"] for item in letters.json() if item["letter"] == "#") == 1

    families = await api_client.get(
        "/v1/vocabulary/families", params={"q": "alpha"}, headers=headers
    )
    assert families.status_code == 200
    assert families.json()["total"] == 1
    assert families.json()["items"][0]["members"][0]["word"] == "alpha"

    detail = await api_client.get(f"/v1/vocabulary/lemmas/{alpha_id}", headers=headers)
    assert detail.status_code == 200
    payload = detail.json()
    assert [item["domain"] for item in payload["domain_stats"]] == ["HIS", "SCI"]
    assert payload["families"][0]["members"][0]["word"] == "alpha"

    missing = await api_client.get(
        "/v1/vocabulary/lemmas/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert missing.status_code == 404
