'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { formatMoney } from '../lib/format';
import { getMe } from '../lib/meCache';
import { hydrateDeviceId } from '../lib/posOffline';
import { openReceiptPrintWindow } from '../lib/posReceiptPrint';
import {
  PHASE_WORDS,
  RECEIPT_EVENT,
  SLOW_AFTER_MS,
  offlineReceiptText,
  receiptPhase,
  sendToTillAgent,
  type ReceiptJob,
  type ReceiptPhase,
  type ReceiptRequest,
  type ReceiptView,
} from '../lib/receiptPrint';
import './receipt-printer.css';

type Slip = {
  key: number;
  request: ReceiptRequest;
  receipt: ReceiptView | null;
  jobs: ReceiptJob[];
  phase: ReceiptPhase;
  detail: string;
  /** For the manual print-window button; never opened by itself. */
  fallback?: { html?: string; text?: string } | null;
};

const POLL_MS = 900;
const POLL_FOR_MS = 120_000;
/** The paper takes this long to feed out; success is not announced before it has. */
const FEED_MS = 2_600;
const CLOSE_AFTER_MS = 3_500;
const REPEAT_WINDOW_MS = 5_000;

/** The shop's name, kept on this computer so an offline slip can carry it too. */
const SHOP_KEY = 'ribdigi.receipt.shop';

function savedShopName(): string {
  try {
    return window.localStorage.getItem(`${SHOP_KEY}:${window.localStorage.getItem('tenant') || ''}`) || '';
  } catch {
    return '';
  }
}

