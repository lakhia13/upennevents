import type { ApiEvent } from "../types/event";

// The PostgREST root. Local dev points this at the docker-compose service; in
// production it's Supabase's REST endpoint (https://<ref>.supabase.co/rest/v1),
// which is also PostgREST -- same query syntax, same api.events view.
const BASE_URL: string =
  (import.meta.env.VITE_POSTGREST_URL as string | undefined) ??
  "http://localhost:3001";

// Supabase authenticates every request with the project's anon key; a
// self-hosted PostgREST needs no key at all. Left unset locally, so one build
// serves both. The key is safe in a client bundle by design -- what actually
// protects the data is that only the `api` schema is exposed and the raw tables
// are RLS-denied (see alembic/versions/0004_rls_lockdown.py).
const ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

const AUTH_HEADERS: Record<string, string> = ANON_KEY
  ? { apikey: ANON_KEY, Authorization: `Bearer ${ANON_KEY}` }
  : {};

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
  const res = await fetch(`${BASE_URL}/events?${params.toString()}`, {
    headers: AUTH_HEADERS,
  });
  if (!res.ok) {
    throw new PostgrestError(
      res.status,
      `PostgREST request failed: ${res.status} ${res.statusText}`
    );
  }
  const rows = (await res.json()) as ApiEvent[];

  // Getting back exactly as many rows as we asked for almost always means the
  // result was capped, not that the data happened to end there. That failure is
  // silent -- the UI just quietly shows less than it should, which is exactly
  // what happened when the event count grew past a stale limit -- so say so.
  const requested = Number(params.get("limit"));
  if (requested && rows.length >= requested) {
    console.warn(
      `[api] got ${rows.length} events for a limit of ${requested} -- results ` +
        `are probably truncated. Raise the limit, and check the server's own ` +
        `max-rows cap (PGRST_DB_MAX_ROWS locally, Settings -> API on Supabase).`
    );
  }
  return rows;
}
