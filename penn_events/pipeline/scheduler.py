"""APScheduler wiring: one cron job per enabled feeder, schedule read from YAML.

Runs inside the `worker` container as the long-lived process. Each feeder gets its
own job so a `schedule:` override on one feeder in `master.yaml` does not affect
any other, and a single slow feeder cannot block the rest from firing on time.

**Local development only.** Production does not run this: the scrape is ~5 minutes
of work four times a day, so it runs as a scheduled GitHub Actions job
(.github/workflows/scrape.yml) calling `cli.py run-all` instead of keeping a
container alive to hold this scheduler. That also sidesteps the failure mode of
free container tiers, which spin down when idle and would silently never fire.

One consequence: in production every feeder runs on the workflow's single cron, so
a per-feeder `schedule:` in master.yaml has no effect there. Every feeder currently
uses the same default, so this changes nothing today -- but a per-feeder override
would need the workflow to change too, not just the YAML.
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from penn_events.config.loader import load_config
from penn_events.core.http import HttpClient
from penn_events.normalize.tagger import Tagger

from .runner import run_feeder

log = logging.getLogger(__name__)


async def _run_and_log(spec, config, http: HttpClient, tagger: Tagger) -> None:
    report = await run_feeder(spec, config, http, tagger)
    if not report.ok:
        log.error("scheduled run failed: %s -- %s", spec.id, report.error)


async def serve(config_path: str | None = None) -> None:
    """Start the scheduler and block forever, running feeders on their cron schedules."""
    config = load_config(config_path)
    tagger = Tagger()
    scheduler = AsyncIOScheduler()

    async with HttpClient(
        user_agent=config.defaults.user_agent,
        timeout_seconds=config.defaults.timeout_seconds,
        retries=config.defaults.retries,
        rate_limit_per_host=config.defaults.rate_limit_per_host,
    ) as http:
        for spec in config.enabled_feeders():
            cron = config.schedule_for(spec)
            scheduler.add_job(
                _run_and_log,
                trigger=CronTrigger.from_crontab(cron),
                args=[spec, config, http, tagger],
                id=spec.id,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=3600,
            )
            log.info("scheduled %s (%s) at %r", spec.id, spec.type, cron)

        scheduler.start()
        log.info("scheduler started with %d jobs; running forever", len(config.enabled_feeders()))
        try:
            await asyncio.Event().wait()
        finally:
            scheduler.shutdown(wait=False)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(serve())


if __name__ == "__main__":
    main()
