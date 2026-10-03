'use client';

import { FormEvent, useState } from 'react';
import { api } from '../../../lib/api';

export default function BillingNoticePage() {
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState('bank_transfer');
  const [reference, setReference] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError('');
    setMessage('');
    try {
      const res = await api('/billing/payment-notices', {
        method: 'POST',
        body: JSON.stringify({
          amount: Number(amount),
          method,
          reference,
        }),
      });
      setMessage(
        res?.data?.funds_captured
          ? 'Unexpected capture flag'
          : 'Payment information saved. No card funds were captured.'
      );
      setAmount('');
      setReference('');
    } catch (err: any) {
      setError(err.message || 'Could not save the payment notice');
    }
  }

  return (
    <main className="page">
      <h1>Payment notice</h1>
      <p>Record how a payment was made. This does not charge a card or change subscription revenue.</p>
      {error ? <p role="alert">{error}</p> : null}
      {message ? <p>{message}</p> : null}
      <form onSubmit={submit}>
        <label>
          Amount
          <input value={amount} onChange={(e) => setAmount(e.target.value)} required type="number" min="0.01" step="0.01" />
        </label>
        <label>
          Method
          <select value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="bank_transfer">Bank transfer</option>
            <option value="cash">Cash</option>
            <option value="card">Card</option>
            <option value="wallet">Wallet</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Reference
          <input value={reference} onChange={(e) => setReference(e.target.value)} required />
        </label>
        <button type="submit">Save payment information</button>
      </form>
    </main>
  );
}
