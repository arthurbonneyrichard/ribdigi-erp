'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { storefrontFetch } from '../../../../lib/storefrontApi';

const TITLES: Record<string, string> = {
  contact: 'Contact',
  shipping: 'Shipping',
  returns: 'Returns',
  privacy: 'Privacy',
};

export default function PolicyPage() {
  const params = useParams<{ slug: string }>();
  const [title, setTitle] = useState('Policy');
  const [body, setBody] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const slug = params.slug;
    if (!slug) return;
    setTitle(TITLES[slug] || slug);
    storefrontFetch(`/storefront/policies/${slug}`)
      .then((res) => {
        setTitle(`${res.data?.company_name || ''} ${TITLES[slug] || slug}`.trim());
        setBody(res.data?.body || '');
        setError('');
      })
      .catch((err) => setError(err.message || 'Policy not found'));
  }, [params.slug]);

  return (
    <main className="sf-main">
      <h1>{title}</h1>
      {error ? <p className="sf-alert" role="alert">{error}</p> : null}
      {error ? null : !body ? (
        <section className="sf-empty" role="status">
          <p className="sf-empty-title">This policy has not been published yet</p>
          <p className="sf-muted">A staff member can add it on the Online store desk.</p>
        </section>
      ) : (
        <article className="sf-card">
          <p>{body}</p>
        </article>
      )}
    </main>
  );
}
