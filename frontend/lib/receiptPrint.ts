/**
 * One receipt printing service for every till and desk.
 *
 * After a payment is saved, a screen calls `printPaymentReceipt`. The server builds the receipt
 * from the saved payment and sends it to the till's thermal printer; the shared overlay
 * (components/ReceiptPrinter.tsx) shows the real job status. No browser print dialog is opened.
 */

export type ReceiptSource =
  | 'pos_sale'
  | 'restaurant_order'
  | 'bakery_sale'
  | 'bakery_order_payment'
  | 'bakery_customer_payment'
  | 'hotel_payment'
  | 'hotel_shop_sale'
  | 'gym_payment'
  | 'gym_sale'
  | 'fmcg_payment'
  | 'customer_payment'
  | 'layaway_payment';

/** What the on-screen paper shows. */
export type ReceiptView = {
  title?: string | null;
  reference?: string | null;
  company_name?: string | null;
  store_name?: string | null;
  created_at?: string | null;
  currency?: string | null;
  items?: Array<{ name: string; quantity: number; line_total: number }>;
  subtotal?: number | null;
  tax?: number | null;
  tax_label?: string | null;
  discount_amount?: number | null;
  total?: number | null;
  tip?: number | null;
  payment_method?: string | null;
  payments?: Array<{ payment_method: string; amount: number }>;
  cash_tendered?: number | null;
  change_due?: number | null;
  balance_due?: number | null;
};

export type ReceiptJob = {
  id: string;
  status: string;
  printer_name?: string | null;
  connection_type?: string | null;
  agent_online?: boolean | null;
  last_error?: string | null;
  html?: string | null;
  text?: string | null;
};

export type SavedReceiptRequest = {
  kind: 'saved';
  sourceType: ReceiptSource;
  sourceId: string;
  mode: 'auto' | 'print' | 'reprint';
  cashTendered?: number | null;
};

/** A sale taken with no connection: the till agent on this computer prints it. */
export type OfflineReceiptRequest = {
  kind: 'offline';
  ref: string;
  receipt: ReceiptView;
  again?: boolean;
  /** Offered as a button only when the till agent cannot print; never run by itself. */
  browserFallback?: () => void;
};

export type ReceiptRequest = SavedReceiptRequest | OfflineReceiptRequest;

export const RECEIPT_EVENT = 'ribdigi:receipt-print';
export const TILL_AGENT_PRINT_URL = 'http://127.0.0.1:8765/v1/print';

export function requestReceiptPrint(request: ReceiptRequest): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent<ReceiptRequest>(RECEIPT_EVENT, { detail: request }));
}

/** Print the receipt of a payment the server has just confirmed. */
export function printPaymentReceipt(
  sourceType: ReceiptSource,
  sourceId: string | null | undefined,
  options: { mode?: SavedReceiptRequest['mode']; cashTendered?: number | null } = {},
): void {
  const id = String(sourceId || '').trim();
  if (!id) return;
  requestReceiptPrint({
    kind: 'saved',
    sourceType,
    sourceId: id,
    mode: options.mode || 'auto',
    cashTendered: options.cashTendered ?? null,
  });
}

export type ReceiptPhase = 'preparing' | 'printing' | 'printed' | 'unavailable' | 'failed';

export const PHASE_WORDS: Record<ReceiptPhase, string> = {
  preparing: 'Preparing receipt',
  printing: 'Printing receipt',
  printed: 'Receipt printed successfully',
  unavailable: 'Printer unavailable',
  failed: 'Printing failed',
};

/** An agent that is switched off is reported after this long. */
export const OFFLINE_AFTER_MS = 4_000;
/** A printer that is still working after this long is reported as unavailable. */
export const SLOW_AFTER_MS = 25_000;

