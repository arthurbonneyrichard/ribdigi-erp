'use client';

/**
 * Security -> Privacy and your data.
 * Marketing email choice, how to take a copy of your data, and deletion requests
 * (own account, or the whole company for a company admin). Ribdigi House reviews each request.
 */
import { FormEvent, useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '../lib/api';
import { getMe } from '../lib/meCache';
import { formatWhen } from '../lib/format';

type DeletionRequest = {
  id: string;
  scope: 'my_account' | 'company';
  status: 'pending' | 'approved' | 'rejected' | 'completed' | 'cancelled';
  reason?: string | null;
  decision_note?: string | null;
  requester_email?: string | null;
  created_at?: string | null;
  decided_at?: string | null;
};

const STATUS_WORDS: Record<DeletionRequest['status'], string> = {
  pending: 'Waiting for review',
  approved: 'Approved; deletion in progress',
  rejected: 'Refused',
  completed: 'Done',
  cancelled: 'Cancelled',
};

const SCOPE_WORDS: Record<DeletionRequest['scope'], string> = {
  my_account: 'My account',
  company: 'Whole company',
};

export default function PrivacyDataCard() {
  const [role, setRole] = useState('');
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [requests, setRequests] = useState<DeletionRequest[]>([]);
  const [scope, setScope] = useState<'my_account' | 'company'>('my_account');
  const [reason, setReason] = useState('');
  const [password, setPassword] = useState('');
  const [understood, setUnderstood] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const isAdmin = role === 'company_admin';

  const load = useCallback(async () => {
    const [mail, list] = await Promise.all([
      api('/me/marketing-email').catch(() => null),
      api('/privacy/deletion-requests').catch(() => null),
    ]);
    if (mail?.data) setSubscribed(Boolean(mail.data.subscribed));
    setRequests(Array.isArray(list?.data) ? list.data : []);
  }, []);

  useEffect(() => {
    getMe()
      .then((r) => setRole(String(r?.data?.role || '')))
      .catch(() => undefined);
    load();
  }, [load]);

  async function toggleMarketing(next: boolean) {
    setError('');
    setMessage('');
    try {
      const r = await api('/me/marketing-email', { method: 'PATCH', body: JSON.stringify({ subscribed: next }) });
      setSubscribed(Boolean(r?.data?.subscribed));
      setMessage(next ? 'Ribdigi House news and offers are on.' : 'Ribdigi House news and offers are off.');
    } catch (err: any) {
      setError(err?.message || 'Could not save your email choice');
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !understood || !password) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/privacy/deletion-requests', {
        method: 'POST',
        body: JSON.stringify({ scope, password, reason: reason.trim() || null }),
      });
      setMessage('Request sent. Ribdigi House will review it and reply by email.');
      setPassword('');
      setReason('');
      setUnderstood(false);
      await load();
    } catch (err: any) {
      setError(err?.message || 'Could not send the request');
    } finally {
      setBusy(false);
    }
  }

  async function cancel(id: string) {
    setError('');
    setMessage('');
    try {
      await api(`/privacy/deletion-requests/${encodeURIComponent(id)}/cancel`, { method: 'POST' });
      setMessage('Request cancelled.');
      await load();
    } catch (err: any) {
      setError(err?.message || 'Could not cancel the request');
    }
  }

  const open = requests.some((r) => r.status === 'pending' || r.status === 'approved');

  return (
    <section className="card privacy-card" aria-labelledby="privacy-card-title">
      <h2 id="privacy-card-title">Privacy and your data</h2>
      {error ? <p className="security-ui-alert" role="alert">{error}</p> : null}
      {message ? <p className="security-ui-ok" role="status">{message}</p> : null}

      <h3>Email from Ribdigi House</h3>
      <label className="privacy-row">
        <input
          type="checkbox"
          checked={subscribed === true}
          disabled={subscribed === null}
          onChange={(e) => toggleMarketing(e.target.checked)}
        />
        <span>Send me product news and offers</span>
      </label>
      <p className="muted">
        Messages about your account (sign-in codes, billing, security notices) are always sent. Every news email also
        has an unsubscribe link.
      </p>

      <h3>A copy of your data</h3>
      <p className="muted">
        {isAdmin ? (
          <>
            Download a full copy of the company&apos;s records from <Link href="/backup">Backup</Link>, and spreadsheets
            from Reports. Do this before asking for the company to be deleted.
          </>
        ) : (
          <>Your company admin can download the company&apos;s records. Ask Ribdigi House for a copy of your own account details.</>
        )}{' '}
        See the <Link href="/legal/privacy">Privacy Policy</Link> for what we hold and why.
      </p>

      <h3>Ask for deletion</h3>
      <form onSubmit={submit} className="privacy-form">
        <fieldset>
          <legend>What should be deleted?</legend>
          <label className="privacy-row">
            <input type="radio" name="privacy-scope" value="my_account" checked={scope === 'my_account'} onChange={() => setScope('my_account')} />
            <span>My sign-in account and personal details</span>
          </label>
          {isAdmin ? (
            <label className="privacy-row">
              <input type="radio" name="privacy-scope" value="company" checked={scope === 'company'} onChange={() => setScope('company')} />
              <span>The whole company and all its records</span>
            </label>
          ) : null}
        </fieldset>
        <p className="privacy-warn">
          {scope === 'company'
            ? 'Every staff account, all sales, stock, accounts and history will be deleted once Ribdigi House approves it and you have had the chance to download your data. This cannot be undone. Records the law requires us to keep are kept for that time only.'
            : 'You will be signed out and your account removed. Sales and other records you made stay with the company, without your name. If you are the only company admin, add another admin first or ask for the whole company to be deleted.'}
        </p>
        <label>
          Reason (optional)
          <textarea value={reason} maxLength={1000} rows={2} onChange={(e) => setReason(e.target.value)} />
        </label>
        <label>
          Your password, to confirm it is you
          <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label className="privacy-row">
          <input type="checkbox" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
          <span>I understand what will be deleted</span>
        </label>
        <button type="submit" className="btn-danger" disabled={busy || !understood || !password || open}>
          Send deletion request
        </button>
        {open ? <p className="muted">A request is already open. Cancel it below to send a different one.</p> : null}
      </form>

      {requests.length ? (
        <table className="table privacy-table">
          <caption>Your requests</caption>
          <thead>
            <tr>
              <th scope="col">Sent</th>
              <th scope="col">What</th>
              {isAdmin ? <th scope="col">By</th> : null}
              <th scope="col">Status</th>
              <th scope="col"><span className="sr-only">Action</span></th>
            </tr>
          </thead>
          <tbody>
            {requests.map((r) => (
              <tr key={r.id}>
                <td>{formatWhen(r.created_at) || '—'}</td>
                <td>{SCOPE_WORDS[r.scope]}</td>
                {isAdmin ? <td>{r.requester_email || '—'}</td> : null}
                <td>
                  {STATUS_WORDS[r.status]}
                  {r.decision_note ? <div className="muted">{r.decision_note}</div> : null}
                </td>
                <td>
                  {r.status === 'pending' ? (
                    <button type="button" onClick={() => cancel(r.id)} aria-label={`Cancel ${SCOPE_WORDS[r.scope]} deletion request`}>
                      Cancel
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}
