'use client';

/**
 * Send a Mobile Money prompt to the customer's phone through the company's own Paystack account,
 * then wait for them to approve it. When paid, `onPaid(reference)` gives the till the reference
 * to complete the sale with; the server checks it is paid and has not paid another sale.
 */

import { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';

type Props = {
  /** The desk's prefix: '/pos', '/restaurant/till', '/hotel' or '/bakery/till'. */
  base: string;
  amount: number;
  onPaid: (reference: string) => void;
  formatMoney?: (n: number) => string;
};

const NETWORKS: [string, string][] = [
  ['mtn', 'MTN'],
  ['telecel', 'Telecel'],
  ['airteltigo', 'AirtelTigo'],
];

export default function TillMomoPrompt({ base, amount, onPaid, formatMoney }: Props) {
  const [phone, setPhone] = useState('');
  const [network, setNetwork] = useState('mtn');
  const [reference, setReference] = useState('');
  const [status, setStatus] = useState('');
  const [message, setMessage] = useState('');
  const [otp, setOtp] = useState('');
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);
  const money = formatMoney || ((n: number) => n.toFixed(2));

  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current);
  }, []);

  function follow(ref: string) {
    if (timer.current) window.clearInterval(timer.current);
    let tries = 0;
    timer.current = window.setInterval(async () => {
      tries += 1;
      try {
        const res = await api(`${base}/momo/${ref}`);
        const row = res?.data || {};
        setStatus(String(row.status || ''));
        setMessage(String(row.message || ''));
        if (row.status === 'success') {
          if (timer.current) window.clearInterval(timer.current);
          onPaid(ref);
        } else if (row.status === 'failed' || row.status === 'otp' || tries > 60) {
          if (timer.current) window.clearInterval(timer.current);
        }
      } catch {
        /* keep asking */
      }
    }, 4000);
  }

  async function send() {
    setBusy(true);
    setMessage('');
    try {
      const res = await api(`${base}/momo`, {
        method: 'POST',
        body: JSON.stringify({ amount: Math.round(amount * 100) / 100, phone: phone.trim(), provider: network }),
      });
      const row = res?.data || {};
      setReference(String(row.reference || ''));
      setStatus(String(row.status || ''));
      setMessage(String(row.message || ''));
      if (row.status === 'success') onPaid(String(row.reference));
      else if (row.status === 'pending') follow(String(row.reference));
    } catch (err) {
      setStatus('failed');
      setMessage(err instanceof Error ? err.message : 'Could not send the prompt.');
    } finally {
      setBusy(false);
    }
  }

  async function sendOtp() {
    setBusy(true);
    try {
      const res = await api(`${base}/momo/${reference}/otp`, { method: 'POST', body: JSON.stringify({ otp: otp.trim() }) });
      const row = res?.data || {};
      setStatus(String(row.status || ''));
      setMessage(String(row.message || ''));
      if (row.status === 'success') onPaid(reference);
      else if (row.status === 'pending') follow(reference);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'That code did not work.');
    } finally {
      setBusy(false);
    }
  }

  if (status === 'success') {
    return <p role="status" style={{ fontWeight: 700 }}>Mobile Money received: {money(amount)}.</p>;
  }

  return (
    <div className="till-momo" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input
          aria-label="Customer Mobile Money number"
          inputMode="tel"
          placeholder="024 123 4567"
          value={phone}
          onChange={(e) => setPhone(e.target.value.replace(/[^0-9+ ]/g, ''))}
          style={{ flex: '1 1 160px', minHeight: 44 }}
        />
        <select aria-label="Mobile Money network" value={network} onChange={(e) => setNetwork(e.target.value)} style={{ minHeight: 44 }}>
          {NETWORKS.map(([k, label]) => (
            <option key={k} value={k}>{label}</option>
          ))}
        </select>
        <button type="button" disabled={busy || phone.replace(/\D/g, '').length < 9 || amount <= 0} onClick={() => void send()} aria-label="Send Mobile Money prompt" style={{ minHeight: 44 }}>
          {status === 'pending' ? 'Send again' : `Send prompt for ${money(amount)}`}
        </button>
      </div>
      {status === 'otp' ? (
        <div style={{ display: 'flex', gap: 8 }}>
          <input aria-label="Code from the customer's phone" inputMode="numeric" value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} style={{ minHeight: 44 }} />
          <button type="button" disabled={busy || otp.length < 3} onClick={() => void sendOtp()} style={{ minHeight: 44 }}>Confirm code</button>
        </div>
      ) : null}
      {message ? (
        <p role={status === 'failed' ? 'alert' : 'status'} style={{ margin: 0, fontWeight: 600 }}>
          {status === 'pending' ? 'Waiting for the customer to approve on their phone… ' : ''}
          {message}
        </p>
      ) : (
        <p style={{ margin: 0, opacity: 0.8 }}>Or take the payment on the customer&apos;s phone and record it without a prompt.</p>
      )}
    </div>
  );
}
