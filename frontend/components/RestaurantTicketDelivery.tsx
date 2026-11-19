'use client';

/**
 * Admin choice of how the kitchen and bar get an order: on the kitchen screen, on a printer,
 * or both. Applies to the whole company. Printer only hides the kitchen board.
 */

import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import '../app/(dashboard)/restaurant/restaurant-desk.css';

type Mode = 'both' | 'screen' | 'printer';

const CHOICES: { value: Mode; label: string; help: string }[] = [
  { value: 'both', label: 'Screen and printer', help: 'Orders show on the kitchen screen and print on the kitchen or bar printer.' },
  { value: 'screen', label: 'Screen only', help: 'Orders show on the kitchen screen. Nothing prints.' },
  { value: 'printer', label: 'Printer only', help: 'Orders print on the kitchen or bar printer. The kitchen screen is hidden.' },
];

export default function RestaurantTicketDelivery() {
  const [mode, setMode] = useState<Mode>('both');
  const [printers, setPrinters] = useState(0);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api('/restaurant/ticket-delivery')
      .then((res) => {
        setMode((res?.data?.mode || 'both') as Mode);
        setPrinters(Number(res?.data?.printers || 0));
      })
      .catch((err) => setError(err?.message || 'Could not load kitchen and bar delivery'));
  }, []);

  async function choose(next: Mode) {
    setBusy(true);
    setError('');
    setSaved('');
    try {
      const res = await api('/restaurant/ticket-delivery', { method: 'PUT', body: JSON.stringify({ mode: next }) });
      setMode((res?.data?.mode || next) as Mode);
      setPrinters(Number(res?.data?.printers || 0));
      setSaved('Saved. It applies from the next order.');
    } catch (err: any) {
      setError(err?.message || 'Could not save');
    } finally {
      setBusy(false);
    }
  }

  const current = CHOICES.find((c) => c.value === mode);

  return (
    <details className="rd-panel rd-domain">
      <summary>
        <strong>Kitchen and bar orders</strong>
        <span>{current?.label}</span>
      </summary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, textAlign: 'left', alignItems: 'stretch' }}>
        <p className="rd-hint-line">
          Choose how the kitchen and bar receive each order. Printing needs a Kitchen or Bar printer under Printers
          ({printers ? `${printers} added` : 'none added yet'}).
        </p>
        {CHOICES.map((c) => (
          <label
            key={c.value}
            style={{ display: 'flex', gap: 10, alignItems: 'flex-start', justifyContent: 'flex-start', textAlign: 'left', width: '100%', margin: 0 }}
          >
            <input
              type="radio"
              name="restaurant-ticket-delivery"
              style={{ marginTop: 4, flex: '0 0 auto' }}
              aria-label={`Kitchen and bar orders: ${c.label}`}
              checked={mode === c.value}
              disabled={busy}
              onChange={() => void choose(c.value)}
            />
            <span>
              <strong>{c.label}</strong>
              <br />
              <small>{c.help}</small>
            </span>
          </label>
        ))}
        {saved ? <p className="rd-hint-line" role="status">{saved}</p> : null}
        {error ? <p className="error" role="alert">{error}</p> : null}
      </div>
    </details>
  );
}
