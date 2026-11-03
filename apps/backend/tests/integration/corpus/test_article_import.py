"""External article source import: license-first fetch, dedup, paging, and outages."""

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.config import settings as core_settings
from aprkb.core.deps import get_db_session
from aprkb.modules.audit.models import AuditEvent
from aprkb.modules.corpus.blobstore import LocalBlobStore
from aprkb.modules.corpus.models import Article, ArticleSection, Sentence
from aprkb.modules.corpus.sources import ArticleSource, ImportOptions, SourceArticleRef, SourcePage
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.mining.models import Job
from aprkb.seeds.load import run_seed
from aprkb.worker.runner import run_once

_MARKDOWN = (
    b"# Introduction\n\nPrior work has examined retrieval in isolation.\n\n"
    b"# Results\n\nThe proposed method improves accuracy."
)


def _ref(external_id: str, license_code: str | None, content_type: str = "text/markdown"):
    return SourceArticleRef(
        external_id=external_id,
        title=f"Article {external_id}",
        doi=f"10.0000/{external_id}",
        license_code=license_code,
        content_type=content_type,
    )


class FakeArticleSource:
    name = "fake"

    def __init__(self, pages: dict[str | None, SourcePage], *, fail: bool = False) -> None:
        self._pages = pages
        self._fail = fail
        self.fetched: list[str] = []

    async def list_articles(
        self, *, cursor: str | None, limit: int, options: ImportOptions
    ) -> SourcePage:
        del limit, options
        if self._fail:
            raise ConnectionError("source unavailable")
        return self._pages.get(cursor, SourcePage(articles=(), next_cursor=None))

    async def fetch_content(self, article: SourceArticleRef) -> bytes:
        self.fetched.append(article.external_id)
        return _MARKDOWN


def _factory(source: ArticleSource):
    def build(name: str) -> ArticleSource:
        if name != source.name:
            raise ValueError(name)
        return source

    return build


@pytest_asyncio.fixture
async def import_sessions(postgres_test_engine: AsyncEngine) -> AsyncIterator[async_sessionmaker]:
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        await run_seed(session)
        await session.commit()
    yield factory


@pytest_asyncio.fixture
async def import_client(
    import_sessions: async_sessionmaker, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[AsyncClient, str]]:
    monkeypatch.setattr(core_settings, "blob_dir", str(tmp_path))
    app = create_app()

    async def override_db_session():
        async with import_sessions() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client,
    ):
        async with import_sessions() as session:
            _, key = await create_api_key(session, name="import curator", role="curator")
            await session.commit()
        yield client, key


async def _enqueue(client: AsyncClient, key: str, **body: object) -> UUID:
    response = await client.post("/v1/admin/corpus/imports", headers={"X-API-Key": key}, json=body)
    assert response.status_code == 202, response.text
    return UUID(response.json()["job_id"])


