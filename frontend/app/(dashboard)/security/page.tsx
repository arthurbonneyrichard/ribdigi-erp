'use client';

import { useEffect, useState } from 'react';
import { api, isAbortError } from '../../../lib/api';
import { getPrefetched } from '../../../lib/prefetchCache';
import { pageLoadStarted } from '../../../lib/navTiming';
import PageHeader from '../../../components/PageHeader';
import PageSkeleton from '../../../components/PageSkeleton';

import { closeShiftForSignOut } from '../../../lib/cashierShift';
import './security-ui.css';
import { formatWhen } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';

function bufferToBase64url(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let str = '';
  bytes.forEach((b) => {
    str += String.fromCharCode(b);
  });
  return btoa(str).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function base64urlToBuffer(value: string): ArrayBuffer {
  const pad = '='.repeat((4 - (value.length % 4)) % 4);
  const b64 = (value + pad).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(b64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes.buffer;
}

function publicKeyFromJson(options: any): PublicKeyCredentialCreationOptions | PublicKeyCredentialRequestOptions {
  const copy = { ...options };
  if (copy.challenge) copy.challenge = base64urlToBuffer(copy.challenge);
  if (copy.user?.id) copy.user = { ...copy.user, id: base64urlToBuffer(copy.user.id) };
  if (Array.isArray(copy.excludeCredentials)) {
    copy.excludeCredentials = copy.excludeCredentials.map((c: any) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    }));
  }
  if (Array.isArray(copy.allowCredentials)) {
    copy.allowCredentials = copy.allowCredentials.map((c: any) => ({
      ...c,
      id: base64urlToBuffer(c.id),
    }));
  }
  return copy;
}

function credentialToJson(cred: PublicKeyCredential): Record<string, unknown> {
  const anyCred = cred as PublicKeyCredential & {
    response: AuthenticatorAttestationResponse & AuthenticatorAssertionResponse;
  };
  const response: Record<string, unknown> = {
    clientDataJSON: bufferToBase64url(anyCred.response.clientDataJSON),
  };
  const att = anyCred.response as AuthenticatorAttestationResponse;
  if (att.attestationObject) {
    response.attestationObject = bufferToBase64url(att.attestationObject);
    const allowed = new Set(['usb', 'nfc', 'ble', 'internal', 'hybrid', 'smart-card']);
    response.transports = (att.getTransports?.() || [])
      .map((t) => (t === 'cable' ? 'hybrid' : String(t).trim().toLowerCase()))
      .filter((t) => allowed.has(t));
  }
  const assertion = anyCred.response as AuthenticatorAssertionResponse;
  if (assertion.authenticatorData) {
    response.authenticatorData = bufferToBase64url(assertion.authenticatorData);
    response.signature = bufferToBase64url(assertion.signature);
    if (assertion.userHandle) response.userHandle = bufferToBase64url(assertion.userHandle);
  }
  return {
    id: cred.id,
    rawId: bufferToBase64url(cred.rawId),
    type: cred.type,
    response,
    clientExtensionResults: cred.getClientExtensionResults?.() || {},
  };
}

type AuthSessionRow = {
  id: string;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at?: string;
  expires_at?: string;
  current?: boolean;
};

function shortAgent(ua?: string | null): string {
  if (!ua) return 'Unknown device';
  const lower = ua.toLowerCase();
  if (lower.includes('python') || lower.includes('urllib') || lower.includes('curl')) return 'App or script';
  let browser = 'Browser';
  if (lower.includes('edg/')) browser = 'Edge';
  else if (lower.includes('chrome/') || lower.includes('crios/')) browser = 'Chrome';
  else if (lower.includes('firefox/')) browser = 'Firefox';
  else if (lower.includes('safari/')) browser = 'Safari';
  let system = '';
  if (lower.includes('windows')) system = 'Windows';
  else if (lower.includes('mac os') || lower.includes('macintosh')) system = 'Mac';
  else if (lower.includes('android')) system = 'Android';
  else if (lower.includes('iphone') || lower.includes('ipad')) system = 'iPhone or iPad';
  else if (lower.includes('linux')) system = 'Linux';
  return system ? `${browser} on ${system}` : browser;
}

