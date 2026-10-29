'use client';

import { useState } from 'react';
import { api } from '../lib/api';
import { openReceiptPrintWindow } from '../lib/posReceiptPrint';
import { printerPurposeLabel } from '../lib/printerPurposes';

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
      if (!opened) {
        setNote('Print failed — the sale is still saved.');
        return;
      }
      await api(`/printers/jobs/${job.id}/browser-ack`, {
        method: 'POST',
        body: JSON.stringify({ status: 'printed' }),
      });
      setRows((prev) => prev.map((j) => (j.id === job.id ? { ...j, status: 'printed' } : j)));
      setNote('The print dialog opened. This does not confirm that paper came out.');
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
    <div className="tpos-print-status print-ui-page">
      <strong>Print jobs</strong>
      <p className="print-ui-help">The print dialog does not confirm that paper came out of a printer.</p>
      {note ? <p className="muted">{note}</p> : null}
      <ul>
        {rows.map((job) => (
          <li key={job.id} className="print-ui-row">
            <span>
              {printerPurposeLabel(job.purpose)}: {jobStatusLabel(job.status)}
            </span>
            {job.payload?.browser_fallback || job.status === 'browser_pending' ? (
              <button type="button" className="btn-ok" disabled={busy} onClick={() => browserPrint(job)}>
                Print this job
              </button>
            ) : null}
          </li>
        ))}
      </ul>
      {saleId ? (
        <button type="button" className="btn-ok" disabled={busy} onClick={reprint}>
          Print again
        </button>
      ) : null}
    </div>
  );
}

function jobStatusLabel(status: string) {
  if (status === 'browser_pending') return 'Waiting for the print dialog';
  if (status === 'printed') return 'Marked printed';
  if (status === 'queued') return 'Queued';
  return status.replace(/_/g, ' ');
}
