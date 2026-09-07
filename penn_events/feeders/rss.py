"""RSS feeder.

Confirmed live against SAS's real feed (`www.sas.upenn.edu/events/rss.xml`), which --
unusually for RSS -- embeds a `<sdo:Event>` schema.org block per item with a real
`startDate`/`endDate`, not just the item's publish date. The adapter prefers that
over `pubDate`, which is when the item was posted, not when the event happens.
"""
from __future__ import annotations

from typing import AsyncIterator

from pydantic import BaseModel

from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Adapter, Feeder
from penn_events.core.models import RawRecord

from .factory import register_feeder


class RssConfig(BaseModel):
    url: str


@register_feeder
class RssFeeder(Feeder):
    type = "rss"
    config_model = RssConfig

    def __init__(self, spec, config: RssConfig, http: HttpClient) -> None:
        super().__init__(spec, config, http)
        self.config: RssConfig = config

    async def fetch(self) -> AsyncIterator[RawRecord]:
        xml = await self.http.get_text(self.config.url)
        yield RawRecord(format="xml", url=self.config.url, payload=xml)

    def adapter(self) -> Adapter:
        from penn_events.adapters.rss_adapter import RssAdapter

        return RssAdapter()
