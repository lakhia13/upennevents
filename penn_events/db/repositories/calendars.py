"""Reads and writes for table 1, the source registry."""
from __future__ import annotations

import csv
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from penn_events.db.models import Calendar

from .base import Repository

log = logging.getLogger(__name__)

# CSV header -> column name.  Order and spelling follow penn-calendars.csv exactly.
CSV_COLUMN_MAP = {
    "Unit": "unit",
    "School / Division": "school_division",
    "Category": "category",
    "Calendar name": "calendar_name",
    "Calendar URL": "calendar_url",
    "Platform / CMS": "platform_cms",
    "How content is rendered": "how_content_is_rendered",
    "Feed / API endpoint": "feed_api_endpoint",
    "Best way to fetch it programmatically": "best_fetch_method",
    "Confidence": "confidence",
    "Notes": "notes",
}


class CalendarRepository(Repository):
    def get_by_url(self, calendar_url: str) -> Calendar | None:
        return self.session.scalar(select(Calendar).where(Calendar.calendar_url == calendar_url))

    def get(self, calendar_id: UUID) -> Calendar | None:
        return self.session.get(Calendar, calendar_id)

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(Calendar)) or 0

    def all_urls(self) -> set[str]:
        return set(self.session.scalars(select(Calendar.calendar_url)))

    def list_all(self) -> list[Calendar]:
        return list(self.session.scalars(select(Calendar).order_by(Calendar.calendar_name)))

    def import_csv(self, path: str | Path) -> tuple[int, int]:
        """Load penn-calendars.csv, upserting on `calendar_url`.

        Idempotent: re-running against an unchanged file leaves the row count alone.
        Returns (rows_seen, rows_written).
        """
        csv_path = Path(path)
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = set(CSV_COLUMN_MAP) - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"{csv_path} is missing expected columns: {sorted(missing)}")

            rows = []
            for raw_row in reader:
                row = {
                    column: (raw_row.get(header) or "").strip() or None
                    for header, column in CSV_COLUMN_MAP.items()
                }
                if not row["calendar_url"]:
                    log.warning("skipping registry row with no Calendar URL: %r", row["unit"])
                    continue
                rows.append(row)

        if not rows:
            return 0, 0

        statement = insert(Calendar).values(rows)
        updatable = [c for c in CSV_COLUMN_MAP.values() if c != "calendar_url"]
        statement = statement.on_conflict_do_update(
            index_elements=[Calendar.calendar_url],
            set_={
                **{column: statement.excluded[column] for column in updatable},
                "updated_at": func.now(),
            },
        ).returning(Calendar.id)

        written = len(list(self.session.scalars(statement)))
        log.info("registry import: %d rows read, %d rows written", len(rows), written)
        return len(rows), written
