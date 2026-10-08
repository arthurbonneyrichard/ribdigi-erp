'use client';

import { useEffect, useState } from 'react';
import { api } from '../../../../lib/api';
import { mergePlatformBillingStatus } from '../../../../lib/billingStatus';

export default function PlatformBillingPage() {
  const [status, setStatus] = useState<any>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [attention, setAttention] = useState<any[]>([]);
  const [tenantRef, setTenantRef] = useState('');
  const [detail, setDetail] = useState<any>(null);
  const [assignPlan, setAssignPlan] = useState('professional-month');
  const [trialEnds, setTrialEnds] = useState('');
  const [payment, setPayment] = useState({ amount: '', currency: 'GHS', reference: '', note: '' });
  const [suspendReason, setSuspendReason] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [gatewayForm, setGatewayForm] = useState({
    provider: 'mock',
    mode: 'sandbox',
    api_base_url: 'https://api.paystack.co',
    secret: '',
    webhook_secret: '',
  });
  const [form, setForm] = useState({
    code: '',
    package_code: 'professional',
    name: '',
    interval: 'month',
    amount: '499.00',
    currency: 'GHS',
    trial_days: '14',
    grace_days: '7',
  });

  async function load() {
    const [statusRes, planRes, attentionRes] = await Promise.allSettled([
      api('/platform/billing/status'),
      api('/platform/billing/plans'),
      api('/platform/billing/attention'),
    ]);
    if (statusRes.status === 'fulfilled') {
      const data = statusRes.value?.data || null;
      setStatus(data);
      const gateway = data?.gateway;
      if (gateway) {
        setGatewayForm((current) => ({
          ...current,
          provider: gateway.provider === 'paystack' ? 'paystack' : 'mock',
          mode: gateway.mode === 'live' ? 'live' : 'sandbox',
          api_base_url: gateway.api_base_url || current.api_base_url,
          secret: '',
          webhook_secret: '',
        }));
      }
    } else {
      setStatus(null);
      setError(statusRes.reason?.message || 'Could not load platform billing');
    }
    if (planRes.status === 'fulfilled') setPlans(planRes.value?.data || []);
    if (attentionRes.status === 'fulfilled') setAttention(attentionRes.value?.data || []);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message || 'Could not load platform billing'));
  }, []);

  async function saveGateway() {
    setError('');
    setMessage('');
    try {
      const body: Record<string, string> = {
        provider: gatewayForm.provider,
        mode: gatewayForm.mode,
      };
      if (gatewayForm.provider === 'paystack') body.api_base_url = gatewayForm.api_base_url.trim();
      if (gatewayForm.secret.trim()) body.secret = gatewayForm.secret.trim();
      if (gatewayForm.webhook_secret.trim()) body.webhook_secret = gatewayForm.webhook_secret.trim();
      const saved = await api('/platform/billing/gateway', {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      setGatewayForm((current) => ({ ...current, secret: '', webhook_secret: '' }));
      setStatus((current: any) => mergePlatformBillingStatus(current, saved?.data || saved));
      setMessage('Sandbox gateway saved. Secrets stay on the server.');
    } catch (err: any) {
      setError(err.message || 'Could not save the gateway');
    }
  }

  async function testGateway() {
    setError('');
    setMessage('');
    try {
      const result = await api('/platform/billing/gateway/test', { method: 'POST' });
      const probe = result?.data || result;
      setStatus((current: any) => mergePlatformBillingStatus(current, probe));
      setMessage(probe?.last_test_message || result?.message || 'Connection test finished.');
    } catch (err: any) {
      setError(err.message || 'Could not test the gateway');
    }
  }

  async function createPlan() {
    setError('');
    try {
      await api('/platform/billing/plans', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          amount: form.amount,
          trial_days: Number(form.trial_days),
          grace_days: Number(form.grace_days),
          is_active: true,
        }),
      });
      setMessage('Plan saved.');
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not save plan');
    }
  }

  async function viewTenant() {
    setError('');
    try {
      const row = await api(`/platform/billing/tenants/${encodeURIComponent(tenantRef.trim())}`);
      const body = row?.data || row;
      setDetail(body);
      if (body?.account?.plan?.code) setAssignPlan(body.account.plan.code);
      if (body?.account?.plan) {
        setPayment((current) => ({
          ...current,
          amount: String(body.account.plan.amount ?? current.amount),
          currency: body.account.plan.currency || current.currency,
        }));
      }
    } catch (err: any) {
      setError(err.message || 'Tenant billing was not found');
    }
  }

  async function assign() {
    setError('');
    setMessage('');
    try {
      const body: Record<string, string> = { plan_code: assignPlan };
      if (trialEnds.trim()) body.trial_ends_at = trialEnds.trim();
      await api(`/platform/billing/tenants/${encodeURIComponent(tenantRef.trim())}/assign`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setMessage('Plan assigned. No charge was made.');
      await viewTenant();
    } catch (err: any) {
      setError(err.message || 'Could not assign the plan');
    }
  }

  async function recordPayment() {
    setError('');
    setMessage('');
    try {
      await api(`/platform/billing/tenants/${encodeURIComponent(tenantRef.trim())}/payments`, {
        method: 'POST',
        body: JSON.stringify({
          amount: payment.amount,
          currency: payment.currency,
          reference: payment.reference.trim(),
          note: payment.note.trim() || null,
        }),
      });
      setMessage('Payment recorded.');
      await viewTenant();
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not record the payment');
    }
  }

  async function retryCharge() {
    setError('');
    setMessage('');
    try {
      const result = await api(`/platform/billing/tenants/${encodeURIComponent(tenantRef.trim())}/retry`, {
        method: 'POST',
      });
      setMessage(`Retry result: ${result?.data?.outcome || 'done'}.`);
      await viewTenant();
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not retry the payment');
    }
  }

  async function suspendTenant() {
    setError('');
    setMessage('');
    try {
      await api(`/tenants/${encodeURIComponent(tenantRef.trim())}/suspend`, {
        method: 'POST',
        body: JSON.stringify({ reason: suspendReason.trim() }),
      });
      setMessage('Workspace suspended. Company data is kept.');
      await viewTenant();
    } catch (err: any) {
      setError(err.message || 'Could not suspend the workspace');
    }
  }

  async function reactivateTenant() {
    setError('');
    setMessage('');
    try {
      await api(`/platform/billing/tenants/${encodeURIComponent(tenantRef.trim())}/reactivate`, {
        method: 'POST',
      });
      setMessage('Access restored. This did not create a charge.');
      await viewTenant();
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not restore access');
    }
  }

  async function setPlanActive(plan: any, isActive: boolean) {
    setError('');
    try {
      await api(`/platform/billing/plans/${plan.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: isActive }),
      });
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not update the plan');
    }
  }

  return (
    <main className="page">
      <h1>Platform subscription billing</h1>
      <p>
        Charges here are for tenant ERP subscriptions. Customer sales and POS payments are separate.
        Live recurring billing works only after a compatible gateway secret is configured. Card numbers are not stored.
      </p>
      {error && <p role="alert">{error}</p>}
      {message && <p>{message}</p>}
      <section className="card">
        <h2>Gateway</h2>
        <p>Provider: {status?.provider || '—'}</p>
        <p>Configured: {status?.configured ? 'Yes' : 'No'}</p>
        <p>Live charges: {status?.live_charges ? 'Yes' : 'No'}</p>
        <p>Enabled: {status?.gateway?.enabled ? 'Yes' : 'No'}</p>
        <p>{status?.gateway?.secret_configured ? `Secret on file ends ${status.gateway.secret_hint || '••••'}` : 'No secret on file.'}</p>
        <p>
          Last test:{' '}
          {status?.gateway?.last_test_ok ? 'ok' : status?.gateway?.last_test_message ? 'not ok' : 'not run'}
          {status?.gateway?.last_test_at ? ` at ${status.gateway.last_test_at}` : ''}
        </p>
        <label>
          Provider
          <select
            aria-label="Billing gateway provider"
            value={gatewayForm.provider}
            onChange={(event) => setGatewayForm({ ...gatewayForm, provider: event.target.value })}
          >
            <option value="mock">Mock</option>
            <option value="paystack">Paystack</option>
          </select>
        </label>
        <label>
          Mode
          <select
            aria-label="Billing gateway mode"
            value={gatewayForm.mode}
            onChange={(event) => setGatewayForm({ ...gatewayForm, mode: event.target.value })}
          >
            <option value="sandbox">Sandbox</option>
            <option value="live">Live</option>
          </select>
        </label>
        {gatewayForm.provider === 'paystack' && (
          <label>
            API base URL
            <input
              aria-label="Billing gateway API base URL"
              value={gatewayForm.api_base_url}
              onChange={(event) => setGatewayForm({ ...gatewayForm, api_base_url: event.target.value })}
            />
          </label>
        )}
        <label>
          Secret
          <input
            aria-label="Billing gateway secret"
            type="password"
            autoComplete="new-password"
            value={gatewayForm.secret}
            onChange={(event) => setGatewayForm({ ...gatewayForm, secret: event.target.value })}
          />
        </label>
        <label>
          Webhook secret
          <input
            aria-label="Billing gateway webhook secret"
            type="password"
            autoComplete="new-password"
            value={gatewayForm.webhook_secret}
            onChange={(event) => setGatewayForm({ ...gatewayForm, webhook_secret: event.target.value })}
          />
        </label>
        <button aria-label="Save billing gateway" type="button" onClick={saveGateway}>Save gateway</button>
        <button aria-label="Test billing gateway connection" type="button" onClick={testGateway}>Test connection</button>
      </section>
      <section className="card">
        <h2>Plans</h2>
        <ul>
          {plans.map((plan) => (
            <li key={plan.id}>
              {plan.name} ({plan.code}) — {plan.currency} {plan.amount} / {plan.interval}; trial {plan.trial_days} days; grace {plan.grace_days} days; package {plan.package_code}; {plan.is_active ? 'active' : 'inactive'}
              <button
                aria-label={plan.is_active ? `Deactivate billing plan ${plan.code}` : `Activate billing plan ${plan.code}`}
                type="button"
                onClick={() => setPlanActive(plan, !plan.is_active)}
              >
                {plan.is_active ? 'Deactivate' : 'Activate'}
              </button>
            </li>
          ))}
        </ul>
        <label>
          Plan code
          <input aria-label="Billing plan code" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} />
        </label>
        <label>
          Name
          <input aria-label="Billing plan name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
        </label>
        <label>
          Package
          <select aria-label="Billing package" value={form.package_code} onChange={(event) => setForm({ ...form, package_code: event.target.value })}>
            <option value="starter">starter</option>
            <option value="professional">professional</option>
            <option value="enterprise">enterprise</option>
          </select>
        </label>
        <label>
          Interval
          <select aria-label="Billing interval" value={form.interval} onChange={(event) => setForm({ ...form, interval: event.target.value })}>
            <option value="month">month</option>
            <option value="year">year</option>
          </select>
        </label>
        <label>
          Amount
          <input aria-label="Billing plan amount" value={form.amount} onChange={(event) => setForm({ ...form, amount: event.target.value })} />
        </label>
        <label>
          Currency
          <select aria-label="Billing plan currency" value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })}>
            <option value="GHS">GHS</option>
            <option value="USD">USD</option>
          </select>
        </label>
        <button aria-label="Create billing plan" className="btn-primary" type="button" onClick={createPlan}>
          Create plan
        </button>
      </section>
      <section className="card">
        <h2>Needs attention</h2>
        <ul>
          {attention.map((row) => (
            <li key={row.tenant_id}>
              {row.company_name} ({row.slug}) — {row.billing_status}
            </li>
          ))}
        </ul>
        <label>
          Tenant slug
          <input aria-label="Tenant billing slug" value={tenantRef} onChange={(event) => setTenantRef(event.target.value)} />
        </label>
        <button aria-label="View tenant billing" type="button" onClick={viewTenant}>
          View tenant
        </button>
        {detail && (
          <div>
            <h3>{detail.company_name}</h3>
            <p>Workspace: {detail.tenant_status}</p>
            <p>Billing: {detail.account?.billing_status || '—'}</p>
            <p>Trial ends: {detail.trial_ends_at || '—'}</p>
            <p>Next renewal: {detail.account?.next_renewal_at || '—'}</p>
            <p>Paid through: {detail.account?.paid_through || '—'}</p>
            <p>Payment method: {detail.account?.authorization_present ? detail.account.authorization_hint || 'Yes' : 'No'}</p>
            <p>{detail.account?.access_note}</p>
            <label>
              Assign plan
              <select aria-label="Assign billing plan" value={assignPlan} onChange={(event) => setAssignPlan(event.target.value)}>
                {plans.filter((plan) => plan.is_active).map((plan) => (
                  <option key={plan.id} value={plan.code}>{plan.name}</option>
                ))}
              </select>
            </label>
            <label>
              Trial end
              <input aria-label="Tenant trial end" type="date" value={trialEnds} onChange={(event) => setTrialEnds(event.target.value)} />
            </label>
            <button aria-label="Assign tenant billing plan" type="button" onClick={assign}>Assign plan</button>
            <label>
              Payment amount
              <input aria-label="Manual payment amount" value={payment.amount} onChange={(event) => setPayment({ ...payment, amount: event.target.value })} />
            </label>
            <label>
              Payment currency
              <select aria-label="Manual payment currency" value={payment.currency === 'USD' ? 'USD' : 'GHS'} onChange={(event) => setPayment({ ...payment, currency: event.target.value })}>
                <option value="GHS">GHS</option>
                <option value="USD">USD</option>
              </select>
            </label>
            <label>
              Payment reference
              <input aria-label="Manual payment reference" value={payment.reference} onChange={(event) => setPayment({ ...payment, reference: event.target.value })} />
            </label>
            <label>
              Payment note
              <input aria-label="Manual payment note" value={payment.note} onChange={(event) => setPayment({ ...payment, note: event.target.value })} />
            </label>
            <button aria-label="Record manual subscription payment" className="btn-ok" type="button" onClick={recordPayment}>Record payment</button>
            <button aria-label="Retry subscription payment" type="button" onClick={retryCharge}>Retry charge</button>
            <label>
              Suspend reason
              <input aria-label="Tenant suspend reason" value={suspendReason} onChange={(event) => setSuspendReason(event.target.value)} />
            </label>
            <button aria-label="Suspend tenant for billing" className="btn-danger" type="button" onClick={suspendTenant}>Suspend access</button>
            <button aria-label="Reactivate tenant billing access" className="btn-ok" type="button" onClick={reactivateTenant}>Restore access</button>
            <table aria-label="Tenant subscription invoices">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Amount</th>
                  <th>Currency</th>
                  <th>Gateway reference</th>
                </tr>
              </thead>
              <tbody>
                {(detail.invoices || []).map((row: any) => (
                  <tr key={row.id}>
                    <td>{row.status}</td>
                    <td>{row.amount}</td>
                    <td>{row.currency}</td>
                    <td>{row.gateway_reference || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
