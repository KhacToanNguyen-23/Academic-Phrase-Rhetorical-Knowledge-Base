"""Placeholder article source used until the external API adapter is implemented."""

from aprkb.modules.corpus.sources.base import SourceArticleRef, SourcePage


class NullArticleSource:
    name = "null"

    async def list_articles(self, *, cursor: str | None, limit: int) -> SourcePage:
        """Return no articles; the scaffold does not call any external API."""
        del cursor, limit
        return SourcePage(articles=(), next_cursor=None)

    async def fetch_content(self, article: SourceArticleRef) -> bytes:
        del article
        raise LookupError("The null article source has no content")
