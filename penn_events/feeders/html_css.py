"""Declarative HTML/CSS feeder.

385 of 511 registry rows (Drupal, generic WordPress, static HTML) are
server-rendered pages whose *layout* differs per site but whose *shape* -- a list
of event teasers, each with a title, a link, a date, a location -- is the same.
Rather than one Python class per site, this feeder reads its CSS selectors from
`master.yaml`: one implementation, N configs.
"""
from __future__ import annotations

import logging
from typing import AsyncIterator
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Adapter, Feeder
from penn_events.core.models import RawRecord

from .factory import register_feeder

log = logging.getLogger(__name__)


class FieldSelector(BaseModel):
    css: str
    attr: str = "text"  # "text", or an HTML attribute name e.g. "href", "datetime"
    multiple: bool = False  # collect every match (used for tags) instead of the first


class PaginationConfig(BaseModel):
    param: str = "page"
    start: int = 0
    max_pages: int = 5
    stop_when_empty: bool = True


class HtmlCssConfig(BaseModel):
    list_url: str
    base_url: str | None = None
    item: str  # CSS selector for one event's container element
    fields: dict[str, FieldSelector]
    pagination: PaginationConfig | None = None
    # Per-site override of defaults.user_agent. Exists for hosts whose WAF blocks
    # on a literal "Bot" substring rather than real bot fingerprinting (confirmed
    # live on almanac.upenn.edu: our real UA -> 403, the same UA with "Bot" removed
    # -> 200, and its own robots.txt is `User-agent: *` / `Crawl-delay: 10` with no
    # bot disallow) -- a keyword false-positive, not a site that has decided to
    # block automated access. Still a real, contactable identifying string; not a
    # browser impersonation.
    user_agent: str | None = None

    def resolved_base_url(self) -> str:
        if self.base_url:
            return self.base_url
        parsed = urlparse(self.list_url)
        return f"{parsed.scheme}://{parsed.netloc}"


@register_feeder
class HtmlCssFeeder(Feeder):
    type = "html_css"
    config_model = HtmlCssConfig

    def __init__(self, spec, config: HtmlCssConfig, http: HttpClient) -> None:
        super().__init__(spec, config, http)
        self.config: HtmlCssConfig = config

    def _headers(self) -> dict[str, str] | None:
        return {"User-Agent": self.config.user_agent} if self.config.user_agent else None

    async def fetch(self) -> AsyncIterator[RawRecord]:
        pagination = self.config.pagination
        if pagination is None:
            html = await self.http.get_text(self.config.list_url, headers=self._headers())
            yield RawRecord(format="html", url=self.config.list_url, payload=html)
            return

        separator = "&" if "?" in self.config.list_url else "?"
        for page in range(pagination.start, pagination.start + pagination.max_pages):
            url = f"{self.config.list_url}{separator}{pagination.param}={page}"
            html = await self.http.get_text(url, headers=self._headers())
            item_count = len(BeautifulSoup(html, "lxml").select(self.config.item))
            if item_count == 0 and pagination.stop_when_empty:
                log.debug("%s: page %d empty, stopping pagination", self.spec.id, page)
                break
            yield RawRecord(format="html", url=url, payload=html)

    def adapter(self) -> Adapter:
        from penn_events.adapters.html_adapter import HtmlCssAdapter

        return HtmlCssAdapter(self.config)
