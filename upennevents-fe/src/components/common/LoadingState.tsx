export function LoadingState({ label = "Loading events…" }: { label?: string }) {
  return <div className="page-status">{label}</div>;
}
