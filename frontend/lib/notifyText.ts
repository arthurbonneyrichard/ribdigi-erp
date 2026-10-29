/** Plain words for notification categories and times, shared by the Alerts dropdown and the Notifications page. */

import { normalizeIndustry } from './industries';

export const NOTIFY_CATEGORY_LABELS: Record<string, string> = {
  low_stock: 'Stock',
  new_order: 'Order',
  payment_due: 'Payment',
  purchase_received: 'Purchasing',
  credit_limit: 'Credit',
  shift_variance: 'Till',
  expense_approval: 'Expense',
  quotation_expiry: 'Quotation',
  batch_expiry: 'Expiry',
  recurring_expense_due: 'Recurring',
  transfer: 'Transfer',
  system: 'System',
  security: 'Security',
  billing: 'Billing',
  provisioning: 'Provisioning',
  platform_security: 'Platform security',
  staff_account: 'Staff account',
  admin_password_reset: 'Password reset',
  platform: 'Platform',
};

const HOTEL_NOTIFY_LABELS: Record<string, string> = {
  low_stock: 'Supplies',
  new_order: 'Sales orders',
  shift_variance: 'Shop till',
  quotation_expiry: 'Sales quotes',
};

const RESTAURANT_NOTIFY_LABELS: Record<string, string> = {
  low_stock: 'Ingredients',
  new_order: 'Restaurant orders',
  shift_variance: 'Restaurant till',
};

export function notifyCategoryLabel(id: string, industry?: string | null): string {
  const ind = normalizeIndustry(industry);
  if (ind === 'hotel' && HOTEL_NOTIFY_LABELS[id]) return HOTEL_NOTIFY_LABELS[id];
  if (ind === 'restaurant' && RESTAURANT_NOTIFY_LABELS[id]) return RESTAURANT_NOTIFY_LABELS[id];
  if (NOTIFY_CATEGORY_LABELS[id]) return NOTIFY_CATEGORY_LABELS[id];
  const text = String(id || '').split('_').join(' ');
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** "Today 17:40", "Yesterday 16:43", or "21 Oct, 09:15". API times are UTC without a zone. */
export function formatNoticeTime(value?: string): string {
  if (!value) return '';
  const d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
  if (Number.isNaN(d.getTime())) return value;
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  const today = new Date();
  const startOfDay = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const days = Math.round((startOfDay(today) - startOfDay(d)) / 86400000);
  if (days === 0) return `Today ${time}`;
  if (days === 1) return `Yesterday ${time}`;
  return `${d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}, ${time}`;
}
