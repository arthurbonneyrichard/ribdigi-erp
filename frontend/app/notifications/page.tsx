'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Note = {
  id: string;
  category: string;
  title: string;
  message: string;
  status: string;
  created_at: string;
};

export default function Page() {
  const [rows, setRows] = useState<Note[]>([]);
  const [status, setStatus] = useState('unread');
  const [prefs, setPrefs] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function refresh() {
    const q = status ? `?status=${status}` : '';
    const [notes, settings] = await Promise.all([
      api(`/notifications${q}`),
      api('/notifications/settings'),
    ]);
    setRows(notes.data || []);
    setPrefs(settings.data);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, [status]);

  async function markRead(id: string) {
    setError('');
    try {
      await api(`/notifications/${id}/read`, { method: 'PATCH' });
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
      await refresh();
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
      <p className="muted">In-app alerts, preferences, and payment-due scan</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <button onClick={() => setStatus('unread')} disabled={status === 'unread'}>
          Unread
        </button>
        <button onClick={() => setStatus('')} disabled={status === ''}>
          All
        </button>
        <button onClick={markAll}>Mark all read</button>
        <button onClick={scanDue}>Scan payment due</button>
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
          {rows.map((n) => (
            <tr key={n.id}>
              <td>{n.category}</td>
              <td>{n.title}</td>
              <td>{n.message}</td>
              <td>{n.status}</td>
              <td>
                {n.status === 'unread' && (
                  <button onClick={() => markRead(n.id)}>Mark read</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {prefs && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Channel preferences</h3>
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
