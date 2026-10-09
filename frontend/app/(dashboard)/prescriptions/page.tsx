'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import FormModal from '../../../components/FormModal';
import { api, apiRoot, getAccessToken } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { normalizeIndustry } from '../../../lib/industries';

type RxProduct = {
  id: string;
  name: string;
  sku?: string | null;
  dosage_instructions?: string | null;
  rx_only?: boolean;
};

type PrescriptionItem = {
  id?: string;
  product_id: string;
  product_name?: string | null;
  quantity: number;
  qty_dispensed?: number;
  qty_remaining?: number;
  dosage_text?: string | null;
};

type Attachment = {
  id: string;
  original_filename?: string | null;
  content_type?: string | null;
};

type Prescription = {
  id: string;
  rx_number: string;
  customer_id?: string | null;
  customer_name?: string | null;
  sale_id?: string | null;
  sale_number?: string | null;
  prescriber_name?: string | null;
  notes?: string | null;
  status: string;
  created_at?: string | null;
  items: PrescriptionItem[];
  attachments?: Attachment[];
};

type Customer = { id: string; name: string; status?: string };
type BatchHold = {
  id: string;
  batch_id?: string;
  batch_number?: string | null;
  product_name?: string | null;
  hold_type: string;
  status: string;
  reason?: string | null;
};

type LotRow = {
  id: string;
  batch_number?: string | null;
  product_id?: string;
  quantity?: number;
  expiry_date?: string | null;
};

const NEXT: Record<string, { status: string; label: string }[]> = {
  received: [
    { status: 'review', label: 'Send to review' },
    { status: 'approved', label: 'Approve' },
    { status: 'cancelled', label: 'Cancel' },
  ],
  review: [
    { status: 'approved', label: 'Approve' },
    { status: 'cancelled', label: 'Cancel' },
  ],
  approved: [{ status: 'cancelled', label: 'Cancel' }],
  partially_dispensed: [{ status: 'cancelled', label: 'Cancel remaining' }],
};

