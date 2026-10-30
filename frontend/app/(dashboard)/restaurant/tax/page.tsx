'use client';

/**
 * Restaurant tax: what was collected on bills, what can be claimed back on supplies, what is
 * owed for the period, the GRA return files, and the tax rates the menu uses.
 * Uses the shared tax engine and filing exports.
 */

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { downloadAttachment } from '../../../../lib/attachments';
import { money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Preset = 'month' | 'last' | 'quarter' | 'custom';

function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function rangeFor(preset: Preset): [string, string] {
  const now = new Date();
  if (preset === 'last') return [iso(new Date(now.getFullYear(), now.getMonth() - 1, 1)), iso(new Date(now.getFullYear(), now.getMonth(), 0))];
  if (preset === 'quarter') return [iso(new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1)), iso(now)];
  return [iso(new Date(now.getFullYear(), now.getMonth(), 1)), iso(now)];
}

function niceDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

function rateLabel(r: Row) {
  const parts = (r.components || []) as Row[];
  return parts.length ? parts.map((c) => `${c.name || c.code} ${Number(c.rate)}%`).join(' + ') : `${Number(r.rate)}%`;
}

export default function RestaurantTaxPage() {
  const [preset, setPreset] = useState<Preset>('month');
  const [from, setFrom] = useState(() => rangeFor('month')[0]);
  const [to, setTo] = useState(() => rangeFor('month')[1]);
  const [report, setReport] = useState<Row | null>(null);
  const [rates, setRates] = useState<Row[]>([]);
  const [company, setCompany] = useState<Row | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState<Row | 'new' | null>(null);

  const loadRates = useCallback(async () => {
    try {
      const [r, t] = await Promise.all([api('/tax/rates'), api('/tenants/me').catch(() => ({ data: null }))]);
      setRates(r?.data || []);
      setCompany(t?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  useEffect(() => {
    void loadRates();
  }, [loadRates]);

  useEffect(() => {
    api(`/reports/tax?from_date=${from}&to_date=${to}`)
      .then((res) => {
        setReport(res?.data || null);
        setError('');
      })
      .catch((err) => setError(problem(err)));
  }, [from, to]);

  function pick(next: Preset) {
    setPreset(next);
    if (next !== 'custom') {
      const [a, b] = rangeFor(next);
      setFrom(a);
      setTo(b);
    }
  }

  async function download(format: 'xlsx' | 'pdf' | 'csv') {
    setError('');
    const ghana = (company?.tax_jurisdiction || 'GH') === 'GH';
    const params = new URLSearchParams({ report_type: ghana ? 'tax_filing_gh' : 'tax_filing', format, from_date: from, to_date: to });
    if (ghana) params.set('jurisdiction', 'GH');
    try {
      await downloadAttachment(`/reports/export?${params}`, `${ghana ? 'gra-vat-return' : 'tax-return'}-${from}-to-${to}.${format}`);
      setNotice(`${ghana ? 'GRA VAT return' : 'Tax return'} downloaded`);
    } catch (err) {
      setError(problem(err));
    }
  }

  const due = Number(report?.net_tax_payable || 0);
  const active = rates.filter((r) => r.is_active !== false);
  const main = active.find((r) => r.is_default) || active[0];
  const ghana = (company?.tax_jurisdiction || 'GH') === 'GH';

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Tax</h1>
          <p>Tax on your bills, tax you can claim back on supplies, and what to pay.</p>
        </div>
      </header>

      <div className="rd-period" role="group" aria-label="Tax period">
        <div className="rd-chips">
          {([['month', 'This month'], ['last', 'Last month'], ['quarter', 'This quarter'], ['custom', 'Pick dates']] as const).map(([key, label]) => (
            <button key={key} type="button" className={preset === key ? 'on' : ''} aria-pressed={preset === key} onClick={() => pick(key)}>
              {label}
            </button>
          ))}
        </div>
        {preset === 'custom' ? (
          <div className="rd-dates">
            <input type="date" aria-label="Tax from date" value={from} max={to} onChange={(e) => e.target.value && setFrom(e.target.value)} />
            <span>to</span>
            <input type="date" aria-label="Tax to date" value={to} min={from} onChange={(e) => e.target.value && setTo(e.target.value)} />
          </div>
        ) : null}
      </div>

      {notice ? <div className="rd-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="rd-error" role="alert" onClick={() => setError('')}>{error}</div> : null}

      {report ? (
        <div className="rd-tax-sum" aria-label="Tax for the period">
          <div>
            <span>Tax on your bills</span>
            <strong>{money(report.output_tax)}</strong>
            <small>
              On {money(report.taxable_outputs_net)} of sales before tax
            </small>
          </div>
          <span className="op" aria-hidden="true">−</span>
          <div>
            <span>Tax you can claim back</span>
            <strong>{money(report.input_tax)}</strong>
            <small>
              Paid on {money(report.taxable_inputs_net)} of supplies
              {report.input_tax_source === 'purchase_orders' ? ' · from supplier orders (no supplier bills recorded)' : ''}
            </small>
          </div>
          <span className="op" aria-hidden="true">=</span>
          <div className={`result${due < 0 ? ' refund' : ''}`}>
            <span>{due < 0 ? 'Refund due to you' : 'Tax to pay'}</span>
            <strong>{money(Math.abs(due))}</strong>
            <small>{niceDate(from)} to {niceDate(to)}</small>
          </div>
        </div>
      ) : (
        <div className="rd-empty">Working it out…</div>
      )}

      <section className="rd-panel">
        <div className="rd-panel-head">
          <h2>{ghana ? 'GRA VAT return' : 'Tax return'}</h2>
          <small>Files for this period, ready to enter on the {ghana ? 'GRA portal' : 'tax office form'}. Nothing is sent for you.</small>
        </div>
        {!company?.tax_registration_number ? (
          <p className="rd-hint-line rd-warn-text">
            Your TIN is not set, so it will be missing from the return. <Link href="/company">Add it on the company profile</Link>.
          </p>
        ) : (
          <p className="rd-hint-line">TIN {company.tax_registration_number}</p>
        )}
        <div className="rd-row-actions">
          <button type="button" className="rd-primary" aria-label="Download tax return Excel" onClick={() => void download('xlsx')}>Download Excel</button>
          <button type="button" aria-label="Download tax return PDF" onClick={() => void download('pdf')}>PDF</button>
          <button type="button" aria-label="Download tax return CSV" onClick={() => void download('csv')}>CSV</button>
        </div>
      </section>

      <section className="rd-panel">
        <div className="rd-panel-head">
          <h2>Tax rates</h2>
          <small>
            {main
              ? main.pricing_mode === 'inclusive'
                ? `Your menu prices already include ${main.name}.`
                : `${main.name} is added on top of your menu prices.`
              : 'No tax rate yet: bills carry no tax.'}
          </small>
          <button type="button" className="rd-link" aria-label="Add a tax rate" onClick={() => setEditing('new')}>+ Tax rate</button>
        </div>
        <div className="rd-list rd-list-flat" aria-label="Tax rates">
          {rates.map((r) => (
            <div key={r.id} className={`rd-stock-row${r.is_active === false ? ' muted' : ''}`}>
              <div className="what">
                <strong>{r.name}</strong>
                <small>{rateLabel(r)} · {r.pricing_mode === 'inclusive' ? 'included in prices' : 'added on top'}</small>
              </div>
              <div className="onhand">
                <strong>{Number(r.rate)}%</strong>
                <small>{r.is_active === false ? 'not in use' : r.is_default ? 'used on bills' : 'in use'}</small>
              </div>
              {r.is_default ? <span className="rd-pill">Default</span> : <span />}
              <div className="acts">
                {!r.is_default && r.is_active !== false ? (
                  <button
                    type="button"
                    aria-label={`Make ${r.name} the default`}
                    onClick={async () => {
                      try {
                        await api(`/tax/rates/${r.id}/default`, { method: 'POST' });
                        setNotice(`${r.name} is now used on bills`);
                        await loadRates();
                      } catch (err) {
                        setError(problem(err));
                      }
                    }}
                  >
                    Make default
                  </button>
                ) : null}
                <button type="button" aria-label={`Edit ${r.name}`} onClick={() => setEditing(r)}>Edit</button>
              </div>
            </div>
          ))}
        </div>
        <p className="rd-hint-line">Changing a rate does not change bills already paid.</p>
      </section>

      {editing ? (
        <RateSheet
          row={editing === 'new' ? null : editing}
          onClose={() => setEditing(null)}
          onDone={async (m) => {
            setEditing(null);
            setNotice(m);
            await loadRates();
          }}
        />
      ) : null}
    </div>
  );
}

function RateSheet({ row, onClose, onDone }: { row: Row | null; onClose: () => void; onDone: (m: string) => Promise<void> }) {
  const [name, setName] = useState(String(row?.name || ''));
  const [rate, setRate] = useState(row ? String(Number(row.rate)) : '');
  const [mode, setMode] = useState(String(row?.pricing_mode || 'exclusive'));
  const [active, setActive] = useState(row ? row.is_active !== false : true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const hasParts = Boolean(row?.components?.length);

  async function save() {
    if (!name.trim()) return setError('Name the rate, like VAT.');
    if (!hasParts && !(Number(rate) >= 0 && rate.trim() !== '')) return setError('Enter the percent.');
    setBusy(true);
    setError('');
    try {
      const body: Row = { name: name.trim(), pricing_mode: mode, is_active: active };
      if (!hasParts) body.rate = Number(rate);
      if (row) await api(`/tax/rates/${row.id}`, { method: 'PATCH', body: JSON.stringify(body) });
      else await api('/tax/rates', { method: 'POST', body: JSON.stringify({ ...body, tax_type: 'vat' }) });
      await onDone(`${name.trim()} saved`);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={row ? `Edit ${row.name}` : 'New tax rate'} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{row ? `Edit ${row.name}` : 'New tax rate'}</h2>
            <p>New bills use the change; paid bills keep their tax.</p>
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-form-grid">
          <label>
            <span>Name</span>
            <input aria-label="Tax rate name" placeholder="VAT" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </label>
          <label>
            <span>Percent</span>
            {hasParts ? (
              <input aria-label="Tax percent" value={`${Number(row?.rate)}% (${rateLabel(row as Row)})`} readOnly />
            ) : (
              <input aria-label="Tax percent" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value.replace(/[^0-9.]/g, ''))} />
            )}
          </label>
          <span className="rd-field-label rd-span">Your menu prices</span>
          <div className="rd-chips rd-span" role="radiogroup" aria-label="Menu prices">
            <button type="button" role="radio" aria-checked={mode === 'exclusive'} className={mode === 'exclusive' ? 'on' : ''} onClick={() => setMode('exclusive')}>
              Tax added on top
            </button>
            <button type="button" role="radio" aria-checked={mode === 'inclusive'} className={mode === 'inclusive' ? 'on' : ''} onClick={() => setMode('inclusive')}>
              Prices include tax
            </button>
          </div>
          {row ? (
            <label>
              <span>In use</span>
              <select aria-label="Tax rate in use" value={active ? 'yes' : 'no'} onChange={(e) => setActive(e.target.value === 'yes')} disabled={row.is_default}>
                <option value="yes">Yes</option>
                <option value="no">No</option>
              </select>
            </label>
          ) : null}
        </div>
        {hasParts ? <p className="rd-hint-line">This rate is made of several levies; change the parts under <Link href="/tax">full tax settings</Link>.</p> : null}
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Save tax rate" disabled={busy} onClick={() => void save()}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </aside>
    </div>
  );
}
