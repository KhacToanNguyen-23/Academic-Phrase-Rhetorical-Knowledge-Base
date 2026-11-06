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
        return _MARKDOWN + f"\n\nPaper {article.external_id}.".encode()


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
async def test_same_title_without_doi_is_a_review_hint_across_work_ids(
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

    assert source.fetched == ["work-a", "work-b", "work-c", "work-d"]
    async with import_sessions() as session:
        count = await session.scalar(
            select(func.count()).select_from(Article).where(Article.source == "fake")
        )
        assert count == 4
        events = list(
            await session.scalars(
                select(AuditEvent).where(AuditEvent.action == "corpus.import.page")
            )
        )
        assert sum(len(event.after["suspected_duplicates"]) for event in events) == 3
        assert all(event.after["skipped_duplicate"] == 0 for event in events)


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


@pytest.mark.asyncio
async def test_doi_variants_skip_download_across_sources_and_failed_ingest(
    import_client,
    import_sessions,
    tmp_path,
    monkeypatch,
):
    from aprkb.modules.corpus.models import License

    monkeypatch.setattr(core_settings, "article_source", "fake")
    async with import_sessions() as session:
        license_id = await session.scalar(select(License.id).where(License.code == "CC-BY"))
        existing = Article(
            source="upload",
            title="Original",
            doi=" HTTPS://doi.org/10.1234/ABC ",
            license_id=license_id,
            blob_key="old.md",
            ingest_status="failed",
        )
        session.add(existing)
        await session.commit()
        existing_id = str(existing.id)
    source = FakeArticleSource(
        {
            None: SourcePage(
                articles=(
                    SourceArticleRef(
                        "new-id", "Changed title", "doi:10.1234/abc", "CC-BY", "text/markdown"
                    ),
                ),
                next_cursor=None,
            )
        }
    )
    client, key = import_client
    job_id = await _enqueue(client, key)
    await run_once(
        import_sessions,
        blob_store=LocalBlobStore(tmp_path),
        article_source_factory=_factory(source),
    )
    assert source.fetched == []
    async with import_sessions() as session:
        result = (await session.get(Job, job_id)).result
        assert result["skipped_duplicate"] == 1
        assert result["duplicates"][0]["reason"] == "doi"
        assert result["duplicates"][0]["matched_article_id"] == existing_id
        assert result["duplicates"][0]["matched_status"] == "failed"
        assert await session.scalar(select(func.count()).select_from(Article)) == 1


@pytest.mark.asyncio
async def test_identical_files_with_different_ids_are_skipped_and_invalid_fetch_can_retry(
    import_client,
    import_sessions,
    tmp_path,
    monkeypatch,
):
    from aprkb.modules.corpus.sources import InvalidContentError

    class RepeatedFileSource(FakeArticleSource):
        async def fetch_content(self, article):
            self.fetched.append(article.external_id)
            if len(self.fetched) == 1:
                raise InvalidContentError("Invalid fixture content")
            return _MARKDOWN

    monkeypatch.setattr(core_settings, "article_source", "fake")
    source = RepeatedFileSource(
        {
            None: SourcePage(
                articles=(
                    _ref("retry", "CC-BY"),
                    _ref("retry", "CC-BY"),
                    _ref("copy", "CC-BY"),
                ),
                next_cursor=None,
            )
        }
    )
    client, key = import_client
    job_id = await _enqueue(client, key)
    await run_once(
        import_sessions,
        blob_store=LocalBlobStore(tmp_path),
        article_source_factory=_factory(source),
    )
    async with import_sessions() as session:
        result = (await session.get(Job, job_id)).result
        assert result["skipped_invalid_content"] == 1
        assert result["imported"] == 1
        assert result["skipped_duplicate"] == 1
        assert result["duplicates"][0]["reason"] == "file_sha256"
        assert len(list(tmp_path.glob("articles/*"))) == 1


@pytest.mark.asyncio
async def test_upload_duplicates_return_original_without_new_blob_or_job(
    import_client,
    import_sessions,
    tmp_path,
):
    client, key = import_client
    headers = {"X-API-Key": key}
    first = await client.post(
        "/v1/admin/corpus/articles",
        headers=headers,
        data={"title": "Original", "doi": "10.1234/original", "license_code": "CC-BY"},
        files={"file": ("first.md", _MARKDOWN)},
    )
    assert first.status_code == 202, first.text
    original_id = first.json()["article_id"]
    for data, content, reason in [
        ({"doi": "https://doi.org/10.1234/ORIGINAL"}, b"Different bytes", "doi"),
        ({}, _MARKDOWN, "file_sha256"),
    ]:
        response = await client.post(
            "/v1/admin/corpus/articles",
            headers=headers,
            data={"title": "Renamed", "license_code": "CC-BY", **data},
            files={"file": ("renamed.md", content)},
        )
        assert response.status_code == 409, response.text
        details = response.json()["error"]["details"]
        assert details["matched_article_id"] == original_id
        assert details["reason"] == reason
    async with import_sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Article)) == 1
        assert await session.scalar(select(func.count()).select_from(Job)) == 1
    assert len(list(tmp_path.glob("articles/*"))) == 1


