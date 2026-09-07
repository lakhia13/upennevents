export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export const MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** YYYY-MM-DD for a *local* Date -- deliberately not toISOString(), which
 * would convert through UTC and can land on the wrong calendar day. */
export function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/** Parses an America/New_York wall-clock "HH:MM:SS" column (start_time /
 * end_time) into a decimal hour, e.g. "14:30:00" -> 14.5. */
export function parseTimeToHour(t: string | null): number | null {
  if (!t) return null;
  const [h, m] = t.split(":").map(Number);
  return h + m / 60;
}

export function formatHour(h: number): string {
  const hour = Math.floor(h);
  const min = Math.round((h - hour) * 60);
  const ampm = hour >= 12 ? "PM" : "AM";
  let displayHour = hour % 12;
  if (displayHour === 0) displayHour = 12;
  return min === 0 ? `${displayHour}:00 ${ampm}` : `${displayHour}:${pad2(min)} ${ampm}`;
}

export function formatHourShort(h: number): string {
  const ampm = h >= 12 ? "PM" : "AM";
  let displayHour = h % 12;
  if (displayHour === 0) displayHour = 12;
  return `${displayHour} ${ampm}`;
}

export function startOfWeek(d: Date): Date {
  const start = new Date(d);
  start.setDate(start.getDate() - start.getDay());
  start.setHours(0, 0, 0, 0);
  return start;
}

export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

export function addDays(d: Date, days: number): Date {
  const next = new Date(d);
  next.setDate(next.getDate() + days);
  return next;
}

export function addMonths(d: Date, months: number): Date {
  const next = new Date(d);
  next.setMonth(next.getMonth() + months);
  return next;
}

/** [start, endExclusive) covering every cell the Month view's 6x7 grid can
 * show, including leading/trailing days from adjacent months. */
export function monthGridRange(refDate: Date): [Date, Date] {
  const firstOfMonth = new Date(refDate.getFullYear(), refDate.getMonth(), 1);
  const gridStart = startOfWeek(firstOfMonth);
  return [gridStart, addDays(gridStart, 42)];
}

/** [start, endExclusive) for the Week view -- Sunday through the following Sunday. */
export function weekRange(refDate: Date): [Date, Date] {
  const start = startOfWeek(refDate);
  return [start, addDays(start, 7)];
}
