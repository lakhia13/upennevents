import { FILTER_TAGS, tagLabel } from "../../lib/filterEvents";

interface Props {
  activeTags: string[];
  onToggleTag: (tag: string) => void;
  hasActiveFilters: boolean;
  onClearFilters: () => void;
}

export function TagRow({ activeTags, onToggleTag, hasActiveFilters, onClearFilters }: Props) {
  return (
    <div className="tag-row">
      {FILTER_TAGS.map((tag) => {
        const active = activeTags.includes(tag);
        return (
          <button
            key={tag}
            className={active ? "tag-toggle tag-toggle-active" : "tag-toggle"}
            onClick={() => onToggleTag(tag)}
            aria-pressed={active}
          >
            {tagLabel(tag)}
          </button>
        );
      })}
      {hasActiveFilters && (
        <button className="clear-link" onClick={onClearFilters}>
          Clear filters
        </button>
      )}
    </div>
  );
}
