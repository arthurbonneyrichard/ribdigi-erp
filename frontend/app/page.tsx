'use client';

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
  const [error, setError] = useState('');
  const router = useRouter();

  function finishLogin(data: any) {
    localStorage.setItem('token', data.access_token);
    if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('tenant', data.user.tenant_id);
    if (data.must_enroll_2fa) {
      router.push('/security');
    } else {
      router.push('/dashboard');
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

  async function go(e: React.FormEvent) {
    e.preventDefault();
    setError('');
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
      setError(err.message || 'Login failed');
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
        <div className="login-brand">
          <div className="login-badge" aria-hidden>
            R
          </div>
          <h1>RIBDIGI ERP</h1>
          <p className="login-tagline">One System. Total Business Control.</p>
        </div>

        <form className="login-form" onSubmit={go}>
          {!needs2fa && (
            <>
              <label className="login-field">
                <span>Workspace</span>
                <input
                  value={tenant}
                  onChange={(e) => setTenant(e.target.value)}
                  placeholder="Tenant slug or ID"
                  autoComplete="organization"
                  required
                />
              </label>
              <label className="login-field">
                <span>Email</span>
                <input
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  type="email"
                  autoComplete="username"
                  required
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
                  required
                />
              </label>
            </>
          )}

          {needs2fa && showTotp && (
            <label className="login-field">
              <span>Authenticator code</span>
              <p className="login-hint">Enter the 6-digit code from your authenticator app, or a backup code.</p>
              <input
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                placeholder="000000"
                inputMode="numeric"
                autoComplete="one-time-code"
                required={methods.includes('totp') && !methods.includes('webauthn')}
                autoFocus
              />
            </label>
          )}

          {showPasskey && <p className="login-hint">Or continue with a registered passkey.</p>}

          <button className="login-primary" type="submit">
            {needs2fa ? (methods.includes('totp') ? 'Verify & continue' : 'Continue') : 'Sign in'}
          </button>

          {showPasskey && (
            <button className="login-secondary" type="button" onClick={verifyPasskey}>
              Use passkey
            </button>
          )}

          {needs2fa && (
            <button
              className="login-ghost"
              type="button"
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
        </form>

        <p className="login-foot">A Ribdigi House Product</p>
      </div>
    </div>
  );
}
