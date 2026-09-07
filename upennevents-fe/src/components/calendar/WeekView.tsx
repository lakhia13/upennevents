import {
  toDateKey,
  formatHour,
  formatHourShort,
  parseTimeToHour,
  startOfWeek,
  addDays,
  WEEKDAYS,
} from "../../lib/datetime";
import { categoryCssVars, deriveCategory } from "../../lib/category";
import type { ApiEvent } from "../../types/event";

const ROW_H = 56;
const START_HOUR = 8;
const HOURS = Array.from({ length: 13 }, (_, i) => START_HOUR + i); // 8am - 8pm labels
const GRID_HEIGHT = HOURS.length * ROW_H;

interface Props {
  refDate: Date;
  events: ApiEvent[];
  today: Date;
}

interface WeekBlock {
  id: string;
  title: string;
  timeLabel: string;
  top: number;
  height: number;
  catStyle: Record<string, string>;
}

interface WeekColumn {
  key: string;
  weekdayLabel: string;
  dayNumber: number;
  headerClass: string;
  blocks: WeekBlock[];
}

function buildWeekColumns(refDate: Date, events: ApiEvent[], today: Date): WeekColumn[] {
  const start = startOfWeek(refDate);
  const todayKey = toDateKey(today);

  const byDate = new Map<string, ApiEvent[]>();
  for (const e of events) {
    if (e.all_day) continue; // all-day events aren't shown on the timed week grid
    const list = byDate.get(e.event_date);
    if (list) list.push(e);
    else byDate.set(e.event_date, [e]);
  }

  const columns: WeekColumn[] = [];
  for (let i = 0; i < 7; i++) {
    const date = addDays(start, i);
    const key = toDateKey(date);
    const isToday = key === todayKey;
    const dayEvents = byDate.get(key) ?? [];

    const blocks: WeekBlock[] = dayEvents.map((e) => {
      const startHour = parseTimeToHour(e.start_time) ?? START_HOUR;
      const endHourRaw = parseTimeToHour(e.end_time);
      const endHour = endHourRaw !== null && endHourRaw > startHour ? endHourRaw : startHour + 1;

      const rawTop = (startHour - START_HOUR) * ROW_H;
      const top = Math.min(Math.max(rawTop, 0), GRID_HEIGHT);
      const rawHeight = Math.max((endHour - startHour) * ROW_H, 30);
      const height = Math.min(rawHeight, GRID_HEIGHT - top);

      return {
        id: e.id,
        title: e.event_name,
        timeLabel:
          endHourRaw !== null
            ? `${formatHour(startHour)} – ${formatHour(endHour)}`
            : formatHour(startHour),
        top,
        height,
        catStyle: categoryCssVars(deriveCategory(e.school_division)),
      };
    });

    columns.push({
      key,
      weekdayLabel: WEEKDAYS[i],
      dayNumber: date.getDate(),
      headerClass: "week-day-header" + (isToday ? " week-day-header-today" : ""),
      blocks,
    });
  }
  return columns;
}

export function WeekView({ refDate, events, today }: Props) {
  const columns = buildWeekColumns(refDate, events, today);

  return (
    <div className="week-wrap">
      <div className="week-header-row">
        <div className="time-gutter-spacer" />
        {columns.map((col) => (
          <div className={col.headerClass} key={col.key}>
            <div className="wd-label">{col.weekdayLabel}</div>
            <div className="wd-number">{col.dayNumber}</div>
          </div>
        ))}
      </div>
      <div className="week-body">
        <div className="time-gutter">
          {HOURS.map((h) => (
            <div className="hour-label" key={h}>
              {formatHourShort(h)}
            </div>
          ))}
        </div>
        <div className="week-columns">
          {columns.map((col) => (
            <div className="week-day-col" key={col.key}>
              {col.blocks.map((blk) => (
                <div
                  className="week-event"
                  key={blk.id}
                  style={{ top: `${blk.top}px`, height: `${blk.height}px`, ...blk.catStyle }}
                >
                  <div className="week-event-title">{blk.title}</div>
                  <div className="week-event-time">{blk.timeLabel}</div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
