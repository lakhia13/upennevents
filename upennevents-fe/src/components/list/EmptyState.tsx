export function EmptyState({ onClearFilters }: { onClearFilters: () => void }) {
  return (
    <div className="empty-state">
      <div className="empty-title">No events match your filters</div>
      <div className="empty-sub">Try clearing a filter or searching a different term.</div>
      <button className="clear-btn" onClick={onClearFilters}>
        Clear all filters
      </button>
    </div>
  );
}
