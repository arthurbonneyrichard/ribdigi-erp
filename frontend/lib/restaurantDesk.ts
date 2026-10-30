/** Small shared words and helpers for the restaurant Orders, Bills and Guests screens. */

import { formatMoney } from './format';

export type Row = Record<string, any>;

export const LIVE_STATUSES = new Set(['open', 'sent', 'preparing', 'ready']);

export const STATUS_WORDS: Record<string, string> = {
  open: 'Not sent yet',
  sent: 'In the kitchen',
  preparing: 'Cooking',
  ready: 'Ready to serve',
  completed: 'Paid',
  refunded: 'Refunded',
  cancelled: 'Cancelled',
  voided: 'Voided',
};

export const MODE_WORDS: Record<string, string> = {
  dine_in: 'Dine in',
  takeaway: 'Takeaway',
  delivery: 'Delivery',
};

export const METHOD_WORDS: Record<string, string> = {
  cash: 'Cash',
  card: 'Card',
  mobile_money: 'Mobile Money',
  wallet: 'Wallet',
};

export const PREP_WORDS: Record<string, string> = {
  queued: 'Waiting',
  cooking: 'Cooking',
  preparing: 'Cooking',
  ready: 'Ready',
  done: 'Served',
};

export function money(value: unknown): string {
  return formatMoney(Number(value || 0));
}

export function problem(err: unknown): string {
  const raw = (err as { message?: string } | null)?.message || String(err || '');
  return raw || 'Something went wrong. Try again.';
}

export function parseWhen(value: unknown): Date | null {
  if (!value) return null;
  const text = String(value);
  // The API sends UTC without a zone mark.
  const date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(text) ? text : `${text}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function minutesSince(value: unknown, now = Date.now()): number {
  const date = parseWhen(value);
  return date ? Math.max(0, Math.round((now - date.getTime()) / 60000)) : 0;
}

export function waitWords(minutes: number): string {
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}

export function clock(value: unknown): string {
  const date = parseWhen(value);
  return date ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
}

export function dayAndTime(value: unknown): string {
  const date = parseWhen(value);
  if (!date) return '';
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  const yesterday = new Date(today.getTime() - 86400000).toDateString() === date.toDateString();
  const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (sameDay) return `Today ${time}`;
  if (yesterday) return `Yesterday ${time}`;
  return `${date.toLocaleDateString([], { day: 'numeric', month: 'short' })} ${time}`;
}

/** "Table 3", or the guest name, or the service. */
export function whereWords(order: Row, tables: Row[]): string {
  const table = tables.find((t) => t.id === order.table_id);
  if (table) return `Table ${table.name || table.code}`;
  if (order.customer_name) return String(order.customer_name);
  return MODE_WORDS[order.service_mode] || 'Order';
}

export function dishSummary(order: Row, max = 3): string {
  const items: Row[] = order.items || [];
  const parts = items.slice(0, max).map((i) => `${Number(i.quantity)} ${i.name}`);
  if (items.length > max) parts.push(`+${items.length - max} more`);
  return parts.join(', ') || 'No dishes yet';
}

export function initials(name: unknown): string {
  const words = String(name || '?').trim().split(/\s+/).filter(Boolean);
  return ((words[0]?.[0] || '?') + (words[1]?.[0] || '')).toUpperCase();
}
