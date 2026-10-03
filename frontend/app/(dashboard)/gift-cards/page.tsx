'use client';

import { FormEvent, useState } from 'react';
import { api } from '../../../lib/api';

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
      <h1>Gift cards</h1>
      <p>Issue a card, then take it at POS with the code in the payment reference. One point of loyalty equals one currency unit and is earned on a named customer sale.</p>
      {error ? <p role="alert">{error}</p> : null}
      <form onSubmit={issue}>
        <label>
          Amount
          <input value={amount} onChange={(e) => setAmount(e.target.value)} required type="number" min="0.01" step="0.01" />
        </label>
        <button type="submit">Issue gift card</button>
      </form>
      {issued ? (
        <p>
          Code <strong>{issued.code}</strong> · balance {issued.balance} · {issued.status}
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
          {found.code} · balance {found.balance} · {found.status}
        </p>
      ) : null}
    </main>
  );
}
