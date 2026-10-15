'use client';

import { useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { billingGatewayLabel } from '../../../../lib/billingStatus';
import { currencySign, formatDate, formatDateTime, formatMoney, formatNumber, type FormatPrefs } from '../../../../lib/format';
import './billing-page.css';

type Plan = {
  name: string;
  amount: number;
  currency: string;
  interval: string;
  code: string;
};

type Account = {
  billing_status?: string;
  tenant_status?: string;
  access_note?: string;
  auto_renew?: boolean;
  paid_through?: string | null;
  next_renewal_at?: string | null;
  authorization_present?: boolean;
  authorization_hint?: string | null;
  consent_at?: string | null;
  canceled_at?: string | null;
  trial_ends_at?: string | null;
  plan?: Plan | null;
  provider?: { provider?: string; live_charges?: boolean };
};

type Invoice = {
  id: string;
  status?: string;
  description?: string;
  amount?: number;
  currency?: string;
  period_start?: string | null;
  period_end?: string | null;
  created_at?: string | null;
};

const HONESTY =
  'A return from the payment page leaves the invoice unpaid until that gateway confirms a reusable authorization. This page is not a production charge.';

const STATUS_LABELS: Record<string, string> = {
  trialing: 'Trial',
  active: 'Active',
  payment_required: 'Payment needed',
  past_due: 'Payment overdue',
  grace_period: 'Grace',
  canceled: 'Renewal off',
  suspended: 'Suspended',
  paid: 'Paid',
  pending: 'Pending',
  failed: 'Failed',
  open: 'Open',
};

function labelStatus(value?: string | null): string {
  const key = String(value || '').trim().toLowerCase();
  if (!key) return '—';
  if (STATUS_LABELS[key]) return STATUS_LABELS[key];
  return key.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function companyStatusKey(account: Account | null): string {
  const tenant = String(account?.tenant_status || '').trim().toLowerCase();
  if (tenant === 'trial' || tenant === 'active' || tenant === 'grace' || tenant === 'suspended') return tenant;
  const billing = String(account?.billing_status || '').trim().toLowerCase();
  if (billing === 'trialing') return 'trial';
  if (billing === 'active' || billing === 'canceled') return 'active';
  if (billing === 'suspended') return 'suspended';
  if (billing === 'payment_required' || billing === 'past_due' || billing === 'grace_period') return 'grace';
  return billing;
}

function companyStatusLabel(account: Account | null): string {
  const key = companyStatusKey(account);
  if (key === 'trial') return 'Trial';
  if (key === 'active') return 'Active';
  if (key === 'grace') return 'Grace';
  if (key === 'suspended') return 'Suspended';
  return labelStatus(key);
}

function statusTone(value?: string | null): string {
  const key = String(value || '').trim().toLowerCase();
  if (key === 'trial' || key === 'trialing') return 'billing-page-status-trial';
  if (key === 'active' || key === 'paid') return 'billing-page-status-active';
  if (key === 'grace' || key === 'grace_period' || key === 'past_due' || key === 'payment_required') {
    return 'billing-page-status-grace';
  }
  if (key === 'suspended' || key === 'failed' || key === 'canceled') return 'billing-page-status-suspended';
  return 'billing-page-status-other';
}

function showWhen(value?: string | null, prefs?: FormatPrefs | null): string {
  if (!value) return '—';
  const text = String(value);
  const hasTime = text.includes('T') || /\d{1,2}:\d{2}/.test(text);
  const formatted = hasTime ? formatDateTime(text, prefs) : formatDate(text, prefs);
  return formatted || '—';
}

function moneyLine(amount: number | null | undefined, currency?: string | null, prefs?: FormatPrefs | null): string {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) return '—';
  return formatMoney(amount, prefs, currency || 'GHS');
}

function periodWord(interval?: string | null): string {
  if (interval === 'year') return 'year';
  if (interval === 'month') return 'month';
  return interval || 'period';
}

function termWord(interval?: string | null): string {
  if (interval === 'year') return 'Yearly';
  if (interval === 'month') return 'Monthly';
  if (!interval) return '—';
  return interval.charAt(0).toUpperCase() + interval.slice(1);
}

function invoiceWhen(row: Invoice): string | null | undefined {
  return row.created_at || row.period_start || row.period_end;
}

function invoiceDescription(row: Invoice, planName?: string | null): string {
  const provided = String(row.description || '').trim();
  if (provided) return provided;
  const name = planName || 'Subscription';
  return `${name} subscription`;
}

function MoneyRead({
  amount,
  currency,
  prefs,
}: {
  amount: number | null | undefined;
  currency?: string | null;
  prefs?: FormatPrefs | null;
}) {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) return <>—</>;
  const code = currency || 'GHS';
  return (
    <span className="billing-page-money">
      <span className="billing-page-sign">{currencySign(code)}</span>
      <span className="billing-page-figure">{formatNumber(amount, prefs)}</span>
    </span>
  );
}

