'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

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
    response.transports = att.getTransports?.() || [];
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

export default function Page() {
  const [status, setStatus] = useState<any>(null);
  const [passkeys, setPasskeys] = useState<any[]>([]);
  const [setup, setSetup] = useState<any>(null);
  const [code, setCode] = useState('');
  const [passkeyName, setPasskeyName] = useState('My passkey');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [disablePassword, setDisablePassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function refresh() {
    const [r, keys] = await Promise.all([
      api('/auth/2fa/status'),
      api('/auth/webauthn/credentials').catch(() => ({ data: [] })),
    ]);
    setStatus(r.data);
    setPasskeys(keys.data || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

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
    try {
      const r = await api('/auth/2fa/confirm', {
        method: 'POST',
        body: JSON.stringify({ code }),
      });
      setBackupCodes(r.data?.backup_codes || []);
      setSetup(null);
      setCode('');
      setMessage(r.message || '2FA enabled');
      await refresh();
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
        body: JSON.stringify({ credential: credentialToJson(cred), name: passkeyName || 'Passkey' }),
      });
      setMessage('Passkey registered');
      await refresh();
    } catch (err: any) {
      setError(err.message || 'Passkey registration failed');
    }
  }

  async function removePasskey(id: string) {
    setError('');
    try {
      await api(`/auth/webauthn/credentials/${id}`, { method: 'DELETE' });
      setMessage('Passkey removed');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function regenCodes() {
    setError('');
    try {
      const r = await api('/auth/2fa/backup-codes', {
        method: 'POST',
        body: JSON.stringify({ code }),
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
    try {
      const r = await api('/auth/2fa/disable', {
        method: 'POST',
        body: JSON.stringify({ password: disablePassword, code }),
      });
      setMessage(r.message || '2FA disabled');
      setCode('');
      setDisablePassword('');
      setBackupCodes([]);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <Shell>
      <h1>Security / 2FA</h1>
      <p className="muted">TOTP authenticator, passkeys, and recovery codes</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      {status && (
        <div className="card" style={{ marginBottom: 16 }}>
          <p>TOTP enabled: {String(status.enabled)}</p>
          <p>Passkeys: {status.webauthn_count ?? passkeys.length}</p>
          <p>Role requires 2FA: {String(status.role_requires_2fa)}</p>
          {status.must_enroll_2fa && (
            <p style={{ color: '#b45309' }}>Enrollment required before using other modules.</p>
          )}
          {status.confirmed_at && <p className="muted">TOTP confirmed: {String(status.confirmed_at)}</p>}
        </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h2>Passkeys (WebAuthn)</h2>
        <p className="muted">Register a platform or security-key passkey for passwordless second factor.</p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          <input
            value={passkeyName}
            onChange={(e) => setPasskeyName(e.target.value)}
            placeholder="Passkey name"
            style={{ minWidth: 160 }}
          />
          <button type="button" onClick={registerPasskey}>
            Add passkey
          </button>
        </div>
        <ul>
          {passkeys.map((p) => (
            <li key={p.id}>
              {p.name || 'Passkey'} · sign count {p.sign_count}{' '}
              <button type="button" onClick={() => removePasskey(p.id)}>
                Remove
              </button>
            </li>
          ))}
          {!passkeys.length && <li className="muted">No passkeys yet</li>}
        </ul>
      </div>

      {!status?.enabled && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Enable TOTP</h2>
          {!setup ? (
            <button onClick={startSetup}>Start setup</button>
          ) : (
            <>
              {setup.qr_png_base64 && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={`data:image/png;base64,${setup.qr_png_base64}`}
                  alt="2FA QR code"
                  width={180}
                  height={180}
                />
              )}
              <p className="muted">Secret: {setup.secret}</p>
              <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="6-digit code" />
              <button onClick={confirmSetup}>Confirm &amp; enable</button>
            </>
          )}
        </div>
      )}

      {status?.enabled && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h2>Backup codes</h2>
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Current 2FA code" />
          <button onClick={regenCodes}>Regenerate backup codes</button>
          {!status.role_requires_2fa && (
            <div style={{ marginTop: 12 }}>
              <h3>Disable TOTP</h3>
              <input
                type="password"
                value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)}
                placeholder="Password"
              />
              <button onClick={disable}>Disable</button>
            </div>
          )}
        </div>
      )}

      {backupCodes.length > 0 && (
        <div className="card">
          <h2>Save these codes now</h2>
          <ul>
            {backupCodes.map((c) => (
              <li key={c}>
                <code>{c}</code>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Shell>
  );
}