export default function Page() {
  const prefs = useCompanyFormat();
  const [status, setStatus] = useState<any>(null);
  const [passkeys, setPasskeys] = useState<any[]>([]);
  const [sessions, setSessions] = useState<AuthSessionRow[]>([]);
  const [setup, setSetup] = useState<any>(null);
  const [code, setCode] = useState('');
  const [passkeyName, setPasskeyName] = useState('My passkey');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [disablePassword, setDisablePassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [revokingId, setRevokingId] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [pwdBusy, setPwdBusy] = useState(false);
  const [revokeOthersBusy, setRevokeOthersBusy] = useState(false);
  const [bootLoading, setBootLoading] = useState(true);

  async function refresh(opts?: { force?: boolean; signal?: AbortSignal }) {
    const force = Boolean(opts?.force);
    const load = (path: string) =>
      force ? api(path, opts?.signal ? { signal: opts.signal } : {}) : getPrefetched(path);
    const [r, keys, sess] = await Promise.all([
      load('/auth/2fa/status'),
      load('/auth/webauthn/credentials').catch((err: unknown) => {
        if (isAbortError(err)) throw err;
        return { data: [] };
      }),
      load('/auth/sessions').catch((err: unknown) => {
        if (isAbortError(err)) throw err;
        return { data: [] };
      }),
    ]);
    if (opts?.signal?.aborted) return;
    setStatus(r.data);
    setPasskeys(keys.data || []);
    setSessions(Array.isArray(sess.data) ? sess.data : []);
  }

  useEffect(() => {
    const ac = new AbortController();
    const done = pageLoadStarted('security');
    refresh({ signal: ac.signal })
      .catch((err) => {
        if (!isAbortError(err)) setError(err.message);
      })
      .finally(() => {
        if (!ac.signal.aborted) setBootLoading(false);
        done();
      });
    return () => ac.abort();
  }, []);

  async function revokeSession(id: string, isCurrent: boolean) {
    setError('');
    setMessage('');
    setRevokingId(id);
    try {
      await api(`/auth/sessions/${id}`, { method: 'DELETE' });
      if (isCurrent) {
        try {
          await closeShiftForSignOut();
        } catch {
          /* sign-out still proceeds */
        }
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('tenant');
        window.location.href = '/';
        return;
      }
      setMessage('Session revoked');
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Failed to revoke session');
    } finally {
      setRevokingId('');
    }
  }

  async function startSetup() {
    setError('');
    setMessage('');
    try {
      const r = await api('/auth/2fa/setup', { method: 'POST', body: '{}' });
      setSetup(r.data);
      setBackupCodes([]);
      setMessage('Scan the QR code, then enter a code to confirm.');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function confirmSetup() {
    setError('');
    if (!code.trim()) {
      setError('Enter the code from your authenticator app.');
      return;
    }
    try {
      const r = await api('/auth/2fa/confirm', {
        method: 'POST',
        body: JSON.stringify({ code: code.trim() }),
      });
      setBackupCodes(r.data?.backup_codes || []);
      setSetup(null);
      setCode('');
      setMessage(r.message || '2FA enabled');
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function registerPasskey() {
    setError('');
    setMessage('');
    try {
      if (!window.PublicKeyCredential) {
        throw new Error('This browser does not support passkeys');
      }
      const opt = await api('/auth/webauthn/register/options', { method: 'POST', body: '{}' });
      const publicKey = publicKeyFromJson(opt.data) as PublicKeyCredentialCreationOptions;
      const cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential | null;
      if (!cred) throw new Error('Passkey registration cancelled');
      await api('/auth/webauthn/register/verify', {
        method: 'POST',
        body: JSON.stringify({
          credential: credentialToJson(cred),
          name: passkeyName.trim() ? passkeyName.trim() : null,
        }),
      });
      setMessage('Passkey registered');
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message || 'Passkey registration failed');
    }
  }

  async function removePasskey(id: string) {
    setError('');
    try {
      await api(`/auth/webauthn/credentials/${id}`, { method: 'DELETE' });
      setMessage('Passkey removed');
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function regenCodes() {
    setError('');
    if (!code.trim()) {
      setError('Enter a current authenticator code before generating new backup codes.');
      return;
    }
    try {
      const r = await api('/auth/2fa/backup-codes', {
        method: 'POST',
        body: JSON.stringify({ code: code.trim() }),
      });
      setBackupCodes(r.data?.backup_codes || []);
      setCode('');
      setMessage('New backup codes generated');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function disable() {
    setError('');
    const trimmedPassword = disablePassword.trim();
    if (!trimmedPassword) {
      setError('Password is required');
      return;
    }
    if (!code.trim()) {
      setError('Enter a current authenticator code to turn two-factor off.');
      return;
    }
    try {
      const r = await api('/auth/2fa/disable', {
        method: 'POST',
        body: JSON.stringify({ password: trimmedPassword, code: code.trim() }),
      });
      setMessage(r.message || '2FA disabled');
      setCode('');
      setDisablePassword('');
      setBackupCodes([]);
      await refresh({ force: true });
    } catch (err: any) {
      setError(err.message);
    }
  }

  const twoFactorOn = Boolean(status?.enabled);

  return (
    <div className="security-ui">
      <PageHeader
        title={twoFactorOn ? 'Two-factor sign-in is on' : 'Turn on two-factor'}
        subtitle={
          twoFactorOn
            ? 'Your authenticator app is required at sign-in. Review the devices below, then change your password if you need to.'
            : 'Start here. Scan the QR code with an authenticator app, then enter the code it shows.'
        }
      />
      {error && <p className="security-ui-alert" role="alert">{error}</p>}
      {message && <p className="security-ui-ok" role="status">{message}</p>}
      {bootLoading && !status ? <PageSkeleton label="Loading security…" cards={4} /> : null}

      {backupCodes.length > 0 && (
        <div className="card">
          <h2>Save these codes now</h2>
          <p className="muted security-ui-note">Write these down. Each code works once if you cannot open your authenticator app.</p>
          <ul>
            {backupCodes.map((c) => (
              <li key={c}>
                <code>{c}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!twoFactorOn && (
        <div className="card">
          <h2>Turn on two-factor</h2>
          {!setup ? (
            <button onClick={startSetup} aria-label="Start 2FA setup">Start setup</button>
          ) : (
            <div className="security-ui-form">
              {setup.qr_png_base64 && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`data:image/png;base64,${setup.qr_png_base64}`}
                  alt="2FA QR code"
                  width={180}
                  height={180}
                />
              )}
              <p className="muted">If you cannot scan, type this secret into the app: {setup.secret}</p>
              <input
                aria-label="2FA setup code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="6-digit code"
              />
              <button type="button" onClick={confirmSetup} disabled={!code.trim()} aria-label="Confirm 2FA setup">
                Confirm &amp; enable
              </button>
            </div>
          )}
        </div>
      )}

      {twoFactorOn && status && (
        <div className="card">
          <p>Two-factor sign-in is on.</p>
          <p>Passkeys on this account: {status.webauthn_count ?? passkeys.length}</p>
          {status.role_requires_2fa ? <p>Your role must keep two-factor on.</p> : null}
          {status.must_enroll_2fa ? (
            <p className="security-ui-warn">Finish enrollment before using other modules.</p>
          ) : null}
          {status.confirmed_at ? (
            <p className="muted">Confirmed {formatWhen(String(status.confirmed_at), prefs)}</p>
          ) : null}
        </div>
      )}


      <div className="card">
        <h2>Signed-in devices</h2>
        <p className="muted security-ui-note">
          Revoke a device you do not recognize. Signing out this device ends this visit.
        </p>
        <ul className="security-ui-list">
          {sessions.map((s) => (
            <li key={s.id} className="security-ui-session">
              <div>
                <div>
                  {shortAgent(s.user_agent)}
                  {s.current ? (
                    <span className="muted" style={{ marginLeft: 8 }}>
                      (this device)
                    </span>
                  ) : null}
                </div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {s.ip_address ? `From ${s.ip_address}` : 'Location not recorded'}
                  {s.created_at ? ` · Signed in ${formatWhen(s.created_at, prefs)}` : ''}
                </div>
              </div>
              <button
                type="button"
                disabled={revokingId === s.id}
                onClick={() => revokeSession(String(s.id).trim(), Boolean(s.current))}
                aria-label={s.current ? 'Sign out this device' : 'Revoke session'}
              >
                {revokingId === s.id ? 'Revoking…' : s.current ? 'Sign out here' : 'Revoke'}
              </button>
            </li>
          ))}
          {!sessions.length && (
            <li className="muted">No signed-in devices are listed. Sign in again if this stays empty.</li>
          )}
        </ul>
        <button
          type="button"
          style={{ marginTop: 12 }}
          disabled={revokeOthersBusy}
          onClick={async () => {
            setError('');
            setMessage('');
            setRevokeOthersBusy(true);
            try {
              const r = await api('/auth/sessions/revoke-others', { method: 'POST', body: '{}' });
              setMessage(r.message || 'Other sessions signed out');
              await refresh({ force: true });
            } catch (err: any) {
              setError(err.message);
            } finally {
              setRevokeOthersBusy(false);
            }
          }}
        >
          {revokeOthersBusy ? 'Signing out…' : 'Sign out other sessions'}
        </button>
      </div>

      <div className="card">
        <h2>Password</h2>
        <p className="muted security-ui-note">Changing your password signs out other devices.</p>
        <div className="security-ui-form">
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="Current password"
            aria-label="Current password"
          />
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="New password"
            aria-label="New password"
          />
          <button
            type="button"
            aria-label="Update password"
            disabled={pwdBusy || !currentPassword.trim() || !newPassword.trim()}
            onClick={async () => {
              setError('');
              setMessage('');
              setPwdBusy(true);
              try {
                const r = await api('/auth/change-password', {
                  method: 'POST',
                  body: JSON.stringify({
                    current_password: currentPassword.trim(),
                    new_password: newPassword.trim(),
                  }),
                });
                setCurrentPassword('');
                setNewPassword('');
                setMessage(r.message || 'Password updated');
              } catch (err: any) {
                setError(err.message || 'Password was not changed');
              } finally {
                setPwdBusy(false);
              }
            }}
          >
            {pwdBusy ? 'Saving…' : 'Update password'}
          </button>
        </div>
      </div>

      <div className="card">
        <h2>Passkeys</h2>
        <p className="muted security-ui-note">Use a fingerprint, face, or security key as a second step at sign-in. A blank name is saved as Passkey.</p>
        <div className="security-ui-inline">
          <input
            aria-label="Passkey name"
            value={passkeyName}
            onChange={(e) => setPasskeyName(e.target.value)}
            placeholder="Passkey name"
            title="Optional label"
          />
          <button type="button" onClick={registerPasskey} aria-label="Add passkey">
            Add passkey
          </button>
        </div>
        <ul className="security-ui-list">
          {passkeys.map((p) => (
            <li key={p.id} className="security-ui-session">
              <span>{p.name || 'Passkey'}</span>
              <button type="button" onClick={() => removePasskey(p.id)} aria-label="Remove passkey">
                Remove passkey
              </button>
            </li>
          ))}
          {!passkeys.length && (
            <li className="muted">No passkeys yet. Type a name or leave it blank, then choose Add passkey.</li>
          )}
        </ul>
      </div>

      {twoFactorOn && (
        <div className="card">
          <h2>Backup codes</h2>
          <p className="muted security-ui-note">Enter a current authenticator code, then generate a new set. The old set stops working.</p>
          <div className="security-ui-form">
          <input
            aria-label="2FA code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Current 2FA code"
          />
          <button type="button" onClick={regenCodes} disabled={!code.trim()} aria-label="Regenerate backup codes">
            Regenerate backup codes
          </button>
          </div>
        </div>
      )}

      {twoFactorOn && !status?.role_requires_2fa && (
        <details className="card security-ui-advanced">
          <summary>Turn off two-factor</summary>
          <p className="muted security-ui-note">This removes the authenticator step at sign-in. Enter your password and a current code.</p>
          <div className="security-ui-form">
            <input
              aria-label="2FA code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="Current 2FA code"
            />
            <input
              type="password"
              aria-label="Disable 2FA password"
              value={disablePassword}
              onChange={(e) => setDisablePassword(e.target.value)}
              placeholder="Password"
            />
            <button type="button" onClick={disable} disabled={!disablePassword.trim() || !code.trim()} aria-label="Disable 2FA">
              Disable
            </button>
          </div>
        </details>
      )}
    </div>
  );
}
