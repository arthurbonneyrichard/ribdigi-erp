'use client';

import { useEffect, useState } from 'react';
import PageHeader from '../../../components/PageHeader';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import './notify-ui.css';

type Note = {
  id: string;
  category: string;
  title: string;
  message: string;
  status: string;
  created_at: string;
};

/** BR-4.4 category chips — maps to backend notification categories. */
const PLATFORM_ROLES = new Set([
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
]);

/** Store operations stay on the tenant notification list. */
const OPERATIONAL_CATEGORIES = new Set([
  'low_stock',
  'new_order',
  'payment_due',
  'purchase_received',
  'credit_limit',
  'shift_variance',
  'expense_approval',
  'quotation_expiry',
  'batch_expiry',
  'recurring_expense_due',
  'transfer',
]);

const PLATFORM_CATEGORY_CHIPS: { id: string; label: string }[] = [
  { id: '', label: 'All platform' },
  { id: 'provisioning', label: 'Provisioning' },
  { id: 'platform_security', label: 'Platform security' },
  { id: 'staff_account', label: 'Staff accounts' },
  { id: 'admin_password_reset', label: 'Password resets' },
  { id: 'platform', label: 'Platform actions' },
  { id: 'security', label: 'Security' },
];

const CATEGORY_CHIPS: { id: string; label: string }[] = [
  { id: '', label: 'All types' },
  { id: 'low_stock', label: 'Stock' },
  { id: 'new_order', label: 'Orders' },
  { id: 'payment_due', label: 'Payments' },
  { id: 'purchase_received', label: 'Purchasing' },
  { id: 'credit_limit', label: 'Credit' },
  { id: 'shift_variance', label: 'POS' },
  { id: 'expense_approval', label: 'Expenses' },
  { id: 'quotation_expiry', label: 'Quotations' },
  { id: 'batch_expiry', label: 'Expiry' },
  { id: 'recurring_expense_due', label: 'Recurring' },
  { id: 'transfer', label: 'Transfers' },
  { id: 'system', label: 'System' },
  { id: 'security', label: 'Security' },
  { id: 'billing', label: 'Billing' },
];

