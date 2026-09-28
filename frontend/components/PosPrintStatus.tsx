'use client';

import { useState } from 'react';
import { api } from '../lib/api';

type PrintJob = {
  id: string;
  purpose: string;
  status: string;
  payload?: { text?: string; browser_fallback?: boolean };
};

export default function PosPrintStatus({
  jobs,
  saleId,
}: {
  jobs: PrintJob[];
  saleId?: string;
}) {
  const [rows, setRows] = useState<PrintJob[]>(jobs || []);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');

  async function browserPrint(job: PrintJob) {
    const text = job.payload?.text || '';
    setBusy(true);
    try {
      const frame = window.open('', '_blank', 'noopener,noreferrer,width=480,height=640');
      if (frame) {
        frame.document.write(`<pre style="font-family:monospace;white-space:pre-wrap">${text.replace(/</g, '&lt;')}</pre>`);
        frame.document.close();
        frame.focus();
        frame.print();
      } else {
        window.print();
      }
      await api(`/printers/jobs/${job.id}/browser-ack`, {
        method: 'POST',
        body: JSON.stringify({ status: 'printed' }),
      });
      setRows((prev) => prev.map((j) => (j.id === job.id ? { ...j, status: 'printed' } : j)));
      setNote('Browser print acknowledged. Queued was not printed until this ack.');
    } catch (err: any) {
      setNote(err?.message || 'Print ack failed');
    } finally {
      setBusy(false);
    }
  }

  async function reprint() {
    if (!saleId) return;
    setBusy(true);
    try {
      const r = await api('/printers/reprint', {
        method: 'POST',
        body: JSON.stringify({ source_type: 'pos_sale', source_id: saleId }),
      });
      setRows(r.data || []);
      setNote('Reprint queued for the same sale. No new sale was created.');
    } catch (err: any) {
      setNote(err?.message || 'Reprint failed');
    } finally {
      setBusy(false);
    }
  }

  if (!rows.length) {
    return (
      <p className="muted">
        No printer jobs yet. The sale is already saved. Use the OS print dialog on the receipt, or
        configure printers under Settings → Printers.
      </p>
    );
  }

  return (
    <div className="card">
      <h3>Print queue</h3>
      <p className="muted">
        A queued ticket is not printed. Retry reprints the same sale. The browser cannot discover
        every OS printer.
      </p>
      {note ? <p className="muted">{note}</p> : null}
      <ul>
        {rows.map((job) => (
          <li key={job.id}>
            {job.purpose}: <strong>{job.status}</strong>{' '}
            {job.payload?.browser_fallback || job.status === 'browser_pending' ? (
              <button type="button" disabled={busy} onClick={() => browserPrint(job)}>
                Open print dialog
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {saleId ? (
        <button type="button" disabled={busy} onClick={reprint}>
          Reprint (same sale)
        </button>
      ) : null}
    </div>
  );
}
