'use client';

import { FormEvent, useEffect, useState } from 'react';
import PageHeader from '../../../components/PageHeader';
import { api } from '../../../lib/api';
import { AmountField } from '../../../components/AmountField';
import { formatMoney } from '../../../lib/format';
import { getMe } from '../../../lib/meCache';
import { normalizeIndustry } from '../../../lib/industries';

type Card = { code: string; balance: number; status: string };

export default function GiftCardsPage() {
  const [amount, setAmount] = useState('');
  const [lookup, setLookup] = useState('');
  const [issued, setIssued] = useState<Card | null>(null);
  const [found, setFound] = useState<Card | null>(null);
  const [error, setError] = useState('');

  async function issue(e: FormEvent) {
    e.preventDefault();
    setError('');
    setIssued(null);
    try {
      const res = await api('/gift-cards', {
        method: 'POST',
        body: JSON.stringify({ amount: Number(amount) }),
      });
      setIssued(res.data);
      setAmount('');
    } catch (err: any) {
      setError(err.message || 'Could not issue the gift card');
    }
  }

  async function find(e: FormEvent) {
    e.preventDefault();
    setError('');
    setFound(null);
    try {
      const res = await api(`/gift-cards/${encodeURIComponent(lookup.trim())}`);
      setFound(res.data);
    } catch (err: any) {
      setError(err.message || 'Gift card not found');
    }
  }

  return (
    <main className="page">
      <PageHeader
        title="Gift cards"
        subtitle="Issue a card, then enter that code in Gift card code at POS. The balance stays a liability until the card is spent. One loyalty point equals one currency unit. A named customer earns 1% of the sale."
      />
      {error ? <p role="alert">{error}</p> : null}
      <form onSubmit={issue}>
        <label>
          Amount
          <AmountField value={amount} onChange={(e) => setAmount(e.target.value)} required type="number" min="0.01" step="0.01" aria-label="Gift card amount" />
        </label>
        <button type="submit">Issue gift card</button>
      </form>
      {issued ? (
        <p>
          Code <strong>{issued.code}</strong> · balance {formatMoney(issued.balance)} · {issued.status}
        </p>
      ) : null}
      <form onSubmit={find}>
        <label>
          Look up code
          <input value={lookup} onChange={(e) => setLookup(e.target.value)} required />
        </label>
        <button type="submit">Find</button>
      </form>
      {found ? (
        <p>
          {found.code} · balance {formatMoney(found.balance)} · {found.status}
        </p>
      ) : null}
    </main>
  );
}
