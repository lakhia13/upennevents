import { useEffect, useState } from "react";
import { fetchAllActiveEvents } from "../api/events";
import type { ApiEvent } from "../types/event";
import type { AsyncEvents } from "./useEventsInRange";

/** Fetches the full active event set once on mount -- used by the List view,
 * which then filters/sorts client-side. */
export function useAllActiveEvents(): AsyncEvents {
  const [state, setState] = useState<AsyncEvents>({
    events: [],
    loading: true,
    error: null,
  });

  useEffect(() => {
    let cancelled = false;
    fetchAllActiveEvents()
      .then((events: ApiEvent[]) => {
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
  }, []);

  return state;
}
