import { fetchEvents } from "./client";
import { toDateKey } from "../lib/datetime";
import type { ApiEvent } from "../types/event";

/** All events with event_date in [start, endExclusive), ordered by start time.
 * Used by the Month and Week calendar views. */
export async function fetchEventsInRange(
  start: Date,
  endExclusive: Date
): Promise<ApiEvent[]> {
  const params = new URLSearchParams();
  params.append("event_date", `gte.${toDateKey(start)}`);
  params.append("event_date", `lt.${toDateKey(endExclusive)}`);
  params.set("order", "starts_at.asc");
  params.set("limit", "500");
  return fetchEvents(params);
}

/** The full active event set, for the List view -- search/tag/school/date/sort
 * filtering all happens client-side against this (see lib/filterEvents.ts),
 * same as the approved design mockup. Fine at today's data volume (~150
 * active events); if ingestion coverage grows well past PGRST_DB_MAX_ROWS,
 * this is the place to move filtering server-side. */
export async function fetchAllActiveEvents(): Promise<ApiEvent[]> {
  const params = new URLSearchParams();
  params.set("order", "starts_at.asc");
  params.set("limit", "1000");
  return fetchEvents(params);
}
