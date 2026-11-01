'use client';

/**
 * Lets a kitchen or bar screen print its own tickets on a printer connected to that tablet or PC
 * (browser printers). Network and till-agent printers print by themselves and never reach this.
 * The choice is kept on this device only.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../lib/api';
import { openReceiptPrintWindow } from '../../../lib/posReceiptPrint';

type Station = '' | 'kitchen' | 'bar';
type Ticket = { id: string; station: string; reference?: string; text: string };

const KEY = 'ribdigi.restaurant.printStation';

function readStation(): Station {
  try {
    const v = window.localStorage.getItem(KEY);
    return v === 'kitchen' || v === 'bar' ? v : '';
  } catch {
    return '';
  }
}

export default function KitchenPrintTool() {
  const [station, setStation] = useState<Station>('');
  const [waiting, setWaiting] = useState<Ticket[]>([]);
  const [note, setNote] = useState('');
  const busy = useRef(false);

  useEffect(() => setStation(readStation()), []);

  function choose(next: Station) {
    setStation(next);
    setWaiting([]);
    setNote('');
    try {
      if (next) window.localStorage.setItem(KEY, next);
      else window.localStorage.removeItem(KEY);
    } catch {
      // Private window: the choice lasts until the page closes.
    }
  }

  const printAll = useCallback(async (tickets: Ticket[]) => {
    if (!tickets.length || busy.current) return;
    busy.current = true;
    try {
      const text = tickets.map((t) => t.text).join('\n\n\n');
      if (!openReceiptPrintWindow(undefined, text)) {
        setNote('The print dialog could not open. Use Print waiting tickets.');
        return;
      }
      await Promise.all(
        tickets.map((t) => api(`/restaurant/print-queue/${t.id}/printed`, { method: 'POST', body: JSON.stringify({ status: 'printed' }) })),
      );
      setWaiting([]);
      setNote(`${tickets.length} ${tickets.length === 1 ? 'ticket' : 'tickets'} sent to the printer.`);
    } catch (err) {
      setNote(err instanceof Error ? err.message : 'Printing failed. The orders are still on the screen.');
    } finally {
      busy.current = false;
    }
  }, []);

  useEffect(() => {
    if (!station) return undefined;
    let stopped = false;
    async function check() {
      if (document.hidden || busy.current) return;
      try {
        const res = await api(`/restaurant/print-queue?station=${station}`);
        const tickets: Ticket[] = res?.data || [];
        if (stopped) return;
        setWaiting(tickets);
        if (tickets.length) await printAll(tickets);
      } catch {
        // The kitchen screen keeps working; the next check tries again.
      }
    }
    void check();
    const id = window.setInterval(() => void check(), 10000);
    return () => {
      stopped = true;
      window.clearInterval(id);
    };
  }, [station, printAll]);

  return (
    <div className="rd-tool" aria-label="Ticket printing on this screen">
      <span>
        <strong>Print tickets here</strong>
        <small>
          {station
            ? `This screen prints ${station} tickets on its printer. ${note || 'Waiting for orders.'}`
            : 'For a printer plugged into this tablet or PC. Network printers print by themselves.'}
        </small>
      </span>
      <select aria-label="Tickets this screen prints" value={station} onChange={(e) => choose(e.target.value as Station)}>
        <option value="">Off</option>
        <option value="kitchen">Kitchen tickets</option>
        <option value="bar">Bar tickets</option>
      </select>
      {station && waiting.length ? (
        <button type="button" className="rd-primary" aria-label="Print waiting tickets" onClick={() => void printAll(waiting)}>
          Print waiting tickets ({waiting.length})
        </button>
      ) : null}
    </div>
  );
}
