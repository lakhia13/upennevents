import type { ApiEvent } from "../types/event";
import { deriveCategory, type CategoryKey } from "./category";

export type DateFilter = "all" | "week" | "month";
export type SortMode = "soonest" | "latest" | "az";

export interface ListFilters {
  search: string;
  tags: string[];
  category: CategoryKey | "all";
  dateFilter: DateFilter;
  sort: SortMode;
}

export const DEFAULT_FILTERS: ListFilters = {
  search: "",
  tags: [],
  category: "all",
  dateFilter: "all",
  sort: "soonest",
};

// A curated, human-useful subset of the real tag vocabulary (see the
// `deriveCategory` comment in lib/category.ts for the same rationale) --
// picked from what ingestion actually produces today rather than the fixed
// demo list in the original design mockup.
export const FILTER_TAGS = [
  "seminar",
  "colloquium",
  "workshop",
  "lecture",
  "performance",
  "exhibition",
  "conference",
  "fair",
  "graduate",
  "undergraduate",
  "alumni",
  "faculty",
];

export function tagLabel(tag: string): string {
  return tag
    .split("-")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function matchesSearch(e: ApiEvent, term: string): boolean {
  if (!term) return true;
  const t = term.toLowerCase();
  return (
    e.event_name.toLowerCase().includes(t) ||
    (e.host ?? "").toLowerCase().includes(t) ||
    (e.location ?? "").toLowerCase().includes(t)
  );
}

function matchesTags(e: ApiEvent, activeTags: string[]): boolean {
  if (activeTags.length === 0) return true;
  const tagSet = new Set(e.tags.map((t) => t.toLowerCase()));
  return activeTags.some((tag) => tagSet.has(tag));
}

function matchesCategory(e: ApiEvent, category: CategoryKey | "all"): boolean {
  if (category === "all") return true;
  return deriveCategory(e.school_division) === category;
}

function daysUntil(dateKey: string, todayKey: string): number {
  const a = new Date(`${dateKey}T00:00:00`).getTime();
  const b = new Date(`${todayKey}T00:00:00`).getTime();
  return Math.round((a - b) / 86400000);
}

function matchesDate(e: ApiEvent, dateFilter: DateFilter, todayKey: string): boolean {
  const diff = daysUntil(e.event_date, todayKey);
  if (dateFilter === "week") return diff >= 0 && diff < 7;
  if (dateFilter === "month") return diff >= 0 && diff < 31;
  return diff >= 0; // "all" means "all upcoming", matching the button's label
}

function sortKey(e: ApiEvent): string {
  return `${e.event_date}T${e.start_time ?? "00:00:00"}`;
}

function sortEvents(list: ApiEvent[], mode: SortMode): ApiEvent[] {
  const copy = list.slice();
  if (mode === "soonest") copy.sort((a, b) => sortKey(a).localeCompare(sortKey(b)));
  else if (mode === "latest") copy.sort((a, b) => sortKey(b).localeCompare(sortKey(a)));
  else if (mode === "az") copy.sort((a, b) => a.event_name.localeCompare(b.event_name));
  return copy;
}

export function applyFilters(
  events: ApiEvent[],
  filters: ListFilters,
  todayKey: string
): ApiEvent[] {
  const filtered = events.filter(
    (e) =>
      matchesSearch(e, filters.search) &&
      matchesTags(e, filters.tags) &&
      matchesCategory(e, filters.category) &&
      matchesDate(e, filters.dateFilter, todayKey)
  );
  return sortEvents(filtered, filters.sort);
}
