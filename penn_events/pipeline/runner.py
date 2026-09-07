"""Orchestrates one feeder end to end: fetch -> adapt -> normalize -> upsert.

This is the only module that wires the four patterns together. Feeders and
adapters never see a database session; the repository never sees an HTTP client.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from penn_events.core.errors import ConfigError
from penn_events.core.http import HttpClient
from penn_events.core.models import FeedContext, NormalizedEvent, RunReport
from penn_events.db.repositories.calendars import CalendarRepository
from penn_events.db.repositories.events import EventRepository
from penn_events.db.session import session_scope
from penn_events.feeders.factory import FeederFactory
from penn_events.normalize.datetimes import horizon
from penn_events.normalize.pipeline import Normalizer
from penn_events.normalize.tagger import Tagger, registry_tags

if TYPE_CHECKING:
    from penn_events.config.schema import FeederSpec, MasterConfig

log = logging.getLogger(__name__)


def _feeder_source(spec: "FeederSpec") -> str:
    """`source` column value when the feeder does not set one explicitly.

    Format is `<type>:<host>`, e.g. `ics:events.med.upenn.edu` -- lets you find
    "everything from a broken feeder type" with a single WHERE clause.
    """
    if spec.source:
        return spec.source
    from urllib.parse import urlparse

    host = urlparse(spec.registry_url).netloc if spec.registry_url else spec.id
    return f"{spec.type}:{host or spec.id}"


def build_context(spec: "FeederSpec", config: "MasterConfig") -> FeedContext:
    """Join a feeder spec to its `calendars` registry row (if any) into a FeedContext."""
    calendar_id = None
    source_calendar_name = spec.source_calendar_name
    host = spec.host
    reg_tags: tuple[str, ...] = ()

    if spec.registry_url:
        with session_scope() as session:
            row = CalendarRepository(session).get_by_url(spec.registry_url)
            if row is None:
                # Not a warn-and-continue: a silently unresolved registry_url means
                # every event this feeder writes gets calendar_id=None, which is
                # exactly what makes it (and its school_division) invisible to the
                # API and frontend -- caught here instead, before any events exist.
                raise ConfigError(
                    f"feeder {spec.id!r}: registry_url {spec.registry_url!r} has no "
                    "matching calendars row -- run `import-registry` or fix the URL"
                )
            calendar_id = row.id
            source_calendar_name = source_calendar_name or row.calendar_name
            host = host or row.school_division or row.unit
            reg_tags = tuple(registry_tags(row.school_division, row.category))

    return FeedContext(
        feeder_id=spec.id,
        source=_feeder_source(spec),
        host=host,
        source_calendar_name=source_calendar_name,
        calendar_id=calendar_id,
        calendar_url=spec.registry_url,
        timezone=config.timezone_for(spec),
        static_tags=tuple(spec.tags),
        registry_tags=reg_tags,
        horizon_days=config.horizon_for(spec),
    )


async def run_feeder(
    spec: "FeederSpec",
    config: "MasterConfig",
    http: HttpClient,
    tagger: Tagger | None = None,
) -> RunReport:
    """Run one feeder to completion and write its events."""
    started = time.monotonic()
    report = RunReport(feeder_id=spec.id, ok=False)

    try:
        ctx = build_context(spec, config)
        feeder = FeederFactory.build(spec, http)
        adapter = feeder.adapter()
        normalizer = Normalizer(tagger)

        raw_events: list[NormalizedEvent] = []
        records = 0
        async for record in feeder.fetch():
            records += 1
            raw_events.extend(adapter.adapt(record, ctx))

        finished_events = normalizer.normalize(raw_events, ctx)

        with session_scope() as session:
            stats = EventRepository(session).upsert_many(finished_events)
            removed = 0
            if finished_events:
                window_start, window_end = horizon(ctx.horizon_days)
                removed = EventRepository(session).mark_absent_as_removed(
                    ctx.calendar_id,
                    ctx.source,
                    [e.dedupe_key for e in finished_events],
                    window_start,
                    window_end,
                )

        report = RunReport(
            feeder_id=spec.id,
            ok=True,
            records=records,
            events=len(finished_events),
            stats=stats,
            removed=removed,
        )
        log.info("%s: %d records -> %d events (%s, %d removed)", spec.id, records, len(finished_events), stats, removed)
    except Exception as exc:  # noqa: BLE001 -- one feeder's failure must not sink the run
        log.exception("%s: run failed", spec.id)
        report = RunReport(feeder_id=spec.id, ok=False, error=str(exc))

    report.duration_seconds = round(time.monotonic() - started, 2)
    return report


async def run_all(
    config: "MasterConfig",
    *,
    feeder_ids: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    max_concurrency: int = 8,
) -> list[RunReport]:
    """Run every enabled feeder (or a chosen subset) concurrently.

    One shared `HttpClient` means the per-host rate limiter actually limits across
    the whole run, not just within a single feeder.
    """
    specs = config.enabled_feeders()
    if feeder_ids:
        wanted = set(feeder_ids)
        specs = [s for s in specs if s.id in wanted]
        missing = wanted - {s.id for s in specs}
        if missing:
            log.warning("requested feeder ids not found or disabled: %s", sorted(missing))
    if exclude_tags:
        excluded = set(exclude_tags)
        skipped = [s.id for s in specs if excluded & set(s.tags)]
        if skipped:
            log.info("skipping %d feeder(s) tagged %s: %s", len(skipped), sorted(excluded), sorted(skipped))
        specs = [s for s in specs if not (excluded & set(s.tags))]

    tagger = Tagger()
    semaphore = asyncio.Semaphore(max_concurrency)

    async with HttpClient(
        user_agent=config.defaults.user_agent,
        timeout_seconds=config.defaults.timeout_seconds,
        retries=config.defaults.retries,
        rate_limit_per_host=config.defaults.rate_limit_per_host,
    ) as http:

        async def _bounded(spec: "FeederSpec") -> RunReport:
            async with semaphore:
                return await run_feeder(spec, config, http, tagger)

        return list(await asyncio.gather(*(_bounded(spec) for spec in specs)))
