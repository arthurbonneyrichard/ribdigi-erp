'use client';

import { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { useRouter, useSearchParams } from 'next/navigation';

export default function Page() {
  const params = useSearchParams();
  const router = useRouter();
  const [token, setToken] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const t = params.get('token');
    if (t) setToken(t);
  }, [params]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    try {
      const r = await api('/auth/verify-email', {
        method: 'POST',
        body: JSON.stringify({ token }),
      });
      setMessage(r.message || 'Email verified');
      setTimeout(() => router.push('/'), 1200);
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <div className="login">
      <h1>Verify email</h1>
      <form onSubmit={submit}>
        <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="Verification token" required />
        <button type="submit">Verify</button>
        {error && <p>{error}</p>}
        {message && <p style={{ color: '#047857' }}>{message}</p>}
      </form>
    </div>
  );
}
