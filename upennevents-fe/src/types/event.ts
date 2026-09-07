/** Mirrors the columns exposed by the `api.events` PostgREST view (see
 * alembic/versions/0002_api_schema.py). Internal columns (raw, dedupe_key,
 * content_hash, source_uid, status) are never selected, so they don't appear here.
 */
export interface ApiEvent {
  id: string;
  event_name: string;
  host: string | null;
  source: string;
  source_calendar_name: string | null;
  calendar_id: string | null;
  starts_at: string; // ISO timestamptz
  ends_at: string | null; // ISO timestamptz
  all_day: boolean;
  /** America/New_York calendar date, e.g. "2026-09-10" -- always use this
   * (not starts_at) for day-bucketing, since starts_at is UTC and reading
   * Date getters on it uses the browser's local timezone instead of Penn's. */
  event_date: string;
  /** America/New_York wall-clock time, e.g. "14:30:00", or null for all-day events. */
  start_time: string | null;
  end_time: string | null;
  location: string | null;
  is_virtual: boolean;
  event_url: string | null;
  meeting_link: string | null;
  description: string | null;
  tags: string[];
  /** From calendars.school_division (see alembic/versions/0003_events_school_division.py)
   * -- the registry's own school/division label, e.g. "Engineering", "Vet",
   * "University Life". Null only if the event has no calendar_id. */
  school_division: string | null;
}
