import { useMemo, useState } from "react";
import { FiltersBar } from "../components/list/FiltersBar";
import { TagRow } from "../components/list/TagRow";
import { EventRow } from "../components/list/EventRow";
import { EmptyState } from "../components/list/EmptyState";
import { LoadingState } from "../components/common/LoadingState";
import { ErrorState } from "../components/common/ErrorState";
import { useAllActiveEvents } from "../hooks/useAllActiveEvents";
import { DEFAULT_FILTERS, applyFilters, type ListFilters } from "../lib/filterEvents";
import { toDateKey } from "../lib/datetime";
import type { CategoryKey } from "../lib/category";

export function ListPage() {
  const { events, loading, error } = useAllActiveEvents();
  const [filters, setFilters] = useState<ListFilters>(DEFAULT_FILTERS);
  const todayKey = useMemo(() => toDateKey(new Date()), []);

  const rows = useMemo(
    () => applyFilters(events, filters, todayKey),
    [events, filters, todayKey]
  );

  const hasActiveFilters =
    filters.search !== "" ||
    filters.tags.length > 0 ||
    filters.category !== "all" ||
    filters.dateFilter !== "all";

  function toggleTag(tag: string) {
    setFilters((f) => ({
      ...f,
      tags: f.tags.includes(tag) ? f.tags.filter((t) => t !== tag) : [...f.tags, tag],
    }));
  }

  function clearFilters() {
    setFilters(DEFAULT_FILTERS);
  }

  return (
    <>
      <FiltersBar
        search={filters.search}
        onSearchChange={(search) => setFilters((f) => ({ ...f, search }))}
        category={filters.category}
        onCategoryChange={(category: CategoryKey | "all") =>
          setFilters((f) => ({ ...f, category }))
        }
        dateFilter={filters.dateFilter}
        onDateFilterChange={(dateFilter) => setFilters((f) => ({ ...f, dateFilter }))}
        sort={filters.sort}
        onSortChange={(sort) => setFilters((f) => ({ ...f, sort }))}
      />
      <TagRow
        activeTags={filters.tags}
        onToggleTag={toggleTag}
        hasActiveFilters={hasActiveFilters}
        onClearFilters={clearFilters}
      />

      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} />}
      {!loading && !error && (
        <>
          <div className="results-meta">
            {rows.length} {rows.length === 1 ? "event found" : "events found"}
          </div>
          <div className="results-list">
            {rows.map((event) => (
              <EventRow event={event} key={event.id} />
            ))}
            {rows.length === 0 && <EmptyState onClearFilters={clearFilters} />}
          </div>
        </>
      )}
    </>
  );
}
