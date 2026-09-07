import { useMemo } from "react";
import { CATEGORY_ORDER, categoryCssVars, deriveCategory, type CategoryKey } from "../../lib/category";
import type { ApiEvent } from "../../types/event";

interface Props {
  events: ApiEvent[];
}

/** Shows only the schools/divisions actually present in the events currently
 * on screen -- with 16 possible categories (see lib/category.ts), always
 * showing the full list would be mostly-unused clutter at today's ingestion
 * coverage. The School filter dropdown (FiltersBar) shows the full official
 * list regardless, since that's a catalog of what you *can* filter by. */
export function CalendarLegend({ events }: Props) {
  const present = useMemo(() => {
    const keys = new Set<CategoryKey>(events.map((e) => deriveCategory(e.school_division)));
    return CATEGORY_ORDER.filter((c) => keys.has(c.key));
  }, [events]);

  if (present.length === 0) return null;

  return (
    <div className="legend">
      {present.map((c) => (
        <span className="legend-item" key={c.key}>
          <span className="legend-dot" style={categoryCssVars(c.key)} />
          {c.shortLabel}
        </span>
      ))}
    </div>
  );
}