/** Turn real job statuses into what the cashier is told. Success needs every printer to say printed. */
export function receiptPhase(jobs: ReceiptJob[], waitedMs: number): { phase: ReceiptPhase; detail: string } {
  const direct = jobs.filter((j) => j.status !== 'browser_pending');
  if (!direct.length) {
    return {
      phase: 'unavailable',
      detail: jobs.length
        ? 'This printer is set to the computer’s print window, so it cannot print by itself. Connect it to the till agent in Printers.'
        : 'No receipt printer is set up for this till. Add one in Printers.',
    };
  }
  const failed = direct.find((j) => j.status === 'failed' || j.status === 'cancelled');
  const waiting = direct.filter((j) => ['queued', 'claimed', 'printing'].includes(j.status));
  if (!waiting.length) {
    if (failed) {
      return {
        phase: 'failed',
        detail: `${failed.printer_name || 'Printer'}: ${failed.last_error || 'could not print'}`,
      };
    }
    const names = direct.map((j) => j.printer_name).filter(Boolean).join(', ');
    return { phase: 'printed', detail: names ? `Sent to ${names}` : 'Sent to the printer' };
  }
  const asleep = waiting.find((j) => j.status === 'queued' && j.agent_online === false);
  if (asleep && waitedMs >= OFFLINE_AFTER_MS) {
    return {
      phase: 'unavailable',
      detail: `The till agent for ${asleep.printer_name || 'this printer'} is not running. The receipt is kept and prints when it is back.`,
    };
  }
  if (waitedMs >= SLOW_AFTER_MS) {
    return { phase: 'unavailable', detail: 'The printer has not answered yet. Check that it is on and has paper.' };
  }
  return { phase: 'printing', detail: waiting[0].printer_name || '' };
}

const WIDTH = 42;

function row(left: string, right: string, width = WIDTH): string {
  const room = Math.max(1, width - right.length - 1);
  return `${left.slice(0, room).padEnd(room)} ${right}`;
}

const amount = (value: unknown) => Number(value || 0).toFixed(2);

function middle(text: string, width = WIDTH): string {
  const cut = text.slice(0, width);
  return ' '.repeat(Math.floor((width - cut.length) / 2)) + cut;
}

/** Plain slip for a sale taken offline. Clearly not the final receipt. 32 columns fit 58 mm and 80 mm rolls. */
export function offlineReceiptText(receipt: ReceiptView, width = 32): string {
  const line = '-'.repeat(width);
  const out = [
    middle(receipt.company_name || receipt.store_name || 'RIBDIGI ERP', width),
    line,
    middle('OFFLINE SALE', width),
    middle('Pending synchronization.', width),
    middle('Not the final receipt.', width),
    row('Receipt no.', String(receipt.reference || ''), width),
    row('Date', String(receipt.created_at || '').slice(0, 16).replace('T', ' '), width),
    line,
  ];
  for (const item of receipt.items || []) {
    out.push(row(`${item.quantity} ${item.name}`, amount(item.line_total), width));
  }
  out.push(line, row(`TOTAL ${receipt.currency || ''}`.trim(), amount(receipt.total), width));
  for (const pay of receipt.payments || []) {
    out.push(row(pay.payment_method.replace(/_/g, ' ').toUpperCase(), amount(pay.amount), width));
  }
  if (receipt.cash_tendered != null) {
    out.push(row('Cash received', amount(receipt.cash_tendered), width));
    out.push(row('Change', amount(receipt.change_due), width));
  }
  out.push(line, middle('Powered by RIBDIGI ERP', width));
  return out.join('\n');
}

/** Ask the till agent on this computer to print. Throws with words for the cashier. */
export async function sendToTillAgent(ref: string, text: string, again = false): Promise<void> {
  let response: Response;
  try {
    response = await fetch(TILL_AGENT_PRINT_URL, {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref, text, again }),
      signal: AbortSignal.timeout(20_000),
    });
  } catch {
    throw new Error('The till agent on this computer is not running.');
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(body.error || 'The till agent could not print.');
  }
}
