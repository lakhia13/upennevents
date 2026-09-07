"""Headless-browser HTML feeder, for pages behind a genuine JS challenge.

Penn Today and Annenberg both sit behind Cloudflare's "managed" challenge
(`cType: 'managed'`, confirmed live) -- a plain HTTP client gets a 403 even with
an exact Chrome User-Agent, but a stock headless Chromium that actually executes
the challenge's JS and waits for it to resolve passes cleanly, still presenting
our real, honest `PennEventsBot` identity the whole time. That's not detection
evasion (no `navigator.webdriver` patching, no fingerprint spoofing, no browser
impersonation over plain HTTP) -- it's just using the class of client the
challenge is designed to admit.

Reuses `HtmlCssConfig`'s `item`/`fields` selector shape and `HtmlCssAdapter`:
only the transport differs from `html_css`, not the parsing.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import AsyncIterator

from playwright.async_api import Page, async_playwright

from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Adapter, Feeder
from penn_events.core.models import RawRecord
from penn_events.feeders.html_css import HtmlCssConfig

from .factory import register_feeder

log = logging.getLogger(__name__)

# `run_all`'s own semaphore (core/../pipeline/runner.py) caps *all* feeders
# together (default 8), with no distinction between a cheap httpx GET and a full
# Chromium launch executing a real JS challenge. Confirmed live in production
# (2026-09-07): master.yaml lists most playwright_html feeders consecutively, so
# a run legitimately landed 8+ of them in the same concurrent batch -- on a
# CI runner with far less headroom than local dev, that many simultaneous
# Cloudflare-challenge solves starved each other for CPU and every single one
# blew the wait_ms budget below, while every non-Playwright feeder (unaffected
# by that contention) succeeded normally. This semaphore caps concurrent browser
# launches specifically, independent of overall feeder concurrency, so cheap
# feeders keep running at full speed while heavy ones queue for a browser slot.
_MAX_CONCURRENT_BROWSERS = 3
_browser_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_BROWSERS)


class PlaywrightHtmlConfig(HtmlCssConfig):
    wait_selector: str | None = None  # CSS selector to wait for instead of a fixed delay
    # Settle time for the Cloudflare challenge + page JS to finish. 6000ms was
    # sized against local dev running one or two of these at a time; raised
    # after the CI failure above, where the same challenge under real
    # contention took longer than that to resolve even for well-behaved sites.
    wait_ms: int = 15000
    nav_timeout_ms: int = 30000


@register_feeder
class PlaywrightHtmlFeeder(Feeder):
    type = "playwright_html"
    config_model = PlaywrightHtmlConfig

    def __init__(self, spec, config: PlaywrightHtmlConfig, http: HttpClient) -> None:
        super().__init__(spec, config, http)
        self.config: PlaywrightHtmlConfig = config

    async def fetch(self) -> AsyncIterator[RawRecord]:
        async with _browser_semaphore:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    page = await browser.new_page(user_agent=self.http.user_agent)
                    response = await page.goto(
                        self.config.list_url,
                        wait_until="domcontentloaded",
                        timeout=self.config.nav_timeout_ms,
                    )
                    try:
                        if self.config.wait_selector:
                            await page.wait_for_selector(self.config.wait_selector, timeout=self.config.wait_ms)
                        else:
                            await page.wait_for_timeout(self.config.wait_ms)
                    except Exception:
                        status = response.status if response else None
                        log.warning("%s: nav status %s before wait failed", self.id, status)
                        await self._dump_debug(page)
                        raise
                    html = await page.content()
                finally:
                    await browser.close()
        yield RawRecord(format="html", url=self.config.list_url, payload=html)

    async def _dump_debug(self, page: Page) -> None:
        """Best-effort capture of what the browser actually saw, gated on an env
        var so this never runs (or costs anything) outside CI debugging. Added
        after a production failure where every playwright_html feeder timed out
        identically regardless of wait time -- distinguishing "still shows a
        Cloudflare challenge" from "loaded something else entirely" needs to see
        the real page, not just the exception."""
        debug_dir = os.environ.get("PLAYWRIGHT_DEBUG_DIR")
        if not debug_dir:
            return
        try:
            out = Path(debug_dir)
            out.mkdir(parents=True, exist_ok=True)
            html = await page.content()
            (out / f"{self.id}.html").write_text(html, encoding="utf-8")
            await page.screenshot(path=str(out / f"{self.id}.png"), full_page=True)
        except Exception:
            log.warning("%s: debug capture itself failed", self.id, exc_info=True)

    def adapter(self) -> Adapter:
        from penn_events.adapters.html_adapter import HtmlCssAdapter

        return HtmlCssAdapter(self.config)