async function loadShopName(): Promise<string> {
  try {
    const me = await getMe();
    const name = String(me?.data?.company_name || '').trim();
    if (name) window.localStorage.setItem(`${SHOP_KEY}:${window.localStorage.getItem('tenant') || ''}`, name);
    return name || savedShopName();
  } catch {
    return savedShopName();
  }
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const words = (method?: string | null) =>
  method === 'mobile_money' ? 'Mobile Money' : String(method || 'cash').replace(/_/g, ' ');

export default function ReceiptPrinterHost() {
  const [slip, setSlip] = useState<Slip | null>(null);
  const [shop, setShop] = useState('');
  const run = useRef(0);
  const recent = useRef(new Map<string, number>());

  const update = useCallback((key: number, patch: Partial<Slip>) => {
    setSlip((current) => (current && current.key === key ? { ...current, ...patch } : current));
  }, []);

  const start = useCallback(
    async (request: ReceiptRequest, action: 'start' | 'retry' = 'start') => {
      const key = ++run.current;
      const alive = () => run.current === key;
      if (request.kind === 'offline' && !request.receipt.company_name) {
        request = { ...request, receipt: { ...request.receipt, company_name: savedShopName() || null } };
      }
      void loadShopName().then(setShop);
      const began = Date.now();
      const base: Slip = {
        key,
        request,
        receipt: request.kind === 'offline' ? request.receipt : null,
        jobs: [],
        phase: 'preparing',
        detail: '',
      };
      setSlip(base);

      if (request.kind === 'offline') {
        update(key, { phase: 'printing' });
        try {
          await sendToTillAgent(request.ref, offlineReceiptText(request.receipt), request.again || action === 'retry');
          await wait(Math.max(0, FEED_MS - (Date.now() - began)));
          update(key, { phase: 'printed', detail: 'Printed by the till agent on this computer' });
        } catch (err) {
          update(key, { phase: 'unavailable', detail: (err as Error).message });
        }
        return;
      }

      const id = { source_type: request.sourceType, source_id: request.sourceId };
      try {
        const terminal = await hydrateDeviceId().catch(() => null);
        const res = await api('/printers/receipts', {
          method: 'POST',
          body: JSON.stringify({
            ...id,
            mode: action === 'retry' ? 'retry' : request.mode,
            terminal_id: terminal,
            ...(request.cashTendered != null ? { cash_tendered: request.cashTendered } : {}),
          }),
        });
        if (!alive()) return;
        if (res.data?.auto_print === false) {
          setSlip(null);
          return;
        }
        let jobs: ReceiptJob[] = res.data?.jobs || [];
        let seen = receiptPhase(jobs, 0);
        const hasPaper = seen.phase === 'printing' || seen.phase === 'printed';
        update(key, {
          receipt: res.data?.receipt || null,
          jobs,
          fallback: res.data?.fallback || null,
          phase: hasPaper ? 'printing' : seen.phase,
          detail: seen.detail,
        });
        const polling = Date.now();
        while (alive() && jobs.some((j) => ['queued', 'claimed', 'printing'].includes(j.status))) {
          if (Date.now() - polling > POLL_FOR_MS) break;
          await wait(Date.now() - polling > SLOW_AFTER_MS ? 4_000 : POLL_MS);
          try {
            const query = new URLSearchParams(id).toString();
            const next = await api(`/printers/receipts?${query}`);
            jobs = next.data?.jobs || jobs;
          } catch {
            // A dropped poll is not a printer fault; the next one asks again.
          }
          seen = receiptPhase(jobs, Date.now() - polling);
          if (seen.phase !== 'printed') update(key, { jobs, phase: seen.phase, detail: seen.detail });
        }
        seen = receiptPhase(jobs, Date.now() - polling);
        if (seen.phase === 'printed') await wait(Math.max(0, FEED_MS - (Date.now() - began)));
        if (alive()) update(key, { jobs, phase: seen.phase, detail: seen.detail });
      } catch (err) {
        update(key, {
          phase: 'failed',
          detail: `${(err as Error).message || 'The print service did not answer.'} The payment is saved.`,
        });
      }
    },
    [update],
  );

  useEffect(() => {
    const onRequest = (event: Event) => {
      const request = (event as CustomEvent<ReceiptRequest>).detail;
      if (!request) return;
      if (request.kind === 'saved' && request.mode === 'auto') {
        // A repeated payment callback must not restart the job on screen.
        const id = `${request.sourceType}:${request.sourceId}`;
        const last = recent.current.get(id) || 0;
        if (Date.now() - last < REPEAT_WINDOW_MS) return;
        recent.current.set(id, Date.now());
      }
      void start(request);
    };
    window.addEventListener(RECEIPT_EVENT, onRequest);
    return () => {
      window.removeEventListener(RECEIPT_EVENT, onRequest);
      run.current += 1;
    };
  }, [start]);

  useEffect(() => {
    if (slip?.phase !== 'printed') return;
    const key = slip.key;
    const timer = setTimeout(() => setSlip((c) => (c && c.key === key ? null : c)), CLOSE_AFTER_MS);
    return () => clearTimeout(timer);
  }, [slip?.key, slip?.phase]);

  if (!slip) return null;

  const close = () => {
    run.current += 1;
    setSlip(null);
  };
  const { request, receipt, phase, jobs } = slip;
  const problem = phase === 'failed' || phase === 'unavailable';
  const busy = phase === 'preparing' || phase === 'printing';
  const windowJob = jobs.find((j) => j.status === 'browser_pending');
  const canOpenWindow = request.kind === 'offline' || Boolean(windowJob || slip.fallback);
  const money = (value: unknown) => formatMoney(Number(value || 0), null, receipt?.currency);

  async function openPrintWindow() {
    if (request.kind === 'offline') {
      if (request.browserFallback) request.browserFallback();
      else openReceiptPrintWindow(undefined, offlineReceiptText(request.receipt));
      return;
    }
    if (!windowJob) {
      const spare = slip?.fallback;
      if (spare && openReceiptPrintWindow(spare.html, spare.text || '')) close();
      return;
    }
    if (!openReceiptPrintWindow(windowJob.html || undefined, windowJob.text || '')) return;
    await api(`/printers/jobs/${windowJob.id}/browser-ack`, {
      method: 'POST',
      body: JSON.stringify({ status: 'printed' }),
    }).catch(() => undefined);
    close();
  }

  return (
    <section className={`rprint rprint-${phase}`} aria-label="Receipt printer">
      <button type="button" className="rprint-close" onClick={close} aria-label="Close receipt printer">
        ×
      </button>
      <div className="rprint-stage" aria-hidden="true">
        <div className="rprint-machine">
          <span className="rprint-slot" />
          <span className="rprint-led" />
          <span className="rprint-shop"><span>{shop || receipt?.company_name || receipt?.store_name || 'Receipt printer'}</span></span>
          {phase === 'printed' ? (
            <svg className="rprint-check" viewBox="0 0 48 48">
              <circle cx="24" cy="24" r="22" />
              <path d="M13 25l8 8 15-17" />
            </svg>
          ) : null}
        </div>
        <div className="rprint-slot-window">
          {receipt ? (
            <div className="rprint-paper" key={slip.key}>
              <strong>{receipt.company_name || 'Receipt'}</strong>
              {receipt.store_name ? <span>{receipt.store_name}</span> : null}
              {receipt.title ? <b>{receipt.title}</b> : null}
              <hr />
              <p><span>No.</span><span>{receipt.reference}</span></p>
              <p>
                <span>Date</span>
                <span>{String(receipt.created_at || '').slice(0, 16).replace('T', ' ')}</span>
              </p>
              <hr />
              {(receipt.items || []).slice(-8).map((item, index) => (
                <p key={index}><span>{item.quantity} × {item.name}</span><span>{money(item.line_total)}</span></p>
              ))}
              {(receipt.items || []).length > 8 ? <em>{(receipt.items || []).length} items in all</em> : null}
              <hr />
              {Number(receipt.discount_amount) > 0 ? (
                <p><span>Discount</span><span>-{money(receipt.discount_amount)}</span></p>
              ) : null}
              {Number(receipt.tax) > 0 ? (
                <p><span>{receipt.tax_label || 'Tax'}</span><span>{money(receipt.tax)}</span></p>
              ) : null}
              <p className="rprint-total"><span>TOTAL</span><span>{money(receipt.total)}</span></p>
              {(receipt.payments?.length
                ? receipt.payments
                : [{ payment_method: receipt.payment_method || 'cash', amount: Number(receipt.total || 0) }]
              ).map((pay, index) => (
                <p key={`pay-${index}`}><span className="rprint-cap">{words(pay.payment_method)}</span><span>{money(pay.amount)}</span></p>
              ))}
              {receipt.cash_tendered != null ? (
                <>
                  <p><span>Cash received</span><span>{money(receipt.cash_tendered)}</span></p>
                  <p className="rprint-total"><span>Change</span><span>{money(receipt.change_due)}</span></p>
                </>
              ) : null}
              {Number(receipt.balance_due) > 0 ? (
                <p><span>Balance due</span><span>{money(receipt.balance_due)}</span></p>
              ) : null}
              <span className="rprint-thanks">Thank you</span>
            </div>
          ) : null}
        </div>
      </div>
      <div className="rprint-status" role="status" aria-live="polite">
        <strong>
          {PHASE_WORDS[phase]}
          {busy ? <span className="rprint-dots"><i /><i /><i /></span> : null}
        </strong>
        {slip.detail ? <span>{slip.detail}</span> : null}
        {problem ? <span className="rprint-safe">The payment is saved. Do not charge it again.</span> : null}
      </div>
      {!busy ? (
        <div className="rprint-actions">
          {problem ? (
            <button type="button" className="rprint-primary" onClick={() => void start(request, 'retry')} aria-label="Retry printing">
              Retry printing
            </button>
          ) : null}
          {phase === 'printed' ? (
            <button
              type="button"
              onClick={() =>
                void start(
                  request.kind === 'saved' ? { ...request, mode: 'reprint' } : { ...request, again: true },
                )
              }
              aria-label="Print another copy of this receipt"
            >
              Print another copy
            </button>
          ) : null}
          {problem && canOpenWindow ? (
            <button type="button" onClick={() => void openPrintWindow()} aria-label="Open the computer print window">
              Open print window
            </button>
          ) : null}
          <button type="button" onClick={close}>Done</button>
        </div>
      ) : null}
    </section>
  );
}
