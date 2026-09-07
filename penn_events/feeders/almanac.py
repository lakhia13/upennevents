"""Almanac 'at Penn' calendar feeder.

Penn's Almanac (almanac.upenn.edu) publishes one page per current month listing
every campus event, grouped into Bootstrap accordion panels by category (Talks,
Music, Exhibits, ...), not by date. Genuinely unique to this one site in the
registry -- no other row shares this shape -- so it gets its own feeder/adapter
pair rather than folding into the declarative `html_css` field-selector engine,
which has no way to express "day number carries forward across sibling <p>s."

The host's WAF 403s any User-Agent containing a `(+http...)`-style contact URL
(the conventional "polite crawler" format, e.g. Googlebot's) regardless of the
rest of the string -- confirmed live, 2026-09-07, and contradicted by the site's
own robots.txt (`User-agent: *`, `Crawl-delay: 10`, no bot disallow). That's a
keyword/pattern false positive, not a deliberate "no bots" policy, so `user_agent`
below drops the URL but keeps a real, contactable identity (still no browser
impersonation).
"""
from __future__ import annotations

from typing import AsyncIterator

from pydantic import BaseModel

from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Adapter, Feeder
from penn_events.core.models import RawRecord

from .factory import register_feeder


class AlmanacConfig(BaseModel):
    url: str
    user_agent: str | None = None


@register_feeder
class AlmanacFeeder(Feeder):
    type = "almanac_calendar"
    config_model = AlmanacConfig

    def __init__(self, spec, config: AlmanacConfig, http: HttpClient) -> None:
        super().__init__(spec, config, http)
        self.config: AlmanacConfig = config

    async def fetch(self) -> AsyncIterator[RawRecord]:
        headers = {"User-Agent": self.config.user_agent} if self.config.user_agent else None
        html = await self.http.get_text(self.config.url, headers=headers)
        yield RawRecord(format="html", url=self.config.url, payload=html)

    def adapter(self) -> Adapter:
        from penn_events.adapters.almanac_adapter import AlmanacAdapter

        return AlmanacAdapter()
