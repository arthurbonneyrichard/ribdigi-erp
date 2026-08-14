'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api, authHeaders } from '../../lib/api';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type TaxRate = {
  id: string;
  name: string;
  rate: number;
  tax_type: string;
  pricing_mode: string;
  components?: { code: string; name: string; rate: number; basis: string }[] | null;
  is_reverse_charge?: boolean;
  is_default: boolean;
  is_active: boolean;
};

function isoDate(d: Date) {
  return d.toISOString().slice(0, 10);
}

export default function Page() {
  const [rows, setRows] = useState<TaxRate[]>([]);
  const [report, setReport] = useState<any>(null);
  const [filing, setFiling] = useState<any>(null);
  // Stage 109 R1 — shareable filing period dates
  const [fromDate, setFromDate] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('from_date')?.trim() || '';
  });
  const [toDate, setToDate] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('to_date')?.trim() || '';
  });
  // Stage 123 F1 — tax_active → GET /tax/rates?is_active=
  const [taxActiveFilter, setTaxActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('tax_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  const [periodPreset, setPeriodPreset] = useState('');
  const [name, setName] = useState('Standard VAT');
  const [rate, setRate] = useState('15');
  const [taxType, setTaxType] = useState('vat');
  const [pricingMode, setPricingMode] = useState('exclusive');
  const [reverseCharge, setReverseCharge] = useState(false);
  const [componentsJson, setComponentsJson] = useState('');
  const [editId, setEditId] = useState<string | null>(null);
  const [calcAmount, setCalcAmount] = useState('100');
  const [calcResult, setCalcResult] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  function writeTaxPeriodUrl(nextFrom?: string, nextTo?: string) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    const fd = nextFrom !== undefined ? nextFrom : fromDate;
    const td = nextTo !== undefined ? nextTo : toDate;
    if (fd) url.searchParams.set('from_date', fd);
    else url.searchParams.delete('from_date');
    if (td) url.searchParams.set('to_date', td);
    else url.searchParams.delete('to_date');
    const qs = url.searchParams.toString();
    window.history.replaceState({}, '', qs ? `${url.pathname}?${qs}${url.hash}` : `${url.pathname}${url.hash}`);
  }

  function qs(presetOverride?: string) {
    const params = new URLSearchParams();
    const preset = presetOverride ?? periodPreset;
    if (preset === 'monthly' || preset === 'quarterly' || preset === 'annually') {
      params.set('period', preset);
      const now = new Date();
      params.set('year', String(now.getUTCFullYear()));
      if (preset === 'monthly') params.set('month', String(now.getUTCMonth() + 1));
      if (preset === 'quarterly') {
        params.set('quarter', String(Math.floor(now.getUTCMonth() / 3) + 1));
      }
    } else {
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
    }
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  async function refresh(presetOverride?: string, opts?: { taxActive?: string }) {
    const q = qs(presetOverride);
    const taxActive = opts?.taxActive !== undefined ? opts.taxActive : taxActiveFilter;
    const taxQs =
      taxActive === 'true'
        ? '?is_active=true'
        : taxActive === 'false'
          ? '?is_active=false'
          : '';
    const [rates, taxReport, filingPack] = await Promise.all([
      api(`/tax/rates${taxQs}`),
      api(`/reports/tax${q}`),
      api(`/reports/tax/filing${q}`),
    ]);
    setRows(rates.data || []);
    setReport(taxReport.data);
    setFiling(filingPack.data);
    if (taxReport.data?.from_date) {
      const fd = String(taxReport.data.from_date).slice(0, 10);
      if (fd) setFromDate(fd);
    }
    if (taxReport.data?.to_date) {
      const td = String(taxReport.data.to_date).slice(0, 10);
      if (td) setToDate(td);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  // Stage 102 T1 — honor Shell #rates / #calculator / #filing
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!hash) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
  }, []);

  function applyPeriod(kind: 'monthly' | 'quarterly' | 'annually') {
    setPeriodPreset(kind);
    refresh(kind).catch((err) => setError(err.message));
  }

  function resetForm() {
    setEditId(null);
    setName('Standard VAT');
    setRate('15');
    setTaxType('vat');
    setPricingMode('exclusive');
    setReverseCharge(false);
    setComponentsJson('');
  }

  function startEdit(r: TaxRate) {
    setEditId(r.id);
    setName(r.name);
    setRate(String(r.rate));
    setTaxType(r.tax_type);
    setPricingMode(r.pricing_mode);
    setReverseCharge(!!r.is_reverse_charge);
    setComponentsJson(r.components?.length ? JSON.stringify(r.components) : '');
  }

  async function saveRate() {
    setError('');
    setMessage('');
    try {
      let components = null;
      if (componentsJson.trim()) {
        components = JSON.parse(componentsJson);
        if (!Array.isArray(components)) throw new Error('Components must be a JSON array');
      }
      if (editId) {
        await api(`/tax/rates/${editId}`, {
          method: 'PATCH',
          body: JSON.stringify({
            name,
            rate: Number(rate),
            tax_type: taxType,
            pricing_mode: pricingMode,
            components,
            clear_components: !components,
            is_reverse_charge: reverseCharge,
          }),
        });
        setMessage('Tax rate updated');
      } else {
        await api('/tax/rates', {
          method: 'POST',
          body: JSON.stringify({
            name,
            rate: Number(rate),
            tax_type: taxType,
            pricing_mode: pricingMode,
            components,
            is_reverse_charge: reverseCharge,
            is_default: rows.length === 0,
            is_active: true,
          }),
        });
        setMessage('Tax rate created');
      }
      resetForm();
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function makeDefault(id: string) {
    setError('');
    try {
      await api(`/tax/rates/${id}/default`, { method: 'POST' });
      setMessage('Default rate updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setActive(id: string, is_active: boolean) {
    setError('');
    try {
      await api(`/tax/rates/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      setMessage(is_active ? 'Tax rate activated' : 'Tax rate deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function calculate() {
    setError('');
    try {
      const r = await api('/tax/calculate', {
        method: 'POST',
        body: JSON.stringify({ amount: Number(calcAmount) }),
      });
      setCalcResult(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function downloadFiling(
    format: 'csv' | 'pdf' | 'xlsx',
    reportType: 'tax_filing' | 'tax_filing_gh' | 'tax_filing_ke' | 'tax_filing_ng' = 'tax_filing',
  ) {
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      params.set('report_type', reportType);
      params.set('format', format);
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      if (reportType === 'tax_filing_gh') params.set('jurisdiction', 'GH');
      if (reportType === 'tax_filing_ke') params.set('jurisdiction', 'KE');
      if (reportType === 'tax_filing_ng') params.set('jurisdiction', 'NG');
      const res = await fetch(`${base}/reports/export?${params}`, {
        headers: authHeaders(),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Export failed');
      }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || `${reportType}.${format}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      const labels: Record<string, string> = {
        tax_filing_gh: 'Ghana VAT return',
        tax_filing_ke: 'Kenya VAT return',
        tax_filing_ng: 'Nigeria VAT return',
        tax_filing: 'Filing pack',
      };
      setMessage(`${labels[reportType] || 'Filing pack'} ${format.toUpperCase()} downloaded`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  const boxes = filing?.filing_boxes?.boxes || [];

  return (
    <Shell>
      <h1>Tax</h1>
      <p className="muted">Rates, calculator, period summary, and filing export pack</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Period</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => {
              setPeriodPreset('');
              setFromDate(e.target.value);
              writeTaxPeriodUrl(e.target.value, toDate);
            }}
            aria-label="Tax filing from date"
          />
          <input
            type="date"
            value={toDate}
            onChange={(e) => {
              setPeriodPreset('');
              setToDate(e.target.value);
              writeTaxPeriodUrl(fromDate, e.target.value);
            }}
            aria-label="Tax filing to date"
          />
          <button type="button" onClick={() => applyPeriod('monthly')}>
            This month
          </button>
          <button type="button" onClick={() => applyPeriod('quarterly')}>
            This quarter
          </button>
          <button type="button" onClick={() => applyPeriod('annually')}>
            This year
          </button>
          <button
            onClick={() => {
              setPeriodPreset('');
              writeTaxPeriodUrl();
              refresh().catch((err) => setError(err.message));
            }}
          >
            Apply
          </button>
        </div>
        {report?.period && (
          <p className="muted" style={{ marginTop: 8 }}>
            Preset: {report.period}
            {report.period_year != null ? ` ${report.period_year}` : ''}
            {report.period_month != null ? `-${String(report.period_month).padStart(2, '0')}` : ''}
            {report.period_quarter != null ? ` Q${report.period_quarter}` : ''}
          </p>
        )}
      </div>

      <div className="grid">
        <div className="card" id="rates">
          <h3>{editId ? 'Edit rate' : 'Create rate'}</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
            <input value={rate} onChange={(e) => setRate(e.target.value)} placeholder="Rate %" />
            <select value={taxType} onChange={(e) => setTaxType(e.target.value)}>
              <option value="vat">VAT</option>
              <option value="gst">GST</option>
              <option value="sales_tax">Sales tax</option>
            </select>
            <select value={pricingMode} onChange={(e) => setPricingMode(e.target.value)}>
              <option value="exclusive">Exclusive</option>
              <option value="inclusive">Inclusive</option>
            </select>
            <label className="muted">
              <input
                type="checkbox"
                checked={reverseCharge}
                onChange={(e) => setReverseCharge(e.target.checked)}
              />{' '}
              Reverse charge
            </label>
            <label className="muted">Compound components (optional JSON)</label>
            <textarea
              value={componentsJson}
              onChange={(e) => setComponentsJson(e.target.value)}
              rows={3}
              placeholder='[{"code":"cgst","name":"CGST","rate":9,"basis":"net"},{"code":"sgst","name":"SGST","rate":9,"basis":"net"}]'
            />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" onClick={saveRate}>
                {editId ? 'Save changes' : 'Add rate'}
              </button>
              {editId && (
                <button type="button" onClick={resetForm}>
                  Cancel edit
                </button>
              )}
            </div>
          </div>
        </div>
        <div className="card" id="calculator">
          <h3>Calculator</h3>
          <input value={calcAmount} onChange={(e) => setCalcAmount(e.target.value)} />
          <button onClick={calculate} style={{ marginTop: 8 }}>
            Calculate with default rate
          </button>
          {calcResult && (
            <p className="muted" style={{ marginTop: 8 }}>
              Net {calcResult.net} · Tax {calcResult.tax} · Gross {calcResult.gross} (
              {calcResult.rate}% {calcResult.pricing_mode}
              {calcResult.is_reverse_charge ? ' · reverse charge' : ''})
            </p>
          )}
        </div>
        <div className="card">
          <h3>Tax report</h3>
          <p>Output tax: {report?.output_tax ?? '—'}</p>
          <p className="muted">
            Invoices {report?.output_tax_invoices ?? 0} · POS {report?.output_tax_pos ?? 0}
            {report?.reverse_charge_tax != null
              ? ` · RC memo ${report.reverse_charge_tax}`
              : ''}
          </p>
          <p>Input tax: {report?.input_tax ?? '—'}</p>
          <p className="muted">Source: {report?.input_tax_source ?? '—'}</p>
          <div className="kpi">{report?.net_tax_payable ?? '—'}</div>
          <p className="muted">Net payable / refundable</p>
          <p className="muted" style={{ marginTop: 8 }}>
            Path export via <code>GET /reports/tax/export</code> (Stage 161 X1; distinct from
            generic <code>/reports/export</code>).
          </p>
          <button
            type="button"
            style={{ marginTop: 8 }}
            onClick={async () => {
              setError('');
              setMessage('');
              try {
                const token = localStorage.getItem('token') || '';
                const tenant = localStorage.getItem('tenant') || '';
                const params = new URLSearchParams();
                if (fromDate) params.set('from_date', fromDate);
                if (toDate) params.set('to_date', toDate);
                const qs = params.toString() ? `?${params}` : '';
                const res = await fetch(`${base}/reports/tax/export${qs}`, {
                  headers: {
                    Authorization: `Bearer ${token}`,
                    'X-Tenant-ID': tenant,
                  },
                });
                if (!res.ok) throw new Error(await res.text());
                const blob = await res.blob();
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'reports_tax_export.csv';
                a.click();
                URL.revokeObjectURL(a.href);
                setMessage('Tax path CSV downloaded (Stage 161 X1)');
              } catch (err: any) {
                setError(err.message);
              }
            }}
          >
            Export tax path CSV
          </button>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }} id="filing">
        <h3>Filing pack</h3>
        <p className="muted">
          Jurisdiction-neutral boxes + output/input schedules
          {filing?.jurisdiction ? ` · Tenant jurisdiction: ${filing.jurisdiction}` : ''}
          {filing?.tax_registration_number
            ? ` · TIN ${filing.tax_registration_number}`
            : ' · TIN not set (set on Company)'}
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
          <button onClick={() => downloadFiling('csv')}>Export CSV</button>
          <button onClick={() => downloadFiling('xlsx')}>Export Excel</button>
          <button onClick={() => downloadFiling('pdf')}>Export PDF</button>
          <button onClick={() => downloadFiling('xlsx', 'tax_filing_gh')}>Export Ghana VAT (XLSX)</button>
          <button onClick={() => downloadFiling('csv', 'tax_filing_gh')}>Export Ghana VAT (CSV)</button>
          <button onClick={() => downloadFiling('pdf', 'tax_filing_gh')}>Export Ghana VAT (PDF)</button>
          <button onClick={() => downloadFiling('xlsx', 'tax_filing_ke')}>Export Kenya VAT (XLSX)</button>
          <button onClick={() => downloadFiling('csv', 'tax_filing_ke')}>Export Kenya VAT (CSV)</button>
          <button onClick={() => downloadFiling('pdf', 'tax_filing_ke')}>Export Kenya VAT (PDF)</button>
          <button onClick={() => downloadFiling('xlsx', 'tax_filing_ng')}>Export Nigeria VAT (XLSX)</button>
          <button onClick={() => downloadFiling('csv', 'tax_filing_ng')}>Export Nigeria VAT (CSV)</button>
          <button onClick={() => downloadFiling('pdf', 'tax_filing_ng')}>Export Nigeria VAT (PDF)</button>
        </div>
        <p className="muted" style={{ marginBottom: 12 }}>
          Government exports are manual filing workbooks only — they do not e-file to GRA, KRA iTax, or
          FIRS portals.
        </p>
        {!!filing?.government?.warnings?.length && (
          <p style={{ color: '#b45309' }}>{filing.government.warnings.join(' · ')}</p>
        )}
        {filing?.government?.boxes?.length ? (
          <>
            <h4 style={{ marginTop: 8 }}>{filing.government.template_name || 'Government return'}</h4>
            <table className="table">
              <thead>
                <tr>
                  <th>Box</th>
                  <th>Label</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {filing.government.boxes.map((b: any) => (
                  <tr key={b.code || b.box}>
                    <td>{b.box}</td>
                    <td>{b.label}</td>
                    <td>{b.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
        <h4 style={{ marginTop: 12 }}>Neutral boxes</h4>
        <table className="table">
          <thead>
            <tr>
              <th>Box</th>
              <th>Label</th>
              <th>Amount</th>
            </tr>
          </thead>
          <tbody>
            {boxes.map((b: any) => (
              <tr key={b.box}>
                <td>{b.box}</td>
                <td>{b.label}</td>
                <td>{b.amount}</td>
              </tr>
            ))}
            {!boxes.length && (
              <tr>
                <td colSpan={3} className="muted">
                  No filing data for period
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <p className="muted" style={{ marginTop: 8 }}>
          Output lines: {filing?.schedules?.output?.length ?? 0} · Input lines:{' '}
          {filing?.schedules?.input?.length ?? 0}
        </p>
      </div>

      <h3 style={{ marginTop: 16 }}>Tax rates</h3>
      <p className="muted" style={{ marginBottom: 8 }}>
        Filter via <code>tax_active</code> → <code>GET /tax/rates?is_active=</code> (Stage 123 F1).
      </p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8, alignItems: 'center' }}>
        <label className="muted">
          Active status{' '}
          <select
            value={taxActiveFilter}
            onChange={(e) => {
              const v = e.target.value;
              setTaxActiveFilter(v);
              const url = new URL(window.location.href);
              if (v === 'true' || v === 'false') url.searchParams.set('tax_active', v);
              else url.searchParams.delete('tax_active');
              const qs = url.searchParams.toString();
              window.history.replaceState(
                {},
                '',
                qs ? `${url.pathname}?${qs}${url.hash}` : `${url.pathname}${url.hash}`
              );
              refresh(undefined, { taxActive: v }).catch((err) => setError(err.message));
            }}
            aria-label="Tax rate active filter"
          >
            <option value="">All</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
        </label>
        <button
          type="button"
          onClick={async () => {
            // Stage 121 X1 — tax rates CSV export
            setError('');
            setMessage('');
            try {
              const token = localStorage.getItem('token');
              const tenant = localStorage.getItem('tenant');
              const res = await fetch(`${base}/tax/rates/export`, {
                headers: authHeaders(),
              });
              if (!res.ok) throw new Error('Tax rates export failed');
              const blob = await res.blob();
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.href = url;
              a.download = 'tax_rates_export.csv';
              a.click();
              URL.revokeObjectURL(url);
              setMessage('Tax rates CSV exported');
            } catch (err: any) {
              setError(err.message || 'Tax rates export failed');
            }
          }}
        >
          Export tax rates CSV
        </button>
      </div>
      <table className="table" style={{ marginTop: 8 }}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Rate</th>
            <th>Mode</th>
            <th>RC</th>
            <th>Components</th>
            <th>Default</th>
            <th>Active</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.name}</td>
              <td>{r.tax_type}</td>
              <td>{r.rate}%</td>
              <td>{r.pricing_mode}</td>
              <td>{String(!!r.is_reverse_charge)}</td>
              <td className="muted">
                {r.components?.length
                  ? r.components.map((c) => `${c.code}:${c.rate}%`).join(' + ')
                  : '—'}
              </td>
              <td>{String(r.is_default)}</td>
              <td>{String(r.is_active)}</td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <button type="button" onClick={() => startEdit(r)}>
                  Edit
                </button>
                {!r.is_default && r.is_active && (
                  <button type="button" onClick={() => makeDefault(r.id)}>
                    Set default
                  </button>
                )}
                {r.is_active ? (
                  <button type="button" onClick={() => setActive(r.id, false)}>
                    Deactivate
                  </button>
                ) : (
                  <button type="button" onClick={() => setActive(r.id, true)}>
                    Activate
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
