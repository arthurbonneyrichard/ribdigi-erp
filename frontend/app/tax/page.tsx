'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

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

export default function Page() {
  const [rows, setRows] = useState<TaxRate[]>([]);
  const [report, setReport] = useState<any>(null);
  const [filing, setFiling] = useState<any>(null);
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [name, setName] = useState('Standard VAT');
  const [rate, setRate] = useState('15');
  const [taxType, setTaxType] = useState('vat');
  const [pricingMode, setPricingMode] = useState('exclusive');
  const [reverseCharge, setReverseCharge] = useState(false);
  const [componentsJson, setComponentsJson] = useState('');
  const [calcAmount, setCalcAmount] = useState('100');
  const [calcResult, setCalcResult] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  function qs() {
    const params = new URLSearchParams();
    if (fromDate) params.set('from_date', fromDate);
    if (toDate) params.set('to_date', toDate);
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  async function refresh() {
    const q = qs();
    const [rates, taxReport, filingPack] = await Promise.all([
      api('/tax/rates'),
      api(`/reports/tax${q}`),
      api(`/reports/tax/filing${q}`),
    ]);
    setRows(rates.data || []);
    setReport(taxReport.data);
    setFiling(filingPack.data);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function createRate() {
    setError('');
    setMessage('');
    try {
      let components = null;
      if (componentsJson.trim()) {
        components = JSON.parse(componentsJson);
        if (!Array.isArray(components)) throw new Error('Components must be a JSON array');
      }
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
      setComponentsJson('');
      setReverseCharge(false);
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

  async function downloadFiling(format: 'csv' | 'pdf' | 'xlsx', reportType: 'tax_filing' | 'tax_filing_gh' = 'tax_filing') {
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
      const res = await fetch(`${base}/reports/export?${params}`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
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
      setMessage(
        reportType === 'tax_filing_gh'
          ? `Ghana VAT return ${format.toUpperCase()} downloaded`
          : `Filing pack ${format.toUpperCase()} downloaded`,
      );
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
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          <button
            onClick={() => refresh().catch((err) => setError(err.message))}
          >
            Apply
          </button>
        </div>
      </div>

      <div className="grid">
        <div className="card">
          <h3>Create rate</h3>
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
            <button onClick={createRate}>Add rate</button>
          </div>
        </div>
        <div className="card">
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
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
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
        </div>
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

      <table className="table" style={{ marginTop: 16 }}>
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
              <td>
                {!r.is_default && (
                  <button onClick={() => makeDefault(r.id)}>Set default</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
