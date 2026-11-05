'use client';

import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '../../../../lib/api';
import { formatNumber, formatWhen, plainLabel } from '../../../../lib/format';
import { AmountField } from '../../../../components/AmountField';
import EmptyState from '../../../../components/EmptyState';
import FormModal from '../../../../components/FormModal';
import RowActions from '../../../../components/RowActions';
import StatusChip from '../../../../components/StatusChip';
import { Tabs, Tag, TenantStatus, type PlatTab } from '../../../../components/PlatformUi';
import PageHeader from '../../../../components/PageHeader';
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

function dayOnly(value: string | null | undefined, prefs: Parameters<typeof formatWhen>[1]) {
  const shown = formatWhen(value, prefs);
  // formatWhen always ends with the clock time; plans and invoices only need the day.
  return shown ? shown.replace(/\s+\d{1,2}:\d{2}(\s*[AP]M)?$/i, '') : '—';
}

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

type AttentionRow = {
  slug?: string | null;
  company_name?: string | null;
  tenant_status?: string | null;
  billing_status?: string | null;
  authorization_present?: boolean;
  access_note?: string | null;
  plan?: {
    amount?: number | null;
    currency?: string | null;
    name?: string | null;
    code?: string | null;
  } | null;
};

type InvoiceRow = {
  id?: string;
  status?: string;
  amount?: number | null;
  currency?: string | null;
  description?: string | null;
  period_start?: string | null;
  period_end?: string | null;
  paid_at?: string | null;
  created_at?: string | null;
  gateway_reference?: string | null;
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
  const [gatewayName, setGatewayName] = useState('');
  const [gatewayUrl, setGatewayUrl] = useState('');
  const [gatewayMode, setGatewayMode] = useState('sandbox');
  const [gatewaySecret, setGatewaySecret] = useState('');
  const [gatewayHook, setGatewayHook] = useState('');
  const [gatewayView, setGatewayView] = useState<Record<string, unknown> | null>(null);
  const [attention, setAttention] = useState<AttentionRow[]>([]);
  const [paySlug, setPaySlug] = useState('');
  const [payAmount, setPayAmount] = useState('');
  const [payCurrency, setPayCurrency] = useState('GHS');
  const [payReference, setPayReference] = useState('');
  const [payNote, setPayNote] = useState('');
  const [invoices, setInvoices] = useState<InvoiceRow[]>([]);
  const [tab, setTab] = useState('companies');
  const [assignOpen, setAssignOpen] = useState(false);

  useEffect(() => {
    // The console links straight to a section, e.g. ?tab=attention.
    const wanted = new URLSearchParams(window.location.search).get('tab');
    if (wanted) setTab(wanted);
  }, []);

  async function loadPackages() {
    const res = await api('/platform/billing/plans');
    setPackages((res?.data || []) as PackageRow[]);
  }

  async function loadAttention() {
    const res = await api('/platform/billing/attention');
    setAttention((res?.data || []) as AttentionRow[]);
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
          await loadAttention();
        } catch (err: unknown) {
          const detail = err instanceof Error ? err.message : 'Could not load billing attention';
          if (!cancelled) setError(detail);
        }
        try {
          const status = await api('/platform/billing/status');
          const gateway = (status?.data?.gateway || {}) as Record<string, unknown>;
          if (!cancelled) {
            setGatewayView(gateway);
            const savedProvider = String(gateway.provider || 'mock');
            const builtin = savedProvider === 'mock' || savedProvider === 'paystack' || savedProvider === 'flutterwave';
            setGatewayProvider(builtin ? savedProvider : 'other');
            setGatewayName(builtin ? '' : savedProvider);
            setGatewayUrl(String(gateway.api_base_url || ''));
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

  useEffect(() => {
    if (!canCreate || !selectedSlug) {
      setInvoices([]);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await api(`/platform/billing/tenants/${encodeURIComponent(selectedSlug)}`);
        if (!cancelled) setInvoices((res?.data?.invoices || []) as InvoiceRow[]);
      } catch {
        if (!cancelled) setInvoices([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [canCreate, selectedSlug]);

  function choose(row: CompanyRow) {
    setSelectedSlug(row.slug);
    setPackageCode(PACKAGES.some((item) => item.code === row.package_code) ? row.package_code : 'professional');
    setTermValue(row.term_value && row.term_value > 0 ? row.term_value : 12);
    setTermUnit(row.term_unit === 'years' ? 'years' : 'months');
    setLinkedPlan('');
    setError('');
    setMessage('');
  }

  function beginManualPayment(row: AttentionRow) {
    const slug = String(row.slug || '').trim();
    if (!slug) return;
    setPaySlug(slug);
    const planAmount = row.plan?.amount;
    setPayAmount(planAmount == null ? '' : formatNumber(planAmount, prefs));
    setPayCurrency(String(row.plan?.currency || 'GHS').toUpperCase() === 'USD' ? 'USD' : 'GHS');
    setPayReference('');
    setPayNote('');
    setError('');
    setMessage('');
  }

  async function recordManualPayment(event: FormEvent) {
    event.preventDefault();
    if (!canCreate || !paySlug) return;
    const parsed = subscriptionAmountToSend(payAmount, 'professional', prefs);
    if ('error' in parsed) {
      setError(parsed.error);
      return;
    }
    const reference = payReference.trim();
    if (reference.length < 2) {
      setError('Payment reference is required.');
      return;
    }
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {
        amount: parsed.amount,
        currency: payCurrency,
        reference,
      };
      const note = payNote.trim();
      if (note) body.note = note;
      await api(`/platform/billing/tenants/${encodeURIComponent(paySlug)}/payments`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setMessage(`Manual payment recorded for ${paySlug}.`);
      setPaySlug('');
      setPayReference('');
      setPayNote('');
      await loadCompanies();
      await loadAttention();
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : 'Could not record the payment';
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  async function retryBilling(slug: string) {
    if (!canCreate || !slug) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const res = await api(`/platform/billing/tenants/${encodeURIComponent(slug)}/retry`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      const outcome = res?.data?.outcome ?? res?.data;
      setMessage(`Retry processed for ${slug}${outcome ? `: ${String(outcome)}` : ''}.`);
      await loadCompanies();
      await loadAttention();
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : 'Could not retry the charge';
      setError(detail);
    } finally {
      setBusy(false);
    }
  }

  async function restoreBillingAccess(slug: string) {
    if (!canCreate || !slug) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const res = await api(`/platform/billing/tenants/${encodeURIComponent(slug)}/reactivate`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      const charged = res?.data?.charged;
      setMessage(
        charged === false
          ? `Access restored for ${slug}. No charge was created.`
          : `Access restored for ${slug}.`,
      );
      await loadCompanies();
      await loadAttention();
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : 'Could not restore access';
      setError(detail);
    } finally {
      setBusy(false);
    }
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
      setAssignOpen(false);
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
    setMessage('');
    setAssignOpen(true);
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
      name: gatewayName,
      mode: gatewayMode,
      secret: gatewaySecret,
      webhookSecret: gatewayHook,
      apiBaseUrl: gatewayUrl,
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

  const tabs: PlatTab[] = [{ key: 'companies', label: 'Companies', count: rows.length }];
  if (canCreate) {
    tabs.push(
      { key: 'attention', label: 'Needs attention', count: attention.length, alert: attention.length > 0 },
      { key: 'packages', label: 'Packages', count: packages.length },
      { key: 'gateway', label: 'Payment gateway' },
    );
  }
  const activeTab = tabs.some((item) => item.key === tab) ? tab : 'companies';

  return (
    <div className="plat">
      <PageHeader
        className="plat-hero"
        kicker="Software owner"
        kickerClassName="plat-kicker"
        title="Billing"
        subtitle="Each company, the plan assigned to it, and the term. Assigning a plan does not mark an invoice paid."
        subtitleClassName="plat-sub"
      />
      <Tabs label="Billing sections" tabs={tabs} active={activeTab} onChange={setTab} />

      {activeTab === 'companies' ? (
        <>
          {ready && !canAssign && (
            <p className="plat-note">You can view company plans. Assigning a plan needs package access.</p>
          )}
          <div className="plat-panel">
            <div className="plat-panel-head">
              <h2>Companies</h2>
              <label className="plat-search" style={{ flexBasis: 280 }}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <circle cx="11" cy="11" r="7" />
                  <path d="M20 20l-3.5-3.5" />
                </svg>
                <input
                  aria-label="Find company"
                  placeholder="Find company"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
            </div>
            {visible.length === 0 ? (
              <EmptyState title="No companies to show." />
            ) : (
              <div className="plat-table-wrap is-open">
                <table className="table" aria-label="Company plans">
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Plan</th>
                      <th className="col-right">Amount</th>
                      <th className="plat-hide-sm">Term</th>
                      <th>Status</th>
                      <th className="plat-hide-sm">Renews</th>
                      {canAssign ? <th className="col-right">Actions</th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((row) => (
                      <tr key={row.slug} className={row.slug === selectedSlug ? 'is-selected' : undefined}>
                        <td>
                          <button
                            type="button"
                            className="plat-link"
                            aria-label={`Select ${row.company_name}`}
                            onClick={() => choose(row)}
                          >
                            {row.company_name}
                          </button>
                        </td>
                        <td>{row.plan}</td>
                        <td className="col-right">
                          {subscriptionAmountLabel(row.amount, row.currency, formatNumber(row.amount, prefs))}
                        </td>
                        <td className="plat-hide-sm">{subscriptionTermLabel(row.term_value, row.term_unit)}</td>
                        <td>
                          <TenantStatus status={row.status} />
                        </td>
                        <td className="plat-hide-sm">{dayOnly(row.renews, prefs)}</td>
                        {canAssign ? (
                          <td className="plat-actions-cell col-right">
                            <button
                              type="button"
                              aria-label={`Assign plan to ${row.company_name}`}
                              onClick={() => {
                                choose(row);
                                setAssignOpen(true);
                              }}
                            >
                              Assign plan
                            </button>
                          </td>
                        ) : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          {canCreate && selectedSlug ? (
            <div className="plat-panel">
              <div className="plat-panel-head">
                <h2>Subscription invoices — {selected?.company_name || selectedSlug}</h2>
              </div>
              <p className="plat-panel-sub">
                Settled SaaS invoices for this company. PDF email remains on the company billing page
                when configured; this list is the owner ledger view.
              </p>
              {invoices.length === 0 ? (
                <p className="muted">No subscription invoices yet.</p>
              ) : (
                <div className="plat-table-wrap">
                  <table className="table" aria-label="Owner subscription invoices">
                    <thead>
                      <tr>
                        <th>Status</th>
                        <th className="col-right">Amount</th>
                        <th className="plat-hide-sm">Description</th>
                        <th className="plat-hide-sm">Period</th>
                        <th>Paid</th>
                        <th className="plat-hide-sm">Reference</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.map((inv) => (
                        <tr key={inv.id || `${inv.created_at}-${inv.amount}`}>
                          <td>
                            <StatusChip value={inv.status} label={plainLabel(inv.status || '')} />
                          </td>
                          <td className="col-right">
                            {subscriptionAmountLabel(
                              inv.amount ?? null,
                              inv.currency,
                              formatNumber(inv.amount, prefs),
                            )}
                          </td>
                          <td className="plat-hide-sm">{inv.description || '—'}</td>
                          <td className="plat-hide-sm">
                            {dayOnly(inv.period_start, prefs)} → {dayOnly(inv.period_end, prefs)}
                          </td>
                          <td>{dayOnly(inv.paid_at, prefs)}</td>
                          <td className="plat-hide-sm">{inv.gateway_reference || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : null}
        </>
      ) : null}

      {activeTab === 'attention' ? (
        <div className="plat-panel">
          <div className="plat-panel-head">
            <h2>Needs attention</h2>
          </div>
          <p className="plat-panel-sub">
            Past-due, grace, payment-required, and suspended billing accounts. Recording a payment
            requires amount and currency that match the assigned plan. Restore access does not create
            a charge.
          </p>
          {attention.length === 0 ? (
            <p className="plat-allclear">No companies need billing attention.</p>
          ) : (
            <div className="plat-table-wrap is-open">
              <table className="table" aria-label="Billing attention list">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Billing status</th>
                    <th className="plat-hide-sm">Plan</th>
                    <th className="plat-hide-sm">Saved card</th>
                    <th className="col-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {attention.map((row) => {
                    const slug = String(row.slug || '');
                    const planLabel = row.plan?.name || row.plan?.code || '—';
                    const planAmt =
                      row.plan?.amount == null
                        ? '—'
                        : subscriptionAmountLabel(
                            row.plan.amount,
                            row.plan.currency,
                            formatNumber(row.plan.amount, prefs),
                          );
                    return (
                      <tr key={`${slug}-${row.billing_status || 'attention'}`}>
                        <td>
                          <span className="plat-co">{row.company_name || slug || '—'}</span>
                          {row.tenant_status ? (
                            <span className="plat-small">{plainLabel(row.tenant_status)}</span>
                          ) : null}
                        </td>
                        <td>
                          <Tag tone={row.billing_status === 'suspended' ? 'bad' : 'warn'}>
                            {plainLabel(row.billing_status || '')}
                          </Tag>
                        </td>
                        <td className="plat-hide-sm">
                          {planLabel}
                          <span className="plat-small">{planAmt}</span>
                        </td>
                        <td className="plat-hide-sm">{row.authorization_present ? 'Saved' : 'None'}</td>
                        <td className="plat-actions-cell col-right">
                          <RowActions
                            label={`More billing actions for ${row.company_name || slug}`}
                            items={[
                              {
                                key: 'pay',
                                label: 'Record payment',
                                ariaLabel: `Record manual payment ${slug}`,
                                onClick: () => beginManualPayment(row),
                                disabled: busy || !slug,
                              },
                              {
                                key: 'retry',
                                label: 'Retry charge',
                                ariaLabel: `Retry billing charge ${slug}`,
                                onClick: () => retryBilling(slug),
                                disabled: busy || !slug || !row.authorization_present,
                                title: row.authorization_present ? undefined : 'No saved card to charge',
                              },
                              {
                                key: 'restore',
                                label: 'Restore access',
                                ariaLabel: `Restore billing access ${slug}`,
                                variant: 'ok',
                                onClick: () => restoreBillingAccess(slug),
                                disabled: busy || !slug,
                              },
                            ]}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}

      {activeTab === 'packages' ? (
        <div className="plat-panel">
          <div className="plat-panel-head">
            <h2>Packages</h2>
            <button
              type="button"
              className="plat-cta"
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
          </div>
          {packages.length === 0 ? (
            <EmptyState title="No packages yet." detail="Create a package to reuse a plan and price." />
          ) : (
            <div className="plat-table-wrap">
              <table className="table pkg-table" aria-label="Billing packages">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Features</th>
                    <th>Period</th>
                    <th className="col-right">Amount</th>
                    <th className="col-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {packages.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <span className="plat-co">{item.name}</span>
                        {!item.is_active ? <span className="plat-small">Inactive</span> : null}
                      </td>
                      <td>{plainLabel(item.package_code)}</td>
                      <td>{item.interval === 'year' ? 'Yearly' : 'Monthly'}</td>
                      <td className="col-right">
                        {subscriptionAmountLabel(item.amount, item.currency, formatNumber(item.amount, prefs))}
                      </td>
                      <td className="pkg-actions plat-actions-cell col-right">
                        <span className="plat-row-actions">
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
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}

      {activeTab === 'gateway' ? (
        <div className="plat-cols">
          <div className="plat-panel">
            <div className="plat-panel-head">
              <h2>Payment gateway</h2>
            </div>
            <p className="plat-panel-sub">
              Choose Paystack, Flutterwave, or another gateway. Sandbox does not charge. Saving a
              gateway does not mark an invoice paid. Another gateway needs a public https address, a
              health check that does not charge, and a signed webhook.
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
                  <option value="other">Other gateway</option>
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
              {gatewayProvider === 'other' ? (
                <>
                  <label>
                    <span>Gateway name</span>
                    <input
                      aria-label="Billing gateway name"
                      value={gatewayName}
                      onChange={(event) => setGatewayName(event.target.value)}
                      placeholder="hubtel"
                    />
                  </label>
                  <label>
                    <span>API address</span>
                    <input
                      aria-label="Billing gateway API address"
                      value={gatewayUrl}
                      onChange={(event) => setGatewayUrl(event.target.value)}
                      placeholder="https://api.example.com"
                    />
                  </label>
                </>
              ) : null}
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
              <div className="plat-form-actions">
                <button aria-label="Save billing gateway" className="btn-primary" type="submit" disabled={busy}>
                  Save gateway
                </button>
                <button aria-label="Test billing gateway" type="button" disabled={busy} onClick={testGateway}>
                  Test connection
                </button>
              </div>
            </form>
          </div>
          <div className="plat-panel">
            <div className="plat-panel-head">
              <h2>Current status</h2>
            </div>
            <table className="plat-kv" aria-label="Billing gateway current status">
              <tbody>
                <tr>
                  <th scope="row">Provider</th>
                  <td>{gatewayView?.provider ? plainLabel(String(gatewayView.provider)) : 'Not set'}</td>
                </tr>
                <tr>
                  <th scope="row">Mode</th>
                  <td>{gatewayView?.mode ? plainLabel(String(gatewayView.mode)) : '—'}</td>
                </tr>
                {gatewayView?.secret_hint ? (
                  <tr>
                    <th scope="row">Saved secret ends</th>
                    <td>{String(gatewayView.secret_hint)}</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
            {gatewayView?.webhook_url ? (
              <p className="plat-hint" style={{ overflowWrap: 'anywhere' }}>
                Webhook URL: <code>{String(gatewayView.webhook_url)}</code>
              </p>
            ) : null}
            <div className="plat-row-actions" style={{ justifyContent: 'flex-start', marginTop: 14 }}>
              <button aria-label="Enable billing gateway" className="btn-ok" type="button" disabled={busy} onClick={() => setGatewayEnabled(true)}>
                Enable
              </button>
              <button aria-label="Disable billing gateway" className="btn-danger" type="button" disabled={busy} onClick={() => setGatewayEnabled(false)}>
                Disable
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {paySlug ? (
        <FormModal
          title={`Manual payment — ${paySlug}`}
          busy={busy}
          dirty={Boolean(payReference.trim() || payNote.trim())}
          onClose={() => {
            setPaySlug('');
            setPayReference('');
            setPayNote('');
          }}
        >
          <form className="plat-form" onSubmit={recordManualPayment}>
            <p className="plat-note plat-form-full">Amount and currency must match the assigned billing plan.</p>
            <label>
              <span>Amount</span>
              <AmountField
                aria-label="Manual billing payment amount"
                currency={payCurrency}
                inputMode="decimal"
                value={payAmount}
                onChange={(event) => setPayAmount(event.target.value)}
                required
              />
            </label>
            <label>
              <span>Currency</span>
              <select
                aria-label="Manual billing payment currency"
                value={payCurrency}
                onChange={(event) => setPayCurrency(event.target.value)}
              >
                <option value="GHS">GHS</option>
                <option value="USD">USD</option>
              </select>
            </label>
            <label>
              <span>Reference</span>
              <input
                aria-label="Manual billing payment reference"
                value={payReference}
                onChange={(event) => setPayReference(event.target.value)}
                required
                minLength={2}
              />
            </label>
            <label>
              <span>Note</span>
              <input
                aria-label="Manual billing payment note"
                value={payNote}
                onChange={(event) => setPayNote(event.target.value)}
              />
            </label>
            <div className="plat-form-actions">
              <button
                aria-label="Save manual billing payment"
                className="btn-primary"
                type="submit"
                disabled={busy}
              >
                {busy ? 'Saving…' : 'Save payment'}
              </button>
              <button
                type="button"
                aria-label="Cancel manual billing payment"
                onClick={() => {
                  setPaySlug('');
                  setPayReference('');
                  setPayNote('');
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        </FormModal>
      ) : null}

      {assignOpen && canAssign && selected ? (
        <FormModal title="Assign plan" busy={busy} onClose={() => setAssignOpen(false)}>
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
              <AmountField
                aria-label="Subscription amount"
                currency={selected?.currency}
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
            <div className="plat-form-actions">
              <button aria-label="Assign subscription plan" className="btn-primary" type="submit" disabled={busy}>
                {busy ? 'Saving…' : 'Assign plan'}
              </button>
            </div>
          </form>
        </FormModal>
      ) : null}

      {showCreate ? (
        <FormModal title={editingId ? 'Edit package' : 'Create package'} busy={busy} onClose={closePackageForm}>
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
              <AmountField
                aria-label="Package amount"
                currency={packageCurrency}
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
            <div className="plat-form-actions">
              <button aria-label="Save package" className="btn-primary" type="submit" disabled={busy}>
                {busy ? 'Saving…' : editingId ? 'Save changes' : 'Save package'}
              </button>
              <button type="button" aria-label="Cancel create package" onClick={closePackageForm}>
                Cancel
              </button>
            </div>
          </form>
        </FormModal>
      ) : null}

      {(error || message) && (
        <div className="plat-feedback-dock" aria-live="polite">
          {error ? (
            <div className="plat-toast is-bad" role="alert">
              <p>{error}</p>
              <button type="button" aria-label="Dismiss error" onClick={() => setError('')}>
                ×
              </button>
            </div>
          ) : null}
          {message ? (
            <div className="plat-toast" role="status">
              <p>{message}</p>
              <button type="button" aria-label="Dismiss message" onClick={() => setMessage('')}>
                ×
              </button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
