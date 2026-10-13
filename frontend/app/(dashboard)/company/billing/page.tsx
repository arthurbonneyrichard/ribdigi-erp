'use client';

import { useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { billingGatewayLabel } from '../../../../lib/billingStatus';
import { formatDate, formatDateTime, formatMoney, type FormatPrefs } from '../../../../lib/format';

type Plan = {
  name: string;
  amount: number;
  currency: string;
  interval: string;
  code: string;
};

type Account = {
  billing_status?: string;
  access_note?: string;
  auto_renew?: boolean;
  paid_through?: string | null;
  next_renewal_at?: string | null;
  authorization_present?: boolean;
  consent_at?: string | null;
  canceled_at?: string | null;
  trial_ends_at?: string | null;
  plan?: Plan | null;
  provider?: { provider?: string; live_charges?: boolean };
};

type Invoice = {
  id: string;
  status?: string;
  amount?: number;
  currency?: string;
  period_end?: string | null;
};

const STATUS_LABELS: Record<string, string> = {
  trialing: 'Trial',
  active: 'Active',
  payment_required: 'Payment needed',
  past_due: 'Payment overdue',
  grace_period: 'Grace period',
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

  const assigned = account?.plan || null;
  const price = assigned
    ? `${moneyLine(assigned.amount, assigned.currency, prefs)} per ${periodWord(assigned.interval)}`
    : '—';

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
    <main className="page">
      <h1>Subscription</h1>
      <p className="muted">This is your Ribdigi ERP plan. It is separate from payments you take from your own customers.</p>
      {error && <p role="alert">{error}</p>}
      {message && <p>{message}</p>}
      <section className="card">
        <h2>Your plan</h2>
        <dl className="billing-facts">
          <dt>Plan</dt>
          <dd>{assigned?.name || 'Not assigned'}</dd>
          <dt>Amount</dt>
          <dd>{assigned ? price : '—'}</dd>
          <dt>Status</dt>
          <dd>{labelStatus(account?.billing_status)}</dd>
          <dt>Trial ends</dt>
          <dd>{showWhen(account?.trial_ends_at, prefs)}</dd>
          <dt>Next renewal</dt>
          <dd>{showWhen(account?.next_renewal_at, prefs)}</dd>
          <dt>Paid through</dt>
          <dd>{showWhen(account?.paid_through, prefs)}</dd>
          <dt>Automatic renewal</dt>
          <dd>{account?.auto_renew ? 'On' : 'Off'}</dd>
          <dt>Payment method</dt>
          <dd>{account?.authorization_present ? 'Saved' : 'Not saved'}</dd>
          <dt>Renewal agreement</dt>
          <dd>{account?.consent_at ? `Agreed ${showWhen(account.consent_at, prefs)}` : 'Not agreed'}</dd>
        </dl>
        {account?.access_note && <p>{account.access_note}</p>}
        {!assigned && (
          <p role="status">No plan is assigned yet. Ribdigi House sets the plan and the amount for this company.</p>
        )}
      </section>
      <section className="card">
        <h2>Renewal</h2>
        {assigned ? (
          <p aria-label="Subscription plan">
            {assigned.name} at {price}.
          </p>
        ) : (
          <p role="status">Renewal stays off until a plan is assigned.</p>
        )}
        <label>
          <input
            aria-label="Consent to automatic renewal"
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />{' '}
          I agree to renew this plan automatically at the amount shown until I turn renewal off.
        </label>
        <button aria-label="Record renewal consent" className="btn-primary" type="button" disabled={!consent || !assigned} onClick={recordConsent}>
          Agree to renewal
        </button>
        <p role="status">
          Payment gateway: {billingGatewayLabel(account?.provider?.provider)}. A return from the
          payment page leaves the invoice unpaid until that gateway confirms a reusable authorization.
          {account?.provider?.live_charges
            ? ''
            : ' This page is not a production charge.'}
        </p>
        <button aria-label="Start hosted checkout" type="button" disabled={!account?.consent_at || !assigned} onClick={startCheckout}>
          {account?.authorization_present ? 'Update payment method' : 'Add payment method'}
        </button>
        {account?.canceled_at && (
          <p>Renewal was turned off on {showWhen(account.canceled_at, prefs)}. Access continues through {showWhen(account.paid_through, prefs)}.</p>
        )}
        <button aria-label="Cancel automatic renewal" className="btn-danger" type="button" onClick={cancelRenewal}>
          Turn off renewal
        </button>
      </section>
      <section className="card">
        <h2>Invoices</h2>
        {!invoices.length ? (
          <p className="muted">No invoices yet.</p>
        ) : (
          <table aria-label="Subscription invoices">
            <thead>
              <tr>
                <th>Status</th>
                <th>Amount</th>
                <th>Period ends</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((row) => (
                <tr key={row.id}>
                  <td>{labelStatus(row.status)}</td>
                  <td>{moneyLine(row.amount, row.currency, prefs)}</td>
                  <td>{showWhen(row.period_end, prefs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
