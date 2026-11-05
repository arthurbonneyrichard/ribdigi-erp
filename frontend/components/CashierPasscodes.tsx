'use client';

/**
 * Give each person their own till passcode. The server keeps only hashes, so a passcode
 * can be read here once, right after it is generated, and never again.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import { formatWhen } from '../lib/format';
import './cashier-passcodes.css';

type Row = Record<string, any>;

const PASSCODE_LENGTH = 6;

function usesTill(user: Row): boolean {
  const perms = user.permissions;
  if (!perms || typeof perms !== 'object' || Object.keys(perms).length === 0) return true;
  if (Array.isArray(perms['*'])) return true;
  return ['pos', 'restaurant'].some((module) => (perms[module] || []).some((a: string) => a === 'write' || a === '*'));
}

export default function CashierPasscodes({ canManage }: { canManage: boolean }) {
  const [users, setUsers] = useState<Row[]>([]);
  const [codes, setCodes] = useState<Record<string, Row>>({});
  const [editing, setEditing] = useState('');
  const [value, setValue] = useState('');
  const [revealed, setRevealed] = useState<{ name: string; code: string } | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [userRes, codeRes] = await Promise.all([api('/users?is_active=true'), api('/users/pos-passcodes')]);
    setUsers((userRes.data || []).filter((u: Row) => u.is_active !== false && usesTill(u)));
    setCodes(Object.fromEntries((codeRes.data || []).map((row: Row) => [row.user_id, row])));
  }, []);

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : 'Could not load passcodes.'));
  }, [load]);

  const missing = useMemo(() => users.filter((u) => codes[u.id]?.status !== 'active').length, [codes, users]);

  async function run(action: () => Promise<string>) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      setMessage(await action());
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'That did not save.');
    } finally {
      setBusy(false);
    }
  }

  function saveTyped(user: Row) {
    void run(async () => {
      await api(`/users/${user.id}/pos-passcode`, { method: 'PUT', body: JSON.stringify({ passcode: value }) });
      setEditing('');
      setValue('');
      return `Passcode saved for ${user.full_name}.`;
    });
  }

  function generate(user: Row) {
    void run(async () => {
      const res = await api(`/users/${user.id}/pos-passcode`, { method: 'PUT', body: JSON.stringify({}) });
      setEditing('');
      setValue('');
      setRevealed({ name: user.full_name, code: res.data.passcode });
      return '';
    });
  }

  function setActive(user: Row, isActive: boolean) {
    void run(async () => {
      await api(`/users/${user.id}/pos-passcode`, { method: 'PATCH', body: JSON.stringify({ is_active: isActive }) });
      return isActive ? `Passcode turned back on for ${user.full_name}.` : `Passcode turned off for ${user.full_name}.`;
    });
  }

  return (
    <section className="cpass" aria-label="Till passcodes">
      <h2>Till passcodes</h2>
      <p className="cpass-note">
        Each person gets their own {PASSCODE_LENGTH}-digit passcode to unlock the till, so every sale shows who really made it.
        Once the first passcode is set, a till cannot sell until someone unlocks it.
        {missing > 0 ? ` ${missing} ${missing === 1 ? 'person still needs' : 'people still need'} one.` : ''}
      </p>
      {revealed ? (
        <div className="cpass-reveal" role="status">
          <span>
            Passcode for <strong>{revealed.name}</strong>. Note it now. It cannot be shown again.
          </span>
          <code>{revealed.code}</code>
          <button type="button" onClick={() => setRevealed(null)}>
            Done
          </button>
        </div>
      ) : null}
      {error ? <p className="cpass-error" role="alert">{error}</p> : null}
      {message ? <p className="cpass-ok" role="status">{message}</p> : null}
      <div className="cpass-scroll">
        <table className="cpass-table">
          <thead>
            <tr>
              <th scope="col">Staff</th>
              <th scope="col">Passcode</th>
              <th scope="col">Last used</th>
              {canManage ? <th scope="col">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {users.map((user) => {
              const row = codes[user.id];
              const status = row?.status || 'none';
              return (
                <tr key={user.id}>
                  <th scope="row">{user.full_name}</th>
                  <td>
                    <span className={`cpass-chip is-${status}`}>
                      {status === 'active' ? 'On' : status === 'inactive' ? 'Off' : 'Not set'}
                    </span>
                  </td>
                  <td>{row?.last_used_at ? formatWhen(row.last_used_at) : '—'}</td>
                  {canManage ? (
                    <td>
                      {editing === user.id ? (
                        <span className="cpass-edit">
                          <input
                            value={value}
                            inputMode="numeric"
                            autoComplete="off"
                            maxLength={PASSCODE_LENGTH}
                            placeholder={`${PASSCODE_LENGTH} digits`}
                            aria-label={`New passcode for ${user.full_name}`}
                            onChange={(e) => setValue(e.target.value.replace(/\D/g, ''))}
                          />
                          <button
                            type="button"
                            className="btn-ok"
                            disabled={busy || value.length !== PASSCODE_LENGTH}
                            onClick={() => saveTyped(user)}
                          >
                            Save
                          </button>
                          <button type="button" onClick={() => setEditing('')}>
                            Cancel
                          </button>
                        </span>
                      ) : (
                        <span className="cpass-actions">
                          <button type="button" className="btn-ok" disabled={busy} onClick={() => generate(user)}>
                            {status === 'none' ? 'Generate' : 'Reset'}
                          </button>
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => {
                              setEditing(user.id);
                              setValue('');
                            }}
                          >
                            {status === 'none' ? 'Type one' : 'Change'}
                          </button>
                          {status === 'active' ? (
                            <button type="button" className="btn-danger" disabled={busy} onClick={() => setActive(user, false)}>
                              Turn off
                            </button>
                          ) : null}
                          {status === 'inactive' ? (
                            <button type="button" className="btn-ok" disabled={busy} onClick={() => setActive(user, true)}>
                              Turn on
                            </button>
                          ) : null}
                        </span>
                      )}
                    </td>
                  ) : null}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
