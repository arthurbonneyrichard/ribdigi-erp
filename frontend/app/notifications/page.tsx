'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { formatDateTime, type RegionalFormats } from '../../lib/format';

type Note = {
  id: string;
  category: string;
  group?: string;
  title: string;
  message: string;
  status: string;
  created_at: string;
};

const GROUPS: { id: string; label: string }[] = [
  { id: '', label: 'All groups' },
  { id: 'stock', label: 'Stock' },
  { id: 'orders', label: 'Orders' },
  { id: 'payments', label: 'Payments' },
  { id: 'system', label: 'System' },
];

export default function Page() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [rows, setRows] = useState<Note[]>([]);
  const [status, setStatus] = useState(() => {
    const raw = searchParams.get('status');
    if (raw === null) return 'unread';
    return raw;
  });
  const [group, setGroup] = useState(() => searchParams.get('group') || '');
  const [prefs, setPrefs] = useState<any>(null);
  const [formats, setFormats] = useState<RegionalFormats>({});
  const [unread, setUnread] = useState(0);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  function syncUrl(next: { status?: string; group?: string }) {
    const params = new URLSearchParams();
    const ns = next.status !== undefined ? next.status : status;
    const ng = next.group !== undefined ? next.group : group;
    if (ns) params.set('status', ns);
    if (ng) params.set('group', ng);
    const qs = params.toString();
    const hash = typeof window !== 'undefined' ? window.location.hash : '';
    router.replace(qs ? `${pathname}?${qs}${hash}` : `${pathname}${hash}`);
  }

  async function refresh(overrides?: { status?: string; group?: string }) {
    const st = overrides?.status !== undefined ? overrides.status : status;
    const gr = overrides?.group !== undefined ? overrides.group : group;
    const params = new URLSearchParams();
    if (st) params.set('status', st);
    if (gr) params.set('group', gr);
    const q = params.toString() ? `?${params}` : '';
    const [notes, settings, countRes, me] = await Promise.all([
      api(`/notifications${q}`),
      api('/notifications/settings'),
      api('/notifications/unread-count').catch(() => ({ data: { count: 0 } })),
      api('/me').catch(() => ({ data: null })),
    ]);
    setRows(notes.data || []);
    setPrefs(settings.data);
    setUnread(countRes.data?.count || 0);
    if (me.data) {
      setFormats({
        date_format: me.data.date_format,
        number_format: me.data.number_format,
        time_format: me.data.time_format,
      });
    }
  }

  useEffect(() => {
    const fromStatus = searchParams.get('status');
    const fromGroup = searchParams.get('group') || '';
    const nextStatus = fromStatus === null ? 'unread' : fromStatus;
    setStatus(nextStatus);
    setGroup(fromGroup);
    refresh({ status: nextStatus, group: fromGroup }).catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (hash !== 'preferences') return;
    const t = window.setTimeout(() => {
      const el = document.getElementById('preferences');
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
  }, [prefs]);

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
      setMessage(
        `Due alerts created: ${r.data?.created ?? 0}` +
          (r.data?.quotation_expiry
            ? ` (quotes reminded ${r.data.quotation_expiry.reminded ?? 0}, expired ${r.data.quotation_expiry.expired ?? 0})`
            : ''),
      );
      setStatus('unread');
      syncUrl({ status: 'unread' });
      await refresh({ status: 'unread' });
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function togglePref(category: string, channel: string) {
    if (!prefs) return;
    const next = {
      ...prefs,
      [category]: {
        ...prefs[category],
        [channel]: !prefs[category]?.[channel],
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
    <Shell>
      <h1>Notifications</h1>
      <p className="muted">
        In-app alerts (last 90 days). Unread: <strong>{unread}</strong>
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button
          onClick={() => {
            setStatus('unread');
            syncUrl({ status: 'unread' });
          }}
          disabled={status === 'unread'}
        >
          Unread
        </button>
        <button
          onClick={() => {
            setStatus('read');
            syncUrl({ status: 'read' });
          }}
          disabled={status === 'read'}
        >
          Read
        </button>
        <button
          onClick={() => {
            setStatus('');
            syncUrl({ status: '' });
          }}
          disabled={status === ''}
        >
          History
        </button>
        <select
          value={group}
          onChange={(e) => {
            const v = e.target.value;
            setGroup(v);
            syncUrl({ group: v });
          }}
          aria-label="Category group"
        >
          {GROUPS.map((g) => (
            <option key={g.id || 'all'} value={g.id}>
              {g.label}
            </option>
          ))}
        </select>
        <button onClick={markAll}>Mark all read</button>
        <button onClick={scanDue}>Scan payment due</button>
      </div>

      <table className="table">
        <thead>
          <tr>
            <th>When</th>
            <th>Group</th>
            <th>Category</th>
            <th>Title</th>
            <th>Message</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={7} className="muted">
                No notifications in this view
              </td>
            </tr>
          )}
          {rows.map((n) => (
            <tr key={n.id}>
              <td>{formatDateTime(n.created_at, formats.date_format, formats.time_format)}</td>
              <td>{n.group || '—'}</td>
              <td>{n.category}</td>
              <td>{n.title}</td>
              <td>{n.message}</td>
              <td>{n.status}</td>
              <td>
                {n.status === 'unread' ? (
                  <button onClick={() => markRead(n.id)}>Mark read</button>
                ) : (
                  <button onClick={() => markUnread(n.id)}>Mark unread</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {prefs && (
        <div className="card" style={{ marginTop: 16 }} id="preferences">
          <h3>Notification settings / channel preferences</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Dashboard</th>
                <th>Email</th>
                <th>SMS</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(prefs).map(([cat, channels]: any) => (
                <tr key={cat}>
                  <td>{cat}</td>
                  {(['dashboard', 'email', 'sms'] as const).map((ch) => (
                    <td key={ch}>
                      <button onClick={() => togglePref(cat, ch)}>
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
    </Shell>
  );
}
