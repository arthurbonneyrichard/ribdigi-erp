'use client';

import { FormEvent, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { formatMoney, formatWhen } from '../../../lib/format';
import { AmountField } from '../../../components/AmountField';

const METHODS = [
  ['bank_transfer', 'Bank transfer'],
  ['cash', 'Cash'],
  ['card', 'Card'],
  ['wallet', 'Wallet'],
  ['other', 'Other'],
] as const;

type Notice = {
  id: string;
  amount: number;
  method: string;
  reference: string;
  created_at?: string | null;
};

function methodLabel(method: string) {
  return METHODS.find(([value]) => value === method)?.[1] || method;
}

export default function BillingNoticePage() {
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState('bank_transfer');
  const [reference, setReference] = useState('');
  const [notices, setNotices] = useState<Notice[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    const res = await api('/billing/payment-notices');
    setNotices(Array.isArray(res?.data) ? res.data : []);
  }

  useEffect(() => {
    load().catch((err: any) => setError(err?.message || 'Could not load payment notices'));
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await api('/billing/payment-notices', {
        method: 'POST',
        body: JSON.stringify({ amount: Number(amount), method, reference: reference.trim() }),
      });
      setMessage('Payment notice saved.');
      setAmount('');
      setReference('');
      await load();
    } catch (err: any) {
      setError(err.message || 'Could not save the payment notice');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="work">
      <div className="list-page-head">
        <div>
          <h1>Payment notice</h1>
          <p className="muted">Record a payment you already received. The amount, method, and reference stay in the list.</p>
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
              <AmountField
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
          <button className="list-btn-primary" type="submit" disabled={busy} aria-label="Save payment notice">
            Save payment notice
          </button>
        </form>
        <div className="card">
          <h3>Saved notices</h3>
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Amount</th>
                <th>Method</th>
                <th>Reference</th>
              </tr>
            </thead>
            <tbody>
              {notices.length === 0 ? (
                <tr>
                  <td colSpan={4}>No payment notices yet.</td>
                </tr>
              ) : null}
              {notices.map((row) => (
                <tr key={row.id}>
                  <td>{formatWhen(row.created_at) || '—'}</td>
                  <td>{formatMoney(row.amount)}</td>
                  <td>{methodLabel(row.method)}</td>
                  <td>{row.reference}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
