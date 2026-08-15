'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '../../lib/api';
import { useRouter, useSearchParams } from 'next/navigation';

function ResetPasswordForm() {
  const params = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const t = params.get('token');
    if (t) setToken(t);
  }, [params]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setSubmitting(true);
    try {
      const r = await api('/auth/password-reset', {
        method: 'POST',
        body: JSON.stringify({ token, new_password: password }),
      });
      setMessage(r.message || 'Password updated — you can sign in now');
      setTimeout(() => router.push('/'), 1200);
    } catch (err: any) {
      setError(err.message);
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
            width={160}
            height={98}
          />
        </div>

        <h1 className="login-heading">Reset password</h1>
        <p className="login-hint" style={{ marginBottom: 12 }}>
          Choose a strong password (8+ chars, mixed case, number, and symbol).
        </p>

        <form className="login-form" onSubmit={submit}>
          {!params.get('token') && (
            <label className="login-field">
              <span>Reset token</span>
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Paste token from email"
                required
              />
            </label>
          )}
          <label className="login-field">
            <span>New password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="New password"
              autoComplete="new-password"
              required
            />
          </label>
          <label className="login-field">
            <span>Confirm password</span>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Confirm new password"
              autoComplete="new-password"
              required
            />
          </label>
          <button className="login-primary" type="submit" disabled={submitting}>
            {submitting ? 'Updating…' : 'Update password'}
          </button>
          <Link className="login-ghost" href="/forgot-password" style={{ display: 'block', textAlign: 'center' }}>
            Request a new link
          </Link>
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
            <h1 className="login-heading">Reset password</h1>
            <p className="login-hint">Loading…</p>
          </div>
        </div>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
