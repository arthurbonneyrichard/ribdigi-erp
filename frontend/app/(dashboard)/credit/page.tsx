'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '../../../lib/api';
import { formatWhen, plainLabel } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';

function retryAfterFrom(raw: unknown): number {
  const n = Number((raw as { retryAfter?: number })?.retryAfter);
  return Number.isFinite(n) && n > 0 ? Math.min(60, Math.ceil(n)) : 0;
}

function friendlyCreditError(raw: unknown): string {
  const status = (raw as { status?: number })?.status;
  const m = String((raw as { message?: string })?.message || raw || 'Something went wrong. Try again.');
  if (status === 429 || /too many requests|rate limit/i.test(m)) {
    return 'Could not load supplier or customer balances. Wait for the cooldown, then retry.';
  }
  if (/must be positive|payment amount/i.test(m)) return 'Enter an amount greater than zero.';
  if (/select a supplier|supplier not found|customer not found/i.test(m)) {
    return 'Select a supplier or customer first.';
  }
  if (/cannot reach|failed to fetch/i.test(m)) return 'Cannot reach the server. Try again in a moment.';
  return m;
}

function CreateCreditForm({
  customers,
  onCreated,
  onError,
  onMessage,
}: {
  customers: { id: string; name: string }[];
  onCreated: () => void;
  onError: (msg: string) => void;
  onMessage: (msg: string) => void;
}) {
  const [customerId, setCustomerId] = useState('');
  const [products, setProducts] = useState<{ id: string; name: string; selling_price?: number }[]>([]);
  const [productId, setProductId] = useState('');
  const [qty, setQty] = useState('1');
  const [price, setPrice] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api('/products?limit=50')
      .then((r) => setProducts(r.data || []))
      .catch(() => setProducts([]));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    onError('');
    onMessage('');
    setBusy(true);
    try {
      const created = await api('/sales/invoices', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: customerId,
          notes: notes.trim() || null,
          items: [
            {
              product_id: productId,
              quantity: Number(qty),
              unit_price: Number(price),
            },
          ],
        }),
      });
      await api(`/sales/invoices/${created.data.id}/post`, { method: 'POST', body: '{}' });
      onMessage('Credit invoice posted. It stays unpaid until a payment is recorded.');
      setNotes('');
      onCreated();
    } catch (err) {
      onError(friendlyCreditError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="erp-form-grid">
      <p className="muted">
        Posts an invoice the customer still owes. Recording a payment is a separate step.
      </p>
      <label>
        Customer
        <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} required aria-label="Credit customer">
          <option value="">Select</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </label>
      <label>
        Product
        <select
          value={productId}
          onChange={(e) => {
            setProductId(e.target.value);
            const row = products.find((p) => p.id === e.target.value);
            if (row && price === '') setPrice(String(row.selling_price ?? ''));
          }}
          required
          aria-label="Credit product"
        >
          <option value="">Select</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </label>
      <label>
        Quantity
        <input value={qty} onChange={(e) => setQty(e.target.value)} type="number" min="0.001" step="0.001" required aria-label="Credit quantity" />
      </label>
      <label>
        Price
        <input value={price} onChange={(e) => setPrice(e.target.value)} type="number" min="0" step="0.01" required aria-label="Credit price" />
      </label>
      <label>
        Notes
        <input value={notes} onChange={(e) => setNotes(e.target.value)} aria-label="Credit notes" />
      </label>
      <button type="submit" disabled={busy}>Create credit</button>
    </form>
  );
}

