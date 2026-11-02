"""Placeholder article source used until the external API adapter is implemented."""

from aprkb.modules.corpus.sources.base import ImportOptions, SourceArticleRef, SourcePage


class NullArticleSource:
    name = "null"

    async def list_articles(
        self, *, cursor: str | None, limit: int, options: ImportOptions
    ) -> SourcePage:
        """Return no articles; the scaffold does not call any external API."""
        del cursor, limit, options
        return SourcePage(articles=(), next_cursor=None)

    async def fetch_content(self, article: SourceArticleRef) -> bytes:
        del article
        raise LookupError("The null article source has no content")

    async def aclose(self) -> None:
        return None

    async def get_taxonomy(
        self, level: str, parent_id: str | None, cursor: str | None, limit: int
    ) -> dict[str, object]:
        del level, parent_id, cursor, limit
        return {"items": [], "nextCursor": None}
