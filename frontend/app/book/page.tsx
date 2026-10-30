'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiRoot } from '../../lib/api';

export default function RestaurantBookingHostPage() {
  const router = useRouter();
  const [error, setError] = useState('');

  useEffect(() => {
    const host = window.location.hostname.replace(/^www\./, '');
    fetch(`${apiRoot()}/public/restaurant-booking/by-host?host=${encodeURIComponent(host)}`)
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (!res.ok || !body?.data?.slug) {
          setError('This domain is not linked to a restaurant website.');
          return;
        }
        router.replace(`/book/${body.data.slug}`);
      })
      .catch(() => setError('This domain is not linked to a restaurant website.'));
  }, [router]);

  return (
    <main className="card" style={{ maxWidth: 560, margin: '32px auto' }} aria-label="Restaurant booking domain">
      <h1>Restaurant booking</h1>
      {error ? <p role="alert">{error}</p> : <p className="muted">Opening the restaurant website.</p>}
    </main>
  );
}