@pytest.mark.asyncio
async def test_legacy_upload_hash_is_backfilled_and_import_is_skipped(
    import_client,
    import_sessions,
    tmp_path,
    monkeypatch,
):
    from aprkb.modules.corpus.models import License

    store = LocalBlobStore(tmp_path)
    content = _MARKDOWN + b"\n\nPaper incoming."
    store.put("legacy.md", content)
    async with import_sessions() as session:
        license_id = await session.scalar(select(License.id).where(License.code == "CC-BY"))
        legacy = Article(
            source="upload", title="Old name", license_id=license_id, blob_key="legacy.md"
        )
        session.add(legacy)
        await session.commit()
        legacy_id = legacy.id
    monkeypatch.setattr(core_settings, "article_source", "fake")
    source = FakeArticleSource(
        {None: SourcePage(articles=(_ref("incoming", "CC-BY"),), next_cursor=None)}
    )
    client, key = import_client
    job_id = await _enqueue(client, key)
    await run_once(import_sessions, blob_store=store, article_source_factory=_factory(source))
    async with import_sessions() as session:
        result = (await session.get(Job, job_id)).result
        assert result["imported"] == 0
        assert result["duplicates"][0]["matched_article_id"] == str(legacy_id)
        assert (await session.get(Article, legacy_id)).content_sha256 is not None
        assert len(list(tmp_path.glob("articles/*"))) == 0


@pytest.mark.asyncio
async def test_concurrent_import_pages_keep_one_article(import_sessions, tmp_path):
    import asyncio
    from uuid import uuid4

    from aprkb.modules.corpus.importer import import_page

    source = FakeArticleSource(
        {None: SourcePage(articles=(_ref("one", "CC-BY"),), next_cursor=None)}
    )

    async def run_page():
        async with import_sessions() as session:
            result = await import_page(
                session,
                source=source,
                blob_store=LocalBlobStore(tmp_path),
                cursor=None,
                limit=10,
                job_id=uuid4(),
            )
            await session.commit()
            return result

    results = await asyncio.wait_for(asyncio.gather(run_page(), run_page()), timeout=15)
    assert sum(result.imported for result in results) == 1
    assert sum(result.skipped_duplicate for result in results) == 1
    assert source.fetched == ["one"]


@pytest.mark.asyncio
async def test_migration_backfills_legacy_keys_without_deleting_duplicates(import_sessions):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text

    from aprkb.modules.corpus.identity import normalize_doi, title_identity
    from aprkb.modules.corpus.models import License

    async with import_sessions() as session:
        license_id = await session.scalar(select(License.id).where(License.code == "CC-BY"))
        session.add_all(
            [
                Article(
                    source="upload",
                    doi=doi,
                    title="A Study: of Việt Nam!",
                    license_id=license_id,
                    blob_key="legacy.md",
                )
                for doi in ["HTTPS://doi.org/10.1234/ABC", "doi: 10.1234/abc"]
            ]
        )
        await session.commit()
    engine = import_sessions.kw["bind"]
    async with engine.begin() as connection:
        schema = await connection.scalar(text("SELECT current_schema()"))

        def migrate(sync_connection):
            root = Path(__file__).parents[3]
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "migrations"))
            config.attributes["connection"] = sync_connection
            config.attributes["version_table_schema"] = schema
            command.downgrade(config, "0010_merge_vocabulary_and_pack")
            command.upgrade(config, "head")

        await connection.run_sync(migrate)
        rows = (
            await connection.execute(text("SELECT doi, doi_key, title_key FROM articles"))
        ).all()
        assert len(rows) == 2
        assert all(row.doi_key == normalize_doi(row.doi) for row in rows)
        assert all(row.title_key == title_identity("A Study: of Việt Nam!") for row in rows)
