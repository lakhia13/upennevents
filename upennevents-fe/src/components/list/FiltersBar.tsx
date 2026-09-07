import { CATEGORY_ORDER, type CategoryKey } from "../../lib/category";
import type { DateFilter, SortMode } from "../../lib/filterEvents";

interface Props {
  search: string;
  onSearchChange: (value: string) => void;
  category: CategoryKey | "all";
  onCategoryChange: (value: CategoryKey | "all") => void;
  dateFilter: DateFilter;
  onDateFilterChange: (value: DateFilter) => void;
  sort: SortMode;
  onSortChange: (value: SortMode) => void;
}

export function FiltersBar({
  search,
  onSearchChange,
  category,
  onCategoryChange,
  dateFilter,
  onDateFilterChange,
  sort,
  onSortChange,
}: Props) {
  return (
    <div className="filters-bar">
      <div className="search-wrap">
        <svg viewBox="0 0 20 20">
          <circle cx="9" cy="9" r="6" strokeWidth="2" />
          <path d="M14 14l4 4" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <label className="visually-hidden" htmlFor="event-search">
          Search events
        </label>
        <input
          id="event-search"
          className="search-input"
          type="text"
          placeholder="Search events, hosts, locations…"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
      </div>

      <label className="visually-hidden" htmlFor="school-select">
        Filter by school
      </label>
      <select
        id="school-select"
        className="select-input"
        value={category}
        onChange={(e) => onCategoryChange(e.target.value as CategoryKey | "all")}
      >
        <option value="all">All Schools</option>
        {CATEGORY_ORDER.map((c) => (
          <option value={c.key} key={c.key}>
            {c.label}
          </option>
        ))}
      </select>

      <div className="segmented" role="group" aria-label="Date range">
        <button
          className={dateFilter === "all" ? "seg-btn seg-btn-active" : "seg-btn"}
          onClick={() => onDateFilterChange("all")}
          aria-pressed={dateFilter === "all"}
        >
          All Upcoming
        </button>
        <button
          className={dateFilter === "week" ? "seg-btn seg-btn-active" : "seg-btn"}
          onClick={() => onDateFilterChange("week")}
          aria-pressed={dateFilter === "week"}
        >
          This Week
        </button>
        <button
          className={dateFilter === "month" ? "seg-btn seg-btn-active" : "seg-btn"}
          onClick={() => onDateFilterChange("month")}
          aria-pressed={dateFilter === "month"}
        >
          This Month
        </button>
      </div>

      <label className="visually-hidden" htmlFor="sort-select">
        Sort events
      </label>
      <select
        id="sort-select"
        className="select-input"
        value={sort}
        onChange={(e) => onSortChange(e.target.value as SortMode)}
      >
        <option value="soonest">Date: Soonest</option>
        <option value="latest">Date: Latest</option>
        <option value="az">Title: A–Z</option>
      </select>
    </div>
  );
}
