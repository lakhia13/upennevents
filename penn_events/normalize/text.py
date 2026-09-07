"""Text cleanup shared by every adapter."""
from __future__ import annotations

import html
import re
import unicodedata

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_BLOCK_BREAK_RE = re.compile(r"(?i)</(p|div|li|h[1-6])>|<br\s*/?>")

MAX_DESCRIPTION = 20_000


def clean(value: object, *, max_length: int | None = None) -> str | None:
    """Decode entities, strip markup, collapse whitespace.

    Returns None for anything that ends up empty, so the column stays NULL rather
    than holding an empty string.
    """
    if value is None:
        return None
    text = str(value)
    text = _BLOCK_BREAK_RE.sub("\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = "\n".join(_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return None
    if max_length and len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "…"
    return text


def clean_description(value: object) -> str | None:
    return clean(value, max_length=MAX_DESCRIPTION)


def slugify(value: str) -> str:
    """Lowercase ascii slug, used for tag names."""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text


def title_key(value: str) -> str:
    """Normalised title used for identity, so casing and spacing churn is ignored."""
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return _WHITESPACE_RE.sub(" ", re.sub(r"[^a-z0-9 ]+", "", text.lower())).strip()
