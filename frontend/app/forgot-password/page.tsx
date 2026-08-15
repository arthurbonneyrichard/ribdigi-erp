'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '../../lib/api';
import { useSearchParams } from 'next/navigation';

function ForgotPasswordForm() {
  const params = useSearchParams();
  const [tenant, setTenant] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [debugToken, setDebugToken] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const t = params.get('tenant');
    const e = params.get('email');
    if (t) setTenant(t);
    if (e) setEmail(e);
  }, [params]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    setDebugToken('');
    setSubmitting(true);
    try {
      const r = await api('/auth/password-reset-request', {
        method: 'POST',
        body: JSON.stringify({ email, tenant_id: tenant }),
      });
      setMessage(
        r.message ||
          'If the account exists, a reset link was sent. Check your email (or console mail in development).'
      );
      if (r.data?.reset_token) {
        setDebugToken(String(r.data.reset_token));
      }
    } catch (err: any) {
      setError(err.message || 'Unable to request password reset');
    } finally {
      setSubmitting(false);
    }
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

        <h1 className="login-heading">Forgot password</h1>
        <p className="login-hint" style={{ marginBottom: 12 }}>
          Enter your workspace and email. If an account matches, we send a one-hour reset link.
        </p>

        <form className="login-form" onSubmit={submit}>
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

          <button className="login-primary" type="submit" disabled={submitting}>
            {submitting ? 'Sending…' : 'Send reset link'}
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
          {debugToken && (
            <p className="login-hint">
              Dev reset link:{' '}
              <Link href={`/reset-password?token=${encodeURIComponent(debugToken)}`}>
                Open reset form
              </Link>
            </p>
          )}
        </form>

        <p className="login-foot">A Ribdigi House Product</p>
      </div>
    </div>
  );
}

export default function ForgotPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="login-stage">
          <div className="login">
            <h1 className="login-heading">Forgot password</h1>
            <p className="login-hint">Loading…</p>
          </div>
        </div>
      }
    >
      <ForgotPasswordForm />
    </Suspense>
  );
}