export default function Page() {
  const [rows, setRows] = useState<Note[]>([]);
  const [status, setStatus] = useState('');
  const [category, setCategory] = useState('');
  const [prefs, setPrefs] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [prefsError, setPrefsError] = useState('');
  const [platformAudience, setPlatformAudience] = useState(false);

  useEffect(() => {
    getMe()
      .then((me) => setPlatformAudience(PLATFORM_ROLES.has(me.data?.role || '')))
      .catch(() => setPlatformAudience(false));
  }, []);

  const chips = platformAudience ? PLATFORM_CATEGORY_CHIPS : CATEGORY_CHIPS;

  async function refresh() {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (category) params.set('category', category);
    params.set('limit', '100');
    const q = `?${params.toString()}`;
    const notes = await api(`/notifications${q}`);
    setRows(notes.data || []);
    try {
      const settings = await api('/notifications/settings');
      setPrefs(settings.data);
      setPrefsError('');
    } catch (err: any) {
      setPrefs(null);
      setPrefsError(err?.message || 'Channel preferences could not be loaded. Refresh this page to try again.');
    }
  }

  function categoryLabel(id: string): string {
    const chip = chips.find((c) => c.id === id);
    if (chip) return chip.label;
    return id.split('_').join(' ');
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [status, category]);

  async function markRead(id: string) {
    setError('');
    try {
      await api(`/notifications/${id}/read`, { method: 'PATCH' });
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function markUnread(id: string) {
    setError('');
    try {
      await api(`/notifications/${id}/unread`, { method: 'PATCH' });
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function markAll() {
    setError('');
    try {
      const r = await api('/notifications/read-all', { method: 'POST' });
      setMessage(`Marked ${r.data?.marked ?? 0} read`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function scanDue() {
    setError('');
    try {
      const r = await api('/notifications/scan-due', { method: 'POST' });
      const payment = r.data?.payment_due ?? 0;
      const quotes = r.data?.quotation_expiry ?? 0;
      const recurring = r.data?.recurring_expense_due ?? 0;
      setMessage(
        `Due alerts created: ${r.data?.created ?? 0} (payment ${payment}, quotations ${quotes}, recurring ${recurring})`,
      );
      setStatus('unread');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function togglePref(categoryKey: string, channel: string) {
    if (!prefs) return;
    const next = {
      ...prefs,
      [categoryKey]: {
        ...prefs[categoryKey],
        [channel]: !prefs[categoryKey]?.[channel],
      },
    };
    setError('');
    try {
      const r = await api('/notifications/settings', {
        method: 'PATCH',
        body: JSON.stringify({ preferences: next }),
      });
      setPrefs(r.data);
      setMessage('Preferences saved');
    } catch (err: any) {
      setError(err.message);
    }
  }

  const emptyCopy =
    status === 'unread'
      ? platformAudience
        ? 'No unread alerts. Choose All (90 days) to see older platform notices.'
        : 'No unread alerts. Choose All (90 days) to see older ones, or Scan due alerts to look for payments and quotations.'
      : platformAudience
        ? 'Nothing matches this view. Choose All platform or another type above.'
        : 'Nothing matches this view. Choose All types, or Scan due alerts to look for payments and quotations.';

  return (
    <div className="notify-ui">
      <PageHeader
        title="Unread alerts"
        subtitle="Start with unread items. Mark one read when you have dealt with it. All (90 days) keeps the recent history."
      />
      {platformAudience ? (
        <p className="muted notify-ui-note">
          Platform Owner notices only: provisioning, platform security, staff accounts, administrator
          password resets, and other platform actions. Stock, orders, payments, and POS stay on
          tenant notification lists.
        </p>
      ) : null}
      {error && <p className="notify-ui-alert" role="alert">{error}</p>}
      {message && <p className="notify-ui-ok" role="status">{message}</p>}

      <div className="notify-ui-actions">
        <button
          onClick={() => setStatus('unread')}
          disabled={status === 'unread'}
          aria-label="Filter unread notifications"
        >
          Unread
        </button>
        <button
          onClick={() => setStatus('')}
          disabled={status === ''}
          aria-label="Filter all notifications"
        >
          All (90 days)
        </button>
        <button onClick={markAll} aria-label="Mark all notifications read">Mark all read</button>
        {!platformAudience ? (
          <button onClick={scanDue} aria-label="Scan due notification alerts">
            Scan due alerts
          </button>
        ) : null}
      </div>

      <div className="notif-chips" aria-label="Filter by category">
        {chips.map((c) => (
          <button
            key={c.id || 'all'}
            type="button"
            className={category === c.id ? 'notif-chip active' : 'notif-chip'}
            onClick={() => setCategory(c.id)}
            aria-label={`Filter notifications by ${c.label}`}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="notify-ui-scroll">
      <table className="table">
        <thead>
          <tr>
            <th>Type</th>
            <th>Title</th>
            <th>Message</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={5} className="muted">
                {emptyCopy}
              </td>
            </tr>
          ) : (
            rows.map((n) => (
            <tr key={n.id}>
              <td>{categoryLabel(n.category)}</td>
              <td>{n.title}</td>
              <td>{n.message}</td>
              <td>{n.status === 'unread' ? 'Unread' : 'Read'}</td>
              <td>
                <div className="notify-ui-row-actions">
                {n.status === 'unread' ? (
                  <button onClick={() => markRead(n.id)} aria-label={`Mark notification ${n.id} read`}>Mark read</button>
                ) : (
                  <button onClick={() => markUnread(n.id)} aria-label={`Mark notification ${n.id} unread`}>Mark unread</button>
                )}
                </div>
              </td>
            </tr>
            ))
          )}
        </tbody>
      </table>
      </div>

      <details className="card notify-ui-advanced">
        <summary>Channel preferences</summary>
        <p className="muted notify-ui-note">
          Choose whether each type also sends email or SMS. Dashboard stays the in-app list.
        </p>
        {prefsError ? <p className="notify-ui-alert" role="alert">{prefsError}</p> : null}
        {prefs ? (
          <div className="notify-ui-scroll">
          <table className="table" aria-label="Channel preferences">
            <thead>
              <tr>
                <th>Type</th>
                <th>Dashboard</th>
                <th>Email</th>
                <th>SMS</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(prefs)
                .filter(([cat]) =>
                  platformAudience ? !OPERATIONAL_CATEGORIES.has(cat) : true
                )
                .map(([cat, channels]: any) => (
                <tr key={cat}>
                  <td>{categoryLabel(cat)}</td>
                  {(['dashboard', 'email', 'sms'] as const).map((ch) => (
                    <td key={ch}>
                      <button
                        type="button"
                        aria-label={`${cat} ${ch}`}
                        onClick={() => togglePref(cat, ch)}
                      >
                        {channels[ch] ? 'On' : 'Off'}
                      </button>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        ) : (
          <p className="muted notify-ui-note">Channel preferences load with this page. Refresh if the switches are missing.</p>
        )}
      </details>
    </div>
  );
}
