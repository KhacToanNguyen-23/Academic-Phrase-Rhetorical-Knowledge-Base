from hashlib import sha256

import httpx
import pydantic
import pytest

from aprkb.core.config import Settings
from aprkb.modules.corpus.sources.base import ImportOptions, InvalidContentError
from aprkb.modules.corpus.sources.slr_source import SlrRepositorySource
from aprkb.policies.loader import load_policy_bundle


@pytest.mark.asyncio
async def test_list_passes_filters_and_follows_next_cursor_even_for_empty_page() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/works"):
            return httpx.Response(
                200,
                json={
                    "isSuccess": True,
                    "data": {"items": [], "page": {"nextCursor": "next", "scanLimitReached": True}},
                },
            )
        raise AssertionError(request.url)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://slr.test/api"
    )
    config = Settings(slr_api_key="test-secret", slr_max_retries=0)
    source = SlrRepositorySource(client, config, load_policy_bundle().licenses)
    page = await source.list_articles(
        cursor=None,
        limit=10,
        options=ImportOptions({"hasFullText": True, "q": "climate"}, ("SOURCE_PDF",)),
    )
    assert page.articles == () and page.next_cursor == "next"
    assert requests[0].url.params["hasFullText"] == "true"
    assert requests[0].url.params["q"] == "climate"
    assert "cursor" not in requests[0].url.params
    await client.aclose()


@pytest.mark.asyncio
async def test_unknown_license_does_not_request_artifacts_and_auth_error_hides_key() -> None:
    key = "private-slr-key"
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path.endswith("/works"):
            data = {
                "items": [{"workId": "w1", "title": "T", "doi": None}],
                "page": {"nextCursor": None},
            }
            return httpx.Response(200, json={"isSuccess": True, "data": data})
        if request.url.path.endswith("/w1"):
            return httpx.Response(
                200,
                json={
                    "isSuccess": True,
                    "data": {
                        "metadata": {"title": "T"},
                        "metadataSources": [{"originalMetadata": {"license": "mystery"}}],
                    },
                },
            )
        return httpx.Response(401, json={"error": {"code": "UNAUTHORIZED"}})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://slr.test/api"
    )
    source = SlrRepositorySource(
        client,
        Settings(slr_api_key=key, slr_max_retries=0, slr_dev_fallback_license=None),
        load_policy_bundle().licenses,
    )
    page = await source.list_articles(
        cursor=None, limit=1, options=ImportOptions({}, ("FULLTEXT_MARKDOWN",))
    )
    assert page.articles[0].license_code is None
    assert not any("artifacts" in path for path in requested)
    await client.aclose()


@pytest.mark.asyncio
async def test_manifest_priority_and_download_checksum_validation() -> None:
    body = b"# Article\n"
    requests: list[str] = []
    download_status = 200

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal download_status
        path = request.url.path
        requests.append(path)
        if path.endswith("/works"):
            data = {
                "items": [{"workId": "w2", "doi": "10/x", "title": "title"}],
                "page": {"nextCursor": None},
            }
            return httpx.Response(200, json={"isSuccess": True, "data": data})
        if path.endswith("/w2"):
            detail = {
                "metadata": {},
                "metadataSources": [
                    {
                        "originalMetadata": {
                            "best_oa_location": {
                                "license": "https://creativecommons.org/licenses/by/4.0/"
                            }
                        }
                    }
                ],
            }
            return httpx.Response(200, json={"isSuccess": True, "data": detail})
        if path.endswith("/artifacts"):
            kind = request.url.params["kind"]
            if kind == "FULLTEXT_MARKDOWN":
                return httpx.Response(200, json={"isSuccess": True, "data": []})
            return httpx.Response(
                200,
                json={
                    "isSuccess": True,
                    "data": [
                        {
                            "artifactId": "a1",
                            "contentType": "text/markdown",
                            "sizeBytes": len(body),
                            "checksum": sha256(body).hexdigest(),
                            "checksumAlgorithm": "SHA-256",
                        }
                    ],
                },
            )
        if path.endswith("/download"):
            if download_status == 404:
                return httpx.Response(404)
            return httpx.Response(
                200, content=body, headers={"Content-Type": "text/markdown; charset=utf-8"}
            )
        raise AssertionError(path)

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://slr.test/api"
    )
    source = SlrRepositorySource(
        client, Settings(slr_api_key="safe", slr_max_retries=0), load_policy_bundle().licenses
    )
    page = await source.list_articles(
        cursor=None, limit=1, options=ImportOptions({}, ("FULLTEXT_MARKDOWN", "SOURCE_PDF"))
    )
    ref = page.articles[0]
    assert ref.license_code == "CC-BY" and ref.content_locator == "a1"
    assert requests.count("/api/public/v1/repository/works/w2/artifacts") == 2
    assert await source.fetch_content(ref) == body
    source._manifests[("w2", "a1")] = {
        **source._manifests[("w2", "a1")],
        "contentType": "text/markdown; charset=utf-8",
        "sizeBytes": None,
    }
    assert await source.fetch_content(ref) == body
    download_status = 404
    with pytest.raises(InvalidContentError, match="404"):
        await source.fetch_content(ref)
    download_status = 200
    source._manifests[("w2", "a1")] = {**source._manifests[("w2", "a1")], "checksum": "bad"}
    with pytest.raises(InvalidContentError):
        await source.fetch_content(ref)
    source._manifests[("w2", "a1")] = {
        **source._manifests[("w2", "a1")],
        "checksum": sha256(body).hexdigest(),
        "sizeBytes": len(body) + 1,
    }
    with pytest.raises(InvalidContentError, match="size"):
        await source.fetch_content(ref)
    source._manifests[("w2", "a1")] = {
        **source._manifests[("w2", "a1")],
        "sizeBytes": len(body),
        "contentType": "application/pdf",
    }
    with pytest.raises(InvalidContentError, match="type"):
        await source.fetch_content(ref)
    source._manifests[("w2", "a1")] = {
        **source._manifests[("w2", "a1")],
        "contentType": "text/markdown",
        "checksum": sha256(body).hexdigest(),
    }
    source._config.slr_max_download_bytes = 2
    with pytest.raises(InvalidContentError, match="exceeds"):
        await source.fetch_content(ref)
    await client.aclose()


