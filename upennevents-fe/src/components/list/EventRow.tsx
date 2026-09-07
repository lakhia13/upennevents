import { formatHour, parseTimeToHour, MONTHS_SHORT, WEEKDAYS } from "../../lib/datetime";
import { categoryCssVars, categoryShortLabel, deriveCategory } from "../../lib/category";
import { tagLabel } from "../../lib/filterEvents";
import type { ApiEvent } from "../../types/event";

function timeLabel(e: ApiEvent): string {
  if (e.all_day) return "All day";
  const start = parseTimeToHour(e.start_time);
  if (start === null) return "";
  const end = parseTimeToHour(e.end_time);
  return end !== null && end > start ? `${formatHour(start)} – ${formatHour(end)}` : formatHour(start);
}

function sourceDomain(source: string): string {
  const idx = source.indexOf(":");
  return idx === -1 ? source : source.slice(idx + 1);
}

export function EventRow({ event }: { event: ApiEvent }) {
  const [year, month, day] = event.event_date.split("-").map(Number);
  const localDate = new Date(year, month - 1, day);
  const category = deriveCategory(event.school_division);
  const catStyle = categoryCssVars(category);
  const visibleTags = event.tags.slice(0, 5);

  return (
    <div className="event-row">
      <div className="row-date" style={catStyle}>
        <div className="row-weekday">{WEEKDAYS[localDate.getDay()]}</div>
        <div className="row-day">{day}</div>
        <div className="row-month">{MONTHS_SHORT[month - 1]}</div>
      </div>
      <div className="row-main">
        <div className="row-title-line">
          <span className="row-title">{event.event_name}</span>
          {event.is_virtual && <span className="badge-virtual">Virtual</span>}
        </div>
        <div className="row-meta">
          <span className="meta-item">{timeLabel(event)}</span>
          {event.host && (
            <>
              <span className="meta-sep">·</span>
              <span className="meta-item">{event.host}</span>
            </>
          )}
          {(event.is_virtual || event.location) && (
            <>
              <span className="meta-sep">·</span>
              <span className="meta-item">
                <svg viewBox="0 0 20 20">
                  <path
                    d="M10 18s6-5.2 6-9.5A6 6 0 004 8.5C4 12.8 10 18 10 18z"
                    strokeWidth="1.6"
                  />
                  <circle cx="10" cy="8.3" r="2" strokeWidth="1.6" />
                </svg>
                {event.is_virtual ? "Virtual" : event.location}
              </span>
            </>
          )}
        </div>
        <div className="row-tags">
          <span className="cat-chip" style={catStyle}>{categoryShortLabel(category)}</span>
          {visibleTags.map((tag) => (
            <span className="tag-chip" key={tag}>
              {tagLabel(tag)}
            </span>
          ))}
        </div>
      </div>
      <div className="row-action">
        <span className="row-source">{sourceDomain(event.source)}</span>
        {event.event_url && (
          <a href={event.event_url} target="_blank" rel="noopener noreferrer" aria-label="Open event page">
            <svg viewBox="0 0 20 20">
              <path d="M8 4h8v8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M16 4L8 12" strokeWidth="1.8" strokeLinecap="round" />
              <path d="M14 12v4H4V6h4" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </a>
        )}
      </div>
    </div>
  );
}
