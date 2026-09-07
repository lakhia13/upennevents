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

from typing import AsyncIterator

from playwright.async_api import async_playwright

from penn_events.core.http import HttpClient
from penn_events.core.interfaces import Adapter, Feeder
from penn_events.core.models import RawRecord
from penn_events.feeders.html_css import HtmlCssConfig

from .factory import register_feeder


class PlaywrightHtmlConfig(HtmlCssConfig):
    wait_selector: str | None = None  # CSS selector to wait for instead of a fixed delay
    wait_ms: int = 6000  # settle time for the Cloudflare challenge + page JS to finish
    nav_timeout_ms: int = 30000


@register_feeder
class PlaywrightHtmlFeeder(Feeder):
    type = "playwright_html"
    config_model = PlaywrightHtmlConfig

    def __init__(self, spec, config: PlaywrightHtmlConfig, http: HttpClient) -> None:
        super().__init__(spec, config, http)
        self.config: PlaywrightHtmlConfig = config

    async def fetch(self) -> AsyncIterator[RawRecord]:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(user_agent=self.http.user_agent)
                await page.goto(
                    self.config.list_url, wait_until="domcontentloaded", timeout=self.config.nav_timeout_ms
                )
                if self.config.wait_selector:
                    await page.wait_for_selector(self.config.wait_selector, timeout=self.config.wait_ms)
                else:
                    await page.wait_for_timeout(self.config.wait_ms)
                html = await page.content()
            finally:
                await browser.close()
        yield RawRecord(format="html", url=self.config.list_url, payload=html)

    def adapter(self) -> Adapter:
        from penn_events.adapters.html_adapter import HtmlCssAdapter

        return HtmlCssAdapter(self.config)
