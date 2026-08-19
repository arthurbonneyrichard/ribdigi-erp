'use client';

import Link from 'next/link';
import { useState } from 'react';
import { api } from '../lib/api';
import { useRouter } from 'next/navigation';

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
  const [remember, setRemember] = useState(true);
  const [showReset, setShowReset] = useState(false);
  const [resetMsg, setResetMsg] = useState('');
  const [needsVerify, setNeedsVerify] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState('');
  const [error, setError] = useState('');
  const router = useRouter();

  function finishLogin(data: any) {
    localStorage.setItem('token', data.access_token);
    if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('tenant', data.user.tenant_id);
    const principal = data.principal || data.user?.principal || 'tenant';
    localStorage.setItem('principal', principal);
    // Stage 87 Z1 — cookie for Next middleware console boundary (readable server-side)
    document.cookie = `ribdigi_principal=${encodeURIComponent(principal)}; path=/; SameSite=Lax`;
    if (!remember) {
      // Session-only preference marker for future idle logout UX.
      sessionStorage.setItem('ribdigi_session_only', '1');
    } else {
      sessionStorage.removeItem('ribdigi_session_only');
    }
    if (data.must_enroll_2fa) {
      router.push('/security');
    } else {
      const dest =
        data.redirect_path ||
        data.user?.redirect_path ||
        (data.principal === 'platform' || data.user?.principal === 'platform'
          ? '/platform/dashboard'
          : '/dashboard');
      router.push(dest);
    }
  }

  async function requestReset(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setResetMsg('');
    try {
      await api('/auth/password-reset-request', {
        method: 'POST',
        body: JSON.stringify({ email, tenant_id: tenant }),
      });
      setResetMsg('If the account exists, a reset link was sent (check email / console in dev).');
    } catch (err: any) {
      setError(err.message || 'Reset request failed');
    }
  }

  async function verifyPasskey() {
    setError('');
    try {
      if (!window.PublicKeyCredential) {
        throw new Error('This browser does not support passkeys');
      }
      const opt = await api('/auth/webauthn/login/options', {
        method: 'POST',
        body: JSON.stringify({ challenge_token: challengeToken }),
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
        body: JSON.stringify({ challenge_token: challengeToken, credential }),
      });
      finishLogin(r.data);
    } catch (err: any) {
      setError(err.message || 'Passkey login failed');
    }
  }

  async function resendVerification() {
    setError('');
    setVerifyMsg('');
    try {
      await api('/auth/resend-verification', {
        method: 'POST',
        body: JSON.stringify({ email, tenant_id: tenant }),
      });
      setVerifyMsg('If the account exists, a verification email was sent.');
    } catch (err: any) {
      setError(err.message || 'Could not resend verification');
    }
  }

  async function go(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setNeedsVerify(false);
    setVerifyMsg('');
    try {
      if (needs2fa && challengeToken) {
        if (!methods.includes('totp') && methods.includes('webauthn')) {
          await verifyPasskey();
          return;
        }
        const r = await api('/auth/2fa/verify', {
          method: 'POST',
          body: JSON.stringify({ challenge_token: challengeToken, code: totpCode }),
        });
        finishLogin(r.data);
        return;
      }

      const r = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({
          email,
          password,
          tenant_id: tenant,
          totp_code: totpCode || null,
        }),
      });
      if (r.data?.requires_2fa) {
        setNeeds2fa(true);
        setChallengeToken(r.data.challenge_token);
        setMethods(r.data.methods || ['totp']);
        setTotpCode('');
        return;
      }
      finishLogin(r.data);
    } catch (err: any) {
      if (err?.code === 'EMAIL_NOT_VERIFIED') {
        setNeedsVerify(true);
      }
      setError(err.message || 'Login failed');
    }
  }

  const showTotp = !needs2fa || methods.includes('totp') || methods.length === 0;
  const showPasskey = needs2fa && methods.includes('webauthn');

  return (
    <div className="login">
      <h1>RIBDIGI ERP</h1>
      <p className="muted">One ERP Platform. Unlimited Business.</p>
      {showReset ? (
        <form onSubmit={requestReset}>
          <p className="muted">Enter your tenant and email to request a password reset.</p>
          <input value={tenant} onChange={(e) => setTenant(e.target.value)} placeholder="Tenant slug or ID" required />
          <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" type="email" required />
          <button type="submit">Send reset link</button>
          <button type="button" onClick={() => setShowReset(false)}>
            Back to sign in
          </button>
          {resetMsg && <p style={{ color: '#047857' }}>{resetMsg}</p>}
          {error && <p>{error}</p>}
        </form>
      ) : (
        <form onSubmit={go}>
          {!needs2fa && (
            <>
              <input value={tenant} onChange={(e) => setTenant(e.target.value)} placeholder="Tenant slug or ID" required />
              <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" type="email" required />
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" required />
              <label className="muted" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
                Remember me on this device
              </label>
            </>
          )}
          {needs2fa && showTotp && (
            <>
              <p className="muted">Enter the 6-digit code from your authenticator app (or a backup code).</p>
              <input
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                placeholder="Authenticator or backup code"
                required={methods.includes('totp') && !methods.includes('webauthn')}
                autoFocus
              />
            </>
          )}
          {showPasskey && (
            <p className="muted">Or use a registered passkey for this account.</p>
          )}
          <button type="submit">
            {needs2fa ? (methods.includes('totp') ? 'Verify 2FA' : 'Continue') : 'Sign in'}
          </button>
          {showPasskey && (
            <button type="button" onClick={verifyPasskey}>
              Use passkey
            </button>
          )}
          {needs2fa && (
            <button
              type="button"
              onClick={() => {
                setNeeds2fa(false);
                setChallengeToken('');
                setTotpCode('');
                setMethods([]);
              }}
            >
              Back
            </button>
          )}
          {!needs2fa && (
            <>
              <button type="button" onClick={() => setShowReset(true)}>
                Forgot password?
              </button>
              <p className="muted">
                New company? <Link href="/register">Register</Link>
              </p>
            </>
          )}
          {error && <p>{error}</p>}
          {needsVerify && !needs2fa && (
            <div>
              <p className="muted">
                Verify your email before signing in.{' '}
                <Link href="/verify-email">Have a token?</Link>
              </p>
              <button type="button" onClick={resendVerification}>
                Resend verification email
              </button>
              {verifyMsg && <p style={{ color: '#047857' }}>{verifyMsg}</p>}
            </div>
          )}
        </form>
      )}
    </div>
  );
}
