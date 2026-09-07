export type CalendarMode = "month" | "week";

interface Props {
  mode: CalendarMode;
  headerLabel: string;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
  onModeChange: (mode: CalendarMode) => void;
}

export function CalendarToolbar({
  mode,
  headerLabel,
  onPrev,
  onNext,
  onToday,
  onModeChange,
}: Props) {
  const isMonth = mode === "month";

  return (
    <div className="toolbar">
      <div className="toolbar-left">
        <button className="icon-btn" onClick={onPrev} aria-label="Previous period">
          <svg viewBox="0 0 20 20">
            <path
              d="M12.5 4.5L7 10l5.5 5.5"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <button className="icon-btn" onClick={onNext} aria-label="Next period">
          <svg viewBox="0 0 20 20">
            <path
              d="M7.5 4.5L13 10l-5.5 5.5"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <button className="today-btn" onClick={onToday}>
          Today
        </button>
        <h1 className="period-label">{headerLabel}</h1>
      </div>
      <div className="toolbar-right">
        <div className="segmented" role="group" aria-label="Calendar view">
          <button
            className={isMonth ? "seg-btn seg-btn-active" : "seg-btn"}
            onClick={() => onModeChange("month")}
            aria-pressed={isMonth}
          >
            Month
          </button>
          <button
            className={!isMonth ? "seg-btn seg-btn-active" : "seg-btn"}
            onClick={() => onModeChange("week")}
            aria-pressed={!isMonth}
          >
            Week
          </button>
        </div>
      </div>
    </div>
  );
}
