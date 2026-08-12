'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function Page() {
  const [kind, setKind] = useState<'receivable' | 'payable'>('receivable');
  const [report, setReport] = useState<any>(null);
  const [customers, setCustomers] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [partyId, setPartyId] = useState('');
  const [statement, setStatement] = useState<any>(null);
  const [paymentSchedule, setPaymentSchedule] = useState<any>(null);
  const [outstanding, setOutstanding] = useState<any[] | null>(null);
  const [outstandingPartyName, setOutstandingPartyName] = useState('');
  const [payAmount, setPayAmount] = useState('');
  const [payMethod, setPayMethod] = useState('cash');
  const [liquidAccountId, setLiquidAccountId] = useState('');
  const [liquidAccounts, setLiquidAccounts] = useState<any[]>([]);
  const [allocateKey, setAllocateKey] = useState(''); // '' = auto oldest-first
  const [openDocs, setOpenDocs] = useState<any[]>([]);
  const [creditLimit, setCreditLimit] = useState('');
  const [applyEarly, setApplyEarly] = useState(true);
  const [epPct, setEpPct] = useState('2');
  const [epDays, setEpDays] = useState('10');
  const [epEnabled, setEpEnabled] = useState(false);
  const [fxRates, setFxRates] = useState<any[]>([]);
  const [baseCurrency, setBaseCurrency] = useState('GHS');
  const [fxCode, setFxCode] = useState('USD');
  const [fxRate, setFxRate] = useState('15');
  const [fxAutoRefresh, setFxAutoRefresh] = useState(true);
  const [payFxRate, setPayFxRate] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  // Stage 136 C1 / S1 — payment register list + method filter
  const [payments, setPayments] = useState<any[]>([]);
  const [paymentMethodFilter, setPaymentMethodFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('payment_method') || '')
      .trim()
      .toLowerCase();
    return ['cash', 'bank_transfer', 'card', 'cheque', 'mobile_money', 'other'].includes(v)
      ? v
      : '';
  });

  async function refresh() {
    const methodQs = paymentMethodFilter
      ? `?payment_method=${encodeURIComponent(paymentMethodFilter)}`
      : '';
    const payPath =
      kind === 'receivable'
        ? `/credit/customer-payments${methodQs}`
        : `/credit/supplier-payments${methodQs}`;
    const [aging, cust, supp, settings, liquid, fx, payRes] = await Promise.all([
      api(`/credit/aging?kind=${kind}`),
      api('/customers'),
      api('/suppliers'),
      api('/credit/settings'),
      api('/accounting/liquid-accounts').catch(() => ({ data: [] })),
      api('/credit/exchange-rates').catch(() => ({ data: { base_currency: 'GHS', rates: [] } })),
      api(payPath).catch(() => ({ data: [] })),
    ]);
    setReport(aging.data);
    setCustomers(cust.data || []);
    setSuppliers(supp.data || []);
    setLiquidAccounts(liquid.data || []);
    setPayments(payRes.data || []);
    setEpPct(String(settings.data?.early_pay_discount_pct ?? 0));
    setEpDays(String(settings.data?.early_pay_discount_days ?? 0));
    setEpEnabled(!!settings.data?.enabled);
    setBaseCurrency(fx.data?.base_currency || 'GHS');
    setFxRates(fx.data?.rates || []);
    setFxAutoRefresh(fx.data?.fx_auto_refresh !== false);
    if (!partyId) {
      const first = kind === 'receivable' ? cust.data?.[0]?.id : supp.data?.[0]?.id;
      if (first) setPartyId(first);
    }
  }

  function setKindAndUrl(next: 'receivable' | 'payable') {
    setKind(next);
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('kind', next);
    const qs = url.searchParams.toString();
    window.history.replaceState({}, '', qs ? `${url.pathname}?${qs}` : url.pathname);
  }

  useEffect(() => {
    const raw = new URLSearchParams(window.location.search).get('kind')?.trim() || '';
    if (raw === 'payable' || raw === 'receivable') setKind(raw);
  }, []);

  // Stage 104 R1 / Stage 108 C1 — honor Shell #aging / #early-pay / #exchange-rates /
  // #payment-schedule / #party-actions / #by-party / #statement
  // Stage 136 C1 / S1 — honor #payments
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

  useEffect(() => {
    setStatement(null);
    setPaymentSchedule(null);
    setOutstanding(null);
    setOutstandingPartyName('');
    setAllocateKey('');
    setOpenDocs([]);
    refresh().catch((err) => setError(err.message));
  }, [kind, paymentMethodFilter]);

  async function downloadCreditExport(path: string, filename: string, okMessage: string) {
    setError('');
    try {
      const token = localStorage.getItem('token') || '';
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}${path}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        setError(await res.text());
        return;
      }
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      setMessage(okMessage);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }
  useEffect(() => {
    setAllocateKey('');
    if (!partyId) {
      setOpenDocs([]);
      return;
    }
    loadOpenDocs(partyId).catch(() => setOpenDocs([]));
  }, [partyId, kind]);

  function clearDetailPanels() {
    setStatement(null);
    setPaymentSchedule(null);
    setOutstanding(null);
    setOutstandingPartyName('');
  }

  function docKey(row: any): string {
    if (kind === 'receivable' && row.invoice_id) return `si:${row.invoice_id}`;
    if (row.purchase_invoice_id) return `pi:${row.purchase_invoice_id}`;
    if (row.purchase_order_id) return `po:${row.purchase_order_id}`;
    return '';
  }

  function docLabel(row: any): string {
    const num = row.invoice_number || row.po_number || row.invoice_id || row.purchase_invoice_id || 'Doc';
    const due = row.amount != null ? ` · due ${row.amount}` : '';
    const typ = row.document_type || (kind === 'receivable' ? 'sales_invoice' : 'bill');
    return `${num} (${typ}${due})`;
  }

  async function loadOpenDocs(id: string = partyId) {
    if (!id) {
      setOpenDocs([]);
      return;
    }
    const path =
      kind === 'receivable' ? `/customers/${id}/outstanding` : `/suppliers/${id}/outstanding`;
    const r = await api(path);
    setOpenDocs(Array.isArray(r.data) ? r.data : []);
  }

  async function loadStatement() {
    if (!partyId) return;
    setError('');
    try {
      const path =
        kind === 'receivable'
          ? `/credit/customers/${partyId}/statement`
          : `/credit/suppliers/${partyId}/statement`;
      const r = await api(path);
      clearDetailPanels();
      setStatement(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadOutstanding() {
    if (!partyId) return;
    setError('');
    try {
      const path =
        kind === 'receivable'
          ? `/customers/${partyId}/outstanding`
          : `/suppliers/${partyId}/outstanding`;
      const r = await api(path);
      const party = (kind === 'receivable' ? customers : suppliers).find((p) => p.id === partyId);
      clearDetailPanels();
      const rows = Array.isArray(r.data) ? r.data : [];
      setOutstanding(rows);
      setOpenDocs(rows);
      setOutstandingPartyName(party?.name || 'Selected party');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadPaymentSchedule() {
    if (!partyId || kind !== 'payable') return;
    setError('');
    try {
      const r = await api(`/suppliers/${partyId}/payment-schedule`);
      clearDetailPanels();
      setPaymentSchedule(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function recordPayment() {
    if (!partyId || !payAmount) return;
    setError('');
    try {
      const selected = allocateKey
        ? openDocs.find((d) => docKey(d) === allocateKey) ||
          (outstanding || []).find((d) => docKey(d) === allocateKey)
        : null;
      if (kind === 'receivable') {
        await api(`/customers/${partyId}/payments`, {
          method: 'POST',
          body: JSON.stringify({
            customer_id: partyId,
            amount: Number(payAmount),
            payment_method: payMethod,
            apply_early_discount: applyEarly,
            liquid_account_id: liquidAccountId || null,
            exchange_rate: payFxRate === '' ? null : Number(payFxRate),
            sales_invoice_id: selected?.invoice_id || null,
          }),
        });
      } else {
        await api(`/suppliers/${partyId}/payments`, {
          method: 'POST',
          body: JSON.stringify({
            supplier_id: partyId,
            amount: Number(payAmount),
            payment_method: payMethod === 'cash' ? 'bank_transfer' : payMethod,
            apply_early_discount: applyEarly,
            liquid_account_id: liquidAccountId || null,
            exchange_rate: payFxRate === '' ? null : Number(payFxRate),
            purchase_invoice_id: selected?.purchase_invoice_id || null,
            purchase_order_id:
              !selected?.purchase_invoice_id && selected?.purchase_order_id
                ? selected.purchase_order_id
                : null,
          }),
        });
      }
      setMessage(
        selected
          ? `Payment recorded against ${docLabel(selected)}`
          : applyEarly && epEnabled
            ? 'Payment recorded (early discount applied when eligible; oldest open docs first)'
            : 'Payment recorded (oldest open docs first)',
      );
      setPayAmount('');
      setAllocateKey('');
      await refresh();
      await loadOpenDocs();
      await loadStatement();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function updateLimit() {
    if (!partyId || kind !== 'receivable') return;
    setError('');
    try {
      await api(`/customers/${partyId}/credit-limit`, {
        method: 'PATCH',
        body: JSON.stringify({ credit_limit: Number(creditLimit) || 0 }),
      });
      setMessage('Credit limit updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveEarlyPay() {
    setError('');
    setMessage('');
    try {
      const r = await api('/credit/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          early_pay_discount_pct: Number(epPct) || 0,
          early_pay_discount_days: Number(epDays) || 0,
        }),
      });
      setEpEnabled(!!r.data?.enabled);
      setMessage(
        r.data?.enabled
          ? `Early pay terms set: ${r.data.early_pay_discount_pct}% / ${r.data.early_pay_discount_days} days`
          : 'Early pay discount disabled (set pct and days > 0)',
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveFxRate() {
    setError('');
    setMessage('');
    try {
      await api(`/credit/exchange-rates/${fxCode}`, {
        method: 'PUT',
        body: JSON.stringify({ currency_code: fxCode, rate_to_base: Number(fxRate) }),
      });
      setMessage(`Saved ${fxCode} @ ${fxRate} ${baseCurrency}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeFxRate(code: string) {
    setError('');
    try {
      await api(`/credit/exchange-rates/${code}`, { method: 'DELETE' });
      setMessage(`Removed ${code}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function refreshFxFromFeed() {
    setError('');
    setMessage('');
    try {
      const r = await api('/credit/exchange-rates/refresh', {
        method: 'POST',
        body: JSON.stringify({}),
      });
      const n = r.data?.updated_count ?? r.data?.updated?.length ?? 0;
      setMessage(`Refreshed ${n} rate(s) from ${r.data?.provider || 'feed'}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function toggleFxAutoRefresh() {
    setError('');
    try {
      const next = !fxAutoRefresh;
      const r = await api('/credit/exchange-rates/settings', {
        method: 'PATCH',
        body: JSON.stringify({ fx_auto_refresh: next }),
      });
      setFxAutoRefresh(!!r.data?.fx_auto_refresh);
      setMessage(next ? 'Scheduled FX auto-refresh enabled' : 'Scheduled FX auto-refresh disabled');
    } catch (err: any) {
      setError(err.message);
    }
  }

  const parties = kind === 'receivable' ? customers : suppliers;
  const totals = report?.totals || {};

  return (
    <Shell>
      <h1>Credit & Aging</h1>
      <p className="muted">
        AR/AP aging, outstanding bills, statements, supplier payment schedule, payments, and
        early-payment discounts
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button onClick={() => setKindAndUrl('receivable')} disabled={kind === 'receivable'}>
          Receivables
        </button>
        <button onClick={() => setKindAndUrl('payable')} disabled={kind === 'payable'}>
          Payables
        </button>
      </div>

      <div className="grid">
        <div className="card" id="aging">
          <h3>Totals · {kind}</h3>
          <p className="muted">
            Document CSV via <code>GET /credit/aging/export?kind=</code> (Stage 136 A1).
          </p>
          <p>Current: {totals.current ?? 0}</p>
          <p>1–30: {totals['1_30'] ?? 0}</p>
          <p>31–60: {totals['31_60'] ?? 0}</p>
          <p>61–90: {totals['61_90'] ?? 0}</p>
          <p>90+: {totals['90_plus'] ?? 0}</p>
          <div className="kpi">{report?.total_due ?? 0}</div>
          <button
            type="button"
            style={{ marginTop: 8 }}
            onClick={() =>
              downloadCreditExport(
                `/credit/aging/export?kind=${encodeURIComponent(kind)}`,
                'credit_aging_export.csv',
                'Aging CSV downloaded (Stage 136 A1)',
              )
            }
          >
            Export aging CSV
          </button>
        </div>
        <div className="card" id="early-pay">
          <h3>Early payment terms</h3>
          <p className="muted">
            e.g. 2% if paid within 10 days (AR give / AP take). Export via{' '}
            <code>GET /credit/settings/export</code> (Stage 138 C1).
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              value={epPct}
              onChange={(e) => setEpPct(e.target.value)}
              placeholder="% discount"
              style={{ width: 90 }}
            />
            <input
              value={epDays}
              onChange={(e) => setEpDays(e.target.value)}
              placeholder="Days"
              style={{ width: 80 }}
            />
            <button onClick={saveEarlyPay}>Save terms</button>
            <button
              type="button"
              onClick={() =>
                downloadCreditExport(
                  '/credit/settings/export',
                  'early_pay_settings_export.csv',
                  'Early-pay settings CSV downloaded (Stage 138 C1)',
                )
              }
            >
              Export early-pay settings CSV
            </button>
          </div>
          <p className="muted" style={{ marginTop: 8 }}>
            Status: {epEnabled ? 'enabled' : 'disabled'}
          </p>
        </div>
        <div className="card" id="exchange-rates">
          <h3>Exchange rates</h3>
          <p className="muted">
            Base: {baseCurrency} — 1 foreign unit = rate × {baseCurrency}. Export via{' '}
            <code>GET /credit/exchange-rates/export</code> (Stage 127 F1).
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              value={fxCode}
              onChange={(e) => setFxCode(e.target.value.toUpperCase())}
              placeholder="USD"
              style={{ width: 70 }}
            />
            <input
              value={fxRate}
              onChange={(e) => setFxRate(e.target.value)}
              placeholder="Rate to base"
              style={{ width: 100 }}
            />
            <button onClick={saveFxRate}>Save rate</button>
            <button type="button" onClick={refreshFxFromFeed}>
              Refresh from feed
            </button>
            <button
              type="button"
              onClick={async () => {
                const token = localStorage.getItem('token') || '';
                const res = await fetch(`${apiBase}/credit/exchange-rates/export`, {
                  headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok) {
                  setError(await res.text());
                  return;
                }
                const blob = await res.blob();
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'exchange_rates_export.csv';
                a.click();
                URL.revokeObjectURL(a.href);
                setMessage('Exchange rates CSV downloaded');
              }}
            >
              Export FX rates CSV
            </button>
          </div>
          <label className="muted" style={{ display: 'block', marginTop: 8 }}>
            <input type="checkbox" checked={fxAutoRefresh} onChange={toggleFxAutoRefresh} />{' '}
            Auto-refresh via scheduled job
          </label>
          <ul style={{ marginTop: 8, paddingLeft: 18 }}>
            {fxRates.map((r: any) => (
              <li key={r.currency_code}>
                {r.currency_code}: {r.rate_to_base}
                {r.source ? ` · ${r.source}` : ''}
                {r.provider_fetched_at
                  ? ` · ${String(r.provider_fetched_at).replace('T', ' ').slice(0, 16)}`
                  : ''}{' '}
                <button type="button" onClick={() => removeFxRate(r.currency_code)}>
                  Remove
                </button>
              </li>
            ))}
            {!fxRates.length && <li className="muted">No foreign rates yet</li>}
          </ul>
        </div>
        <div className="card" id="party-actions">
          <h3>Party actions</h3>
          <select value={partyId} onChange={(e) => setPartyId(e.target.value)}>
            {parties.map((p: any) => (
              <option key={p.id} value={p.id}>
                {p.name} (bal {p.balance ?? 0})
              </option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <button type="button" onClick={loadOutstanding}>
              Outstanding
            </button>
            <button onClick={loadStatement}>Statement</button>
            {kind === 'payable' && (
              <button type="button" onClick={loadPaymentSchedule}>
                Payment schedule
              </button>
            )}
            <select
              value={allocateKey}
              onChange={(e) => setAllocateKey(e.target.value)}
              aria-label="Allocate payment to document"
              style={{ minWidth: 220 }}
              title="Leave as Auto to apply oldest open documents first"
            >
              <option value="">Auto — oldest open docs first</option>
              {openDocs.map((row) => {
                const key = docKey(row);
                if (!key) return null;
                return (
                  <option key={key} value={key}>
                    {docLabel(row)}
                  </option>
                );
              })}
            </select>
            <input
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              placeholder="Payment amount"
              style={{ width: 120 }}
            />
            <select value={payMethod} onChange={(e) => setPayMethod(e.target.value)}>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="card">Card</option>
              <option value="cheque">Cheque</option>
            </select>
            <select
              value={liquidAccountId}
              onChange={(e) => setLiquidAccountId(e.target.value)}
              title="Optional GL override"
            >
              <option value="">GL: method default</option>
              {liquidAccounts.map((a: any) => (
                <option key={a.id} value={a.id}>
                  {a.code} {a.name}
                </option>
              ))}
            </select>
            <input
              value={payFxRate}
              onChange={(e) => setPayFxRate(e.target.value)}
              placeholder="Settle FX rate"
              style={{ width: 110 }}
              title="Optional payment exchange rate (same currency as invoice)"
            />
            <button onClick={recordPayment}>Pay</button>
          </div>
          <p className="muted" style={{ marginTop: 6 }}>
            Allocate to a selected invoice/bill, or leave Auto for oldest-first. Click an outstanding
            row to select it.
          </p>
          {(kind === 'receivable' || kind === 'payable') && (
            <label className="muted" style={{ display: 'block', marginTop: 8 }}>
              <input
                type="checkbox"
                checked={applyEarly}
                onChange={(e) => setApplyEarly(e.target.checked)}
              />{' '}
              Apply early-payment discount when eligible
            </label>
          )}
          {kind === 'receivable' && (
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <input
                value={creditLimit}
                onChange={(e) => setCreditLimit(e.target.value)}
                placeholder="New credit limit"
                style={{ width: 140 }}
              />
              <button onClick={updateLimit}>Set limit</button>
            </div>
          )}
        </div>
      </div>

      <h3 style={{ marginTop: 16 }} id="by-party">
        By party
      </h3>
      <table className="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Total due</th>
            <th>Current</th>
            <th>1–30</th>
            <th>31–60</th>
            <th>61–90</th>
            <th>90+</th>
          </tr>
        </thead>
        <tbody>
          {(report?.parties || []).map((r: any) => (
            <tr key={r.party_id}>
              <td>{r.name}</td>
              <td>{r.total_due}</td>
              <td>{r.current}</td>
              <td>{r['1_30']}</td>
              <td>{r['31_60']}</td>
              <td>{r['61_90']}</td>
              <td>{r['90_plus']}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="card" style={{ marginTop: 16 }} id="payments">
        <h3>
          {kind === 'receivable' ? 'Customer' : 'Supplier'} payment register
        </h3>
        <p className="muted">
          Filter via <code>payment_method</code>; export via{' '}
          <code>
            /credit/{kind === 'receivable' ? 'customer' : 'supplier'}-payments/export
          </code>{' '}
          (Stage 136 {kind === 'receivable' ? 'C1' : 'S1'}).
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
          <select
            value={paymentMethodFilter || 'default'}
            onChange={(e) => {
              const v = e.target.value === 'default' ? '' : e.target.value;
              setPaymentMethodFilter(v);
              const url = new URL(window.location.href);
              if (v) url.searchParams.set('payment_method', v);
              else url.searchParams.delete('payment_method');
              const qs = url.searchParams.toString();
              window.history.replaceState(
                {},
                '',
                `${url.pathname}${qs ? `?${qs}` : ''}${url.hash}`,
              );
            }}
            aria-label="Payment method filter"
          >
            <option value="default">All methods</option>
            <option value="cash">cash</option>
            <option value="bank_transfer">bank_transfer</option>
            <option value="card">card</option>
            <option value="cheque">cheque</option>
            <option value="mobile_money">mobile_money</option>
            <option value="other">other</option>
          </select>
          <button
            type="button"
            onClick={() => {
              const qs = paymentMethodFilter
                ? `?payment_method=${encodeURIComponent(paymentMethodFilter)}`
                : '';
              const base =
                kind === 'receivable'
                  ? '/credit/customer-payments/export'
                  : '/credit/supplier-payments/export';
              downloadCreditExport(
                `${base}${qs}`,
                kind === 'receivable'
                  ? 'customer_payments_export.csv'
                  : 'supplier_payments_export.csv',
                kind === 'receivable'
                  ? 'Customer payments CSV downloaded (Stage 136 C1)'
                  : 'Supplier payments CSV downloaded (Stage 136 S1)',
              );
            }}
          >
            Export {kind === 'receivable' ? 'customer' : 'supplier'} payments CSV
          </button>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Party</th>
              <th>Method</th>
              <th>Amount</th>
              <th>Currency</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((p: any) => (
              <tr key={p.id}>
                <td>{p.payment_number}</td>
                <td>
                  {kind === 'receivable' ? p.customer_id : p.supplier_id}
                </td>
                <td>{p.payment_method}</td>
                <td>{p.amount}</td>
                <td>{p.currency || '—'}</td>
                <td>
                  {p.created_at
                    ? String(p.created_at).replace('T', ' ').slice(0, 16)
                    : '—'}
                </td>
              </tr>
            ))}
            {!payments.length && (
              <tr>
                <td colSpan={6} className="muted">
                  No payments in register
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {outstanding && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>
            Outstanding bills — {outstandingPartyName}{' '}
            <span className="muted">
              ({kind === 'receivable' ? 'AR' : 'AP'} · Σ{' '}
              {outstanding.reduce((s, row) => s + Number(row.amount || 0), 0).toFixed(2)})
            </span>
          </h3>
          <p className="muted" style={{ marginBottom: 8 }}>
            Document CSV via{' '}
            <code>
              GET /{kind === 'receivable' ? 'customers' : 'suppliers'}/&#123;id&#125;/outstanding/export
            </code>{' '}
            (Stage 141 O1).
          </p>
          <button
            type="button"
            style={{ marginBottom: 8 }}
            disabled={!partyId}
            onClick={() =>
              downloadCreditExport(
                kind === 'receivable'
                  ? `/customers/${partyId}/outstanding/export`
                  : `/suppliers/${partyId}/outstanding/export`,
                kind === 'receivable'
                  ? 'customer_outstanding_export.csv'
                  : 'supplier_outstanding_export.csv',
                'Outstanding bills CSV downloaded (Stage 141 O1)',
              )
            }
          >
            Export outstanding CSV
          </button>
          <table className="table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Type</th>
                <th>Due</th>
                <th>Status</th>
                <th>Amount</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {outstanding.map((row: any, idx: number) => {
                const key = docKey(row);
                const selected = key && key === allocateKey;
                return (
                  <tr
                    key={key || `out-${idx}`}
                    style={selected ? { background: 'rgba(16, 185, 129, 0.12)' } : undefined}
                  >
                    <td>
                      {row.invoice_number || row.po_number || row.purchase_invoice_id || '—'}
                    </td>
                    <td className="muted">
                      {row.document_type || (kind === 'receivable' ? 'sales_invoice' : '—')}
                    </td>
                    <td>
                      {row.due_date ? String(row.due_date).replace('T', ' ').slice(0, 10) : '—'}
                    </td>
                    <td>{row.status}</td>
                    <td>{row.amount}</td>
                    <td>
                      {key ? (
                        <button
                          type="button"
                          onClick={() => {
                            setAllocateKey(key);
                            setPayAmount(String(row.amount ?? ''));
                          }}
                        >
                          {selected ? 'Selected' : 'Allocate'}
                        </button>
                      ) : (
                        '—'
                      )}
                    </td>
                  </tr>
                );
              })}
              {!outstanding.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No outstanding bills
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="card" style={{ marginTop: 16 }} id="statement">
        <h3>Statement</h3>
        {statement ? (
          <>
            <p className="muted" style={{ marginBottom: 8 }}>
              Line CSV via{' '}
              <code>
                GET /credit/{kind === 'receivable' ? 'customers' : 'suppliers'}
                /&#123;id&#125;/statement/export
              </code>{' '}
              (Stage 141 T1).
            </p>
            <button
              type="button"
              style={{ marginBottom: 8 }}
              disabled={!partyId}
              onClick={() =>
                downloadCreditExport(
                  kind === 'receivable'
                    ? `/credit/customers/${partyId}/statement/export`
                    : `/credit/suppliers/${partyId}/statement/export`,
                  kind === 'receivable'
                    ? 'customer_statement_export.csv'
                    : 'supplier_statement_export.csv',
                  'Statement CSV downloaded (Stage 141 T1)',
                )
              }
            >
              Export statement CSV
            </button>
            <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
              {JSON.stringify(statement, null, 2)}
            </pre>
          </>
        ) : (
          <p className="muted">Select a party and load statement from Party actions.</p>
        )}
      </div>

      <div className="card" style={{ marginTop: 16 }} id="payment-schedule">
        <h3>
          Payment schedule
          {kind === 'payable' && paymentSchedule ? (
            <>
              {' '}
              — {paymentSchedule.supplier_name}{' '}
              <span className="muted">
                (as of {paymentSchedule.as_of} · due {paymentSchedule.total_due} · overdue{' '}
                {paymentSchedule.overdue_total})
              </span>
            </>
          ) : null}
        </h3>
        {kind !== 'payable' ? (
          <p className="muted">Switch to Payables to load a supplier payment schedule.</p>
        ) : paymentSchedule ? (
          <>
            <p className="muted" style={{ marginBottom: 8 }}>
              Schedule CSV via <code>GET /suppliers/&#123;id&#125;/payment-schedule/export</code>{' '}
              (Stage 141 P1; optional <code>schedule_bucket=</code>).
            </p>
            <button
              type="button"
              style={{ marginBottom: 8 }}
              disabled={!partyId}
              onClick={() =>
                downloadCreditExport(
                  `/suppliers/${partyId}/payment-schedule/export`,
                  'supplier_payment_schedule_export.csv',
                  'Payment schedule CSV downloaded (Stage 141 P1)',
                )
              }
            >
              Export schedule CSV
            </button>
            <table className="table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Due</th>
                <th>Amount</th>
                <th>Bucket</th>
                <th>Early discount</th>
              </tr>
            </thead>
            <tbody>
              {(paymentSchedule.items || []).map((item: any, idx: number) => (
                <tr key={`${item.document_type}-${item.purchase_invoice_id || item.purchase_order_id}-${idx}`}>
                  <td>
                    {item.document_type === 'purchase_invoice'
                      ? item.invoice_number
                      : item.po_number}{' '}
                    <span className="muted">({item.document_type})</span>
                  </td>
                  <td>
                    {item.due_date
                      ? String(item.due_date).replace('T', ' ').slice(0, 10)
                      : '—'}
                    {item.days_until_due != null ? (
                      <span className="muted">
                        {' '}
                        ({item.days_until_due < 0
                          ? `${Math.abs(item.days_until_due)}d overdue`
                          : item.days_until_due === 0
                            ? 'today'
                            : `in ${item.days_until_due}d`}
                        )
                      </span>
                    ) : null}
                  </td>
                  <td>{item.amount}</td>
                  <td>{item.schedule_bucket}</td>
                  <td>
                    {item.early_discount?.eligible
                      ? `${item.early_discount.discount_amount} → pay ${item.early_discount.cash_to_settle}`
                      : '—'}
                  </td>
                </tr>
              ))}
              {!paymentSchedule.items?.length && (
                <tr>
                  <td colSpan={5} className="muted">
                    No open bills on the schedule
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </>
        ) : (
          <p className="muted">Select a supplier and load schedule from Party actions.</p>
        )}
      </div>
    </Shell>
  );
}
