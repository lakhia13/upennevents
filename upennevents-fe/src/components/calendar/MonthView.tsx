import { toDateKey, formatHour, parseTimeToHour, WEEKDAYS } from "../../lib/datetime";
import { categoryCssVars, deriveCategory } from "../../lib/category";
import type { ApiEvent } from "../../types/event";

interface Props {
  refDate: Date;
  events: ApiEvent[];
  today: Date;
}

interface MonthCell {
  key: string;
  dayNumber: number;
  cellClass: string;
  numberClass: string;
  events: { id: string; title: string; timeLabel: string; style: Record<string, string> }[];
  overflowCount: number;
  hasOverflow: boolean;
}

function timeLabelFor(e: ApiEvent): string {
  if (e.all_day) return "All day";
  const h = parseTimeToHour(e.start_time);
  return h === null ? "" : formatHour(h);
}

function buildMonthCells(refDate: Date, events: ApiEvent[], today: Date): MonthCell[] {
  const year = refDate.getFullYear();
  const month = refDate.getMonth();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  const raw: { date: Date; inMonth: boolean }[] = [];
  for (let i = firstWeekday - 1; i >= 0; i--) {
    raw.push({ date: new Date(year, month - 1, daysInPrevMonth - i), inMonth: false });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    raw.push({ date: new Date(year, month, d), inMonth: true });
  }
  let nextDay = 1;
  while (raw.length < 42) {
    raw.push({ date: new Date(year, month + 1, nextDay), inMonth: false });
    nextDay++;
  }

  const todayKey = toDateKey(today);
  const byDate = new Map<string, ApiEvent[]>();
  for (const e of events) {
    const list = byDate.get(e.event_date);
    if (list) list.push(e);
    else byDate.set(e.event_date, [e]);
  }

  return raw.map((cell) => {
    const key = toDateKey(cell.date);
    const isToday = key === todayKey;
    const dayEvents = (byDate.get(key) ?? [])
      .slice()
      .sort((a, b) => (parseTimeToHour(a.start_time) ?? -1) - (parseTimeToHour(b.start_time) ?? -1));
    const visible = dayEvents.slice(0, 3).map((e) => ({
      id: e.id,
      title: e.event_name,
      timeLabel: timeLabelFor(e),
      style: categoryCssVars(deriveCategory(e.school_division)),
    }));
    return {
      key,
      dayNumber: cell.date.getDate(),
      cellClass:
        "day-cell" + (cell.inMonth ? "" : " day-cell-dim") + (isToday ? " day-cell-today" : ""),
      numberClass: "day-number" + (isToday ? " day-number-today" : ""),
      events: visible,
      overflowCount: dayEvents.length - visible.length,
      hasOverflow: dayEvents.length > visible.length,
    };
  });
}

export function MonthView({ refDate, events, today }: Props) {
  const cells = buildMonthCells(refDate, events, today);

  return (
    <div className="month-wrap">
      <div className="weekday-row">
        {WEEKDAYS.map((wd) => (
          <div className="weekday-cell" key={wd}>
            {wd}
          </div>
        ))}
      </div>
      <div className="month-grid">
        {cells.map((cell) => (
          <div className={cell.cellClass} key={cell.key}>
            <span className={cell.numberClass}>{cell.dayNumber}</span>
            <div className="day-events">
              {cell.events.map((ev) => (
                <div className="event-pill" style={ev.style} key={ev.id}>
                  <span className="pill-time">{ev.timeLabel}</span>
                  {ev.title}
                </div>
              ))}
              {cell.hasOverflow && (
                <div className="pill-more">+{cell.overflowCount} more</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
