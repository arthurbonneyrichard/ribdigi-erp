'use client';

import { FormEvent, useEffect, useState } from 'react';
import PageHeader from '../../../components/PageHeader';
import { api } from '../../../lib/api';
import { AmountField } from '../../../components/AmountField';
import { formatMoney } from '../../../lib/format';

type Card = { id?: string; code: string; balance: number; status: string; created_at?: string | null };

function statusWord(status: string) {
  if (status === 'active') return 'Ready to spend';
  if (status === 'redeemed' || status === 'used') return 'Spent';
  return status.replace(/_/g, ' ');
}

export default function GiftCardsPage() {
  const [amount, setAmount] = useState('');
  const [lookup, setLookup] = useState('');
  const [issued, setIssued] = useState<Card | null>(null);
  const [found, setFound] = useState<Card | null>(null);
  const [cards, setCards] = useState<Card[]>([]);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  async function loadCards() {
    try {
      const res = await api('/gift-cards');
      setCards(Array.isArray(res.data) ? res.data : []);
    } catch {
      /* the list is a convenience; issuing and lookup still work */
    }
  }

  useEffect(() => {
    void loadCards();
  }, []);

  async function issue(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError('');
    setIssued(null);
    setCopied(false);
    setBusy(true);
    try {
      const res = await api('/gift-cards', {
        method: 'POST',
        body: JSON.stringify({ amount: Number(amount) }),
      });
      setIssued(res.data);
      setAmount('');
      await loadCards();
    } catch (err: any) {
      setError(err.message || 'Could not issue the gift card');
    } finally {
      setBusy(false);
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
      setError(err.message || 'No gift card has that code');
    }
  }

  async function copyCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <main className="page gift-page">
      <PageHeader
        title="Gift cards"
        subtitle="Give a customer a gift card, as a promotion or a thank-you. They spend it at the till: choose Gift card as the payment and type the code. The card's value is booked as a promotion cost, and what is left stays owed to the customer until it is spent."
      />
      {error ? (
        <p className="list-toast err" role="alert">
          {error}
        </p>
      ) : null}
      <div className="gift-grid">
        <section className="card gift-box">
          <h3>Issue a gift card</h3>
          <form onSubmit={issue} className="gift-form">
            <div className="field">
              <label htmlFor="gift-amount">Amount on the card</label>
              <AmountField
                id="gift-amount"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                required
                type="number"
                min="0.01"
                step="0.01"
                aria-label="Gift card amount"
              />
            </div>
            <button type="submit" className="btn-primary" disabled={busy || !(Number(amount) > 0)}>
              {busy ? 'Issuing…' : 'Issue gift card'}
            </button>
          </form>
          {issued ? (
            <div className="gift-issued" role="status">
              <span className="gift-issued-label">Give the customer this code</span>
              <strong className="gift-code">{issued.code}</strong>
              <span>{formatMoney(issued.balance)} on the card</span>
              <button type="button" onClick={() => copyCode(issued.code)} aria-label="Copy gift card code">
                {copied ? 'Copied' : 'Copy code'}
              </button>
            </div>
          ) : null}
        </section>
        <section className="card gift-box">
          <h3>Check a card</h3>
          <form onSubmit={find} className="gift-form">
            <div className="field">
              <label htmlFor="gift-lookup">Gift card code</label>
              <input
                id="gift-lookup"
                value={lookup}
                onChange={(e) => setLookup(e.target.value)}
                required
                placeholder="Type or scan the code"
                aria-label="Gift card lookup code"
              />
            </div>
            <button type="submit" disabled={!lookup.trim()}>
              Check balance
            </button>
          </form>
          {found ? (
            <p className="gift-found">
              <strong>{found.code}</strong> has <strong>{formatMoney(found.balance)}</strong> left · {statusWord(found.status)}
            </p>
          ) : null}
        </section>
      </div>
      <section className="card gift-box">
        <h3>Cards issued</h3>
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th className="col-date">Issued on</th>
                <th className="col-status">Status</th>
                <th className="col-num">Left on card</th>
              </tr>
            </thead>
            <tbody>
              {cards.map((c) => (
                <tr key={c.id || c.code}>
                  <td className="col-id">{c.code}</td>
                  <td className="col-date">{c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}</td>
                  <td className="col-status">{statusWord(c.status)}</td>
                  <td className="col-num">{formatMoney(c.balance)}</td>
                </tr>
              ))}
              {cards.length === 0 ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No gift cards yet. Issue one above.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
