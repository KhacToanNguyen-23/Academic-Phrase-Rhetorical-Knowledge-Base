"""Deterministic article identity keys; titles are review hints, never proof."""

import re
import unicodedata
from hashlib import sha256
from urllib.parse import unquote


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = unquote(value.strip()).casefold()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value).strip()
    # Do not strip punctuation from the suffix: it can be part of a real DOI.
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else None


def normalize_title(value: str | None) -> str | None:
    value = unicodedata.normalize("NFKC", value or "").casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in value).split()) or None


def content_hash(content: bytes) -> str:
    return sha256(content).hexdigest()


def pdf_text_hash(text: str) -> str:
    """Exact text identity, preserving case, exponents, symbols and punctuation."""
    normalized = " ".join(unicodedata.normalize("NFC", text).split())
    return content_hash(normalized.encode("utf-8"))


def title_identity(value: str | None) -> str | None:
    normalized = normalize_title(value)
    return content_hash(normalized.encode("utf-8")) if normalized else None
