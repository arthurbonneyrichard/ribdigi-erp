'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiRoot } from '../../lib/api';

export default function StayHostPage() {
  const router = useRouter();
  const [error, setError] = useState('');

  useEffect(() => {
    const host = window.location.hostname.replace(/^www\./, '');
    fetch(`${apiRoot()}/public/hotel-booking/by-host?host=${encodeURIComponent(host)}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body?.detail || 'This domain is not linked to a hotel booking page.');
        const slug = body?.data?.slug;
        if (!slug) throw new Error('This domain is not linked to a hotel booking page.');
        router.replace(`/stay/${slug}`);
      })
      .catch((err: Error) => setError(err.message || 'This domain is not linked to a hotel booking page.'));
  }, [router]);

  return (
    <main className="card" style={{ maxWidth: 560, margin: '32px auto' }} aria-label="Hotel online booking">
      <h1>Book a stay</h1>
      {error ? <p role="alert">{error}</p> : <p className="muted">Looking up this domain.</p>}
    </main>
  );
}
