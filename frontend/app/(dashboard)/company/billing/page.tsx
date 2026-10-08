'use client';

import { useEffect, useState } from 'react';
import { api } from '../../../../lib/api';

type Plan = {
  code: string;
  name: string;
  amount: number;
  currency: string;
  interval: string;
  trial_days: number;
};

type Account = {
  billing_status?: string;
  access_note?: string;
  auto_renew?: boolean;
  paid_through?: string | null;
  next_renewal_at?: string | null;
  authorization_present?: boolean;
  authorization_hint?: string | null;
  checkout_path?: string;
  consent_at?: string | null;
  consent_version?: string | null;
  consent_amount?: number | null;
  consent_currency?: string | null;
  consent_interval?: string | null;
  canceled_at?: string | null;
  trial_ends_at?: string | null;
  tenant_status?: string;
  plan?: Plan | null;
  provider?: { provider?: string; configured?: boolean; live_charges?: boolean };
};

export default function SubscriptionBillingPage() {
  const [account, setAccount] = useState<Account | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [planCode, setPlanCode] = useState('professional-month');
  const [consent, setConsent] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function load() {
    const [accountRes, planRes, invoiceRes] = await Promise.all([
      api('/billing/account'),
      api('/billing/plans'),
      api('/billing/invoices'),
    ]);
    setAccount(accountRes?.data || null);
    setPlans(planRes?.data || []);
    setInvoices(invoiceRes?.data || []);
    if (accountRes?.data?.plan?.code) setPlanCode(accountRes.data.plan.code);
  }

  useEffect(() => {
    const ref = new URLSearchParams(window.location.search).get('checkout_ref') || '';
    load()
      .then(async () => {
        if (!ref) return;
        const returned = await api(`/billing/checkout/return?reference=${encodeURIComponent(ref)}`);
        if (returned?.data && returned.data.confirmed_by_redirect === false) {
          setMessage('Checkout returned. No invoice was marked paid.');
        }
      })
      .catch((err) => setError(err.message || 'Could not load billing'));
  }, []);

  const selected = plans.find((plan) => plan.code === planCode);

  async function recordConsent() {
    setError('');
    setMessage('');
    try {
      await api('/billing/consent', {
        method: 'POST',
        body: JSON.stringify({ plan_code: planCode, accept: true }),
      });
      setMessage('Renewal consent recorded. A charge happens only after the gateway saves a payment method.');
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
        body: JSON.stringify({ plan_code: planCode }),
      });
      if (result?.data?.checkout_url) {
        window.location.href = result.data.checkout_url;
        return;
      }
      setMessage('Checkout did not return a hosted page.');
    } catch (err: any) {
      setError(err.message || 'Checkout is not available');
    }
  }

  async function saveSandboxMethod() {
    setError('');
    setMessage('');
    try {
      await api('/billing/sandbox/authorize', {
        method: 'POST',
        body: JSON.stringify({ authorization_code: 'mock_auth_sandbox' }),
      });
      setMessage('Sandbox payment method saved. No card was charged.');
      await load();
    } catch (err: any) {
      setError(err.message || 'Sandbox payment method was not saved');
    }
  }

  async function cancelRenewal() {
    if (!window.confirm('Stop future renewals? Access stays through the paid-through date.')) return;
    setError('');
    try {
      await api('/billing/cancel', { method: 'POST', body: JSON.stringify({ confirm: true }) });
      setMessage('Future renewals are canceled.');
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not cancel renewal');
    }
  }

  return (
    <main className="page">
      <h1>Subscription billing</h1>
      <p>
        This page is for your Ribdigi ERP subscription. It does not take payment from your customers.
        Returning from checkout does not mark an invoice paid.
      </p>
      {error && <p role="alert">{error}</p>}
      {message && <p>{message}</p>}
      <section className="card">
        <h2>Current subscription</h2>
        <p>Status: {account?.billing_status || '—'}</p>
        <p>Workspace: {account?.tenant_status || '—'}</p>
        <p>Trial ends: {account?.trial_ends_at || '—'}</p>
        <p>Next renewal: {account?.next_renewal_at || '—'}</p>
        <p>Paid through: {account?.paid_through || '—'}</p>
        <p>
          Price: {account?.plan
            ? `${account.plan.currency} ${account.plan.amount} / ${account.plan.interval}`
            : selected
              ? `${selected.currency} ${selected.amount} / ${selected.interval}`
              : '—'}
        </p>
        <p>
          Consent: {account?.consent_at
            ? `${account.consent_version} on ${account.consent_at} for ${account.consent_currency || ''} ${account.consent_amount ?? ''} / ${account.consent_interval || ''}`
            : 'Not recorded'}
        </p>
        <p>Payment method on file: {account?.authorization_present ? account.authorization_hint || 'Yes' : 'No'}</p>
        <p>Automatic renewal: {account?.auto_renew ? 'On' : 'Off'}</p>
        <p>{account?.access_note}</p>
        <p>
          Gateway: {account?.provider?.provider || 'mock'}
          {account?.provider?.live_charges ? ' (live charges enabled)' : ' (live charges are not enabled)'}
        </p>
      </section>
      <section className="card">
        <h2>Authorize renewal</h2>
        <label>
          Plan
          <select aria-label="Subscription plan" value={planCode} onChange={(event) => setPlanCode(event.target.value)}>
            {plans.map((plan) => (
              <option key={plan.code} value={plan.code}>
                {plan.name} — {plan.currency} {plan.amount}
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            aria-label="Consent to automatic renewal"
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />{' '}
          I agree to automatic renewal of this plan at the price, currency, and interval shown, until I turn renewal off.
        </label>
        <button aria-label="Record renewal consent" className="btn-primary" type="button" disabled={!consent} onClick={recordConsent}>
          Record consent
        </button>
        <button aria-label="Start hosted checkout" type="button" disabled={!account?.consent_at} onClick={startCheckout}>
          {account?.authorization_present ? 'Update payment method' : 'Start hosted checkout'}
        </button>
        {account?.provider?.provider === 'mock' && !account?.provider?.live_charges && (
          <button
            aria-label="Save sandbox payment method"
            type="button"
            disabled={!account?.consent_at}
            onClick={saveSandboxMethod}
          >
            Save sandbox payment method
          </button>
        )}
        {account?.canceled_at && <p>Renewal turned off on {account.canceled_at}. Access continues through {account.paid_through || 'the paid-through date'}.</p>}
        <button aria-label="Cancel automatic renewal" className="btn-danger" type="button" onClick={cancelRenewal}>
          Turn off automatic renewal
        </button>
      </section>
      <section className="card">
        <h2>Invoices</h2>
        <table aria-label="Subscription invoices">
          <thead>
            <tr>
              <th>Status</th>
              <th>Amount</th>
              <th>Currency</th>
              <th>Period end</th>
              <th>Gateway reference</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((row) => (
              <tr key={row.id}>
                <td>{row.status}</td>
                <td>{row.amount}</td>
                <td>{row.currency}</td>
                <td>{row.period_end}</td>
                <td>{row.gateway_reference || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
