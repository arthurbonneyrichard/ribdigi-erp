'use client';

import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { hydrateDeviceId } from '../lib/posOffline';

type Choice = { id: string; name: string; connection_type: string; purposes: string[]; is_enabled: boolean };

/** Which receipt printer this computer uses, and whether it prints straight after payment. */
export default function TillPrinterSettings({ printers }: { printers: Choice[] }) {
  const [terminal, setTerminal] = useState('');
  const [name, setName] = useState('');
  const [printerId, setPrinterId] = useState('');
  const [auto, setAuto] = useState(true);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const id = await hydrateDeviceId();
        const res = await api(`/printers/terminals/${encodeURIComponent(id)}`);
        if (!live) return;
        setTerminal(id);
        setName(res.data?.name || '');
        setPrinterId(res.data?.receipt_printer_id || '');
        setAuto(res.data?.auto_print !== false);
      } catch (err) {
        if (!live) return;
        setFailed(true);
        setNote((err as Error).message || 'Could not load this till’s printer setting.');
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const receipt = printers.filter((p) => p.is_enabled && (p.purposes || []).includes('customer_receipt'));
  const direct = receipt.filter((p) => p.connection_type !== 'browser_dialog');

  async function save() {
    setBusy(true);
    setNote('');
    try {
      await api(`/printers/terminals/${encodeURIComponent(terminal)}`, {
        method: 'PUT',
        body: JSON.stringify({ name: name.trim() || null, receipt_printer_id: printerId || null, auto_print: auto }),
      });
      setFailed(false);
      setNote('Saved for this till.');
    } catch (err) {
      setFailed(true);
      setNote((err as Error).message || 'Could not save.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2 style={{ marginTop: 0 }}>Automatic receipt printing on this till</h2>
      <p className="muted">
        After a payment, the receipt goes straight to a network printer or a paired till agent, with no print window.
        A printer added by its browser name cannot print by itself.
      </p>
      {direct.length === 0 ? (
        <p className="erp-banner err">
          No printer can print automatically yet. Add a network printer or a paired till agent under Printers in use.
        </p>
      ) : null}
      <div className="print-ui-form">
        <label>
          Till name
          <input value={name} maxLength={80} onChange={(e) => setName(e.target.value)} aria-label="This till name" placeholder="Front counter" />
        </label>
        <label>
          Receipt printer for this till
          <select value={printerId} onChange={(e) => setPrinterId(e.target.value)} aria-label="This till receipt printer">
            <option value="">All receipt printers for the store</option>
            {direct.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </label>
      </div>
      <label className="print-switch">
        <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} aria-label="Print receipts automatically on this till" />
        <span>Print the receipt automatically after payment</span>
      </label>
      <div className="print-actions">
        <button type="button" className="btn-ok" disabled={busy || !terminal} onClick={() => void save()} aria-label="Save this till printer">
          Save for this till
        </button>
      </div>
      {note ? <p className={failed ? 'erp-banner err' : 'erp-banner ok'} role="status">{note}</p> : null}
    </div>
  );
}
