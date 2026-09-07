import { useEffect, useState } from "react";
import { fetchEventsInRange } from "../api/events";
import type { ApiEvent } from "../types/event";

export interface AsyncEvents {
  events: ApiEvent[];
  loading: boolean;
  error: string | null;
}

/** Refetches whenever the [start, endExclusive) range changes -- used by the
 * calendar Month/Week views as the user navigates periods. */
export function useEventsInRange(start: Date, endExclusive: Date): AsyncEvents {
  const [state, setState] = useState<AsyncEvents>({
    events: [],
    loading: true,
    error: null,
  });

  const startKey = start.toISOString();
  const endKey = endExclusive.toISOString();

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));

    fetchEventsInRange(start, endExclusive)
      .then((events) => {
        if (!cancelled) setState({ events, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({
            events: [],
            loading: false,
            error: err instanceof Error ? err.message : "Failed to load events.",
          });
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startKey, endKey]);

  return state;
}
