export function ErrorState({ message }: { message: string }) {
  return (
    <div className="page-status page-status-error">
      Couldn't load events: {message}
    </div>
  );
}
