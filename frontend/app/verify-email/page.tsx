'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '../../lib/api';
import { useRouter, useSearchParams } from 'next/navigation';

function VerifyEmailForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [autoTried, setAutoTried] = useState(false);

  useEffect(() => {
    const t = params.get('token');
    if (t) setToken(t);
  }, [params]);

  async function verify(rawToken: string) {
    setError('');
    setMessage('');
    setSubmitting(true);
    try {
      const r = await api('/auth/verify-email', {
        method: 'POST',
        body: JSON.stringify({ token: rawToken }),
      });
      setMessage(r.message || 'Email verified — you can sign in now');
      setTimeout(() => router.push('/'), 1200);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  useEffect(() => {
    const t = params.get('token');
    if (t && !autoTried) {
      setAutoTried(true);
      verify(t);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params, autoTried]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    await verify(token);
  }

  return (
    <div className="login-stage">
      <div className="login-stage-bg" aria-hidden>
        <span className="login-orb login-orb-a" />
        <span className="login-orb login-orb-b" />
        <span className="login-grid" />
      </div>

      <div className="login">
        <div className="login-brand">
          <img
            className="login-logo"
            src="/brand/logo-full.png"
            alt="RIBDIGI ERP — Run your business smarter"
            width={320}
            height={195}
          />
        </div>

        <h1 className="login-heading">Verify email</h1>
        <p className="login-hint" style={{ marginBottom: 12 }}>
          Confirm your email to unlock sign-in for this workspace.
        </p>

        <form className="login-form" onSubmit={submit}>
          {!params.get('token') && (
            <label className="login-field">
              <span>Verification token</span>
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste token from email"
                required
              />
            </label>
          )}
          <button className="login-primary" type="submit" disabled={submitting || !token}>
            {submitting ? 'Verifying…' : 'Verify email'}
          </button>
          <Link className="login-ghost" href="/" style={{ display: 'block', textAlign: 'center' }}>
            Back to sign in
          </Link>
          {error && (
            <p className="login-error" role="alert">
              {error}
            </p>
          )}
          {message && (
            <p className="login-success" role="status">
              {message}
            </p>
          )}
        </form>

        <p className="login-foot">A Ribdigi House Product</p>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="login-stage">
          <div className="login">
            <h1 className="login-heading">Verify email</h1>
            <p className="login-hint">Loading…</p>
          </div>
        </div>
      }
    >
      <VerifyEmailForm />
    </Suspense>
  );
}
