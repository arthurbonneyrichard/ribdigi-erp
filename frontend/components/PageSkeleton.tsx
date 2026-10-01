/** Immediate destination chrome while a dashboard page chunk or data is loading. */

export default function PageSkeleton({
  label = 'Loading…',
  cards = 3,
}: {
  label?: string;
  cards?: number;
}) {
  const n = Math.max(1, Math.min(6, cards));
  return (
    <div className="page-skeleton" role="status" aria-live="polite" aria-busy="true">
      <div className="page-skeleton-progress" />
      <p className="muted page-skeleton-label">{label}</p>
      <div className="page-skeleton-title" />
      <div className="page-skeleton-line" />
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="page-skeleton-card" />
      ))}
    </div>
  );
}
