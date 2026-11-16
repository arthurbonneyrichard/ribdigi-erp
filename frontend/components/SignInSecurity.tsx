'use client';

/**
 * Sign-in security for company admins: accounts that are locked or have wrong tries, an early
 * Unlock, and the recent sign-in events. Accounts lock themselves after 5 wrong tries (15, 30, 60,
 * then 120 minutes) and open again on their own; nobody is locked out for good.
 */

import { useCallback, useEffect, useState } from 'react';
import { api } from '../lib/api';
import { formatWhen } from '../lib/format';
import './cashier-passcodes.css';

type Row = Record<string, any>;

const EVENT_WORDS: Record<string, string> = {
  login: 'Signed in',
  login_failed: 'Wrong password or code',
  '2fa_failed': 'Wrong 2FA code',
  '2fa_challenge': 'Asked for 2FA',
  account_locked: 'Account locked',
  account_unlocked: 'Unlocked by an admin',
  login_blocked_locked: 'Tried while locked',
  login_blocked_unverified: 'Email not verified yet',
  password_reset_requested: 'Asked for a password reset',
  password_reset_completed: 'Password reset',
  full_sign_in_failed: 'Wrong password at the till',
  logout: 'Signed out',
};

function untilText(row: Row): string {
  if (!row.locked) return '—';
  const mins = Math.max(1, Math.ceil(Number(row.seconds_remaining || 0) / 60));
  return `${formatWhen(row.locked_until)} (${mins} min left)`;
}

export default function SignInSecurity({ names }: { names: Record<string, string> }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [events, setEvents] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState('');
  const [showEvents, setShowEvents] = useState(false);

  const load = useCallback(async () => {
    const [stateRes, eventRes] = await Promise.all([
      api('/users/security/locked'),
      api('/users/security/events?limit=30'),
    ]);
    setRows(stateRes.data || []);
    setEvents(eventRes.data || []);
  }, []);

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : 'Could not load sign-in security.'));
  }, [load]);

  async function unlock(row: Row) {
    setBusy(row.user_id);
    setError('');
    setMessage('');
    try {
      await api(`/users/${row.user_id}/unlock`, { method: 'POST', body: JSON.stringify({}) });
      setMessage(`${row.full_name || row.email} can sign in again.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not unlock that account.');
    } finally {
      setBusy('');
    }
  }

  const locked = rows.filter((r) => r.locked).length;

  return (
    <section className="cpass" aria-label="Sign-in security">
      <h2>Sign-in security</h2>
      <p className="cpass-note">
        After 5 wrong tries in a row an account locks for 15 minutes, then 30, 60 and 120 if it keeps happening.
        It opens again by itself. Unlock it early here once you know it was the real person.
        {locked > 0 ? ` ${locked} ${locked === 1 ? 'account is' : 'accounts are'} locked now.` : ''}
      </p>
      {error ? <p className="cpass-error" role="alert">{error}</p> : null}
      {message ? <p className="cpass-ok" role="status">{message}</p> : null}
      {rows.length === 0 ? (
        <p className="cpass-note">No locked accounts and no recent wrong tries.</p>
      ) : (
        <div className="cpass-scroll">
          <table className="cpass-table">
            <thead>
              <tr>
                <th scope="col">Staff</th>
                <th scope="col">Status</th>
                <th scope="col">Wrong tries</th>
                <th scope="col">Locked until</th>
                <th scope="col">Last wrong try</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.user_id}>
                  <th scope="row">{row.full_name || row.email}</th>
                  <td>
                    <span className={`cpass-chip ${row.locked ? 'is-inactive' : 'is-active'}`}>
                      {row.locked ? 'Locked' : 'Can sign in'}
                    </span>
                  </td>
                  <td>
                    {row.failed_login_attempts} of {row.lockout_threshold}
                  </td>
                  <td>{untilText(row)}</td>
                  <td>{row.last_failed_login_at ? formatWhen(row.last_failed_login_at) : '—'}</td>
                  <td>
                    <button
                      type="button"
                      className="btn-ok"
                      disabled={busy === row.user_id}
                      aria-label={`Unlock sign-in for ${row.full_name || row.email}`}
                      onClick={() => void unlock(row)}
                    >
                      {row.locked ? 'Unlock' : 'Clear tries'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div>
        <button type="button" aria-expanded={showEvents} onClick={() => setShowEvents((v) => !v)}>
          {showEvents ? 'Hide recent sign-in events' : 'Show recent sign-in events'}
        </button>
      </div>
      {showEvents ? (
        events.length === 0 ? (
          <p className="cpass-note">No sign-in events yet.</p>
        ) : (
          <div className="cpass-scroll">
            <table className="cpass-table">
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Who</th>
                  <th scope="col">What happened</th>
                  <th scope="col">From IP</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id}>
                    <td>{formatWhen(ev.created_at)}</td>
                    <th scope="row">{names[ev.entity_id] || names[ev.user_id] || '—'}</th>
                    <td>{EVENT_WORDS[ev.action] || ev.action}</td>
                    <td>{ev.ip_address || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : null}
    </section>
  );
}
