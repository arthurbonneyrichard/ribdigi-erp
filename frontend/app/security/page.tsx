'use client';

import { useEffect, useState, type ReactNode } from 'react';
import Shell from '../../components/Shell';
import PlatformShell from '../../components/PlatformShell';
import { api } from '../../lib/api';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES, t } from '../../lib/i18n';

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

function ApiKeyUsageChart({ series }: { series: { date: string; requests: number }[] }) {
  const width = 560;
  const height = 160;
  const pad = { top: 12, right: 8, bottom: 24, left: 36 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const points = series.length ? series : [];
  const maxY = Math.max(1, ...points.map((p) => Number(p.requests) || 0));
  const gap = 2;
  const barW = points.length ? Math.max(2, (innerW - gap * (points.length - 1)) / points.length) : 0;

  if (!points.length) {
    return <p className="muted">No usage recorded yet</p>;
  }

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="API key requests per day"
      style={{ width: '100%', height: 'auto', maxWidth: 640 }}
    >
      <line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + innerH} stroke="#d6d3d1" />
      <line
        x1={pad.left}
        y1={pad.top + innerH}
        x2={pad.left + innerW}
        y2={pad.top + innerH}
        stroke="#d6d3d1"
      />
      <text x={4} y={pad.top + 8} fontSize="10" fill="#57534e">
        {maxY}
      </text>
      {points.map((p, i) => {
        const h = ((Number(p.requests) || 0) / maxY) * innerH;
        const x = pad.left + i * (barW + gap);
        const y = pad.top + innerH - h;
        return (
          <g key={p.date}>
            <rect x={x} y={y} width={barW} height={Math.max(h, 0)} fill="#0f766e" opacity={0.85}>
              <title>
                {p.date}: {p.requests}
              </title>
            </rect>
            {(i === 0 || i === points.length - 1 || i === Math.floor(points.length / 2)) && (
              <text x={x + barW / 2} y={height - 6} fontSize="9" fill="#57534e" textAnchor="middle">
                {p.date.slice(5)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export default function Page() {
  const [status, setStatus] = useState<any>(null);
  const [passkeys, setPasskeys] = useState<any[]>([]);
  const [sessions, setSessions] = useState<any[]>([]);
  const [setup, setSetup] = useState<any>(null);
  const [code, setCode] = useState('');
  const [passkeyName, setPasskeyName] = useState('My passkey');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [disablePassword, setDisablePassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [locale, setLocale] = useState(DEFAULT_LOCALE);
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [apiKeyName, setApiKeyName] = useState('Integration key');
  const [newApiKeySecret, setNewApiKeySecret] = useState('');
  const [apiKeyUsage, setApiKeyUsage] = useState<any | null>(null);
  const [apiKeyUsageId, setApiKeyUsageId] = useState('');
  const [webhooks, setWebhooks] = useState<any[]>([]);
  const [webhookUrl, setWebhookUrl] = useState('https://');
  const [webhookEvents, setWebhookEvents] = useState('sale.created,webhook.test');
  const [newWebhookSecret, setNewWebhookSecret] = useState('');
  const [role, setRole] = useState('');
  const [principal, setPrincipal] = useState('');

  async function refresh() {
    const [r, keys, sess, me] = await Promise.all([
      api('/auth/2fa/status'),
      api('/auth/webauthn/credentials').catch(() => ({ data: [] })),
      api('/auth/sessions').catch(() => ({ data: [] })),
      api('/me').catch(() => ({ data: null })),
    ]);
    setStatus(r.data);
    setPasskeys(keys.data || []);
    setSessions(sess.data || []);
    const userRole = me.data?.role || r.data?.role || '';
    setRole(userRole);
    setPrincipal(me.data?.principal || '');
    if (me.data?.locale === 'en' || me.data?.preferred_language === 'en') {
      setLocale('en');
    }
    if (userRole === 'company_admin' || userRole === 'super_admin') {
      try {
        const listed = await api('/api-keys');
        setApiKeys(listed.data || []);
      } catch {
        setApiKeys([]);
      }
      try {
        const hooks = await api('/webhooks');
        setWebhooks(hooks.data || []);
      } catch {
        setWebhooks([]);
      }
    } else {
      setApiKeys([]);
      setWebhooks([]);
    }
  }

  async function createApiKey() {
    setError('');
    setMessage('');
    setNewApiKeySecret('');
    try {
      const r = await api('/api-keys', {
        method: 'POST',
        body: JSON.stringify({ name: apiKeyName }),
      });
      setNewApiKeySecret(r.data?.api_key || '');
      setMessage(r.message || 'API key created — copy the secret now');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function revokeApiKey(id: string) {
    setError('');
    try {
      await api(`/api-keys/${id}`, { method: 'DELETE' });
      setMessage('API key revoked');
      if (apiKeyUsageId === id) {
        setApiKeyUsage(null);
        setApiKeyUsageId('');
      }
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadApiKeyUsage(id: string) {
    setError('');
    try {
      const r = await api(`/api-keys/${id}/usage?days=30`);
      setApiKeyUsageId(id);
      setApiKeyUsage(r.data || null);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createWebhook() {
    setError('');
    setMessage('');
    setNewWebhookSecret('');
    try {
      const events = webhookEvents
        .split(',')
        .map((e) => e.trim())
        .filter(Boolean);
      const r = await api('/webhooks', {
        method: 'POST',
        body: JSON.stringify({ url: webhookUrl, events }),
      });
      setNewWebhookSecret(r.data?.secret || '');
      setMessage(r.message || 'Webhook created — copy the signing secret now');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function testWebhook(id: string) {
    setError('');
    try {
      const r = await api(`/webhooks/${id}/test`, { method: 'POST', body: '{}' });
      setMessage(`Webhook test: ${r.data?.status || 'attempted'}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deleteWebhook(id: string) {
    setError('');
    try {
      await api(`/webhooks/${id}`, { method: 'DELETE' });
      setMessage('Webhook deleted');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function revokeSession(id: string) {
    setError('');
    try {
      await api(`/auth/sessions/${id}`, { method: 'DELETE' });
      setMessage('Session revoked');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function changePassword() {
    setError('');
    setMessage('');
    if (newPassword !== confirmPassword) {
      setError('New password confirmation does not match');
      return;
    }
    try {
      const r = await api('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setMessage(r.message || 'Password updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  // Stage 103 S1 — honor Shell #passkeys / #totp / #webhooks / #api-keys / #sessions
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!hash) return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
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

  const ConsoleShell = ({ children }: { children: ReactNode }) =>
    principal === 'platform' ? <PlatformShell>{children}</PlatformShell> : <Shell>{children}</Shell>;

  return (
    <ConsoleShell>
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

      <div className="card" style={{ marginBottom: 16, maxWidth: 420 }}>
        <h2>Change password</h2>
        <p className="muted">Other devices will be signed out after a successful change.</p>
        <div style={{ display: 'grid', gap: 8 }}>
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="Current password"
          />
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="New password"
          />
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder="Confirm new password"
          />
          <button type="button" onClick={changePassword}>
            Update password
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16, maxWidth: 480 }}>
        <h2>{t('language.label', locale)}</h2>
        <p className="muted">{t('language.mvp_only', locale)}</p>
        <select value={locale} disabled style={{ maxWidth: 220 }}>
          {SUPPORTED_LOCALES.map((code) => (
            <option key={code} value={code}>
              {t('language.english', locale)} ({code})
            </option>
          ))}
        </select>
      </div>

      <div className="card" style={{ marginBottom: 16 }} id="passkeys">
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
        <div className="card" style={{ marginBottom: 16 }} id="totp">
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
        <div className="card" style={{ marginBottom: 16 }} id="totp">
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
        <div className="card" style={{ marginBottom: 16 }}>
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

      {(role === 'company_admin' || role === 'super_admin') && (
        <div className="card" style={{ marginBottom: 16 }} id="webhooks">
          <h2>Webhooks</h2>
          <p className="muted">
            Outbound signed events use header <code>X-Ribdigi-Signature</code> (<code>t=…,v1=…</code> HMAC-SHA256).
          </p>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            <input
              value={webhookUrl}
              onChange={(e) => setWebhookUrl(e.target.value)}
              placeholder="https://your-app.com/webhooks/ribdigi"
              style={{ minWidth: 280 }}
            />
            <input
              value={webhookEvents}
              onChange={(e) => setWebhookEvents(e.target.value)}
              placeholder="sale.created,webhook.test"
              style={{ minWidth: 200 }}
            />
            <button type="button" onClick={createWebhook}>
              Create webhook
            </button>
          </div>
          {newWebhookSecret && (
            <p>
              Signing secret (copy now): <code>{newWebhookSecret}</code>
            </p>
          )}
          <table className="table">
            <thead>
              <tr>
                <th>URL</th>
                <th>Events</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {webhooks.map((w) => (
                <tr key={w.id}>
                  <td className="muted" style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {w.url}
                  </td>
                  <td>{(w.events || []).join(', ')}</td>
                  <td>{w.is_active ? 'active' : 'paused'}</td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button type="button" onClick={() => testWebhook(w.id)}>
                      Test
                    </button>
                    <button type="button" onClick={() => deleteWebhook(w.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {!webhooks.length && (
                <tr>
                  <td colSpan={4} className="muted">
                    No webhooks yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {(role === 'company_admin' || role === 'super_admin') && (
        <div className="card" style={{ marginBottom: 16 }} id="api-keys">
          <h2>API keys</h2>
          <p className="muted">
            Integration keys authenticate with the <code>X-API-Key</code> header. The secret is shown once.
          </p>
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            <input
              value={apiKeyName}
              onChange={(e) => setApiKeyName(e.target.value)}
              placeholder="Key name"
            />
            <button type="button" onClick={createApiKey}>
              Create key
            </button>
          </div>
          {newApiKeySecret && (
            <p>
              Secret (copy now): <code>{newApiKeySecret}</code>
            </p>
          )}
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Prefix</th>
                <th>Requests</th>
                <th>Last used</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {apiKeys.map((k) => (
                <tr key={k.id}>
                  <td>{k.name}</td>
                  <td>
                    <code>{k.key_prefix}</code>
                  </td>
                  <td>{Number(k.request_count || 0)}</td>
                  <td className="muted">
                    {k.last_used_at ? new Date(k.last_used_at).toLocaleString() : '—'}
                  </td>
                  <td>{k.status}</td>
                  <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <button type="button" onClick={() => loadApiKeyUsage(k.id)}>
                      Usage
                    </button>
                    {k.status === 'active' && (
                      <button type="button" onClick={() => revokeApiKey(k.id)}>
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!apiKeys.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No API keys yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {apiKeyUsage && (
            <div style={{ marginTop: 16 }}>
              <h3 style={{ margin: '0 0 8px' }}>
                Requests per day — {apiKeyUsage.name}{' '}
                <span className="muted">
                  (last {apiKeyUsage.days} days · Σ {apiKeyUsage.period_requests})
                </span>
              </h3>
              <ApiKeyUsageChart series={apiKeyUsage.series || []} />
            </div>
          )}
        </div>
      )}

      <div className="card" id="sessions">
        <h2>Active sessions</h2>
        <p className="muted">Revoke devices you no longer recognize.</p>
        <table className="table">
          <thead>
            <tr>
              <th>Created</th>
              <th>IP</th>
              <th>Agent</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s) => (
              <tr key={s.id}>
                <td>{s.created_at ? String(s.created_at) : '—'}</td>
                <td>{s.ip_address || '—'}</td>
                <td className="muted" style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {s.user_agent || '—'}
                  {s.current ? ' (this device)' : ''}
                </td>
                <td>
                  {!s.current && (
                    <button type="button" onClick={() => revokeSession(s.id)}>
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!sessions.length && (
              <tr>
                <td colSpan={4} className="muted">
                  No active sessions
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </ConsoleShell>
  );
}
