'use client';

import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '../../../../lib/api';
import { formatNumber, formatWhen, plainLabel } from '../../../../lib/format';
import { getMe } from '../../../../lib/meCache';
import {
  canAssignSubscription,
  packageCodeFromName,
  gatewaySaveBody,
  packageCreateBody,
  packageUpdateBody,
  subscriptionAmountLabel,
  subscriptionAmountToSend,
  subscriptionTermLabel,
} from '../../../../lib/platformBilling';
import { useCompanyFormat } from '../../../../lib/useCompanyFormat';

const PLATFORM_ROLES = [
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
];

const PACKAGES = [
  { code: 'trial', name: 'Trial' },
  { code: 'starter', name: 'Starter' },
  { code: 'professional', name: 'Professional' },
  { code: 'enterprise', name: 'Enterprise' },
] as const;

type PackageRow = {
  id: string;
  code: string;
  package_code: string;
  name: string;
  interval: string;
  amount: number;
  currency: string;
  is_active: boolean;
};

type CompanyRow = {
  company_name: string;
  slug: string;
  plan: string;
  package_code: string;
  amount: number | null;
  currency: string | null;
  term_value: number | null;
  term_unit: string | null;
  status: string;
  renews: string | null;
};

export default function PlatformBillingPage() {
  const router = useRouter();
  const prefs = useCompanyFormat();
  const [rows, setRows] = useState<CompanyRow[]>([]);
  const [query, setQuery] = useState('');
  const [selectedSlug, setSelectedSlug] = useState('');
  const [packageCode, setPackageCode] = useState('professional');
  const [termValue, setTermValue] = useState(12);
  const [termUnit, setTermUnit] = useState('months');
  const [startAt, setStartAt] = useState('');
  const [amount, setAmount] = useState('');
  const [canAssign, setCanAssign] = useState(false);
  const [canCreate, setCanCreate] = useState(false);
  const [packages, setPackages] = useState<PackageRow[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState('');
  const [pendingDelete, setPendingDelete] = useState('');
  const [packageName, setPackageName] = useState('');
  const [packageSlug, setPackageSlug] = useState('');
  const [featureSet, setFeatureSet] = useState('professional');
  const [packageInterval, setPackageInterval] = useState('month');
  const [packageAmount, setPackageAmount] = useState('');
  const [packageCurrency, setPackageCurrency] = useState('GHS');
  const [linkedPlan, setLinkedPlan] = useState('');
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [gatewayProvider, setGatewayProvider] = useState('mock');
  const [gatewayMode, setGatewayMode] = useState('sandbox');
  const [gatewaySecret, setGatewaySecret] = useState('');
  const [gatewayHook, setGatewayHook] = useState('');
  const [gatewayView, setGatewayView] = useState<Record<string, unknown> | null>(null);

  async function loadPackages() {
    const res = await api('/platform/billing/plans');
    setPackages((res?.data || []) as PackageRow[]);
  }

  async function loadCompanies() {
    const res = await api('/platform/billing/companies');
    const list = (res?.data || []) as CompanyRow[];
    setRows(list);
    setSelectedSlug((current) => {
      if (current && list.some((row) => row.slug === current)) return current;
      return list[0]?.slug || '';
    });
  }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const me = await getMe();
      if (cancelled) return;
      const role = me.data?.role || '';
      if (!PLATFORM_ROLES.includes(role)) {
        router.replace('/dashboard');
        return;
      }
      const owner = role === 'platform_owner' || role === 'super_admin';
      setCanCreate(owner);
      setCanAssign(canAssignSubscription(me.data?.permissions || {}));
      await loadCompanies();
      if (owner) {
        try {
          await loadPackages();
        } catch (err: unknown) {
          const detail = err instanceof Error ? err.message : 'Could not load packages';
          if (!cancelled) setError(detail);
        }
        try {
          const status = await api('/platform/billing/status');
          const gateway = (status?.data?.gateway || {}) as Record<string, unknown>;
          if (!cancelled) {
            setGatewayView(gateway);
            setGatewayProvider(String(gateway.provider || 'mock'));
            setGatewayMode(String(gateway.mode || 'sandbox'));
          }
        } catch (err: unknown) {
          const detail = err instanceof Error ? err.message : 'Could not load the payment gateway';
          if (!cancelled) setError(detail);
        }
      }
      if (!cancelled) setReady(true);
    })().catch((err) => {
      if (!cancelled) setError(err.message || 'Could not load billing');
    });
    return () => {
      cancelled = true;
    };
  }, [router]);

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter((row) => row.company_name.toLowerCase().includes(needle));
  }, [rows, query]);

  const selected = rows.find((row) => row.slug === selectedSlug) || null;

  useEffect(() => {
    if (!selected) {
      setAmount('');
      return;
    }
    setAmount(selected.amount == null ? '' : formatNumber(selected.amount, prefs));
  }, [selectedSlug, selected?.amount, prefs]);

  function choose(row: CompanyRow) {
    setSelectedSlug(row.slug);
    setPackageCode(PACKAGES.some((item) => item.code === row.package_code) ? row.package_code : 'professional');
    setTermValue(row.term_value && row.term_value > 0 ? row.term_value : 12);
    setTermUnit(row.term_unit === 'years' ? 'years' : 'months');
    setLinkedPlan('');
    setError('');
    setMessage('');
  }

  async function assign(event: FormEvent) {
    event.preventDefault();
    if (!selected || !canAssign) return;
    const parsed = subscriptionAmountToSend(amount, packageCode, prefs);
    if ('error' in parsed) {
      setError(parsed.error);
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {
        package_code: packageCode,
        term_value: Number(termValue),
        term_unit: termUnit,
        activate: true,
        amount: parsed.amount,
      };
      if (startAt.trim()) body.start_at = startAt.trim();
      const savedPackage = packages.find((item) => item.code === linkedPlan);
      const periodMatches =
        savedPackage &&
        savedPackage.package_code === packageCode &&
        (savedPackage.interval === 'year') === (termUnit === 'years');
      if (savedPackage && periodMatches) body.plan_code = savedPackage.code;
      const saved = await api(`/tenants/${encodeURIComponent(selected.slug)}/subscription`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      const plan = saved?.data?.subscription?.package_name || packageCode;
      const shown = subscriptionAmountLabel(parsed.amount, selected.currency, formatNumber(parsed.amount, prefs));
      setMessage(
        `Assigned ${plan} for ${termValue} ${termUnit} at ${shown} to ${selected.company_name}. No payment was recorded.`,
      );
      setStartAt('');
      await loadCompanies();
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : 'Could not assign the plan';
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  function usePackage(item: PackageRow) {
    setPackageCode(item.package_code);
    setTermValue(1);
    setTermUnit(item.interval === 'year' ? 'years' : 'months');
    setAmount(formatNumber(item.amount, prefs));
    setLinkedPlan(item.code);
    setError('');
    setMessage(`${item.name} is ready to assign. Choose the tenant, then save.`);
  }

  function startEdit(item: PackageRow) {
    setEditingId(item.id);
    setShowCreate(true);
    setPackageName(item.name);
    setPackageSlug(item.code);
    setFeatureSet(item.package_code);
    setPackageInterval(item.interval === 'year' ? 'year' : 'month');
    setPackageAmount(formatNumber(item.amount, prefs));
    setPackageCurrency((item.currency || 'GHS').toUpperCase());
    setPendingDelete('');
    setError('');
    setMessage('');
  }

  function closePackageForm() {
    setShowCreate(false);
    setEditingId('');
    setPackageName('');
    setPackageSlug('');
    setPackageAmount('');
  }

  async function removePackage(item: PackageRow) {
    if (!canCreate) return;
    if (pendingDelete !== item.id) {
      setPendingDelete(item.id);
      setError('');
      setMessage('');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const saved = await api(`/platform/billing/plans/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
      if (linkedPlan === item.code) setLinkedPlan('');
      if (editingId === item.id) closePackageForm();
      setPendingDelete('');
      setMessage(saved?.message || 'Package deleted');
      await loadPackages();
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : 'Could not delete the package';
      setError(detail);
      setPendingDelete('');
    } finally {
      setBusy(false);
    }
  }

  async function createPackage(event: FormEvent) {
    event.preventDefault();
    if (!canCreate) return;
    const draft = {
      name: packageName,
      packageCode: featureSet,
      interval: packageInterval,
      amount: packageAmount,
      currency: packageCurrency,
    };
    const built = editingId
      ? packageUpdateBody(draft, prefs)
      : packageCreateBody(
          { ...draft, code: packageSlug || packageCodeFromName(packageName) },
          prefs,
        );
    if ('error' in built) {
      setError(built.error);
      setMessage('');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const saved = editingId
        ? await api(`/platform/billing/plans/${encodeURIComponent(editingId)}`, {
            method: 'PATCH',
            body: JSON.stringify(built.body),
          })
        : await api('/platform/billing/plans', { method: 'POST', body: JSON.stringify(built.body) });
      setMessage(saved?.message || (editingId ? 'Package updated' : 'Package created'));
      closePackageForm();
      await loadPackages();
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : 'Could not save the package';
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  if (!ready && !error) {
    return <p className="muted">Loading billing…</p>;
  }

  async function saveGateway(event: FormEvent) {
    event.preventDefault();
    const built = gatewaySaveBody({
      provider: gatewayProvider,
      mode: gatewayMode,
      secret: gatewaySecret,
      webhookSecret: gatewayHook,
    });
    if ('error' in built) {
      setError(built.error);
      setMessage('');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const saved = await api('/platform/billing/gateway', {
        method: 'PUT',
        body: JSON.stringify(built.body),
      });
      setGatewayView((saved?.data || {}) as Record<string, unknown>);
      setGatewaySecret('');
      setGatewayHook('');
      setMessage('Gateway saved. Run a connection test before enabling it.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not save the gateway');
    } finally {
      setBusy(false);
    }
  }

  async function testGateway() {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const tested = await api('/platform/billing/gateway/test', { method: 'POST' });
      setGatewayView((tested?.data || {}) as Record<string, unknown>);
      setMessage(tested?.data?.last_test_ok ? 'Connection test succeeded. No charge was made.' : 'Connection test failed.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not test the gateway');
    } finally {
      setBusy(false);
    }
  }

  async function setGatewayEnabled(enabled: boolean) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const saved = await api(enabled ? '/platform/billing/gateway/enable' : '/platform/billing/gateway/disable', {
        method: 'POST',
      });
      setGatewayView((saved?.data || {}) as Record<string, unknown>);
      setMessage(enabled ? 'Gateway enabled for checkout.' : 'Gateway disabled.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not update the gateway');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="plat">
      <header className="plat-hero">
        <div>
          <p className="plat-kicker">Software owner</p>
          <h1>Billing</h1>
          <p className="plat-sub">
            Each company, the plan assigned to it, and the term. Assigning a plan does not mark an
            invoice paid.
          </p>
        </div>
      </header>
      {canCreate && (
        <div className="plat-panel">
          <h2>Payment gateway</h2>
          <p>
            Choose Paystack or Flutterwave for hosted checkout. Sandbox does not charge. Saving a
            gateway does not mark an invoice paid.
          </p>
          <form className="plat-form" onSubmit={saveGateway}>
            <label>
              <span>Provider</span>
              <select
                aria-label="Billing gateway provider"
                value={gatewayProvider}
                onChange={(event) => setGatewayProvider(event.target.value)}
              >
                <option value="mock">Sandbox</option>
                <option value="paystack">Paystack</option>
                <option value="flutterwave">Flutterwave</option>
              </select>
            </label>
            <label>
              <span>Mode</span>
              <select
                aria-label="Billing gateway mode"
                value={gatewayMode}
                onChange={(event) => setGatewayMode(event.target.value)}
              >
                <option value="sandbox">Sandbox</option>
                <option value="live">Live</option>
              </select>
            </label>
            <label>
              <span>Secret key</span>
              <input
                aria-label="Billing gateway secret"
                type="password"
                autoComplete="off"
                value={gatewaySecret}
                onChange={(event) => setGatewaySecret(event.target.value)}
              />
            </label>
            <label>
              <span>Webhook secret</span>
              <input
                aria-label="Billing gateway webhook secret"
                type="password"
                autoComplete="off"
                value={gatewayHook}
                onChange={(event) => setGatewayHook(event.target.value)}
              />
            </label>
            <button aria-label="Save billing gateway" className="btn-primary" type="submit" disabled={busy}>
              Save gateway
            </button>
            <button aria-label="Test billing gateway" type="button" disabled={busy} onClick={testGateway}>
              Test connection
            </button>
            <button aria-label="Enable billing gateway" className="btn-ok" type="button" disabled={busy} onClick={() => setGatewayEnabled(true)}>
              Enable
            </button>
          </form>
          {gatewayView?.webhook_url ? <p>Webhook URL: {String(gatewayView.webhook_url)}</p> : null}
          {gatewayView?.secret_hint ? <p>Saved secret ends {String(gatewayView.secret_hint)}</p> : null}
        </div>
      )}
      {error && (
        <p className="login-error" role="alert">
          {error}
        </p>
      )}
      {message && <p>{message}</p>}
      {canAssign && selected && (
        <div className="plat-panel">
          <h2>Assign plan</h2>
          <form className="plat-form" onSubmit={assign}>
            <label>
              <span>Tenant</span>
              <select
                aria-label="Assign plan tenant"
                value={selected.slug}
                onChange={(event) => {
                  const row = rows.find((item) => item.slug === event.target.value);
                  if (row) choose(row);
                }}
              >
                {rows.map((row) => (
                  <option key={row.slug} value={row.slug}>
                    {row.company_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Package</span>
              <select
                aria-label="Subscription package"
                value={packageCode}
                onChange={(event) => {
                  setPackageCode(event.target.value);
                  setLinkedPlan('');
                }}
              >
                {PACKAGES.map((item) => (
                  <option key={item.code} value={item.code}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Term length</span>
              <input
                aria-label="Subscription term length"
                type="number"
                min={1}
                max={120}
                value={termValue}
                onChange={(event) => setTermValue(Number(event.target.value) || 1)}
                required
              />
            </label>
            <label>
              <span>Term unit</span>
              <select
                aria-label="Subscription term unit"
                value={termUnit}
                onChange={(event) => {
                  setTermUnit(event.target.value);
                  setLinkedPlan('');
                }}
              >
                <option value="months">Months</option>
                <option value="years">Years</option>
              </select>
            </label>
            <label>
              <span>Amount</span>
              <input
                aria-label="Subscription amount"
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                required
              />
            </label>
            <label>
              <span>Start date</span>
              <input
                aria-label="Subscription start date"
                type="text"
                placeholder="YYYY-MM-DD (blank = now)"
                value={startAt}
                onChange={(event) => setStartAt(event.target.value)}
              />
            </label>
            <button aria-label="Assign subscription plan" className="btn-primary" type="submit" disabled={busy}>
              {busy ? 'Saving…' : 'Assign plan'}
            </button>
          </form>
        </div>
      )}
      {ready && !canAssign && (
        <p className="muted">You can view company plans. Assigning a plan needs package access.</p>
      )}
      {canCreate && (
        <div className="plat-panel">
          <h2>Packages</h2>
          {packages.length === 0 ? (
            <p className="muted">No packages yet.</p>
          ) : (
            <table className="table pkg-table" aria-label="Billing packages">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Features</th>
                  <th>Period</th>
                  <th>Amount</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {packages.map((item) => (
                  <tr key={item.id}>
                    <td>{item.name}</td>
                    <td>{plainLabel(item.package_code)}</td>
                    <td>{item.interval === 'year' ? 'Yearly' : 'Monthly'}</td>
                    <td>
                      {subscriptionAmountLabel(item.amount, item.currency, formatNumber(item.amount, prefs))}
                      {!item.is_active ? ' (inactive)' : ''}
                    </td>
                    <td className="pkg-actions">
                      <button
                        type="button"
                        aria-label={`Use package ${item.name}`}
                        onClick={() => usePackage(item)}
                      >
                        Use
                      </button>
                      <button
                        type="button"
                        aria-label={`Edit package ${item.name}`}
                        onClick={() => startEdit(item)}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn-danger"
                        aria-label={
                          pendingDelete === item.id
                            ? `Confirm delete package ${item.name}`
                            : `Delete package ${item.name}`
                        }
                        onClick={() => removePackage(item)}
                        disabled={busy}
                      >
                        {pendingDelete === item.id ? 'Confirm delete' : 'Delete'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!showCreate ? (
            <button
              type="button"
              className="btn-primary"
              aria-label="Create package"
              onClick={() => {
                closePackageForm();
                setShowCreate(true);
                setError('');
                setMessage('');
              }}
            >
              Create package
            </button>
          ) : (
            <form className="plat-form" onSubmit={createPackage}>
              <label>
                <span>Package name</span>
                <input
                  aria-label="Package name"
                  value={packageName}
                  onChange={(event) => {
                    const next = event.target.value;
                    setPackageName(next);
                    if (!editingId) setPackageSlug(packageCodeFromName(next));
                  }}
                  required
                />
              </label>
              <label>
                <span>Code</span>
                <input
                  aria-label="Package code"
                  value={packageSlug}
                  onChange={(event) => setPackageSlug(event.target.value)}
                  readOnly={Boolean(editingId)}
                  required
                />
              </label>
              <label>
                <span>Features</span>
                <select
                  aria-label="Package features"
                  value={featureSet}
                  onChange={(event) => setFeatureSet(event.target.value)}
                >
                  <option value="starter">Starter</option>
                  <option value="professional">Professional</option>
                  <option value="enterprise">Enterprise</option>
                </select>
              </label>
              <label>
                <span>Period</span>
                <select
                  aria-label="Package period"
                  value={packageInterval}
                  onChange={(event) => setPackageInterval(event.target.value)}
                >
                  <option value="month">Monthly</option>
                  <option value="year">Yearly</option>
                </select>
              </label>
              <label>
                <span>Amount</span>
                <input
                  aria-label="Package amount"
                  inputMode="decimal"
                  value={packageAmount}
                  onChange={(event) => setPackageAmount(event.target.value)}
                  required
                />
              </label>
              <label>
                <span>Currency</span>
                <select
                  aria-label="Package currency"
                  value={packageCurrency}
                  onChange={(event) => setPackageCurrency(event.target.value)}
                >
                  <option value="GHS">GHS</option>
                  <option value="USD">USD</option>
                </select>
              </label>
              <button aria-label="Save package" className="btn-primary" type="submit" disabled={busy}>
                {busy ? 'Saving…' : editingId ? 'Save changes' : 'Save package'}
              </button>
              <button
                type="button"
                aria-label="Cancel create package"
                onClick={closePackageForm}
              >
                Cancel
              </button>
            </form>
          )}
        </div>
      )}
      <div className="plat-panel">
        <h2>Companies</h2>
        <label>
          Find company
          <input
            aria-label="Find company"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        {visible.length === 0 ? (
          <p className="muted">No companies to show.</p>
        ) : (
          <table className="table" aria-label="Company plans">
            <thead>
              <tr>
                <th>Company</th>
                <th>Plan</th>
                <th>Amount</th>
                <th>Term</th>
                <th>Status</th>
                <th>Renews</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={row.slug} className={row.slug === selectedSlug ? 'is-selected' : undefined}>
                  <td>
                    <button type="button" aria-label={`Select ${row.company_name}`} onClick={() => choose(row)}>
                      {row.company_name}
                    </button>
                  </td>
                  <td>{row.plan}</td>
                  <td>
                    {subscriptionAmountLabel(row.amount, row.currency, formatNumber(row.amount, prefs))}
                  </td>
                  <td>{subscriptionTermLabel(row.term_value, row.term_unit)}</td>
                  <td>{plainLabel(row.status)}</td>
                  <td>{formatWhen(row.renews, prefs) || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
