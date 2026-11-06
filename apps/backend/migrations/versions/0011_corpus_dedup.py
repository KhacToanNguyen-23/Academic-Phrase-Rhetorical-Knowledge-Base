"""Index normalized article identities without deleting legacy duplicates."""

import re
import unicodedata
from hashlib import sha256
from urllib.parse import unquote

import sqlalchemy as sa
from alembic import op

revision = "0011_corpus_dedup"
down_revision = "0010_merge_vocabulary_and_pack"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("doi_key", sa.String(255)))
    op.add_column("articles", sa.Column("title_key", sa.String(64)))
    op.add_column("articles", sa.Column("content_sha256", sa.String(64)))
    articles = sa.table(
        "articles",
        sa.column("id"),
        sa.column("doi"),
        sa.column("title"),
        sa.column("doi_key"),
        sa.column("title_key"),
    )
    connection = op.get_bind()
    # Freeze normalization here so future application changes cannot alter this migration.
    for row in connection.execute(sa.select(articles.c.id, articles.c.doi, articles.c.title)):
        doi = unquote((row.doi or "").strip()).casefold()
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi).strip()
        doi_key = doi if re.fullmatch(r"10\.\d{4,9}/\S+", doi) else None
        title = unicodedata.normalize("NFKC", row.title or "").casefold()
        title_key = " ".join("".join(c if c.isalnum() else " " for c in title).split()) or None
        title_key = sha256(title_key.encode("utf-8")).hexdigest() if title_key else None
        connection.execute(
            articles.update()
            .where(articles.c.id == row.id)
            .values(
                doi_key=doi_key,
                title_key=title_key,
            )
        )
    # Non-unique indexes intentionally preserve pre-existing duplicate records.
    for name in ("doi_key", "title_key", "content_sha256"):
        op.create_index(f"ix_articles_{name}", "articles", [name])


def downgrade() -> None:
    for name in ("content_sha256", "title_key", "doi_key"):
        op.drop_index(f"ix_articles_{name}", table_name="articles")
        op.drop_column("articles", name)
