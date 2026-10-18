type Props = {
  value?: string | null;
  /** Display text; defaults to a plain label of value. */
  label?: string;
};

function toneClass(raw: string) {
  const v = raw.trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (!v) return 'is-neutral';
  if (['active', 'posted', 'paid', 'accepted', 'approved', 'received', 'cleared', 'delivered', 'converted', 'yes', 'completed', 'ok', 'in_stock'].includes(v)) {
    return 'is-ok';
  }
  if (['draft', 'pending', 'sent', 'partial', 'partially_received', 'processing', 'confirmed', 'in_transit', 'requested', 'deposited', 'low', 'low_stock'].includes(v)) {
    return 'is-warn';
  }
  if (['inactive', 'cancelled', 'canceled', 'rejected', 'overdue', 'bounced', 'expired', 'failed', 'no', 'out', 'out_of_stock'].includes(v)) {
    return 'is-danger';
  }
  return 'is-neutral';
}

function plainLabel(value: string) {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function StatusChip({ value, label }: Props) {
  const raw = String(value || '').trim();
  if (!raw && !label) return <span className="muted">—</span>;
  const text = label || plainLabel(raw);
  return <span className={`erp-status ${toneClass(raw || text)}`}>{text}</span>;
}
