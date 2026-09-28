'use client';

import { useCallback, useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Printer = {
  id: string;
  name: string;
  connection_type: string;
  store_id: string | null;
  paper: string;
  purposes: string[];
  copies: number;
  is_enabled: boolean;
  is_default: boolean;
  host: string | null;
  port: number | null;
  status: string;
};

const PURPOSES = ['customer_receipt', 'invoice', 'kitchen', 'bar', 'barcode'];

export default function PrinterSettingsPage() {
  const [rows, setRows] = useState<Printer[]>([]);
  const [stores, setStores] = useState<{ id: string; name: string }[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [pairing, setPairing] = useState('');
  const [form, setForm] = useState({
    name: '',
    connection_type: 'browser_dialog',
    store_id: '',
    paper: '80mm',
    purposes: ['customer_receipt'] as string[],
    copies: 1,
    host: '',
    port: 9100,
  });

  const load = useCallback(async () => {
    try {
      const [printers, storeRes] = await Promise.all([
        api('/printers'),
        api('/stores').catch(() => ({ data: [] })),
      ]);
      setRows(printers.data || []);
      setStores(storeRes.data || []);
      setError('');
    } catch (err: any) {
      setError(err?.message || 'Unable to load printers');
    }
  }, []);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  function togglePurpose(purpose: string) {
    setForm((prev) => ({
      ...prev,
      purposes: prev.purposes.includes(purpose)
        ? prev.purposes.filter((p) => p !== purpose)
        : [...prev.purposes, purpose],
    }));
  }

  async function createPrinter() {
    setBusy(true);
    setError('');
    try {
      await api('/printers', {
        method: 'POST',
        body: JSON.stringify({
          name: form.name,
          connection_type: form.connection_type,
          store_id: form.store_id || null,
          paper: form.paper,
          purposes: form.purposes,
          copies: form.copies,
          host: form.connection_type === 'network' ? form.host : null,
          port: form.connection_type === 'network' ? form.port : 9100,
        }),
      });
      setForm((f) => ({ ...f, name: '', host: '' }));
      await load();
    } catch (err: any) {
      setError(err?.message || 'Save failed');
    } finally {
      setBusy(false);
    }
  }

  async function patchPrinter(id: string, body: Record<string, unknown>) {
    setBusy(true);
    try {
      await api(`/printers/${id}`, { method: 'PATCH', body: JSON.stringify(body) });
      await load();
    } catch (err: any) {
      setError(err?.message || 'Update failed');
    } finally {
      setBusy(false);
    }
  }

  async function testPrint(id: string) {
    setBusy(true);
    try {
      const r = await api(`/printers/${id}/test`, { method: 'POST', body: '{}' });
      setError(
        r.data?.status === 'printed'
          ? 'Test printed'
          : `Test queued as ${r.data?.status || 'queued'} (queued is not printed)`
      );
    } catch (err: any) {
      setError(err?.message || 'Test print failed');
    } finally {
      setBusy(false);
    }
  }

  async function issuePairing() {
    setBusy(true);
    try {
      const r = await api('/printers/agents/pairing-codes', {
        method: 'POST',
        body: JSON.stringify({ label: form.name || 'Till agent', store_id: form.store_id || null }),
      });
      setPairing(r.data?.pairing_code || '');
    } catch (err: any) {
      setError(err?.message || 'Pairing failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell>
      <h1>Printer settings</h1>
      <p className="muted">
        The browser cannot list every OS printer or send to all of them silently. Use the OS print
        dialog as fallback, pair a till print agent (desktop or Android), or register a private
        network printer. Checkout still completes if a printer is offline. Receipt numbers come from
        the server.
      </p>
      {error ? <p className="muted" style={{ color: 'var(--danger)' }}>{error}</p> : null}
      {pairing ? (
        <div className="card" style={{ marginBottom: 16 }}>
          <strong>Pairing code (shown once):</strong> <code>{pairing}</code>
          <p className="muted">Enter this on the till agent within 15 minutes. Do not put tokens in the repo.</p>
        </div>
      ) : null}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Add printer</h2>
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))' }}>
          <label>
            Friendly name
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label>
            Connection
            <select
              value={form.connection_type}
              onChange={(e) => setForm({ ...form, connection_type: e.target.value })}
            >
              <option value="browser_dialog">Browser print dialog</option>
              <option value="print_agent">Paired till agent</option>
              <option value="network">Network (allowlisted private IP)</option>
            </select>
          </label>
          <label>
            Store
            <select value={form.store_id} onChange={(e) => setForm({ ...form, store_id: e.target.value })}>
              <option value="">All stores</option>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Paper
            <select value={form.paper} onChange={(e) => setForm({ ...form, paper: e.target.value })}>
              <option value="80mm">80mm</option>
              <option value="58mm">58mm</option>
              <option value="a4">A4 invoice</option>
            </select>
          </label>
          <label>
            Copies
            <input
              type="number"
              min={1}
              max={9}
              value={form.copies}
              onChange={(e) => setForm({ ...form, copies: Number(e.target.value) || 1 })}
            />
          </label>
          {form.connection_type === 'network' ? (
            <>
              <label>
                Host (private IP or .local)
                <input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
              </label>
              <label>
                Port
                <input
                  type="number"
                  value={form.port}
                  onChange={(e) => setForm({ ...form, port: Number(e.target.value) || 9100 })}
                />
              </label>
            </>
          ) : null}
        </div>
        <div style={{ marginTop: 12 }}>
          {PURPOSES.map((p) => (
            <label key={p} style={{ marginRight: 12 }}>
              <input
                type="checkbox"
                checked={form.purposes.includes(p)}
                onChange={() => togglePurpose(p)}
              />{' '}
              {p.replace('_', ' ')}
            </label>
          ))}
        </div>
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" disabled={busy || !form.name} onClick={createPrinter}>
            Save printer
          </button>
          <button type="button" disabled={busy} onClick={issuePairing}>
            Issue till pairing code
          </button>
        </div>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Connection</th>
            <th>Paper</th>
            <th>Purposes</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.name}</td>
              <td>{row.connection_type}</td>
              <td>{row.paper}</td>
              <td>{(row.purposes || []).join(', ')}</td>
              <td>
                {row.status} {row.is_enabled ? '' : '(disabled)'}
              </td>
              <td>
                <button type="button" disabled={busy} onClick={() => testPrint(row.id)}>
                  Test
                </button>{' '}
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => patchPrinter(row.id, { is_enabled: !row.is_enabled })}
                >
                  {row.is_enabled ? 'Disable' : 'Enable'}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