@pytest.mark.asyncio
async def test_rate_limit_retry_after_and_auth_error_never_reveals_secret() -> None:
    key = "very-secret-key"
    attempt = 0
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempt
        attempt += 1
        if attempt < 3:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(401, json={"error": {"code": "UNAUTHORIZED"}})

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://slr.test/api"
    )
    source = SlrRepositorySource(
        client,
        Settings(slr_api_key=key, slr_max_retries=2),
        load_policy_bundle().licenses,
        sleep=fake_sleep,
    )
    with pytest.raises(PermissionError) as caught:
        await source._json("/public/v1/repository/works")
    assert key not in str(caught.value)
    assert delays == [7, 7]
    await client.aclose()


def _license_handler(license_value: str | None, requested: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        requested.append(path)
        if path.endswith("/works"):
            data = {"items": [{"workId": "w9", "title": "T", "doi": None}], "page": {}}
            return httpx.Response(200, json={"isSuccess": True, "data": data})
        if path.endswith("/w9"):
            original = {} if license_value is None else {"license": license_value}
            detail = {"metadata": {}, "metadataSources": [{"originalMetadata": original}]}
            return httpx.Response(200, json={"isSuccess": True, "data": detail})
        if path.endswith("/artifacts"):
            manifest = {"artifactId": "a9", "contentType": "text/markdown", "sizeBytes": 1}
            return httpx.Response(200, json={"isSuccess": True, "data": [manifest]})
        raise AssertionError(path)

    return handler


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("license_value", "expected_code", "requests_artifacts"),
    [
        (None, "DEV-UNVERIFIED", True),
        ("mystery", "DEV-UNVERIFIED", True),
        ("cc-by-nc", "CC-BY-NC", False),
    ],
)
async def test_dev_fallback_license_applies_only_when_license_is_missing_or_unknown(
    license_value: str | None, expected_code: str, requests_artifacts: bool
) -> None:
    requested: list[str] = []
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(_license_handler(license_value, requested)),
        base_url="https://slr.test/api",
    )
    config = Settings(
        app_env="local",
        slr_api_key="k",
        slr_max_retries=0,
        slr_dev_fallback_license="DEV-UNVERIFIED",
    )
    source = SlrRepositorySource(client, config, load_policy_bundle().licenses)
    page = await source.list_articles(
        cursor=None, limit=1, options=ImportOptions({}, ("FULLTEXT_MARKDOWN",))
    )
    assert page.articles[0].license_code == expected_code
    assert any(path.endswith("/artifacts") for path in requested) is requests_artifacts
    await client.aclose()


def test_dev_fallback_license_is_rejected_outside_local_and_test() -> None:
    with pytest.raises(pydantic.ValidationError, match="SLR_DEV_FALLBACK_LICENSE"):
        Settings(app_env="production", slr_dev_fallback_license="DEV-UNVERIFIED")


def test_dev_fallback_license_must_exist_in_policy() -> None:
    config = Settings(app_env="local", slr_api_key="k", slr_dev_fallback_license="NOPE")
    with pytest.raises(ValueError, match="licenses.yaml"):
        SlrRepositorySource(httpx.AsyncClient(), config, load_policy_bundle().licenses)
