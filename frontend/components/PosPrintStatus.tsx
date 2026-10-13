'use client';

import { useState } from 'react';
import { api } from '../lib/api';
import { openReceiptPrintWindow } from '../lib/posReceiptPrint';

type PrintJob = {
  id: string;
  purpose: string;
  status: string;
  payload?: { text?: string; html?: string; browser_fallback?: boolean };
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
    const html = job.payload?.html;
    const text = job.payload?.text || '';
    setBusy(true);
    try {
      const opened = openReceiptPrintWindow(html, text);
      if (!opened) window.print();
      await api(`/printers/jobs/${job.id}/browser-ack`, {
        method: 'POST',
        body: JSON.stringify({ status: 'printed' }),
      });
      setRows((prev) => prev.map((j) => (j.id === job.id ? { ...j, status: 'printed' } : j)));
      setNote('Printed from this browser.');
    } catch (err: any) {
      setNote(err?.message || 'Print failed — the sale is still saved.');
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
      setNote('Reprint sent. Sale was not created again.');
    } catch (err: any) {
      setNote(err?.message || 'Reprint failed — the sale is still saved.');
    } finally {
      setBusy(false);
    }
  }

  if (!rows.length) {
    return (
      <p className="muted tpos-print-note">
        Sale saved. Print from the receipt buttons if a printer did not fire.
      </p>
    );
  }

  return (
    <div className="tpos-print-status">
      <strong>Printers</strong>
      {note ? <p className="muted">{note}</p> : null}
      <ul>
        {rows.map((job) => (
          <li key={job.id}>
            {job.purpose}: <strong>{job.status}</strong>{' '}
            {job.payload?.browser_fallback || job.status === 'browser_pending' ? (
              <button type="button" className="tpos-btn" disabled={busy} onClick={() => browserPrint(job)}>
                Print here
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {saleId ? (
        <button type="button" className="tpos-btn" disabled={busy} onClick={reprint}>
          Reprint
        </button>
      ) : null}
    </div>
  );
}
