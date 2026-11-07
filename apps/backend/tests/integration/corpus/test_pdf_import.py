"""Real PDF upload/preview, concurrent duplicate prevention and page provenance."""

import asyncio
import json
from uuid import UUID, uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from aprkb.api.main import create_app
from aprkb.core.config import settings
from aprkb.core.deps import get_db_session
from aprkb.modules.corpus.blobstore import LocalBlobStore
from aprkb.modules.corpus.importer import import_page
from aprkb.modules.corpus.models import Article, ArticleSection, Sentence
from aprkb.modules.corpus.sources import SourceArticleRef, SourcePage
from aprkb.modules.identity.service import create_api_key
from aprkb.modules.mining.models import Job
from aprkb.seeds.load import run_seed
from aprkb.worker.runner import run_once
from tests.pdf_factory import make_pdf, make_scanned_pdf


@pytest_asyncio.fixture
async def pdf_context(postgres_test_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "blob_dir", str(tmp_path))
    factory = async_sessionmaker(postgres_test_engine, expire_on_commit=False)
    async with factory() as session:
        await run_seed(session)
        _, key = await create_api_key(session, name="pdf-curator", role="curator")
        await session.commit()
    app = create_app()

    async def get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = get_session
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test", headers={"X-API-Key": key}
        ) as client,
    ):
        yield client, factory, tmp_path


def form(**changes):
    metadata = {"title": "Reviewed paper", "authors": ["Verified Author"], "publication_year": 2026}
    metadata.update(changes)
    return {
        "license_code": "CC-BY",
        "metadata_reviewed": "true",
        "metadata_json": json.dumps(metadata),
    }


async def upload(client, content=None, **metadata):
    return await client.post(
        "/v1/admin/corpus/articles",
        data=form(**metadata),
        files={"file": ("paper.pdf", content or make_pdf(), "application/pdf")},
    )


async def test_preview_is_read_only_then_import_ingest_and_read_page_provenance(pdf_context):
    client, factory, path = pdf_context
    result = await client.post(
        "/v1/admin/corpus/pdf/preview",
        data={"license_code": "CC-BY"},
        files={"file": ("paper.pdf", make_pdf())},
    )
    assert result.status_code == 200, result.text
    preview = result.json()
    assert preview["page_count"] == 2 and preview["duplicate"] is None
    assert preview["suggested_authors"] == ["Test Author"]
    assert "publication_year" not in preview  # CreationDate is not publication year.
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Article)) == 0
        assert await session.scalar(select(func.count()).select_from(Job)) == 0
    assert not list(path.rglob("*.pdf"))

    added = await upload(
        client, doi="https://doi.org/10.1234/PDF-PAPER", genre_id=preview["genres"][0]["id"]
    )
    assert added.status_code == 202, added.text
    article_id = added.json()["article_id"]
    assert await run_once(factory, blob_store=LocalBlobStore(path))
    meta = (await client.get(f"/v1/admin/corpus/articles/{article_id}/metadata")).json()
    assert meta["ingest_status"] == "ready"
    assert meta["doi"] == "10.1234/pdf-paper" and meta["publication_year"] == 2026
    assert meta["authors"] == ["Verified Author"]
    assert meta["license_code"] == "CC-BY" and meta["source"] == "upload"
    assert meta["content_sha256"] and meta["pdf_text_sha256"]
    assert meta["metadata_provenance"]["suggestions"]["authors"] == ["Test Author"]
    assert meta["metadata_provenance"]["reviewed_by"]
    text = await client.get(f"/v1/admin/corpus/articles/{article_id}/text")
    assert text.status_code == 200
    assert [section["page_number"] for section in text.json()["sections"]] == [1, 2]
    async with factory() as session:
        assert (await session.get(Job, UUID(added.json()["job_id"]))).status == "succeeded"
        assert await session.scalar(select(func.count()).select_from(Sentence)) > 0
        sections = list(
            await session.scalars(select(ArticleSection).order_by(ArticleSection.order))
        )
        assert [s.section_code for s in sections] == ["INTRO", "RESULTS"]


async def test_byte_text_doi_duplicates_and_title_hint_do_not_overwrite_metadata(pdf_context):
    client, factory, path = pdf_context
    first = await upload(client, doi="10.1234/original")
    original = first.json()["article_id"]
    for content, metadata, reason in [
        (make_pdf(), {}, "file_sha256"),
        (make_pdf(title="Changed PDF properties"), {}, "pdf_text_sha256"),
        (make_pdf(("Different paper content.",)), {"doi": "doi:10.1234/ORIGINAL"}, "doi"),
    ]:
        result = await upload(client, content, **metadata)
        assert result.status_code == 409, result.text
        assert result.json()["error"]["details"]["reason"] == reason
        assert result.json()["error"]["details"]["matched_article_id"] == original
    preview = await client.post(
        "/v1/admin/corpus/pdf/preview",
        data={"license_code": "CC-BY"},
        files={"file": ("renamed.pdf", make_pdf(title="Different"))},
    )
    assert preview.json()["duplicate"]["reason"] == "pdf_text_sha256"
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Article)) == 1
        assert await session.scalar(select(func.count()).select_from(Job)) == 1
    assert len(list(path.rglob("*.pdf"))) == 1
    # Same title with different content is a review hint, not a forced work merge.
    hint = await client.post(
        "/v1/admin/corpus/pdf/preview",
        data={"license_code": "CC-BY"},
        files={
            "file": ("other.pdf", make_pdf(("Other scientific content.",), title="Reviewed paper"))
        },
    )
    assert hint.json()["duplicate"] is None
    assert hint.json()["suspected_duplicates"][0]["matched_article_id"] == original
    other = await upload(client, make_pdf(("Other scientific content.",), title="Reviewed paper"))
    assert other.status_code == 202


