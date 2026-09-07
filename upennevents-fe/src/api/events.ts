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
 * same as the approved design mockup.
 *
 * The limit must stay above the live active-event count or the List view
 * silently shows a subset: it sat at 1000 while ingestion grew to ~2250, which
 * is exactly that bug. It must also stay at or under the server's own cap
 * (PGRST_DB_MAX_ROWS locally, the max-rows setting on Supabase), since the
 * server truncates regardless of what we ask for. client.ts warns when a
 * response comes back full, which is the signal that this needs raising again
 * -- or that it's finally time to move filtering server-side. */
export async function fetchAllActiveEvents(): Promise<ApiEvent[]> {
  const params = new URLSearchParams();
  params.set("order", "starts_at.asc");
  params.set("limit", "5000");
  return fetchEvents(params);
}
