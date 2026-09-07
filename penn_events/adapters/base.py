"""Shared helpers for adapters.

Adapters do field mapping only -- these helpers exist so that mapping code stays
short and consistent across formats, not to hide cross-cutting logic (that lives in
`penn_events.normalize`).
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin


def pluck(source: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    """First non-empty value found across a list of candidate keys.

    Different feeds spell the same field differently (`"url"` vs `"link"` vs
    `"permalink"`); this avoids a chain of `.get(...) or .get(...)` in every adapter.
    """
    if not source:
        return default
    for key in keys:
        value = source.get(key)
        if value not in (None, "", []):
            return value
    return default


def absolute_url(base_url: str | None, url: str | None) -> str | None:
    """Resolve a possibly-relative URL against the feed's base URL."""
    if not url:
        return None
    if not base_url or url.startswith(("http://", "https://")):
        return url
    return urljoin(base_url, url)


def as_list(value: Any) -> list[Any]:
    """Normalize a field that may be a single item or a list of them."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]