@pytest.mark.asyncio
async def test_import_is_rejected_while_no_article_source_is_configured(
    import_client: tuple[AsyncClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, key = import_client
    monkeypatch.setattr(core_settings, "article_source", "null")

    response = await client.post("/v1/admin/corpus/imports", headers={"X-API-Key": key}, json={})

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_import_fetches_only_minable_articles_and_feeds_the_ingest_path(
    import_client: tuple[AsyncClient, str],
    import_sessions: async_sessionmaker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(core_settings, "article_source", "fake")
    source = FakeArticleSource(
        {
            None: SourcePage(
                articles=(
                    _ref("open-1", "CC-BY"),
                    _ref("open-1", "CC-BY"),
                    _ref("closed", "PROPRIETARY"),
                    _ref("unknown", "NOT-A-LICENSE"),
                    _ref("missing", None),
                    _ref("html", "CC-BY", content_type="text/html"),
                ),
                next_cursor="page-2",
            ),
            "page-2": SourcePage(articles=(_ref("open-2", "CC-BY"),), next_cursor=None),
        }
    )
    client, key = import_client
    store = LocalBlobStore(tmp_path)
    import_job_id = await _enqueue(client, key, limit=10)

    await run_once(import_sessions, blob_store=store, article_source_factory=_factory(source))

    assert source.fetched == ["open-1"]
    async with import_sessions() as session:
        import_job = await session.get(Job, import_job_id)
        assert import_job is not None and import_job.status == "succeeded"
        articles = list(await session.scalars(select(Article).where(Article.source == "fake")))
        assert [article.external_id for article in articles] == ["open-1"]
        assert articles[0].ingest_status == "pending"
        continuation = await session.scalar(
            select(Job).where(Job.type == "import_articles", Job.id != import_job_id)
        )
        assert continuation is not None
        assert continuation.payload == {
            "source": "fake",
            "cursor": "page-2",
            "limit": 10,
            "profile_id": None,
            "batch_id": str(import_job_id),
            "filters": {"hasFullText": True},
            "artifact_kinds": ["FULLTEXT_MARKDOWN", "FETCHER_FULLTEXT_MARKDOWN", "SOURCE_PDF"],
        }
        audit = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "corpus.import.page")
        )
        assert audit is not None
        assert audit.after["imported"] == 1
        assert audit.after["skipped_license"] == 3
        assert audit.after["skipped_duplicate"] == 1
        assert audit.after["skipped_format"] == 1

    # Drain the queue: ingest open-1, run the continuation page, ingest open-2.
    while await run_once(
        import_sessions, blob_store=store, article_source_factory=_factory(source)
    ):
        pass

    assert source.fetched == ["open-1", "open-2"]
    async with import_sessions() as session:
        articles = list(await session.scalars(select(Article).where(Article.source == "fake")))
        assert {article.ingest_status for article in articles} == {"ready"}
        # The continuation page belongs to the same batch as the first page.
        assert {article.import_batch_id for article in articles} == {import_job_id}
        headings = set(await session.scalars(select(ArticleSection.heading)))
        assert {"Introduction", "Results"} <= headings
        sentences = list(await session.scalars(select(Sentence)))
        assert sentences and all(row.article_section_id is not None for row in sentences)


@pytest.mark.asyncio
async def test_reimporting_the_same_page_skips_existing_articles(
    import_client: tuple[AsyncClient, str],
    import_sessions: async_sessionmaker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(core_settings, "article_source", "fake")
    source = FakeArticleSource(
        {None: SourcePage(articles=(_ref("open-1", "CC-BY"),), next_cursor=None)}
    )
    client, key = import_client
    store = LocalBlobStore(tmp_path)

    for _ in range(2):
        await _enqueue(client, key)
        await run_once(import_sessions, blob_store=store, article_source_factory=_factory(source))

    assert source.fetched == ["open-1"]
    async with import_sessions() as session:
        count = await session.scalar(
            select(func.count()).select_from(Article).where(Article.source == "fake")
        )
        assert count == 1


@pytest.mark.asyncio
async def test_same_title_without_doi_is_imported_once_across_work_ids(
    import_client: tuple[AsyncClient, str],
    import_sessions: async_sessionmaker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(core_settings, "article_source", "fake")

    def doi_less(external_id: str, title: str) -> SourceArticleRef:
        return SourceArticleRef(
            external_id=external_id,
            title=title,
            doi=None,
            license_code="CC-BY",
            content_type="text/markdown",
        )

    source = FakeArticleSource(
        {
            None: SourcePage(
                articles=(doi_less("work-a", "Same paper"), doi_less("work-b", "Same paper")),
                next_cursor="more",
            ),
            "more": SourcePage(
                articles=(doi_less("work-c", "Same paper"), doi_less("work-d", "Other paper")),
                next_cursor=None,
            ),
        }
    )
    client, key = import_client
    store = LocalBlobStore(tmp_path)

    await _enqueue(client, key)
    # Drain the queue: the import, its next-page job and the ingest jobs can run in any order.
    while await run_once(
        import_sessions, blob_store=store, article_source_factory=_factory(source)
    ):
        pass

    assert source.fetched == ["work-a", "work-d"]


@pytest.mark.asyncio
async def test_source_outage_fails_the_import_job_without_touching_the_corpus(
    import_client: tuple[AsyncClient, str],
    import_sessions: async_sessionmaker,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(core_settings, "article_source", "fake")
    source = FakeArticleSource({}, fail=True)
    client, key = import_client
    job_id = await _enqueue(client, key)

    await run_once(
        import_sessions,
        blob_store=LocalBlobStore(tmp_path),
        article_source_factory=_factory(source),
    )

    async with import_sessions() as session:
        job = await session.get(Job, job_id)
        assert job is not None and job.status == "failed"
        assert job.error == "Processing failed (ConnectionError)"
        assert await session.scalar(select(func.count()).select_from(Article)) == 0
    assert not (tmp_path / "articles").exists()
    recommendations = await client.post(
        "/v1/recommendations",
        headers={"X-API-Key": key},
        json={
            "intent": "INTRO_GAP_INDICATE",
            "section": "INTRO",
            "genre": "RESEARCH_ARTICLE",
            "journal_id": None,
            "claim_type": "descriptive",
            "evidence_level": "multiple_consistent",
            "discipline": None,
            "limit": 5,
        },
    )
    assert recommendations.status_code == 200