export default function PrescriptionsPage() {
  const searchParams = useSearchParams();
  const statusFilter = (searchParams.get('status') || '').trim();
  const holdParam = (searchParams.get('holds') || '').trim().toLowerCase();
  const holdKind = holdParam === 'quarantine' || holdParam === 'recall' ? holdParam : '';
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [canWrite, setCanWrite] = useState(false);
  const [rows, setRows] = useState<Prescription[]>([]);
  const [rxProducts, setRxProducts] = useState<RxProduct[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<RxProduct[]>([]);
  const [holds, setHolds] = useState<BatchHold[]>([]);
  const [lots, setLots] = useState<LotRow[]>([]);
  const [holdForm, setHoldForm] = useState({ batch_id: '', hold_type: 'quarantine', reason: '' });
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [selected, setSelected] = useState<Prescription | null>(null);
  const [dispenseQty, setDispenseQty] = useState('1');
  const [form, setForm] = useState({
    customer_id: '',
    prescriber_name: '',
    notes: '',
    product_id: '',
    quantity: '1',
    dosage_text: '',
  });

  const visibleRows = useMemo(() => {
    if (!statusFilter) return rows;
    if (statusFilter === 'review') {
      return rows.filter((row) => row.status === 'review' || row.status === 'received');
    }
    return rows.filter((row) => row.status === statusFilter);
  }, [rows, statusFilter]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const row of rows) c[row.status] = (c[row.status] || 0) + 1;
    return c;
  }, [rows]);

  const visibleHolds = useMemo(() => {
    if (!holdKind) return holds;
    return holds.filter((row) => row.hold_type === holdKind);
  }, [holds, holdKind]);

  useEffect(() => {
    if (!holdKind || allowed !== true) return;
    document.getElementById('lot-holds')?.scrollIntoView({ block: 'start' });
  }, [holdKind, allowed, holds.length]);

  async function refresh() {
    const [list, rx, cust, catalog, holdRes, lotRes] = await Promise.all([
      api('/pharmacy/prescriptions'),
      api('/pharmacy/rx-products'),
      api('/customers').catch(() => ({ data: [] })),
      api('/products?is_active=true').catch(() => ({ data: [] })),
      api('/pharmacy/batch-holds').catch(() => ({ data: [] })),
      api('/inventory/batches').catch(() => ({ data: [] })),
    ]);
    const nextRows = Array.isArray(list.data) ? list.data : [];
    setRows(nextRows);
    setRxProducts(Array.isArray(rx.data) ? rx.data : []);
    const custList = Array.isArray(cust.data) ? cust.data : [];
    setCustomers(custList.filter((c: Customer) => (c.status || 'active') === 'active'));
    setProducts(Array.isArray(catalog.data) ? catalog.data : []);
    setHolds(Array.isArray(holdRes.data) ? holdRes.data : []);
    setLots(Array.isArray(lotRes.data) ? lotRes.data : []);
    setSelected((cur) => (cur ? nextRows.find((r: Prescription) => r.id === cur.id) || cur : null));
  }

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const me = await getMe();
        const industry = normalizeIndustry(me.data?.industry);
        if (!active) return;
        if (industry !== 'pharmacy') {
          setAllowed(false);
          setError('Prescriptions are only available for pharmacy tenants.');
          return;
        }
        const perms = me.data?.permissions || {};
        const inv = perms['*'] || perms.inventory || [];
        const writable = inv.includes('*') || inv.includes('write');
        setCanWrite(writable);
        if (writable && searchParams.get('new') === '1') setAddOpen(true);
        setAllowed(true);
        await refresh();
      } catch (err: unknown) {
        if (active) setError(err instanceof Error ? err.message : 'Failed to load prescriptions');
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  async function createRx(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !canWrite) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const product = products.find((p) => p.id === form.product_id);
      await api('/pharmacy/prescriptions', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: form.customer_id.trim() || null,
          prescriber_name: form.prescriber_name.trim() || null,
          notes: form.notes.trim() || null,
          items: [
            {
              product_id: form.product_id,
              quantity: Number(form.quantity) || 1,
              dosage_text: form.dosage_text.trim() || product?.dosage_instructions || null,
            },
          ],
        }),
      });
      setMessage('Prescription received');
      setAddOpen(false);
      setForm({
        customer_id: '',
        prescriber_name: '',
        notes: '',
        product_id: '',
        quantity: '1',
        dosage_text: '',
      });
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not record prescription');
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(id: string, status: string) {
    if (busy || !canWrite) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/pharmacy/prescriptions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      });
      setMessage(`Prescription ${status}`);
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not update prescription');
    } finally {
      setBusy(false);
    }
  }

  async function dispenseSelected() {
    if (!selected || busy || !canWrite) return;
    const line = (selected.items || [])[0];
    if (!line) return;
    const qty = Number(dispenseQty) || 0;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/pharmacy/prescriptions/${selected.id}/dispense`, {
        method: 'POST',
        body: JSON.stringify({
          items: [{ product_id: line.product_id, quantity: qty }],
        }),
      });
      setMessage('Dispense recorded and stock reduced');
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not dispense');
    } finally {
      setBusy(false);
    }
  }

  async function placeHold(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !canWrite) return;
    const reason = holdForm.reason.trim();
    if (!holdForm.batch_id || !reason) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/pharmacy/batch-holds', {
        method: 'POST',
        body: JSON.stringify({
          batch_id: holdForm.batch_id,
          hold_type: holdForm.hold_type,
          reason,
        }),
      });
      setMessage(holdForm.hold_type === 'recall' ? 'Lot recalled' : 'Lot quarantined');
      setHoldForm({ batch_id: '', hold_type: 'quarantine', reason: '' });
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not hold lot');
    } finally {
      setBusy(false);
    }
  }

  async function releaseHold(id: string) {
    if (busy || !canWrite) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api(`/pharmacy/batch-holds/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'released' }),
      });
      setMessage('Lot hold released');
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not release lot hold');
    } finally {
      setBusy(false);
    }
  }

  async function uploadRxFile(file: File | null) {
    if (!selected || !file || busy || !canWrite) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const token = getAccessToken();
      const tenant = typeof window !== 'undefined' ? localStorage.getItem('tenant') : null;
      const apiBase = apiRoot();
      const body = new FormData();
      body.append('file', file);
      const res = await fetch(`${apiBase}/pharmacy/prescriptions/${selected.id}/attachments`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body,
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.detail?.message || payload.message || 'Upload failed');
      }
      setMessage('Attachment saved');
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not upload');
    } finally {
      setBusy(false);
    }
  }

  if (allowed === false) {
    return (
      <>
        <h1>Prescriptions</h1>
        <p className="muted">{error || 'Not available for this business type.'}</p>
        <p>
          <Link href="/dashboard">Back to dashboard</Link>
        </p>
      </>
    );
  }

  const canDispense =
    selected && (selected.status === 'approved' || selected.status === 'partially_dispensed');

  return (
    <>
      <h1>Prescriptions</h1>
      <p className="muted">
        Counter prescription lifecycle: receive, pharmacist approve, then partial or full dispense
        (stock uses FEFO). This is not a hospital, clinic, or HIS module. POS can fill an approved
        Rx against Rx-only products.
      </p>
      {error ? <p style={{ color: '#b91c1c' }}>{error}</p> : null}
      {message ? <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p> : null}

      <section className="card" style={{ marginBottom: 16 }}>
        <h2 style={{ marginTop: 0 }}>Queue</h2>
        <p className="muted">
          Received {counts.received || 0} · Review {counts.review || 0} · Approved {counts.approved || 0}{' '}
          · Partial {counts.partially_dispensed || 0} · Dispensed {counts.dispensed || 0}
        </p>
      </section>

      <section className="card" style={{ marginBottom: 16 }}>
        <h2 style={{ marginTop: 0 }}>Rx-only products</h2>
        <p className="muted">
          Dosage lives on the product. Open{' '}
          <Link href="/inventory?tab=products&rx=1">Rx-only catalog</Link> to edit.
        </p>
        {rxProducts.length === 0 ? (
          <p className="muted">No Rx-only products yet. Mark a product as Rx-only in inventory.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Dosage instructions</th>
              </tr>
            </thead>
            <tbody>
              {rxProducts.map((p) => (
                <tr key={p.id}>
                  <td>{p.name}</td>
                  <td>{p.sku || '—'}</td>
                  <td>{p.dosage_instructions || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        {canWrite ? (
          <button
            type="button"
            className="list-btn-primary"
            onClick={() => {
              setAddOpen(true);
              setError('');
            }}
          >
            Receive prescription
          </button>
        ) : (
          <p className="muted">You can view prescriptions. Recording requires inventory write.</p>
        )}
      </div>

      {visibleRows.length === 0 ? (
        <p className="muted">
          {statusFilter ? 'No prescriptions in this queue.' : 'No prescriptions recorded yet.'}
        </p>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Rx number</th>
              <th>Customer</th>
              <th>Sale</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr key={row.id}>
                <td>{row.rx_number}</td>
                <td>{row.customer_name || '—'}</td>
                <td>{row.sale_number || '—'}</td>
                <td>{row.status}</td>
                <td>
                  <button type="button" onClick={() => setSelected(row)}>
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <section className="card" id="lot-holds" style={{ marginTop: 16 }}>
        <h2 style={{ marginTop: 0 }}>
          {holdKind === 'quarantine' ? 'Quarantine holds' : holdKind === 'recall' ? 'Recall holds' : 'Lot holds'}
        </h2>
        <p className="muted">
          Quarantine or recall a lot so POS FEFO will not sell it. Release the hold here, or from
          Inventory → Batches, when the lot is cleared.
        </p>
        {canWrite ? (
          <form onSubmit={placeHold} className="erp-form-grid" style={{ marginBottom: 12 }}>
            <label className="muted">
              Lot
              <select
                value={holdForm.batch_id}
                onChange={(e) => setHoldForm((f) => ({ ...f, batch_id: e.target.value }))}
                aria-label="Lot to hold"
                required
              >
                <option value="">Select lot</option>
                {lots.map((lot) => (
                  <option key={lot.id} value={lot.id}>
                    {lot.batch_number || lot.id}
                    {lot.expiry_date ? ` · ${String(lot.expiry_date).slice(0, 10)}` : ''}
                  </option>
                ))}
              </select>
            </label>
            <label className="muted">
              Hold type
              <select
                value={holdForm.hold_type}
                onChange={(e) => setHoldForm((f) => ({ ...f, hold_type: e.target.value }))}
                aria-label="Lot hold type"
              >
                <option value="quarantine">Quarantine</option>
                <option value="recall">Recall</option>
              </select>
            </label>
            <label className="muted span-2">
              Reason
              <input
                value={holdForm.reason}
                onChange={(e) => setHoldForm((f) => ({ ...f, reason: e.target.value }))}
                aria-label="Lot hold reason"
                required
              />
            </label>
            <button type="submit" className="btn-danger" disabled={busy || !holdForm.batch_id}>
              {busy ? 'Saving…' : 'Place lot hold'}
            </button>
          </form>
        ) : null}
        {visibleHolds.length === 0 ? (
          <p className="muted">{holdKind ? `No open ${holdKind} holds.` : 'No open lot holds.'}</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Lot</th>
                <th>Product</th>
                <th>Type</th>
                <th>Reason</th>
                {canWrite ? <th></th> : null}
              </tr>
            </thead>
            <tbody>
              {visibleHolds.map((h) => (
                <tr key={h.id}>
                  <td>{h.batch_number || h.batch_id || h.id}</td>
                  <td>{h.product_name || '—'}</td>
                  <td>{h.hold_type}</td>
                  <td>{h.reason || '—'}</td>
                  {canWrite ? (
                    <td>
                      <button
                        type="button"
                        className="btn-ok"
                        onClick={() => releaseHold(h.id)}
                        disabled={busy}
                        aria-label={`Release lot hold ${h.batch_number || h.id}`}
                      >
                        Release
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {addOpen ? (
        <FormModal
          title="Receive prescription"
          onClose={() => setAddOpen(false)}
          closeLabel="Cancel"
        >
          <form onSubmit={createRx} className="erp-form-grid">
            <label className="muted span-2">
              Customer (optional)
              <select
                value={form.customer_id}
                onChange={(e) => setForm((f) => ({ ...f, customer_id: e.target.value }))}
                aria-label="Prescription customer"
              >
                <option value="">Walk-in / not linked</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="muted span-2">
              Prescriber name (optional)
              <input
                value={form.prescriber_name}
                onChange={(e) => setForm((f) => ({ ...f, prescriber_name: e.target.value }))}
                aria-label="Prescriber name"
              />
            </label>
            <label className="muted span-2">
              Product
              <select
                required
                value={form.product_id}
                onChange={(e) => {
                  const product_id = e.target.value;
                  const product = products.find((p) => p.id === product_id);
                  setForm((f) => ({
                    ...f,
                    product_id,
                    dosage_text: product?.dosage_instructions || f.dosage_text,
                  }));
                }}
                aria-label="Prescription product"
              >
                <option value="">Select product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.rx_only ? ' (Rx)' : ''}
                  </option>
                ))}
              </select>
            </label>
            <label className="muted">
              Quantity
              <input
                type="number"
                min="0.001"
                step="0.001"
                value={form.quantity}
                onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))}
                aria-label="Prescription quantity"
                required
              />
            </label>
            <label className="muted span-2">
              Dosage instructions
              <textarea
                value={form.dosage_text}
                onChange={(e) => setForm((f) => ({ ...f, dosage_text: e.target.value }))}
                rows={2}
                aria-label="Prescription dosage instructions"
              />
            </label>
            <label className="muted span-2">
              Notes
              <textarea
                value={form.notes}
                onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                rows={2}
                aria-label="Prescription notes"
              />
            </label>
            <button type="submit" className="list-btn-primary" disabled={busy || !form.product_id}>
              {busy ? 'Saving…' : 'Save'}
            </button>
          </form>
        </FormModal>
      ) : null}

      {selected ? (
        <FormModal title={selected.rx_number} onClose={() => setSelected(null)} closeLabel="Close">
          <p className="muted">Status: {selected.status}</p>
          <p className="muted">Customer: {selected.customer_name || '—'}</p>
          <p className="muted">Sale: {selected.sale_number || selected.sale_id || '—'}</p>
          <p className="muted">Prescriber: {selected.prescriber_name || '—'}</p>
          <ul>
            {(selected.items || []).map((item, i) => (
              <li key={item.id || i}>
                {item.product_name || item.product_id} × {item.quantity}
                {item.qty_dispensed != null ? ` (dispensed ${item.qty_dispensed})` : ''}
                {item.dosage_text ? ` — ${item.dosage_text}` : ''}
              </li>
            ))}
          </ul>
          {canWrite ? (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
              {(NEXT[selected.status] || []).map((action) => (
                <button
                  key={action.status}
                  type="button"
                  onClick={() => setStatus(selected.id, action.status)}
                  disabled={busy}
                >
                  {action.label}
                </button>
              ))}
            </div>
          ) : null}
          {canWrite && canDispense ? (
            <div style={{ marginTop: 12 }}>
              <label className="muted">
                Dispense quantity
                <input
                  type="number"
                  min="0.001"
                  step="0.001"
                  value={dispenseQty}
                  onChange={(e) => setDispenseQty(e.target.value)}
                  aria-label="Dispense quantity"
                />
              </label>
              <button type="button" onClick={dispenseSelected} disabled={busy} style={{ marginLeft: 8 }}>
                Dispense (reduces stock)
              </button>
              <p className="muted">Or complete the fill at POS with this Rx selected.</p>
            </div>
          ) : null}
          {canWrite ? (
            <label className="muted" style={{ display: 'block', marginTop: 12 }}>
              Attach scan (PDF or image)
              <input
                type="file"
                accept="application/pdf,image/*"
                aria-label="Prescription attachment"
                onChange={(e) => uploadRxFile(e.target.files?.[0] || null)}
              />
            </label>
          ) : null}
          {(selected.attachments || []).length ? (
            <ul>
              {selected.attachments!.map((a) => (
                <li key={a.id}>{a.original_filename || a.id}</li>
              ))}
            </ul>
          ) : null}
        </FormModal>
      ) : null}
    </>
  );
}
