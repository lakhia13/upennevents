"""The Events Calendar (WordPress plugin) REST API feeder.

The best-behaved format in the whole registry: a real, paginated, documented JSON
API at `/wp-json/tribe/events/v1/events`. Confirmed on Penn Engineering, Penn Vet,
SP2, Faculty Senate.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, AsyncIterator
from urllib.parse import urlencode

from pydantic import BaseModel, Field

from penn_events.core.errors import FetchError
from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Adapter, Feeder
from penn_events.core.models import RawRecord

from .factory import register_feeder

MAX_PAGES_SAFETY = 50


class TecRestConfig(BaseModel):
    base_url: str  # e.g. https://events.engineering.upenn.edu
    per_page: int = 50
    max_pages: int = 20
    path: str = "/wp-json/tribe/events/v1/events"


@register_feeder
class TecRestFeeder(Feeder):
    type = "tec_rest"
    config_model = TecRestConfig

    def __init__(self, spec, config: TecRestConfig, http: HttpClient) -> None:
        super().__init__(spec, config, http)
        self.config: TecRestConfig = config

    async def fetch(self) -> AsyncIterator[RawRecord]:
        base = self.config.base_url.rstrip("/") + self.config.path
        today = dt.date.today().isoformat()
        page = 1
        max_pages = min(self.config.max_pages, MAX_PAGES_SAFETY)

        while page <= max_pages:
            params = {"page": page, "per_page": self.config.per_page, "start_date": today}
            url = f"{base}?{urlencode(params)}"
            try:
                body: Any = await self.http.get_json(url)
            except FetchError:
                break

            events = body.get("events") if isinstance(body, dict) else None
            if not events:
                break

            yield RawRecord(format="json", url=url, payload=body)

            total_pages = int(body.get("total_pages") or 1)
            if page >= total_pages:
                break
            page += 1

    def adapter(self) -> Adapter:
        from penn_events.adapters.tec_adapter import TecAdapter

        return TecAdapter()
