'use client';

import { FormEvent, useState } from 'react';
import { api } from '../../../lib/api';

const METHODS = [
  ['bank_transfer', 'Bank transfer'],
  ['cash', 'Cash'],
  ['card', 'Card'],
  ['wallet', 'Wallet'],
  ['other', 'Other'],
] as const;

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
        body: JSON.stringify({ amount: Number(amount), method, reference }),
      });
      setMessage(
        res?.data?.funds_captured
          ? 'Unexpected capture flag'
          : 'Payment information saved. No card funds were captured.',
      );
      setAmount('');
      setReference('');
    } catch (err: any) {
      setError(err.message || 'Could not save the payment notice');
    }
  }

  return (
    <div className="work">
      <div className="list-page-head">
        <div>
          <h1>Payment notice</h1>
          <p className="muted">
            Record how a payment was made. This does not charge a card or change subscription revenue.
          </p>
        </div>
      </div>
      {error && <p className="erp-banner err" role="alert">{error}</p>}
      {message && <p className="erp-banner ok" role="status">{message}</p>}
      <div className="work-pair">
        <form className="card" onSubmit={submit}>
          <h3>Record a notice</h3>
          <div className="erp-form-grid">
            <label>
              Amount
              <input
                required
                type="number"
                min="0.01"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                aria-label="Payment notice amount"
              />
            </label>
            <label>
              Method
              <select value={method} onChange={(e) => setMethod(e.target.value)} aria-label="Payment notice method">
                {METHODS.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label className="work-span">
              Reference
              <input
                required
                value={reference}
                onChange={(e) => setReference(e.target.value)}
                placeholder="Receipt, transfer, or teller number"
                aria-label="Payment notice reference"
              />
            </label>
          </div>
          <button className="list-btn-primary" type="submit" aria-label="Save payment notice">
            Save payment information
          </button>
        </form>
        <div className="card">
          <h3>What gets saved</h3>
          <div className="work-facts">
            <span><small>Amount</small><strong>The figure you enter</strong></span>
            <span><small>Method</small><strong>How it was paid</strong></span>
            <span><small>Reference</small><strong>Your receipt number</strong></span>
            <span><small>Card charge</small><strong>None</strong></span>
          </div>
        </div>
      </div>
    </div>
  );
}
