'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '../../../lib/api';
import { formatWhen } from '../../../lib/format';

/** A till receipt line with how many can still come back and the refund per unit. */
type ReturnLine = {
  product_id: string;
  variant_id: string | null;
  name?: string | null;
  sku?: string | null;
  quantity: number;
  returned_quantity: number;
  returnable_quantity: number;
  unit_refund: number;
};

type Receipt = {
  id: string;
  reference: string;
  created_at?: string | null;
  total: number;
  payment_method: string;
  customer_id?: string | null;
  customer_name?: string | null;
  lines: ReturnLine[];
  fully_returned: boolean;
};

type ReceiptRow = {
  id: string;
  reference: string;
  created_at?: string | null;
  total: number;
  customer_name?: string | null;
  item_count: number;
};

const REASONS: [string, string][] = [
  ['defective', 'Faulty'],
  ['damaged', 'Damaged'],
  ['wrong_item', 'Wrong item'],
  ['customer_change', 'Changed their mind'],
  ['other', 'Other'],
];

const REFUND_LABELS: Record<string, string> = {
  cash: 'Cash from the drawer',
  card: 'Back to card',
  mobile_money: 'Mobile Money (MoMo)',
  bank_transfer: 'Bank transfer',
  store_credit: 'Store credit',
};

function defaultRefund(receipt: Receipt): string {
  const paid = receipt.payment_method;
  if (paid in REFUND_LABELS && paid !== 'store_credit') return paid;
  return receipt.customer_id ? 'store_credit' : 'cash';
}

/**
 * Till returns: find the receipt, choose what comes back, and refund it.
 * Stock goes back on the shelf unless the item is marked as not fit to sell; a cash
 * refund comes out of the drawer and shows in the shift report.
 */
