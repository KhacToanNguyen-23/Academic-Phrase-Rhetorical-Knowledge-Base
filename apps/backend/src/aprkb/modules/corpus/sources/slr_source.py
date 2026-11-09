"""Read-only adapter for the SLR Repository API."""

import asyncio
import hashlib
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import SecretStr

from aprkb.core.config import Settings, settings
from aprkb.core.logging import get_logger
from aprkb.modules.corpus.sources.base import (
    ImportOptions,
    InvalidContentError,
    SourceArticleRef,
    SourcePage,
)
from aprkb.policies.loader import load_policy_bundle
from aprkb.policies.schemas import LicensesPolicy

logger = get_logger(__name__)


class SlrRepositorySource:
    name = "slr"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        config: Settings = settings,
        licenses: LicensesPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        worker_managed_retries: bool = False,
    ) -> None:
        if config.slr_api_key is None:
            raise ValueError("SLR_API_KEY is required when ARTICLE_SOURCE=slr")
        self._key: SecretStr = config.slr_api_key
        self._config = config
        self._client = client or httpx.AsyncClient(
            base_url=config.slr_api_base_url.rstrip("/"), timeout=config.slr_timeout_seconds
        )
        self._owns_client = client is None
        self._sleep = sleep
        self._max_retries = 0 if worker_managed_retries else config.slr_max_retries
        self._policy = licenses or load_policy_bundle().licenses
        self._license_lookup = {self._norm(k): v for k, v in self._policy.source_aliases.items()}
        self._license_perms = {row.code: row.allows_mining for row in self._policy.licenses}
        # Development-only fallback for works with no license (see config). Works whose
        # license is known but disallows mining stay blocked.
        self._dev_fallback_license = config.slr_dev_fallback_license
        if (
            self._dev_fallback_license is not None
            and self._dev_fallback_license not in self._license_perms
        ):
            raise ValueError("SLR_DEV_FALLBACK_LICENSE must be a license code in licenses.yaml")
        self._manifests: dict[tuple[str, str], dict[str, Any]] = {}

    @staticmethod
    def _norm(value: str) -> str:
        return " ".join(value.split()).casefold().rstrip("/")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            response = await self._client.request(
                method,
                path.lstrip("/"),
                headers={"X-API-Key": self._key.get_secret_value()},
                **kwargs,
            )
            if response.status_code == 429 and attempt < self._max_retries:
                try:
                    delay = float(response.headers.get("Retry-After", "60"))
                except ValueError:
                    delay = 60
                logger.warning(
                    "SLR rate limited on %s; retry %s/%s in %ss",
                    path,
                    attempt + 1,
                    self._max_retries,
                    delay,
                )
                await self._sleep(delay)
                continue
            if response.status_code in (401, 403):
                logger.error(
                    "SLR rejected the API key status=%s path=%s", response.status_code, path
                )
                try:
                    code = response.json().get("error", {}).get("code", "AUTHORIZATION_FAILED")
                except (ValueError, AttributeError):
                    code = "AUTHORIZATION_FAILED"
                raise PermissionError(f"SLR API configuration error: {code}")
            response.raise_for_status()
            return response
        raise RuntimeError("SLR rate limit retries exhausted")

    async def _json(self, path: str, **kwargs: Any) -> Any:
        response = await self._request("GET", path, **kwargs)
        payload = response.json()
        if not payload.get("isSuccess"):
            error = payload.get("error", {}).get("code", "SLR_REQUEST_FAILED")
            raise RuntimeError(f"SLR API request failed: {error}")
        return payload.get("data")

    async def list_articles(
        self, *, cursor: str | None, limit: int, options: ImportOptions
    ) -> SourcePage:
        from aprkb.modules.corpus.schemas import SlrWorkFilters

        filters = SlrWorkFilters.model_validate(dict(options.filters)).query_params()
        query: dict[str, Any] = {**filters, "limit": limit}
        if cursor is not None:
            query["cursor"] = cursor
        data = await self._json("/public/v1/repository/works", params=query)
        items = data.get("items", [])
        logger.info(
            "SLR listed %s works filters=%s cursor=%s",
            len(items),
            filters,
            "yes" if cursor else "no",
        )
        refs: list[SourceArticleRef] = []
        for item in items:
            work_id = str(item["workId"])
            try:
                detail = await self._json(f"/public/v1/repository/works/{work_id}")
                found_license = self._find_license(detail.get("metadataSources", []))
                license_code = found_license or self._dev_fallback_license
                if found_license is None and license_code is not None:
                    logger.info(
                        "SLR work %s has no license; using dev fallback %s", work_id, license_code
                    )
                title = detail.get("metadata", {}).get("title") or item.get("title")
                doi = detail.get("metadata", {}).get("doi") or item.get("doi")
                content_type = ""
                locator = None
                if license_code and self._license_perms.get(license_code, False):
                    for kind in options.artifact_kinds:
                        manifests = await self._json(
                            f"/public/v1/repository/works/{work_id}/artifacts",
                            params={"kind": kind, "limit": 100},
                        )
                        if manifests:
                            manifest = manifests[0]
                            content_type = str(manifest.get("contentType", ""))
                            locator = str(manifest["artifactId"])
                            self._manifests[(work_id, locator)] = manifest
                            break
                logger.info(
                    "SLR work %s license=%s artifact=%s content_type=%r",
                    work_id,
                    license_code,
                    locator,
                    content_type,
                )
                refs.append(
                    SourceArticleRef(work_id, title, doi, license_code, content_type, locator)
                )
            except httpx.HTTPStatusError as error:
                if error.response.status_code != 404:
                    raise
                logger.warning("SLR work %s returned 404; skipped", work_id)
        return SourcePage(tuple(refs), data.get("page", {}).get("nextCursor"))

    def _find_license(self, sources: list[dict[str, Any]]) -> str | None:
        for source in sources:
            metadata = source.get("originalMetadata", {})
            for path in self._policy.slr_license_paths:
                value: Any = metadata
                for part in path.split("."):
                    value = value.get(part) if isinstance(value, dict) else None
                if isinstance(value, str) and (code := self._license_lookup.get(self._norm(value))):
                    return code
        return None

    async def fetch_content(self, article: SourceArticleRef) -> bytes:
        locator = article.content_locator
        manifest = self._manifests.get((article.external_id, locator or ""))
        if not locator or manifest is None:
            raise InvalidContentError("Artifact manifest unavailable")
        path = f"/public/v1/repository/works/{article.external_id}/artifacts/{locator}/download"
        data_buffer = bytearray()
        response_type = ""
        for attempt in range(self._max_retries + 1):
            async with self._client.stream(
                "GET", path.lstrip("/"), headers={"X-API-Key": self._key.get_secret_value()}
            ) as response:
                if response.status_code == 429 and attempt < self._max_retries:
                    try:
                        delay = float(response.headers.get("Retry-After", "60"))
                    except ValueError:
                        delay = 60
                    logger.warning(
                        "SLR rate limited on download %s/%s; retry in %ss",
                        article.external_id,
                        locator,
                        delay,
                    )
                    await self._sleep(delay)
                    continue
                if response.status_code in (401, 403):
                    raise PermissionError("SLR API configuration error: AUTHORIZATION_FAILED")
                if response.status_code == 404:
                    raise InvalidContentError("Artifact download returned 404")
                response.raise_for_status()
                response_type = (
                    response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
                )
                async for chunk in response.aiter_bytes():
                    data_buffer.extend(chunk)
                    if len(data_buffer) > self._config.slr_max_download_bytes:
                        raise InvalidContentError(
                            "Downloaded content exceeds configured size limit"
                        )
                break
        else:
            raise RuntimeError("SLR rate limit retries exhausted")
        manifest_type = str(manifest.get("contentType", "")).split(";", 1)[0].strip().casefold()
        if response_type != manifest_type:
            raise InvalidContentError("Downloaded content type differs from manifest")
        data = bytes(data_buffer)
        expected_size = manifest.get("sizeBytes")
        if len(data) > self._config.slr_max_download_bytes or (
            expected_size is not None and len(data) != expected_size
        ):
            raise InvalidContentError(
                "Downloaded content size differs from manifest or exceeds limit"
            )
        if manifest.get("checksumAlgorithm") == "SHA-256" and (
            hashlib.sha256(data).hexdigest().casefold()
            != str(manifest.get("checksum", "")).casefold()
        ):
            raise InvalidContentError("Downloaded content checksum differs from manifest")
        return data

    async def get_taxonomy(
        self, level: str, parent_id: str | None, cursor: str | None, limit: int
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"level": level, "limit": limit}
        if parent_id is not None:
            params["parentId"] = parent_id
        if cursor is not None:
            params["cursor"] = cursor
        data = await self._json("/public/v1/repository/taxonomy", params=params)
        # SLR rejects its own ``id`` (e.g. ``fields_17``) as ``parentId`` or a work filter;
        # the OpenAlex URL is accepted by both (probe 2026-11-02), so expose that as ``id``.
        items = [
            {
                **item,
                "id": item.get("openAlexId") or item.get("id"),
                "parentId": item.get("parentOpenAlexId") or item.get("parentId"),
            }
            for item in data.get("items", [])
        ]
        return {"items": items, "nextCursor": data.get("nextCursor")}
