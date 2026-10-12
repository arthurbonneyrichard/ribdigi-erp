'use client';

import { useEffect, useState } from 'react';
import { api, setAuthTokens, unreachableApiMessage } from '../lib/api';
import { getAccessTokenSync } from '../lib/authStorage';
import { getMe, invalidateMeCache } from '../lib/meCache';
import { roleHomePath } from '../lib/tenantNav';
import { invalidatePrefetchCache } from '../lib/prefetchCache';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import LoginBrandLogo from '../components/LoginBrandLogo';
import { loadUserTheme } from '../lib/theme';
import { openShiftForSignedInUser } from '../lib/cashierShift';

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

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [tenant, setTenant] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [challengeToken, setChallengeToken] = useState('');
  const [methods, setMethods] = useState<string[]>([]);
  const [needs2fa, setNeeds2fa] = useState(false);
  const [needsEmailVerify, setNeedsEmailVerify] = useState(false);
  const [verifyMessage, setVerifyMessage] = useState('');
  const [debugVerifyToken, setDebugVerifyToken] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (!getAccessTokenSync()) return;
    let cancelled = false;
    getMe()
      .then((me) => {
        if (cancelled) return;
        if (String(me.data?.role || '') === 'cashier') router.replace('/pos');
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function finishLogin(data: any) {
    invalidateMeCache();
    invalidatePrefetchCache();
    await setAuthTokens(data.access_token, data.refresh_token || null);
    const tenantId = String(data.user?.tenant_id || '').trim();
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(tenantId)) {
      localStorage.setItem('tenant', tenantId);
    } else {
      localStorage.removeItem('tenant');
    }
    const uid = String(data.user?.id || '').trim();
    if (uid) {
      try {
        sessionStorage.setItem('ribdigi:uid', uid);
      } catch {
        /* ignore */
      }
      loadUserTheme(uid);
    }
    if (!data.must_enroll_2fa) {
      await openShiftForSignedInUser();
    }
    if (data.must_enroll_2fa) {
      router.push('/security');
    } else if (
      ['super_admin', 'platform_owner', 'platform_admin', 'platform_support', 'platform_finance'].includes(
        data.user?.role
      )
    ) {
      router.push('/platform');
    } else {
      router.push(roleHomePath(String(data.user?.role || ''), data.user?.industry));
    }
  }

  async function verifyPasskey() {
    setError('');
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      setError(
        'Sign-in requires a connection. Offline selling is allowed only on a device that already signed in online with a valid offline authorization — first-time offline login is not supported.'
      );
      return;
    }
    setBusy(true);
    try {
      if (!window.PublicKeyCredential) {
        throw new Error('This browser does not support passkeys');
      }
      const trimmedChallenge = challengeToken.trim();
      if (!trimmedChallenge) {
        setError('2FA challenge token is required');
        return;
      }
      const opt = await api('/auth/webauthn/login/options', {
        method: 'POST',
        body: JSON.stringify({ challenge_token: trimmedChallenge }),
      });
      const publicKey = { ...opt.data };
      publicKey.challenge = base64urlToBuffer(publicKey.challenge);
      if (Array.isArray(publicKey.allowCredentials)) {
        publicKey.allowCredentials = publicKey.allowCredentials.map((c: any) => ({
          ...c,
          id: base64urlToBuffer(c.id),
        }));
      }
      const cred = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential | null;
      if (!cred) throw new Error('Passkey cancelled');
      const assertion = cred.response as AuthenticatorAssertionResponse;
      const credential = {
        id: cred.id,
        rawId: bufferToBase64url(cred.rawId),
        type: cred.type,
        response: {
          clientDataJSON: bufferToBase64url(assertion.clientDataJSON),
          authenticatorData: bufferToBase64url(assertion.authenticatorData),
          signature: bufferToBase64url(assertion.signature),
          userHandle: assertion.userHandle ? bufferToBase64url(assertion.userHandle) : null,
        },
        clientExtensionResults: cred.getClientExtensionResults?.() || {},
      };
      const r = await api('/auth/webauthn/login/verify', {
        method: 'POST',
        body: JSON.stringify({ challenge_token: trimmedChallenge, credential }),
      });
      await finishLogin(r.data);
    } catch (err: any) {
      setError(err.message || 'Passkey login failed');
    } finally {
      setBusy(false);
    }
  }

  async function go(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      setError(
        'Sign-in requires a connection. Offline selling is allowed only on a device that already signed in online with a valid offline authorization — first-time offline login is not supported.'
      );
      return;
    }
    setBusy(true);
    try {
      if (needs2fa && challengeToken) {
        if (!methods.includes('totp') && methods.includes('webauthn')) {
          await verifyPasskey();
          return;
        }
        const trimmedChallenge = challengeToken.trim();
        if (!trimmedChallenge) {
          setError('2FA challenge token is required');
          return;
        }
        const r = await api('/auth/2fa/verify', {
          method: 'POST',
          body: JSON.stringify({
            challenge_token: trimmedChallenge,
            code: totpCode.trim(),
          }),
        });
        await finishLogin(r.data);
        return;
      }

      const trimmedPassword = password.trim();
      if (!trimmedPassword) {
        setError('Password is required');
        return;
      }
      const trimmedTenant = tenant.trim();
      if (!trimmedTenant) {
        setError('Login tenant is required');
        return;
      }
      const r = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email: email.trim(),
          password: trimmedPassword,
          tenant_id: trimmedTenant,
          totp_code: totpCode.trim() || null,
        }),
      });
      if (r.data?.requires_2fa) {
        setNeeds2fa(true);
        setChallengeToken(r.data.challenge_token);
        setMethods(r.data.methods || ['totp']);
        setTotpCode('');
        return;
      }
      await finishLogin(r.data);
    } catch (err: any) {
      const detail = err.detail;
      const code = typeof detail === 'object' && detail ? detail.code : null;
      if (err.status === 403 && code === 'EMAIL_NOT_VERIFIED') {
        setNeedsEmailVerify(true);
        setVerifyMessage('');
        setError(detail?.message || 'Verify your email before signing in');
        return;
      }
      const raw = String(err.message || '');
      if (!raw || /failed to fetch|networkerror|load failed/i.test(raw)) {
        setError(unreachableApiMessage());
        return;
      }
      setError(raw || 'Login failed');
    } finally {
      setBusy(false);
    }
  }

  async function resendVerification() {
    setError('');
    setVerifyMessage('');
    setDebugVerifyToken('');
    const trimmedTenant = tenant.trim();
    if (!trimmedTenant) {
      setError('Login tenant is required');
      return;
    }
    setBusy(true);
    try {
      const r = await api('/auth/resend-verification', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), tenant_id: trimmedTenant }),
      });
      setVerifyMessage(r.message || 'If verification is needed, a link was sent');
      if (r.data?.verification_token) {
        setDebugVerifyToken(String(r.data.verification_token));
      }
    } catch (err: any) {
      setError(err.message || 'Unable to resend verification');
    } finally {
      setBusy(false);
    }
  }

  const showTotp = !needs2fa || methods.includes('totp') || methods.length === 0;
  const showPasskey = needs2fa && methods.includes('webauthn');

  return (
    <div className="login-stage">
      <div className="login-stage-bg" aria-hidden>
        <span className="login-orb login-orb-a" />
        <span className="login-orb login-orb-b" />
        <span className="login-grid" />
      </div>

      <div className="login">
        <LoginBrandLogo />

        <form className="login-form" onSubmit={go}>
          {!needs2fa && (
            <>
              <label className="login-field">
                <span>Workspace</span>
                <input
                  aria-label="Login tenant"
                  value={tenant}
                  onChange={(e) => setTenant(e.target.value)}
                  placeholder="Tenant slug or ID"
                  autoComplete="organization"
                  required
                  disabled={busy}
                />
              </label>
              <label className="login-field">
                <span>Email</span>
                <input
                  aria-label="Login email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  type="email"
                  autoComplete="username"
                  required
                  disabled={busy}
                />
              </label>
              <label className="login-field">
                <span>Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  aria-label="Login password"
                  required
                  disabled={busy}
                />
              </label>
              <p className="login-forgot">
                <Link
                  href={`/forgot-password${tenant ? `?tenant=${encodeURIComponent(tenant)}` : ''}${email ? `${tenant ? '&' : '?'}email=${encodeURIComponent(email)}` : ''}`}
                >
                  Forgot password?
                </Link>
              </p>
            </>
          )}

          {needs2fa && (
            <input
              type="hidden"
              value={challengeToken}
              readOnly
              aria-label="2FA challenge token"
            />
          )}

          {needs2fa && showTotp && (
            <label className="login-field">
              <span>Authenticator code</span>
              <p className="login-hint">Enter the 6-digit code from your authenticator app, or a backup code.</p>
              <input
                aria-label="2FA code"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                placeholder="000000"
                inputMode="numeric"
                autoComplete="one-time-code"
                required={methods.includes('totp') && !methods.includes('webauthn')}
                autoFocus
                disabled={busy}
              />
            </label>
          )}

          {showPasskey && <p className="login-hint">Or continue with a registered passkey.</p>}

          <button className="login-primary" type="submit" aria-label="Sign in" disabled={busy} aria-busy={busy}>
            {busy
              ? 'Signing in…'
              : needs2fa
                ? methods.includes('totp')
                  ? 'Verify & continue'
                  : 'Continue'
                : 'Sign in'}
          </button>

          {showPasskey && (
            <button
              className="login-secondary"
              type="button"
              onClick={verifyPasskey}
              aria-label="Use passkey"
              disabled={busy}
            >
              {busy ? 'Working…' : 'Use passkey'}
            </button>
          )}

          {needs2fa && (
            <button
              className="login-ghost"
              type="button"
              aria-label="Back to sign in"
              onClick={() => {
                setNeeds2fa(false);
                setChallengeToken('');
                setTotpCode('');
                setMethods([]);
              }}
            >
              Back to sign in
            </button>
          )}

          {error && <p className="login-error" role="alert">{error}</p>}
          {needsEmailVerify && (
            <div className="login-verify-box">
              <p className="login-hint">
                Check your inbox for a verification link, or resend one below.
              </p>
              <button
                className="login-secondary"
                type="button"
                onClick={resendVerification}
                aria-label="Resend verification email"
                disabled={busy}
              >
                {busy ? 'Sending…' : 'Resend verification email'}
              </button>
              <Link className="login-ghost" href="/verify-email" style={{ display: 'block', textAlign: 'center' }}>
                Open verify page
              </Link>
              {verifyMessage && (
                <p className="login-success" role="status">
                  {verifyMessage}
                </p>
              )}
              {debugVerifyToken && (
                <p className="login-hint">
                  Dev verify link:{' '}
                  <Link href={`/verify-email?token=${encodeURIComponent(debugVerifyToken)}`}>
                    Open verify form
                  </Link>
                </p>
              )}
            </div>
          )}
        </form>

        <p className="login-foot">
          <a href="https://ribdigihouse.com" target="_blank" rel="noopener noreferrer">
            A Ribdigi House Product
          </a>
        </p>
      </div>
    </div>
  );
}