export default function Page() {
  useCompanyFormat();
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlKind = searchParams.get('kind') === 'payable' ? 'payable' : 'receivable';
  const [kind, setKind] = useState<'receivable' | 'payable'>(urlKind);
  const [report, setReport] = useState<any>(null);
  const [customers, setCustomers] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [partyId, setPartyId] = useState('');
  const [statement, setStatement] = useState<any>(null);
  const [history, setHistory] = useState<any>(null);
  const [histFromDate, setHistFromDate] = useState('');
  const [histToDate, setHistToDate] = useState('');
  const [creditInfo, setCreditInfo] = useState<any>(null);
  const [schedule, setSchedule] = useState<any>(null);
  const [payAmount, setPayAmount] = useState('');
  const [payMethod, setPayMethod] = useState('cash');
  const [payReference, setPayReference] = useState('');
  const [payNotes, setPayNotes] = useState('');
  const [payChequeNumber, setPayChequeNumber] = useState('');
  const [payChequeBankName, setPayChequeBankName] = useState('');
  const [payChequeDate, setPayChequeDate] = useState('');
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
  const [payBusy, setPayBusy] = useState(false);
  const [limitBusy, setLimitBusy] = useState(false);
  const [loadState, setLoadState] = useState<'loading' | 'success' | 'empty' | 'error'>('loading');
  const [retryAfterSec, setRetryAfterSec] = useState(0);
  const refreshInflight = useRef<Promise<void> | null>(null);

  async function refresh() {
    if (refreshInflight.current) return refreshInflight.current;
    setLoadState('loading');
    setError('');
    const run = (async () => {
      try {
        const aging = await api(`/credit/aging?kind=${kind}`);
        const [cust, supp, settings, liquid, fx] = await Promise.all([
          api('/customers').catch(() => ({ data: [] })),
          api('/suppliers').catch(() => ({ data: [] })),
          api('/credit/settings').catch(() => ({ data: {} })),
          api('/accounting/liquid-accounts').catch(() => ({ data: [] })),
          api('/credit/exchange-rates').catch(() => ({ data: { base_currency: 'GHS', rates: [] } })),
        ]);
        const data = aging.data;
        setReport(data);
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
        const due = Number(data?.total_due || 0);
        const docs = data?.documents || [];
        const parties = data?.parties || [];
        setLoadState(due === 0 && docs.length === 0 && parties.length === 0 ? 'empty' : 'success');
      } catch (err) {
        setReport(null);
        setLoadState('error');
        const wait = retryAfterFrom(err);
        if (wait) setRetryAfterSec(wait);
        throw err;
      }
    })().finally(() => {
      refreshInflight.current = null;
    });
    refreshInflight.current = run;
    return run;
  }

  useEffect(() => {
    if (urlKind !== kind) {
      setKind(urlKind);
      return;
    }
    setSchedule(null);
    setHistory(null);
    setStatement(null);
    setCreditInfo(null);
    refresh().catch((err) => setError(friendlyCreditError(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, urlKind]);

  useEffect(() => {
    if (retryAfterSec <= 0) return;
    const id = window.setTimeout(() => setRetryAfterSec((s) => Math.max(0, s - 1)), 1000);
    return () => window.clearTimeout(id);
  }, [retryAfterSec]);

  function selectKind(next: 'receivable' | 'payable') {
    if (next === 'receivable') setKind('receivable');
    else setKind('payable');
    const panel = next === 'payable' ? searchParams.get('panel') : null;
    const qs = new URLSearchParams();
    qs.set('kind', next);
    if (next === 'payable' && panel === 'pay') qs.set('panel', 'pay');
    router.replace(`/credit?${qs.toString()}`, { scroll: false });
  }

  useEffect(() => {
    const list = kind === 'receivable' ? customers : suppliers;
    const p = list.find((x) => x.id === partyId);
    if (!p) return;
    setPaymentTermsDays(String(p.payment_terms_days ?? 30));
    if (kind === 'receivable') {
      setCreditLimit(String(p.credit_limit ?? 0));
    }
  }, [partyId, customers, suppliers, kind]);

  useEffect(() => {
    if (!partyId) return;
    if (loadState === 'loading' || loadState === 'error') return;
    loadCreditInfo().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partyId, kind, loadState]);

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
      setError(friendlyCreditError(err));
    }
  }

  async function loadHistory() {
    if (!partyId) return;
    setError('');
    try {
      const params = new URLSearchParams();
      if (histFromDate) params.set('from_date', histFromDate);
      if (histToDate) params.set('to_date', histToDate);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const path =
        kind === 'receivable'
          ? `/customers/${partyId}/history${qs}`
          : `/suppliers/${partyId}/history${qs}`;
      const r = await api(path);
      setHistory(r.data);
      const s = r.data?.summary;
      setMessage(
        `History: ${s?.purchase_count ?? 0} purchases · ${s?.return_count ?? 0} returns · ${s?.payment_count ?? 0} payments`,
      );
    } catch (err: any) {
      setError(friendlyCreditError(err));
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
      setError(friendlyCreditError(err));
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
      setError(friendlyCreditError(err));
    }
  }

  async function recordPayment() {
    if (!partyId || !payAmount || payBusy) return;
    setError('');
    setPayBusy(true);
    try {
      const chequeFields =
        payMethod === 'cheque'
          ? {
              // Blank → null so Pay does not 422 (ChequeNumberValue / BankNameValue / IsoDateQueryValue).
              cheque_number: payChequeNumber.trim() || null,
              bank_name: payChequeBankName.trim() || null,
              cheque_date: payChequeDate.trim() || null,
            }
          : {};
      if (kind === 'receivable') {
        await api(`/customers/${partyId.trim()}/payments`, {
          method: 'POST',
          body: JSON.stringify({
            // trim so Record payment (UuidIdValue customer_id) does not 422 on whitespace
            customer_id: partyId.trim(),
            amount: Number(payAmount),
            payment_method: payMethod,
            reference: payReference.trim() || null,
            notes: payNotes.trim() || null,
            apply_early_discount: applyEarly,
            liquid_account_id: liquidAccountId.trim() || null,
            exchange_rate: payFxRate === '' ? null : Number(payFxRate),
            ...chequeFields,
          }),
        });
      } else {
        await api(`/suppliers/${partyId.trim()}/payments`, {
          method: 'POST',
          body: JSON.stringify({
            // trim so Record payment (UuidIdValue supplier_id) does not 422 on whitespace
            supplier_id: partyId.trim(),
            amount: Number(payAmount),
            payment_method: payMethod === 'cash' ? 'bank_transfer' : payMethod,
            reference: payReference.trim() || null,
            notes: payNotes.trim() || null,
            apply_early_discount: applyEarly,
            // null when blank so Pay (UuidIdValue liquid_account_id) does not 422
            liquid_account_id: liquidAccountId.trim() || null,
            exchange_rate: payFxRate === '' ? null : Number(payFxRate),
            ...chequeFields,
          }),
        });
      }
      setMessage(
        applyEarly && epEnabled
          ? 'Payment recorded (early discount applied when eligible)'
          : 'Payment recorded (oldest open docs first)',
      );
      setPayAmount('');
      setPayReference('');
      setPayNotes('');
      setPayChequeNumber('');
      setPayChequeBankName('');
      setPayChequeDate('');
      await refresh();
      await loadStatement();
      await loadCreditInfo();
    } catch (err: any) {
      setError(friendlyCreditError(err));
    } finally {
      setPayBusy(false);
    }
  }

  async function updateLimit() {
    if (!partyId || kind !== 'receivable' || limitBusy) return;
    setError('');
    setLimitBusy(true);
    try {
      await api(`/customers/${partyId}/credit-limit`, {
        method: 'PATCH',
        body: JSON.stringify({
          credit_limit: Number(creditLimit) || 0,
          payment_terms_days: Number(paymentTermsDays) || 0,
        }),
      });
      setMessage('Customer credit limit and payment terms updated');
      await refresh();
    } catch (err: any) {
      setError(friendlyCreditError(err));
    } finally {
      setLimitBusy(false);
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
      setError(friendlyCreditError(err));
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
      setError(friendlyCreditError(err));
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
      setError(friendlyCreditError(err));
    }
  }

  async function removeFxRate(code: string) {
    setError('');
    try {
      await api(`/credit/exchange-rates/${code}`, { method: 'DELETE' });
      setMessage(`Removed ${code}`);
      await refresh();
    } catch (err: any) {
      setError(friendlyCreditError(err));
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
      setError(friendlyCreditError(err));
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
      setError(friendlyCreditError(err));
    }
  }

  const parties = kind === 'receivable' ? customers : suppliers;
  const totals = report?.totals || {};
  const payPanel = kind === 'payable' && searchParams.get('panel') === 'pay';
  const dueOf = (id: string) => {
    const row = (report?.parties || []).find((x: { party_id?: string }) => x.party_id === id);
    return row?.total_due ?? 0;
  };

  function selectPayableView(panel?: 'pay') {
    setKind('payable');
    const qs = new URLSearchParams();
    qs.set('kind', 'payable');
    if (panel === 'pay') qs.set('panel', 'pay');
    router.replace(`/credit?${qs.toString()}`, { scroll: false });
  }

  const balancesOk = loadState === 'success' || loadState === 'empty';
  const overdueAmt = balancesOk ? (report?.overdue_total ?? 0) : null;
  const notDueAmt = balancesOk ? (report?.not_yet_due_total ?? report?.totals?.current ?? 0) : null;
  const weOweAmt = balancesOk ? (report?.total_due ?? 0) : null;

  return (
    <div className="credit-page work">
      <div className="list-page-head">
        <div>
      <h1>
        {kind === 'receivable'
          ? 'Customer credit'
          : payPanel
            ? 'Supplier payments'
            : 'Supplier balances'}
      </h1>
      <p className="muted">
        {kind === 'receivable'
          ? 'Money customers still owe. Record a payment here. New sales on credit are created under Sales or Point of sale.'
          : payPanel
            ? 'Pay an open supplier bill. This records money going out. It does not create a new bill.'
            : 'What this company still owes suppliers. Purchase orders are listed separately until a bill is posted.'}
      </p>
        </div>
      </div>
      {error && (
        <p className="erp-banner err" role="alert">
          {error}{' '}
          <button
            type="button"
            disabled={loadState === 'loading' || retryAfterSec > 0}
            onClick={() => {
              if (loadState === 'loading' || retryAfterSec > 0) return;
              setError('');
              refresh().catch((err) => setError(friendlyCreditError(err)));
            }}
            aria-label="Retry credit data"
          >
            {loadState === 'loading' ? 'Loading…' : retryAfterSec > 0 ? `Retry in ${retryAfterSec}s` : 'Retry'}
          </button>
        </p>
      )}
      {loadState === 'loading' ? <p className="muted">Loading balances…</p> : null}
      {message && <p className="erp-banner ok" role="status">{message}</p>}

      <div className="erp-tabs">
        <button
          onClick={() => selectKind('receivable')}
          disabled={kind === 'receivable'}
          aria-label="Show receivables aging"
        >
          Customers owe us
        </button>
        <button
          onClick={() => selectPayableView()}
          disabled={kind === 'payable' && !payPanel}
          aria-label="Show payables aging"
        >
          We owe suppliers
        </button>
        <button
          onClick={() => selectPayableView('pay')}
          disabled={payPanel}
          aria-label="Show supplier payments"
        >
          Pay
        </button>
      </div>

      <div className="erp-kpis credit-kpis">
        <div className="card">
          <div className="muted">{kind === 'receivable' ? 'Customer balance' : 'We owe'}</div>
          <div className="kpi">{loadState === 'loading' ? '…' : loadState === 'error' ? 'Unavailable' : weOweAmt}</div>
        </div>
        <div className="card">
          <div className="muted">Overdue</div>
          <div className="kpi">{loadState === 'loading' ? '…' : loadState === 'error' ? 'Unavailable' : overdueAmt}</div>
        </div>
        <div className="card">
          <div className="muted">Not yet due</div>
          <div className="kpi">{loadState === 'loading' ? '…' : loadState === 'error' ? 'Unavailable' : notDueAmt}</div>
        </div>
      </div>
      {kind === 'payable' && loadState === 'success' && Number(report?.commitment_total || 0) > 0 ? (
        <p className="muted credit-commitments" role="status">
          Open purchase orders (not yet billed): {report.commitment_total}
        </p>
      ) : null}

      <div className="erp-split credit-bill-info">
        <div className="card credit-compact-card">
          <h3>{kind === 'receivable' ? 'Create credit' : 'New supplier bill'}</h3>
          {kind === 'receivable' ? (
            <CreateCreditForm customers={customers} onCreated={() => refresh()} onError={setError} onMessage={setMessage} />
          ) : (
            <>
          <p className="muted">
            Open Purchases to record a supplier bill. That increases what the company owes. This page only records money going out.
          </p>
          <a href="/purchasing?tab=invoices">
            <button type="button">Go to Purchases</button>
          </a>
            </>
          )}
        </div>
        <div className="card">
          <h3>Aging</h3>
          {loadState === 'error' ? (
            <p className="muted">Aging is unavailable until balances load.</p>
          ) : (
            <div className="work-facts">
              <span><small>Not yet due</small><strong>{totals.current ?? 0}</strong></span>
              <span><small>1–30 days</small><strong>{totals['1_30'] ?? 0}</strong></span>
              <span><small>31–60 days</small><strong>{totals['31_60'] ?? 0}</strong></span>
              <span><small>61–90 days</small><strong>{totals['61_90'] ?? 0}</strong></span>
              <span><small>90+ days</small><strong>{totals['90_plus'] ?? 0}</strong></span>
            </div>
          )}
        </div>
      </div>

      <details className="erp-advanced">
        <summary>Early-pay discount and exchange rates</summary>
        <div className="erp-split" style={{ marginTop: 8 }}>
        <div className="card">
          <h3>Early payment terms</h3>
          <p className="muted">For example, 2% off if the bill is paid within 10 days.</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              value={epPct}
              onChange={(e) => setEpPct(e.target.value)}
              placeholder="% discount"
              aria-label="Early pay discount percent"
              style={{ width: 90 }}
            />
            <input
              value={epDays}
              onChange={(e) => setEpDays(e.target.value)}
              placeholder="Days"
              aria-label="Early pay discount days"
              style={{ width: 80 }}
            />
            <button onClick={saveEarlyPay} aria-label="Save early pay terms">
              Save terms
            </button>
          </div>
          <p className="muted" style={{ marginTop: 8 }}>
            Status: {epEnabled ? 'On' : 'Off'}
          </p>
        </div>
        <div className="card">
          <h3>Exchange rates</h3>
          <p className="muted">
            Company currency is {baseCurrency}. The rate is how many {baseCurrency} equal 1 unit of the other currency.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              value={fxCode}
              onChange={(e) => setFxCode(e.target.value.toUpperCase())}
              placeholder="USD"
              maxLength={3}
              style={{ width: 70 }}
              aria-label="FX currency code"
            />
            <input
              value={fxRate}
              onChange={(e) => setFxRate(e.target.value)}
              placeholder="Rate to base"
              style={{ width: 100 }}
              aria-label="FX rate to base"
            />
            <button onClick={saveFxRate} aria-label="Save FX rate">
              Save rate
            </button>
            <button type="button" onClick={refreshFxFromFeed} aria-label="Refresh FX rates from feed">
              Refresh from feed
            </button>
          </div>
          <label className="muted" style={{ display: 'block', marginTop: 8 }}>
            <input type="checkbox" checked={fxAutoRefresh} onChange={toggleFxAutoRefresh} aria-label="FX auto-refresh" />{' '}
            Update rates automatically
          </label>
          <ul style={{ marginTop: 8, paddingLeft: 18 }}>
            {fxRates.map((r: any) => (
              <li key={r.currency_code}>
                {r.currency_code}: {r.rate_to_base}
                {r.source ? ` · ${r.source}` : ''}
                {r.provider_fetched_at
                  ? ` · ${formatWhen(r.provider_fetched_at)}`
                  : ''}{' '}
                <button type="button" onClick={() => removeFxRate(r.currency_code)} aria-label={`Remove exchange rate ${r.currency_code}`}>
                  Remove
                </button>
              </li>
            ))}
            {!fxRates.length && <li className="muted">No foreign rates yet</li>}
          </ul>
        </div>
        </div>
      </details>

      <div className="card">
          <h3>{kind === 'receivable' ? 'Record repayment' : 'Record payment'}</h3>
          <p className="muted">
            Pays the oldest open documents first. This does not create a new sale or bill.
            Mobile Money records how the customer paid. Ribdigi does not collect or settle those funds.
          </p>
          <select
            value={partyId}
            onChange={(e) => setPartyId(e.target.value)}
            aria-label="Credit payment party"
          >
            {parties.map((p: any) => (
              <option key={p.id} value={p.id}>
                {p.name} (owe {dueOf(p.id)}
                {p.payment_terms_days != null ? ` · Net ${p.payment_terms_days}` : ''})
              </option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
            <input
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              placeholder="Amount"
              aria-label="Payment amount"
              style={{ width: 120 }}
            />
            <select
              value={payMethod}
              onChange={(e) => setPayMethod(e.target.value)}
              aria-label="Payment method"
            >
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank transfer</option>
              <option value="card">Card</option>
              <option value="cheque">Cheque</option>
              <option value="mobile_money">Mobile Money (MoMo)</option>
            </select>
            <input
              value={payReference}
              onChange={(e) => setPayReference(e.target.value)}
              placeholder="Payment reference (optional)"
              aria-label="Payment reference"
              title="Optional reference (1–100 chars; letters/digits required)"
              style={{ width: 180 }}
            />
            <input
              value={payNotes}
              onChange={(e) => setPayNotes(e.target.value)}
              placeholder="Payment notes (optional)"
              aria-label="Payment notes"
              title="Optional notes (1–500 chars; letters/digits required)"
              style={{ width: 180 }}
            />
            {payMethod === 'cheque' ? (
              <>
                <input
                  value={payChequeNumber}
                  onChange={(e) => setPayChequeNumber(e.target.value)}
                  placeholder="Cheque number"
                  aria-label="Payment cheque number"
                  style={{ width: 140 }}
                />
                <input
                  value={payChequeBankName}
                  onChange={(e) => setPayChequeBankName(e.target.value)}
                  placeholder="Cheque bank name"
                  aria-label="Payment cheque bank name"
                  style={{ width: 160 }}
                />
                <input
                  type="date"
                  value={payChequeDate}
                  onChange={(e) => setPayChequeDate(e.target.value)}
                  aria-label="Payment cheque date"
                  title="Cheque date"
                />
              </>
            ) : null}
            <select
              value={liquidAccountId}
              onChange={(e) => setLiquidAccountId(e.target.value)}
              title="Account this payment uses"
              aria-label="Credit payment liquid account"
            >
              <option value="">Default account</option>
              {liquidAccounts.map((a: any) => (
                <option key={a.id} value={a.id}>
                  {a.code} {a.name}
                </option>
              ))}
            </select>
            <input
              value={payFxRate}
              onChange={(e) => setPayFxRate(e.target.value)}
              placeholder="Exchange rate"
              style={{ width: 110 }}
              title="Optional payment exchange rate (same currency as invoice)"
              aria-label="Payment FX rate"
            />
            <button onClick={recordPayment} aria-label="Record payment" disabled={payBusy || !payAmount}>
              {payBusy ? 'Saving…' : 'Pay'}
            </button>
          </div>
          {(kind === 'receivable' || kind === 'payable') && (
            <label className="muted" style={{ display: 'block', marginTop: 8 }}>
              <input
                type="checkbox"
                aria-label="Apply early payment discount"
                checked={applyEarly}
                onChange={(e) => setApplyEarly(e.target.checked)}
              />{' '}
              Apply early-payment discount when eligible
            </label>
          )}
          {kind === 'receivable' && (
            <>
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <input
                value={creditLimit}
                onChange={(e) => setCreditLimit(e.target.value)}
                placeholder="New credit limit"
                aria-label="Credit limit"
                style={{ width: 140 }}
              />
              <input
                value={paymentTermsDays}
                onChange={(e) => setPaymentTermsDays(e.target.value)}
                placeholder="Net days"
                style={{ width: 90 }}
                title="Payment terms (days)"
                aria-label="Customer payment terms days"
              />
              <button aria-label="Set customer credit limit and terms" onClick={updateLimit} disabled={limitBusy}>
                {limitBusy ? 'Saving…' : 'Save limit / terms'}
              </button>
            </div>
            <p className="muted">Needs credit approval permission. Limit 0 means unlimited.</p>
            </>
          )}
          {kind === 'payable' && (
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <input
                value={paymentTermsDays}
                onChange={(e) => setPaymentTermsDays(e.target.value)}
                placeholder="Net days"
                style={{ width: 90 }}
                title="Supplier payment terms (days)"
                aria-label="Supplier payment terms days"
              />
              <button type="button" aria-label="Set supplier payment terms" onClick={updateSupplierTerms}>
                Set terms
              </button>
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            <button aria-label="Load party statement" onClick={loadStatement}>Statement</button>
            {kind === 'payable' && (
              <button type="button" aria-label="Load payment schedule" onClick={loadPaymentSchedule}>
                Schedule
              </button>
            )}
            <input
              type="date"
              value={histFromDate}
              onChange={(e) => setHistFromDate(e.target.value)}
              title="History from date (YYYY-MM-DD)"
              aria-label="Credit history from date"
            />
            <input
              type="date"
              value={histToDate}
              onChange={(e) => setHistToDate(e.target.value)}
              title="History to date (YYYY-MM-DD)"
              aria-label="Credit history to date"
            />
            <button type="button" aria-label="Load party history" onClick={loadHistory}>
              History
            </button>
          </div>
        </div>

      {loadState === 'error' ? (
        <div className="list-empty" role="alert">
          <p>Balances could not be loaded. Use Retry — totals are not shown as zero.</p>
        </div>
      ) : null}
      {loadState === 'empty' && kind === 'payable' ? (
        <div className="list-empty">
          <p>No supplier bills with a remaining balance.</p>
        </div>
      ) : null}
      <div className="list-page-head">
        <h3 style={{ margin: 0 }}>{kind === 'receivable' ? 'Customers' : 'Suppliers'}</h3>
      </div>
      <div className="list-table-wrap">
      <table className="table compact">
        <thead>
          <tr>
            <th>Name</th>
            <th>Balance</th>
            <th>Current</th>
            <th>1–30</th>
            <th>31–60</th>
            <th>61–90</th>
            <th>90+</th>
          </tr>
        </thead>
        <tbody>
          {(report?.parties || []).map((r: any) => (
            <tr
              key={r.party_id}
              onClick={() => setPartyId(r.party_id)}
              style={{
                cursor: 'pointer',
                background: r.party_id === partyId ? 'var(--row-selected, rgba(0,107,46,0.08))' : undefined,
              }}
            >
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
      </div>


      {kind === 'payable' && loadState === 'success' && (report?.documents || []).length > 0 ? (
        <div className="card cat-panel" style={{ marginTop: 16 }}>
          <h3 style={{ margin: 0 }}>Supplier bills</h3>
          <div className="list-table-wrap">
            <table className="table compact">
              <thead>
                <tr>
                  <th>Supplier</th>
                  <th>Bill / ref</th>
                  <th>Invoice date</th>
                  <th>Due</th>
                  <th>Total</th>
                  <th>Paid</th>
                  <th>Balance</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {(report.documents || []).map((row: any) => (
                  <tr
                    key={row.id}
                    onClick={() => {
                      setPartyId(row.party_id);
                      router.push('/purchasing?tab=invoices');
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>{row.party_name}</td>
                    <td>{row.document_number}</td>
                    <td>{formatWhen(row.invoice_date) || '—'}</td>
                    <td>{formatWhen(row.due_date) || '—'}</td>
                    <td>{row.total_amount}</td>
                    <td>{row.paid_amount}</td>
                    <td>{row.balance_due}</td>
                    <td>{plainLabel(row.status)}</td>
                    <td>
                      <button
                        type="button"
                        aria-label="Open payment history"
                        onClick={(e) => {
                          e.stopPropagation();
                          setPartyId(row.party_id);
                          loadHistory();
                        }}
                      >
                        History
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {kind === 'payable' && loadState === 'success' && (report?.commitments || []).length > 0 ? (
        <div className="card cat-panel" style={{ marginTop: 16 }}>
          <h3 style={{ margin: 0 }}>Open purchase orders (not invoiced)</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            These are commitments, not amounts due on supplier bills.
          </p>
          <div className="list-table-wrap">
            <table className="table compact">
              <thead>
                <tr>
                  <th>Supplier</th>
                  <th>PO</th>
                  <th>Status</th>
                  <th>Commitment</th>
                </tr>
              </thead>
              <tbody>
                {(report.commitments || []).map((row: any) => (
                  <tr
                    key={row.id}
                    onClick={() => router.push('/purchasing?tab=orders')}
                    style={{ cursor: 'pointer' }}
                  >
                    <td>{row.party_name}</td>
                    <td>{row.document_number}</td>
                    <td>{plainLabel(row.status)}</td>
                    <td>{row.balance_due}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {statement && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Statement</h3>
          <p>
            Balance {statement.outstanding_balance ?? statement.balance ?? statement.total_due ?? '—'}
          </p>
          {(statement.lines || statement.entries || statement.invoices) ? (
            <table className="table compact">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Document</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {(statement.lines || statement.entries || statement.invoices || []).slice(0, 40).map(
                  (row: any, i: number) => (
                    <tr key={row.id || row.invoice_id || i}>
                      <td>
                        {formatWhen(row.date || row.posted_at || row.created_at) || '—'}
                      </td>
                      <td>{row.reference || row.invoice_number || row.description || '—'}</td>
                      <td>{row.amount ?? row.total_amount ?? row.balance ?? '—'}</td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          ) : (
            <p className="muted">Open documents listed on Balance.</p>
          )}
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
                    <td>{plainLabel(row.status)}</td>
                    <td>{row.amount}</td>
                  </tr>
                ))}
                {(creditInfo.open_bills || []).map((row: any) => (
                  <tr key={row.purchase_invoice_id || row.purchase_order_id}>
                    <td>{row.invoice_number || row.po_number}</td>
                    <td>{plainLabel(row.status)}</td>
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
                  <td>{plainLabel(p.type)}</td>
                  <td>{p.reference}</td>
                  <td>{plainLabel(p.status)}</td>
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
                  <td>{plainLabel(r.status)}</td>
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
                <th>Early discount</th>
              </tr>
            </thead>
            <tbody>
              {(schedule.items || []).map((row: any) => (
                <tr key={`${row.document_type}-${row.id}`}>
                  <td>
                    {formatWhen(row.due_date) || '—'}
                  </td>
                  <td>{row.document_number}</td>
                  <td>{row.document_type === 'purchase_invoice' ? 'Bill' : 'Order'}</td>
                  <td>{plainLabel(row.status)}</td>
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
    </div>
  );
}
