import { useMemo, useState } from "react";
import { CalendarToolbar, type CalendarMode } from "../components/calendar/CalendarToolbar";
import { CalendarLegend } from "../components/calendar/CalendarLegend";
import { MonthView } from "../components/calendar/MonthView";
import { WeekView } from "../components/calendar/WeekView";
import { LoadingState } from "../components/common/LoadingState";
import { ErrorState } from "../components/common/ErrorState";
import { useEventsInRange } from "../hooks/useEventsInRange";
import {
  MONTHS,
  MONTHS_SHORT,
  addDays,
  addMonths,
  monthGridRange,
  weekRange,
} from "../lib/datetime";

export function CalendarPage() {
  const today = useMemo(() => new Date(), []);
  const [mode, setMode] = useState<CalendarMode>("month");
  const [refDate, setRefDate] = useState<Date>(today);

  const [rangeStart, rangeEnd] = useMemo(
    () => (mode === "month" ? monthGridRange(refDate) : weekRange(refDate)),
    [mode, refDate]
  );
  const { events, loading, error } = useEventsInRange(rangeStart, rangeEnd);

  const headerLabel = useMemo(() => {
    if (mode === "month") {
      return `${MONTHS[refDate.getMonth()]} ${refDate.getFullYear()}`;
    }
    const weekStart = rangeStart;
    const weekEnd = addDays(rangeStart, 6);
    return `${MONTHS_SHORT[refDate.getMonth()]} ${weekStart.getDate()}–${weekEnd.getDate()}, ${refDate.getFullYear()}`;
  }, [mode, refDate, rangeStart]);

  function goPrev() {
    setRefDate((d) => (mode === "month" ? addMonths(d, -1) : addDays(d, -7)));
  }
  function goNext() {
    setRefDate((d) => (mode === "month" ? addMonths(d, 1) : addDays(d, 7)));
  }
  function goToday() {
    setRefDate(new Date(today));
  }

  return (
    <>
      <CalendarToolbar
        mode={mode}
        headerLabel={headerLabel}
        onPrev={goPrev}
        onNext={goNext}
        onToday={goToday}
        onModeChange={setMode}
      />
      {!loading && !error && <CalendarLegend events={events} />}
      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} />}
      {!loading && !error && mode === "month" && (
        <MonthView refDate={refDate} events={events} today={today} />
      )}
      {!loading && !error && mode === "week" && (
        <WeekView refDate={refDate} events={events} today={today} />
      )}
    </>
  );
}
