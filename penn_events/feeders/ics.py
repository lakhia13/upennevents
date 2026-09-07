"""ICS/iCal feeder.

Covers LiveWhale's Subscribe feed, VPUL's `/calendar/ics/subscribe`, Trumba's
`.ics` export, TEC's `?ical=1`, CampusGroups' `ics_helper`, and the undocumented
Drupal 7 `/ics` endpoint on SAS sites -- six platform families, one implementation,
because they all speak the same RFC 5545 format on the wire.
"""
from __future__ import annotations

from typing import AsyncIterator

from pydantic import BaseModel, Field

from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Adapter, Feeder
from penn_events.core.models import RawRecord

from .factory import register_feeder


class IcsConfig(BaseModel):
    url: str
    # Some hosts (LiveWhale) serve iCal over `webcal://`; normalize before fetching.
    extra_urls: list[str] = Field(default_factory=list)


@register_feeder
class IcsFeeder(Feeder):
    type = "ics"
    config_model = IcsConfig

    def __init__(self, spec, config: IcsConfig, http: HttpClient) -> None:
        super().__init__(spec, config, http)
        self.config: IcsConfig = config

    async def fetch(self) -> AsyncIterator[RawRecord]:
        for url in [self.config.url, *self.config.extra_urls]:
            fetch_url = url.replace("webcal://", "https://", 1)
            text = await self.http.get_text(fetch_url)
            yield RawRecord(format="ics", url=fetch_url, payload=text)

    def adapter(self) -> Adapter:
        from penn_events.adapters.ics_adapter import IcsAdapter

        return IcsAdapter()
