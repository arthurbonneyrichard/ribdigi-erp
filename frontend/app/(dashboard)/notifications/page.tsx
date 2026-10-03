'use client';

import { useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';

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
    } catch (err: any) {
      setPrefs(null);
      if (err?.message) setError(err.message);
    }
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

  return (
    <>
      <h1>Notifications</h1>
      <p className="muted">
        In-app notification center — unread badge, category filters, mark read/unread, and 90-day
        history. Channel preferences for dashboard / email / SMS per type.
      </p>
      {platformAudience ? (
        <p className="muted">
          Platform Owner notices only: provisioning, platform security, staff accounts, administrator
          password resets, and other platform actions. Stock, orders, payments, and POS stay on
          tenant notification lists.
        </p>
      ) : null}
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
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

      <table className="table">
        <thead>
          <tr>
            <th>Category</th>
            <th>Title</th>
            <th>Message</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={5} className="muted">
                {status === 'unread'
                  ? 'No unread notifications. Switch to All (90 days) to see history.'
                  : 'No notifications in this filter.'}
              </td>
            </tr>
          ) : (
            rows.map((n) => (
            <tr key={n.id}>
              <td>{n.category}</td>
              <td>{n.title}</td>
              <td>{n.message}</td>
              <td>{n.status}</td>
              <td>
                {n.status === 'unread' ? (
                  <button onClick={() => markRead(n.id)} aria-label={`Mark notification ${n.id} read`}>Mark read</button>
                ) : (
                  <button onClick={() => markUnread(n.id)} aria-label={`Mark notification ${n.id} unread`}>Mark unread</button>
                )}
              </td>
            </tr>
            ))
          )}
        </tbody>
      </table>

      {prefs && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Channel preferences</h3>
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
                  <td>{cat}</td>
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
          <p className="muted">
            Email uses SMTP (or console in dev). SMS uses Twilio when configured, otherwise console
            fallback. Set your phone on Company settings for SMS tests.
          </p>
        </div>
      )}
    </>
  );
}
