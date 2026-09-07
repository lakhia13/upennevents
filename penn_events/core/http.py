"""Shared async HTTP client: one connection pool, per-host rate limiting, retries.

Every feeder fetches through this, so politeness policy lives in exactly one place.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import defaultdict
from types import TracebackType
from urllib.parse import urlparse

import httpx

from .errors import FetchError

log = logging.getLogger(__name__)

RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class _HostLimiter:
    """Serialises requests to a single host and spaces them out."""

    def __init__(self, min_interval: float) -> None:
        self._min_interval = min_interval
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def __aenter__(self) -> None:
        await self._lock.acquire()
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            await asyncio.sleep(wait)

    async def __aexit__(self, *exc: object) -> None:
        self._last = time.monotonic()
        self._lock.release()


class HttpClient:
    """Thin wrapper over httpx.AsyncClient.

    `rate_limit_per_host` is requests per second; 0.5 means one request every two
    seconds to any single host, regardless of how many feeders target it.
    """

    def __init__(
        self,
        user_agent: str,
        timeout_seconds: float = 30.0,
        retries: int = 3,
        rate_limit_per_host: float = 0.5,
    ) -> None:
        self._retries = max(0, retries)
        self._min_interval = 1.0 / rate_limit_per_host if rate_limit_per_host > 0 else 0.0
        self._limiters: dict[str, _HostLimiter] = defaultdict(
            lambda: _HostLimiter(self._min_interval)
        )
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={
                "User-Agent": user_agent,
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    async def __aenter__(self) -> HttpClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        """GET with per-host throttling and exponential backoff on transient failures."""
        host = urlparse(url).netloc
        last_error = "unknown error"
        status: int | None = None

        for attempt in range(self._retries + 1):
            async with self._limiters[host]:
                try:
                    response = await self._client.get(url, **kwargs)  # type: ignore[arg-type]
                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                else:
                    status = response.status_code
                    if response.status_code < 400:
                        return response
                    if response.status_code not in RETRY_STATUS:
                        raise FetchError(url, f"HTTP {response.status_code}", response.status_code)
                    last_error = f"HTTP {response.status_code}"

            if attempt < self._retries:
                backoff = (2**attempt) + random.uniform(0, 0.5)
                log.warning("retrying %s in %.1fs (%s)", url, backoff, last_error)
                await asyncio.sleep(backoff)

        raise FetchError(url, f"giving up after {self._retries + 1} attempts: {last_error}", status)

    async def get_text(self, url: str, **kwargs: object) -> str:
        return (await self.get(url, **kwargs)).text

    async def get_json(self, url: str, **kwargs: object) -> object:
        response = await self.get(url, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            raise FetchError(url, f"response was not JSON: {exc}") from exc
