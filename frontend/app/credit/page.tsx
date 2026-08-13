'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

export default function Page() {
  const [kind, setKind] = useState<'receivable' | 'payable'>('receivable');
  const [report, setReport] = useState<any>(null);
  const [customers, setCustomers] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [partyId, setPartyId] = useState('');
  const [statement, setStatement] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [creditInfo, setCreditInfo] = useState<any>(null);
  const [schedule, setSchedule] = useState<any>(null);
  const [payAmount, setPayAmount] = useState('');
  const [payMethod, setPayMethod] = useState('cash');
  const [liquidAccountId, setLiquidAccountId] = useState('');
  const [liquidAccounts, setLiquidAccounts] = useState<any[]>([]);
  const [creditLimit, setCreditLimit] = useState('');
  const [paymentTermsDays, setPaymentTermsDays] = useState('30');
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

  async function refresh() {
    const [aging, cust, supp, settings, liquid, fx] = await Promise.all([
      api(`/credit/aging?kind=${kind}`),
      api('/customers'),
      api('/suppliers'),
      api('/credit/settings'),
      api('/accounting/liquid-accounts').catch(() => ({ data: [] })),
      api('/credit/exchange-rates').catch(() => ({ data: { base_currency: 'GHS', rates: [] } })),
    ]);
    setReport(aging.data);
    setCustomers(cust.data || []);
    setSuppliers(supp.data || []);
    setLiquidAccounts(liquid.data || []);
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

  useEffect(() => {
    setSchedule(null);
    setHistory(null);
    setStatement(null);
    setCreditInfo(null);
    refresh().catch((err) => setError(err.message));
  }, [kind]);

  useEffect(() => {
    const list = kind === 'receivable' ? customers : suppliers;
    const p = list.find((x) => x.id === partyId);
    if (!p) return;
    setPaymentTermsDays(String(p.payment_terms_days ?? 30));
    if (kind === 'receivable') {
      setCreditLimit(String(p.credit_limit ?? 0));
    }
  }, [partyId, customers, suppliers, kind]);

  async function loadStatement() {
    if (!partyId) return;
    setError('');
    try {
      const path =
        kind === 'receivable'
          ? `/credit/customers/${partyId}/statement`
          : `/credit/suppliers/${partyId}/statement`;
      const r = await api(path);
      setStatement(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadHistory() {
    if (!partyId) return;
    setError('');
    try {
      const path =
        kind === 'receivable'
          ? `/customers/${partyId}/history`
          : `/suppliers/${partyId}/history`;
      const r = await api(path);
      setHistory(r.data);
      const s = r.data?.summary;
      setMessage(
        `History: ${s?.purchase_count ?? 0} purchases · ${s?.return_count ?? 0} returns · ${s?.payment_count ?? 0} payments`,
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadCreditInfo() {
    if (!partyId) return;
    setError('');
    try {
      const path =
        kind === 'receivable'
          ? `/customers/${partyId}/credit`
          : `/suppliers/${partyId}/credit`;
      const r = await api(path);
      setCreditInfo(r.data);
      if (kind === 'receivable') {
        setMessage(
          `Credit: balance ${r.data?.outstanding_balance ?? 0} · limit ${
            r.data?.credit_unlimited ? 'unlimited' : r.data?.credit_limit ?? 0
          } · available ${r.data?.available_credit ?? '—'}`,
        );
      } else {
        setMessage(
          `Payable balance ${r.data?.outstanding_balance ?? 0} · open bills ${r.data?.open_bill_count ?? 0}`,
        );
      }
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadPaymentSchedule() {
    if (!partyId || kind !== 'payable') return;
    setError('');
    try {
      const r = await api(`/suppliers/${partyId}/payment-schedule`);
      setSchedule(r.data);
      setMessage(
        `Payment schedule: ${r.data?.upcoming_count ?? 0} upcoming · ${r.data?.overdue_count ?? 0} overdue · total ${r.data?.total_due ?? 0}`,
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function recordPayment() {
    if (!partyId || !payAmount) return;
    setError('');
    try {
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
          }),
        });
      }
      setMessage(
        applyEarly && epEnabled
          ? 'Payment recorded (early discount applied when eligible)'
          : 'Payment recorded (oldest open docs first)',
      );
      setPayAmount('');
      await refresh();
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
        body: JSON.stringify({
          credit_limit: Number(creditLimit) || 0,
          payment_terms_days: Number(paymentTermsDays) || 0,
        }),
      });
      setMessage('Credit limit and payment terms updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function updateSupplierTerms() {
    if (!partyId || kind !== 'payable') return;
    setError('');
    try {
      await api(`/suppliers/${partyId}`, {
        method: 'PATCH',
        body: JSON.stringify({ payment_terms_days: Number(paymentTermsDays) || 0 }),
      });
      setMessage('Supplier payment terms updated');
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
        AR/AP aging, statements, payments, and early-payment discounts. Over-limit credit sales are
        blocked unless a user with <code>credit:approve</code> (store manager / accountant / admin)
        confirms an override on Sales invoice post or POS checkout.
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <button onClick={() => setKind('receivable')} disabled={kind === 'receivable'}>
          Receivables
        </button>
        <button onClick={() => setKind('payable')} disabled={kind === 'payable'}>
          Payables
        </button>
      </div>

      <div className="grid">
        <div className="card">
          <h3>Totals · {kind}</h3>
          <p>Current: {totals.current ?? 0}</p>
          <p>1–30: {totals['1_30'] ?? 0}</p>
          <p>31–60: {totals['31_60'] ?? 0}</p>
          <p>61–90: {totals['61_90'] ?? 0}</p>
          <p>90+: {totals['90_plus'] ?? 0}</p>
          <div className="kpi">{report?.total_due ?? 0}</div>
        </div>
        <div className="card">
          <h3>Early payment terms</h3>
          <p className="muted">e.g. 2% if paid within 10 days (AR give / AP take)</p>
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
          </div>
          <p className="muted" style={{ marginTop: 8 }}>
            Status: {epEnabled ? 'enabled' : 'disabled'}
          </p>
        </div>
        <div className="card">
          <h3>Exchange rates</h3>
          <p className="muted">
            Base: {baseCurrency} — 1 foreign unit = rate × {baseCurrency}
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
        <div className="card">
          <h3>Party actions</h3>
          <select value={partyId} onChange={(e) => setPartyId(e.target.value)}>
            {parties.map((p: any) => (
              <option key={p.id} value={p.id}>
                {p.name} (bal {p.balance ?? 0}
                {p.payment_terms_days != null ? ` · Net ${p.payment_terms_days}` : ''})
              </option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            <button onClick={loadStatement}>Statement</button>
            <button type="button" onClick={loadCreditInfo}>
              Balance
            </button>
            <button type="button" onClick={loadHistory}>
              History
            </button>
            {kind === 'payable' && (
              <button type="button" onClick={loadPaymentSchedule}>
                Payment schedule
              </button>
            )}
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
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <input
                value={creditLimit}
                onChange={(e) => setCreditLimit(e.target.value)}
                placeholder="New credit limit"
                style={{ width: 140 }}
              />
              <input
                value={paymentTermsDays}
                onChange={(e) => setPaymentTermsDays(e.target.value)}
                placeholder="Net days"
                style={{ width: 90 }}
                title="Payment terms (days)"
              />
              <button onClick={updateLimit}>Set limit / terms</button>
            </div>
          )}
          {kind === 'payable' && (
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <input
                value={paymentTermsDays}
                onChange={(e) => setPaymentTermsDays(e.target.value)}
                placeholder="Net days"
                style={{ width: 90 }}
                title="Supplier payment terms (days)"
              />
              <button type="button" onClick={updateSupplierTerms}>
                Set terms
              </button>
            </div>
          )}
        </div>
      </div>

      <h3 style={{ marginTop: 16 }}>By party</h3>
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

      {statement && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Statement</h3>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>
            {JSON.stringify(statement, null, 2)}
          </pre>
        </div>
      )}

      {creditInfo && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>
            Balance · {creditInfo.customer?.name || creditInfo.supplier?.name}
          </h3>
          <div className="grid">
            <div>
              <div className="muted">Outstanding</div>
              <div className="kpi">{creditInfo.outstanding_balance ?? 0}</div>
            </div>
            {creditInfo.customer && (
              <>
                <div>
                  <div className="muted">Credit limit</div>
                  <div className="kpi">
                    {creditInfo.credit_unlimited ? 'Unlimited' : creditInfo.credit_limit ?? 0}
                  </div>
                </div>
                <div>
                  <div className="muted">Available</div>
                  <div className="kpi">{creditInfo.available_credit ?? '—'}</div>
                  {creditInfo.is_over_limit && (
                    <p style={{ color: '#b91c1c' }}>Over limit</p>
                  )}
                </div>
              </>
            )}
            {creditInfo.supplier && (
              <div>
                <div className="muted">Open bills</div>
                <div className="kpi">{creditInfo.open_bill_count ?? 0}</div>
                <p className="muted">Total {creditInfo.open_bill_total ?? 0}</p>
              </div>
            )}
          </div>
          {(creditInfo.credit_sales || creditInfo.open_bills || []).length > 0 && (
            <table className="table" style={{ marginTop: 12 }}>
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Status</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {(creditInfo.credit_sales || []).map((row: any) => (
                  <tr key={row.invoice_id}>
                    <td>{row.invoice_number}</td>
                    <td>{row.status}</td>
                    <td>{row.amount}</td>
                  </tr>
                ))}
                {(creditInfo.open_bills || []).map((row: any) => (
                  <tr key={row.purchase_invoice_id || row.purchase_order_id}>
                    <td>{row.invoice_number || row.po_number}</td>
                    <td>{row.status}</td>
                    <td>{row.amount}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {history && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>
            History · {history.customer?.name || history.supplier?.name} · purchases{' '}
            {history.summary?.purchase_total ?? 0} · returns {history.summary?.return_total ?? 0} ·
            payments {history.summary?.payment_total ?? 0}
          </h3>
          <h4 style={{ marginTop: 12 }}>Purchases</h4>
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Reference</th>
                <th>Status</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(history.purchases || []).map((p: any) => (
                <tr key={`${p.type}-${p.id}`}>
                  <td>{p.type}</td>
                  <td>{p.reference}</td>
                  <td>{p.status}</td>
                  <td>{p.total_amount}</td>
                </tr>
              ))}
              {!history.purchases?.length && (
                <tr>
                  <td colSpan={4} className="muted">
                    No purchases
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <h4 style={{ marginTop: 12 }}>Returns</h4>
          <table className="table">
            <thead>
              <tr>
                <th>Return</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(history.returns || []).map((r: any) => (
                <tr key={r.id}>
                  <td>{r.return_number}</td>
                  <td>{r.reason}</td>
                  <td>{r.status}</td>
                  <td>{r.total_amount}</td>
                </tr>
              ))}
              {!history.returns?.length && (
                <tr>
                  <td colSpan={4} className="muted">
                    No returns
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <h4 style={{ marginTop: 12 }}>Payments</h4>
          <table className="table">
            <thead>
              <tr>
                <th>Payment</th>
                <th>Method</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(history.payments || []).map((p: any) => (
                <tr key={p.id}>
                  <td>{p.payment_number}</td>
                  <td>{p.payment_method}</td>
                  <td>{p.amount}</td>
                </tr>
              ))}
              {!history.payments?.length && (
                <tr>
                  <td colSpan={3} className="muted">
                    No payments
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {kind === 'payable' && schedule && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>
            Payment schedule · {schedule.supplier?.name} · total {schedule.total_due}
          </h3>
          <p className="muted" style={{ marginTop: 0 }}>
            Upcoming {schedule.upcoming_count} · overdue {schedule.overdue_count}
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Due</th>
                <th>Document</th>
                <th>Type</th>
                <th>Status</th>
                <th>Balance</th>
                <th>Days</th>
                <th>Early disc.</th>
              </tr>
            </thead>
            <tbody>
              {(schedule.items || []).map((row: any) => (
                <tr key={`${row.document_type}-${row.id}`}>
                  <td>
                    {row.due_date
                      ? String(row.due_date).replace('T', ' ').slice(0, 10)
                      : '—'}
                  </td>
                  <td>{row.document_number}</td>
                  <td>{row.document_type === 'purchase_invoice' ? 'Bill' : 'PO'}</td>
                  <td>{row.status}</td>
                  <td>{row.balance_due}</td>
                  <td>
                    {row.days_until_due == null
                      ? '—'
                      : row.days_until_due < 0
                        ? `${Math.abs(row.days_until_due)} overdue`
                        : `${row.days_until_due} left`}
                  </td>
                  <td>
                    {row.early_discount
                      ? `${row.early_discount.discount_amount} → ${row.early_discount.cash_to_settle}`
                      : '—'}
                  </td>
                </tr>
              ))}
              {!schedule.items?.length && (
                <tr>
                  <td colSpan={7} className="muted">
                    No open supplier bills or uninvoiced POs
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </Shell>
  );
}
