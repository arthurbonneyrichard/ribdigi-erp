'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { api } from '../../lib/api';
import LoginBrandLogo from '../../components/LoginBrandLogo';
import LoginLegalLinks from '../../components/LoginLegalLinks';

type State = { email: string; subscribed: boolean } | null;

function UnsubscribeForm() {
  const params = useSearchParams();
  const e = params.get('e') || '';
  const t = params.get('t') || '';
  const [state, setState] = useState<State>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const query = `e=${encodeURIComponent(e)}&t=${encodeURIComponent(t)}`;

  const load = useCallback(async () => {
    if (!e || !t) {
      setError('This unsubscribe link is incomplete. Use the link from the newest email.');
      return;
    }
    try {
      const r = await api(`/email/unsubscribe?${query}`);
      setState(r.data);
    } catch (err: any) {
      setError(err?.message || 'This unsubscribe link is not valid.');
    }
  }, [e, t, query]);

  useEffect(() => {
    load();
  }, [load]);

  async function change(subscribe: boolean) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const r = subscribe
        ? await api('/email/resubscribe', { method: 'POST', body: JSON.stringify({ e, t }) })
        : await api(`/email/unsubscribe?${query}`, { method: 'POST' });
      setState(r.data);
      setMessage(r.message || 'Saved.');
    } catch (err: any) {
      setError(err?.message || 'Could not save that. Try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-stage">
      <main className="login">
        <LoginBrandLogo />
        <h1 className="login-heading">Email preferences</h1>
        {error ? <p className="login-error" role="alert">{error}</p> : null}
        {message ? <p className="login-success" role="status">{message}</p> : null}
        {state ? (
          <>
            <p className="login-hint">
              {state.subscribed
                ? `${state.email} gets news and offers from Ribdigi House.`
                : `${state.email} no longer gets news and offers from Ribdigi House.`}
            </p>
            <p className="login-hint">
              Messages about your account, such as sign-in codes, billing and security notices, are still sent.
            </p>
            {state.subscribed ? (
              <button type="button" className="login-primary" disabled={busy} onClick={() => change(false)}>
                Unsubscribe from news and offers
              </button>
            ) : (
              <button type="button" className="login-secondary" disabled={busy} onClick={() => change(true)}>
                Subscribe again
              </button>
            )}
          </>
        ) : !error ? (
          <p className="login-hint" role="status">Checking your link…</p>
        ) : null}
        <LoginLegalLinks />
      </main>
    </div>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={null}>
      <UnsubscribeForm />
    </Suspense>
  );
}