export default function SubscriptionBillingPage() {
  const [account, setAccount] = useState<Account | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [prefs, setPrefs] = useState<FormatPrefs | null>(null);
  const [consent, setConsent] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function load() {
    const [accountRes, invoiceRes, profileRes] = await Promise.all([
      api('/billing/account'),
      api('/billing/invoices'),
      api('/tenants/me').catch(() => null),
    ]);
    setAccount(accountRes?.data || null);
    setInvoices(invoiceRes?.data || []);
    const profile = profileRes?.data;
    if (profile) {
      setPrefs({
        date_format: profile.date_format,
        time_format: profile.time_format,
        decimal_separator: profile.decimal_separator,
        thousand_separator: profile.thousand_separator,
      });
    }
  }

  useEffect(() => {
    if (account?.consent_at) setConsent(true);
  }, [account?.consent_at]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get('checkout_ref') || params.get('reference') || params.get('trxref') || '';
    load()
      .then(async () => {
        if (!ref) return;
        const returned = await api(`/billing/checkout/return?reference=${encodeURIComponent(ref)}`);
        await load();
        const data = returned?.data;
        if (data?.authorization_present) {
          setMessage('Payment method saved. Returning from the payment page did not mark an invoice paid.');
        } else {
          setMessage(
            'You returned from the payment page. The payment method stays unsaved until the provider confirms a reusable authorization. This invoice is not marked paid.'
          );
        }
        window.history.replaceState(null, '', window.location.pathname);
      })
      .catch((err) => setError(err.message || 'Could not load billing'));
  }, []);

  const assigned = account?.plan?.name ? account.plan : null;
  const hasAmount = assigned != null && assigned.amount !== null && assigned.amount !== undefined && !Number.isNaN(Number(assigned.amount));
  const price = hasAmount
    ? `${moneyLine(assigned.amount, assigned.currency, prefs)} per ${periodWord(assigned.interval)}`
    : '';
  const canBill = Boolean(assigned?.code);
  const sandboxAvailable = account?.provider?.provider === 'mock' && account?.provider?.live_charges !== true;
  const openInvoice = invoices.find((row) => {
    const status = String(row.status || '').trim().toLowerCase();
    return status === 'open' || status === 'pending' || status === 'failed' || status === 'past_due';
  });
  const recordedInvoice = openInvoice || invoices[0];

  async function recordConsent() {
    setError('');
    setMessage('');
    if (!assigned?.code) {
      setError('No subscription plan is assigned to this company.');
      return;
    }
    try {
      await api('/billing/consent', {
        method: 'POST',
        body: JSON.stringify({ plan_code: assigned.code, accept: true }),
      });
      setMessage('Renewal agreement saved. A payment is taken only after a payment method is saved.');
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not record consent');
    }
  }

  async function startCheckout() {
    setError('');
    setMessage('');
    if (!assigned?.code) {
      setError('No subscription plan is assigned to this company.');
      return;
    }
    try {
      const result = await api('/billing/checkout', {
        method: 'POST',
        body: JSON.stringify({ plan_code: assigned?.code }),
      });
      if (result?.data?.paid === true) {
        setError('Checkout did not stay unpaid. Refresh this page before trying again.');
        return;
      }
      if (result?.data?.checkout_url) {
        window.location.href = result.data.checkout_url;
        return;
      }
      setMessage('The payment page is not available right now.');
    } catch (err: any) {
      if (err?.status === 503 || /not configured/i.test(String(err?.message || ''))) {
        setMessage('The payment page is not available right now.');
        return;
      }
      setError(err.message || 'Checkout is not available');
    }
  }

  async function saveSandboxMethod() {
    setError('');
    setMessage('');
    if (!assigned?.code) {
      setError('No subscription plan is assigned to this company.');
      return;
    }
    try {
      const saved = await api('/billing/sandbox/authorize', {
        method: 'POST',
        body: JSON.stringify({ authorization_code: 'mock_auth_ok' }),
      });
      if (saved?.data?.paid === true) {
        setError('The sandbox payment method did not stay unpaid. Refresh this page before trying again.');
        return;
      }
      setMessage('Sandbox payment method saved. No invoice was marked paid.');
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not save the sandbox payment method');
    }
  }

  async function cancelRenewal() {
    if (!window.confirm('Turn off future renewals? Access stays through the date already paid.')) return;
    setError('');
    try {
      await api('/billing/cancel', { method: 'POST', body: JSON.stringify({ confirm: true }) });
      setMessage('Future renewals are turned off.');
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not cancel renewal');
    }
  }

  return (
    <main className="page billing-page">
      <header className="billing-page-head">
        <h1>Subscription</h1>
        <p className="muted">This is your Ribdigi ERP plan. It is separate from payments you take from your own customers.</p>
      </header>
      {error && <p role="alert">{error}</p>}
      {message && <p>{message}</p>}
      <section className="card billing-page-card">
        <h2>Your plan</h2>
        <div className="billing-page-summary">
          <div className="billing-page-stat">
            <p className="billing-page-kicker">Plan</p>
            <p className="billing-page-value">{assigned?.name || 'Not assigned'}</p>
          </div>
          <div className="billing-page-stat">
            <p className="billing-page-kicker">Amount</p>
            <p className="billing-page-value">
              {hasAmount ? (
                <MoneyRead amount={assigned.amount} currency={assigned.currency} prefs={prefs} />
              ) : (
                '—'
              )}
            </p>
          </div>
          <div className="billing-page-stat">
            <p className="billing-page-kicker">Term</p>
            <p className="billing-page-value">{assigned ? termWord(assigned.interval) : '—'}</p>
          </div>
          <div className="billing-page-stat">
            <p className="billing-page-kicker">Status</p>
            <p className="billing-page-value">
              <span className={`billing-page-status ${statusTone(companyStatusKey(account))}`}>
                {companyStatusLabel(account)}
              </span>
            </p>
          </div>
        </div>
        <dl className="billing-facts billing-page-details">
          <dt>Trial ends</dt>
          <dd>{showWhen(account?.trial_ends_at, prefs)}</dd>
          <dt>Next renewal</dt>
          <dd>{showWhen(account?.next_renewal_at, prefs)}</dd>
          <dt>Paid through</dt>
          <dd>{showWhen(account?.paid_through, prefs)}</dd>
          <dt>Automatic renewal</dt>
          <dd>{account?.auto_renew ? 'On' : 'Off'}</dd>
          <dt>Payment method</dt>
          <dd>
            {account?.authorization_present
              ? `Saved${account.authorization_hint ? ` (${account.authorization_hint})` : ''}`
              : 'Not saved'}
          </dd>
          <dt>Renewal agreement</dt>
          <dd>{account?.consent_at ? `Agreed ${showWhen(account.consent_at, prefs)}` : 'Not agreed'}</dd>
        </dl>
        {account?.access_note && <p>{account.access_note}</p>}
        {!canBill && (
          <p role="status">
            {!assigned
              ? 'Ask Ribdigi House to assign a plan and amount for this company.'
              : hasAmount
                ? 'Ask Ribdigi House to finish assigning this renewal plan before you agree.'
                : `${assigned.name} is this company's plan. Ask Ribdigi House to confirm the amount before you agree to renewal.`}
          </p>
        )}
      </section>
      <section className="card billing-page-card">
        <h2>What is due</h2>
        {!invoices.length ? (
          <p className="muted" role="status">Invoices appear here after a renewal is recorded for this company.</p>
        ) : (
          <>
        <p className="billing-page-lead muted">
          {openInvoice
            ? 'An open invoice stays unpaid until the provider confirms it.'
            : 'Nothing is waiting to be paid. The newest row is the last amount recorded.'}
        </p>
        <div className="billing-page-scroll">
          <table className="billing-page-invoices" aria-label="Subscription invoices">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Period ends</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((row) => (
                <tr key={row.id}>
                  <td data-label="Date">{showWhen(invoiceWhen(row), prefs)}</td>
                  <td className="billing-page-desc" data-label="Description">{invoiceDescription(row, assigned?.name)}</td>
                  <td data-label="Amount">
                    <MoneyRead amount={row.amount} currency={row.currency} prefs={prefs} />
                  </td>
                  <td data-label="Status">
                    <span className={`billing-page-status ${statusTone(row.status)}`}>{labelStatus(row.status)}</span>
                  </td>
                  <td data-label="Period ends">{showWhen(row.period_end, prefs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
          </>
        )}
      </section>
      <section className="card billing-page-card">
        <h2>Payment method</h2>
        {assigned ? (
          <p className="billing-page-plan-line" aria-label="Subscription plan">
            {hasAmount ? `${assigned.name} at ${price}.` : `${assigned.name}. The amount is not confirmed yet.`}
          </p>
        ) : (
          <p role="status">Ask Ribdigi House to assign a plan and amount for this company.</p>
        )}
        <label className="billing-page-consent">
          <input
            aria-label="Consent to automatic renewal"
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />
          <span>I agree to renew this plan automatically at the amount shown until I turn renewal off.</span>
        </label>
        <div className="billing-page-actions">
          <button aria-label="Record renewal consent" className="btn-ok" type="button" disabled={!consent || !canBill} onClick={recordConsent}>
            Agree to renewal
          </button>
        </div>
        <div className="billing-page-pay">
          <p className="billing-page-honesty" role="status">
            {`Payment gateway: ${billingGatewayLabel(account?.provider?.provider)}. ${HONESTY}`}
          </p>
          <div className="billing-page-pay-actions">
            <button aria-label="Start hosted checkout" type="button" disabled={!account?.consent_at || !canBill} onClick={startCheckout}>
              {account?.authorization_present ? 'Update payment method' : 'Add payment method'}
            </button>
            {sandboxAvailable && (
              <button
                aria-label="Save sandbox payment method"
                type="button"
                disabled={!account?.consent_at || !canBill}
                onClick={saveSandboxMethod}
              >
                Save sandbox payment method
              </button>
            )}
          </div>
        </div>
        <div className="billing-page-stop">
          {account?.canceled_at && (
            <p>Renewal was turned off on {showWhen(account.canceled_at, prefs)}. Access continues through {showWhen(account.paid_through, prefs)}.</p>
          )}
          <button aria-label="Cancel automatic renewal" className="btn-danger" type="button" disabled={!account?.auto_renew} onClick={cancelRenewal}>
            Turn off renewal
          </button>
        </div>
      </section>
    </main>
  );
}
