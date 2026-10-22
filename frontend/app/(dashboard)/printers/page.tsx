'use client';

import { useCallback, useEffect, useState } from 'react';
import FormModal from '../../../components/FormModal';
import PageHeader from '../../../components/PageHeader';
import { api } from '../../../lib/api';
import { openReceiptPrintWindow } from '../../../lib/posReceiptPrint';
import { industryLabel } from '../../../lib/industries';
import { getMe } from '../../../lib/meCache';
import {
  filterListedPrinterPurposes,
  printerPurposeLabel,
  printerPurposesForIndustry,
  printerRowVisible,
  resolvePrinterPurposes,
} from '../../../lib/printerPurposes';
import { hideStoreUx as shouldHideStoreUx } from '../../../lib/tenantNav';

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

type PrintAgentRow = {
  id: string;
  label: string;
  paired: boolean;
  is_active: boolean;
};

export default function PrinterSettingsPage() {
  const [rows, setRows] = useState<Printer[]>([]);
  const [stores, setStores] = useState<{ id: string; name: string }[]>([]);
  const [hideStoreUx, setHideStoreUx] = useState(false);
  const [industry, setIndustry] = useState<string | null>(null);
  const [purposeOptions, setPurposeOptions] = useState<string[]>(() => printerPurposesForIndustry(null));
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [printerAddOpen, setPrinterAddOpen] = useState(false);
  const [pairing, setPairing] = useState('');
  const [installedName, setInstalledName] = useState('');
  const [installedPaper, setInstalledPaper] = useState('80mm');
  const [showEmailSms, setShowEmailSms] = useState(false);
  const [agents, setAgents] = useState<PrintAgentRow[]>([]);
  const [form, setForm] = useState({
    name: '',
    connection_type: 'browser_dialog',
    store_id: '',
    paper: '80mm',
    purposes: ['customer_receipt'] as string[],
    copies: 1,
    host: '',
    port: 9100,
    agent_id: '',
  });

  const load = useCallback(async () => {
    try {
      const [caps, printers, storeRes, me, emailSms, agentRes] = await Promise.all([
        api('/printers/capabilities').catch(() => ({ data: null })),
        api('/printers'),
        api('/stores').catch(() => ({ data: [] })),
        getMe().catch(() => ({ data: {} })),
        api('/printers/receipt-email-sms').catch(() => ({ data: { show_email_sms: false } })),
        api('/printers/agents').catch(() => ({ data: [] })),
      ]);
      setAgents(Array.isArray(agentRes.data) ? agentRes.data : []);
      setShowEmailSms(emailSms.data?.show_email_sms === true);
      const savedIndustry = (me.data?.industry as string | null | undefined) || null;
      const options = resolvePrinterPurposes(savedIndustry, caps.data?.purposes || null);
      setIndustry(savedIndustry);
      setPurposeOptions(options);
      setRows(
        (printers.data || []).filter((row: Printer) => printerRowVisible(row.purposes, options))
      );
      setHideStoreUx(shouldHideStoreUx(me.data));
      setStores(storeRes.data || []);
      setForm((prev) => {
        const next = prev.purposes.filter((p) => options.includes(p));
        return { ...prev, purposes: next.length ? next : ['customer_receipt'] };
      });
      setError('');
    } catch (err: any) {
      setNotice('');
      setError(err?.message || 'Unable to load printers');
    }
  }, []);

  function connectionLabel(kind: string) {
    if (kind === 'browser_dialog') return 'This computer';
    if (kind === 'print_agent') return 'Till agent';
    if (kind === 'network') return 'Network';
    return kind;
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  function togglePurpose(purpose: string) {
    if (!purposeOptions.includes(purpose)) return;
    setForm((prev) => ({
      ...prev,
      purposes: prev.purposes.includes(purpose)
        ? prev.purposes.filter((p) => p !== purpose)
        : [...prev.purposes, purpose],
    }));
  }

  function seeInstalledPrinters() {
    setError('');
    const opened = openReceiptPrintWindow(
      '<!doctype html><html><head><meta charset="utf-8"/><title>Installed printers</title></head><body>' +
        '<p style="font-family:sans-serif">This dialog lists the printers installed on this computer. ' +
        'Pick one to confirm the name, then close the dialog and type that name on the Printers page.</p>' +
        '</body></html>',
      ''
    );
    if (!opened) {
      setNotice('');
      setError('The print dialog could not open. Try again.');
    }
  }

  async function addInstalledPrinter() {
    const name = installedName.trim();
    if (!name || busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const hasDefault = rows.some(
        (row) => row.is_enabled && row.is_default && (row.purposes || []).includes('customer_receipt')
      );
      await api('/printers', {
        method: 'POST',
        body: JSON.stringify({
          name,
          connection_type: 'browser_dialog',
          paper: installedPaper === '58mm' || installedPaper === 'a4' ? installedPaper : '80mm',
          purposes: ['customer_receipt'],
          copies: 1,
          is_default: !hasDefault,
        }),
      });
      setInstalledName('');
      setNotice(`${name} is linked for POS receipts.`);
      await load();
    } catch (err: any) {
      setNotice('');
      setError(err?.message || 'Could not add that printer');
    } finally {
      setBusy(false);
    }
  }

  async function saveEmailSms(next: boolean) {
    setShowEmailSms(next);
    try {
      await api('/printers/receipt-email-sms', {
        method: 'PATCH',
        body: JSON.stringify({ show_email_sms: next }),
      });
    } catch (err: any) {
      setShowEmailSms(!next);
      setNotice('');
      setError(err?.message || 'Could not save the Email and SMS option');
    }
  }

  async function createPrinter() {
    if (busy) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const name = form.name.trim();
      const host = form.host.trim();
      const agentId = form.agent_id.trim();
      if (!name) {
        setError('Enter a printer name.');
        return;
      }
      if (form.connection_type === 'network' && !host) {
        setError('Enter the network printer host.');
        return;
      }
      if (form.connection_type === 'print_agent' && !agentId) {
        setError('Choose a paired till agent. Issue a pairing code and enter it on the till first.');
        return;
      }
      const body: Record<string, unknown> = {
        name,
        connection_type: form.connection_type,
        store_id: form.store_id.trim() || null,
        paper: form.paper === '58mm' || form.paper === 'a4' ? form.paper : '80mm',
        purposes: form.purposes.filter((p) => purposeOptions.includes(p)),
        copies: Math.min(9, Math.max(1, Number(form.copies) || 1)),
      };
      if (form.connection_type === 'network') {
        body.host = host;
        body.port = Number(form.port) || 9100;
      }
      if (form.connection_type === 'print_agent') body.agent_id = agentId;
      await api('/printers', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setForm((f) => ({ ...f, name: '', host: '', agent_id: '' }));
      setPrinterAddOpen(false);
      setNotice('Printer saved.');
      await load();
    } catch (err: any) {
      setNotice('');
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
      setNotice('');
      setError(err?.message || 'Update failed');
    } finally {
      setBusy(false);
    }
  }

  async function deletePrinter(row: Printer) {
    if (busy) return;
    if (!window.confirm(`Delete printer ${row.name}?`)) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await api(`/printers/${row.id}`, { method: 'DELETE' });
      setNotice('Printer deleted.');
      await load();
    } catch (err: any) {
      setNotice('');
      setError(err?.message || 'Could not delete printer');
    } finally {
      setBusy(false);
    }
  }

  async function testPrint(id: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const r = await api(`/printers/${id}/test`, { method: 'POST', body: '{}' });
      const job = r.data || {};
      if (job.status === 'browser_pending' && job.id) {
        const payload = job.payload || {};
        const opened = openReceiptPrintWindow(payload.html, payload.text || '');
        if (!opened) {
          setError('The print dialog could not open. Try again.');
          return;
        }
        await api(`/printers/jobs/${job.id}/browser-ack`, {
          method: 'POST',
          body: JSON.stringify({ status: 'printed' }),
        });
        setNotice('The print dialog opened. Choose the printer there. This does not confirm that paper came out.');
        await load();
        return;
      }
      if (job.status === 'printed') {
        setNotice('The server sent the test to the printer. This does not confirm that paper came out.');
        await load();
        return;
      }
      setNotice(
        `Test queued (${job.status || 'queued'}). Queued is not printed. This does not confirm that paper came out.`
      );
      await load();
    } catch (err: any) {
      setNotice('');
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
        body: JSON.stringify({
          label: form.name.trim() || 'Till agent',
          store_id: form.store_id.trim() || null,
        }),
      });
      setPairing(r.data?.pairing_code || '');
      setNotice('Enter this code on the till agent within 15 minutes, then refresh and choose that agent.');
      await load();
    } catch (err: any) {
      setNotice('');
      setError(err?.message || 'Pairing failed');
    } finally {
      setBusy(false);
    }
  }

  const linked = rows.filter((row) => row.is_enabled);
  return (
    <div className="work print-ui-page">
      <PageHeader
        title="Printers"
        subtitle={`Link a printer in three steps. The size next to Pay only changes the browser receipt. A paired till agent uses the paper size stored on that printer.${industry ? ` Set up for ${industryLabel(industry)}.` : ''}`}
      />
      {error ? <p className="erp-banner err">{error}</p> : null}
      {notice ? <p className="erp-banner ok">{notice}</p> : null}
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Link a printer for the till</h2>
        <ol className="print-steps">
          <li className="print-step">
            <b>1</b>
            <div>
              <h3>See the printers on this computer</h3>
              <p className="muted">
                This browser cannot list every printer. The print dialog shows the names Windows or this
                device offers. Read the name, then close the dialog.
              </p>
              <div className="print-actions">
                <button type="button" className="list-btn-primary" onClick={seeInstalledPrinters} aria-label="See installed printers">
                  See installed printers
                </button>
              </div>
            </div>
          </li>
          <li className="print-step">
            <b>2</b>
            <div>
              <h3>Type the name you saw</h3>
              <p className="muted">Use the same spelling as the print dialog. Step 3 stores that name and a paper size on the printer. The size next to Pay only changes the browser receipt.</p>
              <div className="print-actions">
                <label>
                  Printer name
                  <input
                    value={installedName}
                    onChange={(e) => setInstalledName(e.target.value)}
                    aria-label="Installed printer name"
                    placeholder="Name shown in the print dialog"
                  />
                </label>
              </div>
            </div>
          </li>
          <li className="print-step">
            <b>3</b>
            <div>
              <h3>Use it for POS receipts</h3>
              <p className="muted">
                {linked.length
                  ? `${linked.length} printer${linked.length === 1 ? '' : 's'} linked. Browser receipts use the size next to Pay. A paired till agent uses the paper size stored on that printer.`
                  : 'Nothing is linked yet. Type the name from step 2, then add it.'}
              </p>
              <div className="print-ui-row">
                <label className="print-ui-paper">
                  Paper
                  <select
                    value={installedPaper === '58mm' || installedPaper === 'a4' ? installedPaper : '80mm'}
                    onChange={(e) => setInstalledPaper(e.target.value)}
                    aria-label="Till printer paper size"
                  >
                    <option value="80mm">80mm receipt</option>
                    <option value="58mm">58mm receipt</option>
                    <option value="a4">A4 invoice</option>
                  </select>
                </label>
                <div className="print-ui-actions">
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={addInstalledPrinter}
                    disabled={busy || !installedName.trim()}
                    aria-label="Add to printers used for POS"
                  >
                    Add to printers used for POS
                  </button>
                </div>
                <p className="print-ui-help">58mm and 80mm are receipt rolls stored on this printer. A4 is a full page, and a receipt job still uses 80mm. A paired till agent uses this stored size. The size next to Pay only changes the browser receipt.</p>
              </div>
            </div>
          </li>
        </ol>
      </div>
      <div className="card">
        <h2 style={{ marginTop: 0 }}>After Pay</h2>
        <label className="print-switch">
          <input
            type="checkbox"
            checked={showEmailSms}
            onChange={(e) => saveEmailSms(e.target.checked)}
            aria-label="Add Email and SMS receipt actions to POS"
          />
          <span>
            Add Email and SMS receipt actions to POS
            <span className="muted" style={{ display: 'block', fontWeight: 500, marginTop: 4 }}>
              Leave this off for a printed receipt only. Turn it on when the till should also offer Email and SMS.
            </span>
          </span>
        </label>
      </div>
      <div className="card">
        <div className="list-page-head page-head">
          <div>
            <h2 style={{ margin: 0 }}>Printers in use</h2>
            <p className="muted" style={{ margin: '6px 0 0' }}>
              Receipt, invoice, and barcode
              {purposeOptions.includes('kitchen') ? ', plus kitchen and bar' : ''}. Paper on each row is the size a till agent or network printer uses for POS. Sales invoice Print uses the paper beside that button in the browser. Barcode labels use copies and symbology only. Neither of those buttons sends a job to a till agent. A sale still completes if a printer is offline.
            </p>
          </div>
          <button type="button" onClick={() => setPrinterAddOpen(true)} aria-label="Add printer">
            Network or till agent
          </button>
        </div>
      {pairing ? (
        <div className="card" style={{ marginBottom: 16 }}>
          <strong>Pairing code (shown once):</strong> <code>{pairing}</code>
          <p className="muted">Enter this code on the till agent within 15 minutes, then choose that agent in the form. Do not put tokens in the repo.</p>
        </div>
      ) : null}

      {printerAddOpen ? (
      <FormModal
        title="Add printer"
        busy={busy}
        dirty={Boolean(form.name.trim() || form.host.trim())}
        onClose={() => setPrinterAddOpen(false)}
      >
        <div className="print-ui-form">
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
          {!hideStoreUx && (
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
          )}
          <label className="print-ui-paper">
            Paper
            <select
              value={form.paper}
              onChange={(e) => setForm({ ...form, paper: e.target.value })}
              aria-label="New printer paper size"
            >
              <option value="80mm">80mm receipt</option>
              <option value="58mm">58mm receipt</option>
              <option value="a4">A4 invoice</option>
            </select>
            <span className="print-ui-help">58mm and 80mm are receipt rolls stored on this printer. A4 is a full page, and a receipt job still uses 80mm. A paired till agent uses this stored size. The size next to Pay only changes the browser receipt.</span>
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
          {form.connection_type === 'print_agent' ? (
            <label>
              Paired till agent
              <select
                value={form.agent_id}
                aria-label="Paired till agent"
                onChange={(e) => setForm({ ...form, agent_id: e.target.value })}
              >
                <option value="">Choose a paired agent</option>
                {agents
                  .filter((row) => row.paired && row.is_active)
                  .map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.label || 'Till agent'}
                    </option>
                  ))}
              </select>
              {agents.some((row) => row.paired && row.is_active) ? null : (
                <span className="print-ui-help">
                  No till agent is paired yet. Issue a pairing code, enter it on the till within 15 minutes, then refresh this list.
                </span>
              )}
            </label>
          ) : null}
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
          {purposeOptions.map((p) => (
            <label key={p} style={{ marginRight: 12 }}>
              <input
                type="checkbox"
                checked={form.purposes.includes(p)}
                onChange={() => togglePurpose(p)}
              />{' '}
              {printerPurposeLabel(p)}
            </label>
          ))}
        </div>
        {pairing ? (
          <p className="print-ui-help" style={{ marginTop: 12 }}>
            Pairing code (shown once): <code>{pairing}</code>. Enter it on the till within 15 minutes, then refresh and choose that agent.
          </p>
        ) : null}
        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            type="button"
            disabled={
              busy ||
              !form.name.trim() ||
              (form.connection_type === 'network' && !form.host.trim()) ||
              (form.connection_type === 'print_agent' && !form.agent_id.trim())
            }
            onClick={createPrinter}
          >
            Save printer
          </button>
          <button type="button" disabled={busy} onClick={issuePairing}>
            Issue till pairing code
          </button>
          {form.connection_type === 'print_agent' ? (
            <button type="button" disabled={busy} aria-label="Refresh paired till agents" onClick={() => void load()}>
              Refresh paired till agents
            </button>
          ) : null}
        </div>
      </FormModal>
      ) : null}

      <div className="print-ui-list">
      <table className="table">
        <thead>
          <tr>
            <th>Printer</th>
            <th>How it connects</th>
            <th>Paper</th>
            <th>Used for</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={6}>No printer is linked yet. Type the name from step 2 and add it, or add a network printer or a paired till agent.</td>
            </tr>
          ) : null}
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                {row.name}
                {row.is_default ? ' · Default' : ''}
              </td>
              <td>{connectionLabel(row.connection_type)}</td>
              <td>
                <div className="print-ui-row">
                  <label className="print-ui-paper">
                    Paper
                    <select
                      value={row.paper === '58mm' || row.paper === 'a4' ? row.paper : '80mm'}
                      aria-label={`Printer paper ${row.name}`}
                      disabled={busy}
                      onChange={(e) => patchPrinter(row.id, { paper: e.target.value })}
                    >
                      <option value="80mm">80mm receipt</option>
                      <option value="58mm">58mm receipt</option>
                      <option value="a4">A4 invoice</option>
                    </select>
                  </label>
                  <div className="print-ui-actions">
                    <button type="button" className="btn-ok" disabled={busy} onClick={() => testPrint(row.id)}>
                      Print test page
                    </button>
                  </div>
                </div>
              </td>
              <td>
                {filterListedPrinterPurposes(row.purposes, purposeOptions)
                  .map((p) => printerPurposeLabel(p))
                  .join(', ')}
              </td>
              <td>{row.is_enabled ? 'On' : 'Off'}</td>
              <td className="erp-row-actions">
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => patchPrinter(row.id, { is_enabled: !row.is_enabled })}
                >
                  {row.is_enabled ? 'Turn off' : 'Turn on'}
                </button>
                <button
                  type="button"
                  className="btn-danger"
                  disabled={busy}
                  onClick={() => deletePrinter(row)}
                  aria-label={`Delete printer ${row.name}`}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      </div>
    </div>
  );
}