export function TillReturnPanel({
  open,
  onClose,
  money,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  money: (n: number) => string;
  onDone: (result: { message: string; session?: unknown }) => void;
}) {
  const [query, setQuery] = useState('');
  const [rows, setRows] = useState<ReceiptRow[]>([]);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [qty, setQty] = useState<Record<string, number>>({});
  const [shelf, setShelf] = useState<Record<string, boolean>>({});
  const [reason, setReason] = useState('');
  const [refund, setRefund] = useState('cash');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  // Only the newest search may fill the list (an earlier, slower one must not overwrite it).
  const searchSeq = useRef(0);

  const lineKey = (line: ReturnLine) => `${line.product_id}:${line.variant_id || ''}`;

  const search = useCallback(async (text: string) => {
    const seq = ++searchSeq.current;
    setError('');
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (text.trim()) params.set('q', text.trim());
      const r = await api(`/pos/receipts?${params.toString()}`);
      if (seq !== searchSeq.current) return [];
      const found: ReceiptRow[] = r.data || [];
      setRows(found);
      return found;
    } catch (err: unknown) {
      if (seq === searchSeq.current) setError(err instanceof Error ? err.message : 'Could not load receipts.');
      return [];
    } finally {
      if (seq === searchSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    setReceipt(null);
    setQuery('');
    setReason('');
    setError('');
    void search('');
  }, [open, search]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  async function pick(id: string) {
    setError('');
    try {
      const r = await api(`/pos/sales/${id}/returnable`);
      const data: Receipt = r.data;
      setReceipt(data);
      setQty({});
      setShelf(Object.fromEntries(data.lines.map((line) => [lineKey(line), true])));
      setReason('');
      setRefund(defaultRefund(data));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not open that receipt.');
    }
  }

  const refundTotal = useMemo(() => {
    if (!receipt) return 0;
    return receipt.lines.reduce((sum, line) => sum + (qty[lineKey(line)] || 0) * line.unit_refund, 0);
  }, [receipt, qty]);

  const chosen = receipt ? receipt.lines.filter((line) => (qty[lineKey(line)] || 0) > 0) : [];

  function bump(line: ReturnLine, delta: number) {
    const key = lineKey(line);
    setQty((prev) => {
      const next = Math.min(line.returnable_quantity, Math.max(0, (prev[key] || 0) + delta));
      return { ...prev, [key]: next };
    });
  }

  async function submit() {
    if (!receipt || busy) return;
    if (!chosen.length) {
      setError('Choose at least one item to return.');
      return;
    }
    if (!reason) {
      setError('Choose why the item is coming back.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const r = await api(`/pos/sales/${receipt.id}/returns`, {
        method: 'POST',
        body: JSON.stringify({
          items: chosen.map((line) => ({
            product_id: line.product_id,
            variant_id: line.variant_id,
            quantity: qty[lineKey(line)],
            restock: shelf[lineKey(line)] !== false,
          })),
          reason,
          refund_method: refund,
        }),
      });
      const done = r.data || {};
      const amount = Number(done.total_amount || refundTotal);
      onDone({
        message:
          refund === 'store_credit'
            ? `Return ${done.return_number} saved. ${money(amount)} added to the customer's store credit.`
            : `Return ${done.return_number} saved. Refund ${money(amount)} — ${REFUND_LABELS[refund] || refund}.`,
        session: done.session,
      });
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'The return could not be saved.');
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;

  return (
    <div
      className="pos-shift-panel is-open"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="pos-shift-panel-card pos-return-card" role="dialog" aria-modal aria-label="Till return">
        <div className="pos-shift-panel-head">
          <h2>{receipt ? `Return from ${receipt.reference}` : 'Return an item'}</h2>
          <button type="button" className="tpos-btn" aria-label="Close till return" onClick={onClose}>
            Close
          </button>
        </div>

        {!receipt ? (
          <>
            <form
              className="pos-return-find"
              onSubmit={(e) => {
                e.preventDefault();
                void search(query).then((found) => {
                  // A full receipt number finds one sale: open it straight away.
                  if (query.trim() && found.length === 1) void pick(found[0].id);
                });
              }}
            >
              <input
                className="tpos-input"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Receipt number, e.g. POS20260061"
                aria-label="Find receipt"
                autoFocus
              />
              <button type="submit" className="tpos-btn tpos-btn-primary" aria-label="Find receipt number">
                Find
              </button>
            </form>
            <p className="muted pos-return-hint">The receipt number is printed at the top of the receipt. Recent sales:</p>
            <ul className="pos-return-list">
              {loading && rows.length === 0 ? <li className="muted">Loading receipts…</li> : null}
              {!loading && rows.length === 0 ? <li className="muted">No till receipts match.</li> : null}
              {rows.map((row) => (
                <li key={row.id}>
                  <button type="button" className="pos-return-row" onClick={() => void pick(row.id)} aria-label={`Open receipt ${row.reference}`}>
                    <span>
                      <strong>{row.reference}</strong>
                      <small>
                        {row.created_at ? formatWhen(row.created_at) : ''}
                        {row.customer_name ? ` · ${row.customer_name}` : ''} · {row.item_count}{' '}
                        {row.item_count === 1 ? 'item' : 'items'}
                      </small>
                    </span>
                    <strong>{money(Number(row.total || 0))}</strong>
                  </button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <p className="muted pos-return-hint">
              {receipt.created_at ? `${formatWhen(receipt.created_at)} · ` : ''}
              {receipt.customer_name || 'Walk-in'} · paid {money(receipt.total)}{' '}
              <button type="button" className="pos-return-back" onClick={() => setReceipt(null)} aria-label="Choose another receipt">
                Choose another receipt
              </button>
            </p>
            {receipt.fully_returned ? (
              <p className="tpos-banner tpos-banner-err">Everything on this receipt has already been returned.</p>
            ) : null}
            <ul className="pos-return-lines">
              {receipt.lines.map((line) => {
                const key = lineKey(line);
                const n = qty[key] || 0;
                const none = line.returnable_quantity <= 0;
                return (
                  <li key={key} className={n > 0 ? 'is-chosen' : ''}>
                    <div className="pos-return-line-name">
                      <strong>{line.name || 'Item'}</strong>
                      <small>
                        Bought {line.quantity}
                        {line.returned_quantity > 0 ? ` · ${line.returned_quantity} already returned` : ''} ·{' '}
                        {money(line.unit_refund)} each
                      </small>
                    </div>
                    <div className="tpos-qty pos-ui-qty" aria-label={`Return quantity for ${line.name || 'item'}`}>
                      <button type="button" onClick={() => bump(line, -1)} disabled={none || n <= 0} aria-label={`Return one less ${line.name || 'item'}`}>
                        −
                      </button>
                      <span className="pos-return-qty">{n}</span>
                      <button type="button" onClick={() => bump(line, 1)} disabled={none || n >= line.returnable_quantity} aria-label={`Return one more ${line.name || 'item'}`}>
                        +
                      </button>
                    </div>
                    <label className="pos-return-shelf">
                      <input
                        type="checkbox"
                        checked={shelf[key] !== false}
                        onChange={(e) => setShelf((prev) => ({ ...prev, [key]: e.target.checked }))}
                        aria-label={`Put ${line.name || 'item'} back on the shelf`}
                      />
                      Back on shelf
                    </label>
                  </li>
                );
              })}
            </ul>
            <div className="pos-return-options">
              <label className="tpos-field">
                <span>Why is it coming back?</span>
                <select value={reason} onChange={(e) => setReason(e.target.value)} aria-label="Return reason">
                  <option value="">Choose a reason</option>
                  {REASONS.map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="tpos-field">
                <span>Refund by</span>
                <select value={refund} onChange={(e) => setRefund(e.target.value)} aria-label="Refund method">
                  {Object.entries(REFUND_LABELS)
                    .filter(([value]) => value !== 'store_credit' || receipt.customer_id)
                    .map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                </select>
              </label>
            </div>
            {error ? (
              <p className="tpos-banner tpos-banner-err" role="alert">
                {error}
              </p>
            ) : null}
            <button
              type="button"
              className="tpos-btn tpos-btn-primary pos-return-submit"
              onClick={() => void submit()}
              disabled={busy || !chosen.length}
              aria-label="Refund return"
            >
              {busy ? 'Saving…' : chosen.length ? `Refund ${money(refundTotal)}` : 'Choose items to return'}
            </button>
          </>
        )}
        {!receipt && error ? (
          <p className="tpos-banner tpos-banner-err" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
