"""schema.org JSON-LD feeder.

Many sites that look like plain server-rendered HTML also embed structured
`<script type="application/ld+json">` blocks for SEO. Worth trying before writing
CSS selectors for a site: zero-config data extraction when it is present.
"""
from __future__ import annotations

from typing import AsyncIterator

from pydantic import BaseModel

from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Adapter, Feeder
from penn_events.core.models import RawRecord

from .factory import register_feeder


class JsonLdConfig(BaseModel):
    url: str


@register_feeder
class JsonLdFeeder(Feeder):
    type = "jsonld"
    config_model = JsonLdConfig

    def __init__(self, spec, config: JsonLdConfig, http: HttpClient) -> None:
        super().__init__(spec, config, http)
        self.config: JsonLdConfig = config

    async def fetch(self) -> AsyncIterator[RawRecord]:
        html = await self.http.get_text(self.config.url)
        yield RawRecord(format="html", url=self.config.url, payload=html)

    def adapter(self) -> Adapter:
        from penn_events.adapters.jsonld_adapter import JsonLdAdapter

        return JsonLdAdapter()
