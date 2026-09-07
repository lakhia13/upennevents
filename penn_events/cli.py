"""Command-line entrypoints. Run as `python -m penn_events.cli <command>`."""
from __future__ import annotations

import asyncio
import logging

import typer

from penn_events.config.loader import load_config
from penn_events.core.errors import ConfigError, PennEventsError
from penn_events.core.http import HttpClient
from penn_events.db.repositories.calendars import CalendarRepository
from penn_events.db.repositories.events import EventRepository
from penn_events.db.session import session_scope
from penn_events.feeders import known_types  # noqa: F401 -- import registers every feeder type
from penn_events.pipeline.runner import run_all, run_feeder

app = typer.Typer(add_completion=False, help="Penn unified events calendar -- ingestion CLI")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command("import-registry")
def import_registry(
    csv_path: str = typer.Argument(..., help="Path to penn-calendars.csv"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Load the calendar registry CSV into the `calendars` table (idempotent upsert)."""
    _setup_logging(verbose)
    with session_scope() as session:
        repo = CalendarRepository(session)
        seen, written = repo.import_csv(csv_path)
        total = repo.count()
    typer.echo(f"{seen} rows read, {written} written, {total} total rows in `calendars`")


@app.command("validate-config")
def validate_config(
    config_path: str = typer.Option(None, "--config", "-c", help="Path to master.yaml"),
) -> None:
    """Load, expand and validate master.yaml without fetching anything."""
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        typer.secho(f"INVALID: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    unregistered = []
    with session_scope() as session:
        repo = CalendarRepository(session)
        for spec in config.feeders:
            if spec.registry_url and repo.get_by_url(spec.registry_url) is None:
                unregistered.append((spec.id, spec.registry_url))

    typer.echo(f"OK: {len(config.feeders)} feeders ({len(config.enabled_feeders())} enabled)")
    typer.echo(f"    types in use: {sorted({f.type for f in config.feeders})}")
    if unregistered:
        # A hard failure, not a warning: run_feeder() (pipeline/runner.py) now
        # raises on exactly this condition too, since a silently-unresolved
        # registry_url produces events with no calendar_id/school_division.
        # This check exists to catch it before anything ever tries to run.
        typer.secho(
            f"FAILED: {len(unregistered)} feeders reference a registry_url with no "
            f"matching `calendars` row (run import-registry first):",
            fg=typer.colors.RED,
        )
        for feeder_id, url in unregistered:
            typer.echo(f"    {feeder_id}: {url}")
        raise typer.Exit(code=1)


@app.command("run")
def run_one(
    feeder_id: str = typer.Argument(..., help="Feeder id from master.yaml"),
    config_path: str = typer.Option(None, "--config", "-c"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run a single feeder end to end and print its result."""
    _setup_logging(verbose)
    config = load_config(config_path)
    spec = config.by_id(feeder_id)
    if spec is None:
        typer.secho(f"no feeder named {feeder_id!r} in config", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    async def _run() -> None:
        async with HttpClient(
            user_agent=config.defaults.user_agent,
            timeout_seconds=config.defaults.timeout_seconds,
            retries=config.defaults.retries,
            rate_limit_per_host=config.defaults.rate_limit_per_host,
        ) as http:
            report = await run_feeder(spec, config, http)
        if report.ok:
            typer.secho(
                f"OK {report.feeder_id}: {report.records} records -> {report.events} events "
                f"({report.stats}, {report.removed} removed) in {report.duration_seconds}s",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(f"FAILED {report.feeder_id}: {report.error}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

    asyncio.run(_run())


@app.command("run-all")
def run_all_command(
    config_path: str = typer.Option(None, "--config", "-c"),
    feeder_id: list[str] = typer.Option(None, "--feeder-id", help="Restrict to these feeder ids"),
    concurrency: int = typer.Option(8, "--concurrency"),
    max_failures: int = typer.Option(
        0,
        "--max-failures",
        help=(
            "Exit 0 while at most this many feeders failed. Feeders that succeed "
            "still write their events either way -- this only controls the exit "
            "code, for scheduled runs where a couple of flaky upstream sites "
            "shouldn't mark the whole run as broken."
        ),
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Run every enabled feeder (or a chosen subset) concurrently."""
    _setup_logging(verbose)
    config = load_config(config_path)
    reports = asyncio.run(
        run_all(config, feeder_ids=feeder_id or None, max_concurrency=concurrency)
    )

    failures = 0
    for report in sorted(reports, key=lambda r: r.feeder_id):
        if report.ok:
            typer.secho(
                f"OK   {report.feeder_id}: {report.events} events ({report.stats}, "
                f"{report.removed} removed) in {report.duration_seconds}s",
                fg=typer.colors.GREEN,
            )
        else:
            failures += 1
            typer.secho(f"FAIL {report.feeder_id}: {report.error}", fg=typer.colors.RED)

    typer.echo(f"\n{len(reports)} feeders run, {failures} failed")
    if failures > max_failures:
        raise typer.Exit(code=1)
    if failures:
        typer.secho(
            f"tolerating {failures} failure(s) (--max-failures {max_failures})",
            fg=typer.colors.YELLOW,
        )


@app.command("upcoming")
def upcoming(limit: int = typer.Option(20, "--limit", "-n")) -> None:
    """Print the next N active events -- a quick sanity check after a run."""
    with session_scope() as session:
        events = EventRepository(session).upcoming(limit)
    if not events:
        typer.echo("no upcoming events")
        return
    for event in events:
        typer.echo(f"{event.starts_at:%Y-%m-%d %H:%M} {event.event_name!r} @ {event.location} [{', '.join(event.tags)}]")


@app.command("probe")
def probe(
    url: str = typer.Argument(..., help="A calendar's base URL to probe for known feed patterns"),
) -> None:
    """Test common feed/API patterns against one URL and report what responds.

    A cheap first pass for the long-tail registry rows: not a replacement for
    reading calendar_source_types.md, but enough to tell you which feeder `type`
    to try first.
    """

    async def _probe() -> None:
        base = url.rstrip("/")
        candidates = {
            "ics": f"{base}/ics",
            "ics_query": f"{base}?ical=1",
            "tec_rest": f"{base}/wp-json/tribe/events/v1/events?per_page=1",
            "wp_types": f"{base}/wp-json/wp/v2/types",
            "livewhale_json": f"{base}?format=json",
            "rss": f"{base}/rss.xml",
        }
        async with HttpClient(user_agent="PennEventsBot/1.0 (+probe)", retries=1) as http:
            for label, candidate_url in candidates.items():
                try:
                    response = await http.get(candidate_url)
                    content_type = response.headers.get("content-type", "")
                    typer.echo(f"{label:16} {response.status_code:4} {content_type:40} {candidate_url}")
                except PennEventsError as exc:
                    typer.echo(f"{label:16} FAIL {exc}")

    asyncio.run(_probe())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
