import type { ApiEvent } from "../types/event";

const BASE_URL: string =
  (import.meta.env.VITE_POSTGREST_URL as string | undefined) ??
  "http://localhost:3001";

// Explicit column list -- keeps search_vector (large tsvector text) and the
// *_seen_at/updated_at bookkeeping columns out of every response; the UI
// doesn't use them.
const EVENT_FIELDS = [
  "id", "event_name", "host", "source", "source_calendar_name", "calendar_id",
  "starts_at", "ends_at", "all_day", "event_date", "start_time", "end_time",
  "location", "is_virtual", "event_url", "meeting_link", "description", "tags",
  "school_division",
].join(",");

export class PostgrestError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "PostgrestError";
    this.status = status;
  }
}

export async function fetchEvents(params: URLSearchParams): Promise<ApiEvent[]> {
  params.set("select", EVENT_FIELDS);
  const res = await fetch(`${BASE_URL}/events?${params.toString()}`);
  if (!res.ok) {
    throw new PostgrestError(
      res.status,
      `PostgREST request failed: ${res.status} ${res.statusText}`
    );
  }
  return (await res.json()) as ApiEvent[];
}