async def test_concurrent_uploads_and_legacy_pdf_backfill(pdf_context):
    client, factory, path = pdf_context
    results = await asyncio.gather(upload(client), upload(client, make_pdf(title="Renamed")))
    assert sorted(r.status_code for r in results) == [202, 409]
    async with factory() as session:
        row = await session.scalar(select(Article))
        row.pdf_text_sha256 = None  # Emulate a pre-migration stored PDF.
        await session.commit()
    duplicate = await upload(client, make_pdf(title="Another container"))
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["details"]["reason"] == "pdf_text_sha256"
    assert len(list(path.rglob("*.pdf"))) == 1


async def test_invalid_metadata_rights_and_unreadable_pdfs_never_create_jobs(
    pdf_context, monkeypatch
):
    client, factory, path = pdf_context
    for values in (
        {"doi": "not-a-doi"},
        {"title": " "},
        {"publication_year": 999},
        {"journal_id": str(uuid4())},
        {"authors": [""]},
    ):
        result = await upload(client, **values)
        assert result.status_code == 422
    for content, code in (
        (b"fake PDF", "invalid_pdf"),
        (make_pdf(("",)), "pdf_ocr_required"),
        (make_scanned_pdf(), "pdf_ocr_required"),
        (make_pdf(encrypted=True), "pdf_encrypted"),
    ):
        result = await upload(client, content)
        assert result.status_code == 422, result.text
        assert result.json()["error"]["details"]["code"] == code
    for endpoint in ("/v1/admin/corpus/pdf/preview", "/v1/admin/corpus/articles"):
        data = {**form(), "license_code": "PROPRIETARY"}
        result = await client.post(endpoint, data=data, files={"file": ("paper.pdf", make_pdf())})
        assert result.status_code == 403
    result = await client.post(
        "/v1/admin/corpus/articles",
        data={"license_code": "CC-BY"},
        files={"file": ("paper.pdf", make_pdf())},
    )
    assert result.status_code == 422
    monkeypatch.setattr(settings, "pdf_max_upload_bytes", 10)
    assert (await upload(client)).status_code == 413
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Article)) == 0
        assert await session.scalar(select(func.count()).select_from(Job)) == 0
    assert not list(path.rglob("*.pdf"))


async def test_slr_pdf_and_upload_share_extracted_text_dedup(pdf_context):
    client, factory, path = pdf_context
    original = await upload(client)
    assert original.status_code == 202

    class Source:
        name = "pdf-source"

        async def list_articles(self, **kwargs):
            return SourcePage(
                (
                    SourceArticleRef(
                        "another-id", "Other metadata", None, "CC-BY", "application/pdf"
                    ),
                ),
                None,
            )

        async def fetch_content(self, ref):
            return make_pdf(title="Other source container")

    async with factory() as session:
        result = await import_page(
            session,
            source=Source(),
            blob_store=LocalBlobStore(path),
            cursor=None,
            limit=1,
            job_id=uuid4(),
        )
        await session.commit()
    assert result.imported == 0 and result.skipped_duplicate == 1
    assert result.duplicates[0]["reason"] == "pdf_text_sha256"


async def test_pdf_header_cannot_bypass_review_by_using_a_text_extension(pdf_context):
    client, factory, path = pdf_context
    for endpoint in ("/v1/admin/corpus/pdf/preview", "/v1/admin/corpus/articles"):
        response = await client.post(
            endpoint, data=form(), files={"file": ("misnamed.md", make_pdf())}
        )
        assert response.status_code == 415
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(Article)) == 0
    assert not list(path.rglob("*.md"))


async def test_legacy_pdf_text_backfill_does_not_parse_revoked_rights(pdf_context, monkeypatch):
    from aprkb.modules.corpus import dedup
    from aprkb.modules.corpus.models import License

    client, factory, path = pdf_context
    assert (await upload(client)).status_code == 202
    async with factory() as session:
        row = await session.scalar(select(Article))
        row.pdf_text_sha256 = None
        row.license_id = await session.scalar(
            select(License.id).where(License.code == "PROPRIETARY")
        )
        await session.commit()

    def forbidden_parse(content):
        raise AssertionError("Legacy PDF with revoked mining rights must not be parsed")

    monkeypatch.setattr(dedup, "inspect_pdf", forbidden_parse)
    async with factory() as session:
        assert (
            await dedup.find_pdf_text_duplicate(session, "no-match", LocalBlobStore(path)) is None
        )
