/** Tenant regional display helpers (BR-20.2). */

export type FormatPrefs = {
  date_format?: string | null;
  decimal_separator?: string | null;
  thousand_separator?: string | null;
  time_format?: string | null;
};

const DEFAULTS: Required<FormatPrefs> = {
  date_format: 'DD/MM/YYYY',
  decimal_separator: '.',
  thousand_separator: ',',
  time_format: '24h',
};

function prefsOrDefault(prefs?: FormatPrefs | null): Required<FormatPrefs> {
  return {
    date_format: prefs?.date_format || DEFAULTS.date_format,
    decimal_separator: prefs?.decimal_separator || DEFAULTS.decimal_separator,
    thousand_separator:
      prefs?.thousand_separator !== undefined && prefs?.thousand_separator !== null
        ? prefs.thousand_separator
        : DEFAULTS.thousand_separator,
    time_format: prefs?.time_format || DEFAULTS.time_format,
  };
}

/** Format a number with tenant decimal/thousand separators. */
export function formatNumber(
  value: number | string | null | undefined,
  prefs?: FormatPrefs | null,
  fractionDigits = 2
): string {
  if (value === null || value === undefined || value === '') return '';
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  const p = prefsOrDefault(prefs);
  const fixed = Math.abs(n).toFixed(fractionDigits);
  const [intPart, fracPart = ''] = fixed.split('.');
  const groups: string[] = [];
  for (let i = intPart.length; i > 0; i -= 3) {
    groups.unshift(intPart.slice(Math.max(0, i - 3), i));
  }
  const joined =
    p.thousand_separator === '' || p.thousand_separator == null
      ? groups.join('')
      : groups.join(p.thousand_separator);
  const sign = n < 0 ? '-' : '';
  if (fractionDigits <= 0) return `${sign}${joined}`;
  return `${sign}${joined}${p.decimal_separator}${fracPart}`;
}

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

/** Format a date (date-only or ISO) with tenant date_format. */
export function formatDate(
  value: string | Date | null | undefined,
  prefs?: FormatPrefs | null
): string {
  if (value === null || value === undefined || value === '') return '';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const p = prefsOrDefault(prefs);
  const day = pad2(d.getDate());
  const month = pad2(d.getMonth() + 1);
  const year = String(d.getFullYear());
  switch (p.date_format) {
    case 'MM/DD/YYYY':
      return `${month}/${day}/${year}`;
    case 'YYYY-MM-DD':
      return `${year}-${month}-${day}`;
    case 'DD/MM/YYYY':
    default:
      return `${day}/${month}/${year}`;
  }
}

/** Format time using tenant 12h/24h preference. */
export function formatTime(
  value: string | Date | null | undefined,
  prefs?: FormatPrefs | null
): string {
  if (value === null || value === undefined || value === '') return '';
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  const p = prefsOrDefault(prefs);
  const hours = d.getHours();
  const minutes = pad2(d.getMinutes());
  if (p.time_format === '12h') {
    const h12 = hours % 12 || 12;
    const ampm = hours < 12 ? 'AM' : 'PM';
    return `${h12}:${minutes} ${ampm}`;
  }
  return `${pad2(hours)}:${minutes}`;
}

export function formatDateTime(
  value: string | Date | null | undefined,
  prefs?: FormatPrefs | null
): string {
  const date = formatDate(value, prefs);
  const time = formatTime(value, prefs);
  if (!date) return time;
  if (!time) return date;
  return `${date} ${time}`;
}

let rememberedPrefs: FormatPrefs | null = null;

/** Pages remember company date settings so shared formatters stay consistent. */
export function rememberFormatPrefs(prefs?: FormatPrefs | null) {
  if (prefs) rememberedPrefs = prefs;
}

function activePrefs(prefs?: FormatPrefs | null): FormatPrefs | null | undefined {
  return prefs || rememberedPrefs;
}

/** Date-only values stay dates. Values with a clock include the time. */
export function formatWhen(
  value?: string | Date | null,
  prefs?: FormatPrefs | null
): string {
  if (value == null || value === '') return '';
  const raw = value instanceof Date ? value.toISOString() : String(value).trim();
  if (!raw) return '';
  const use = activePrefs(prefs);
  const hasClock = raw.includes('T') || /\d{1,2}:\d{2}/.test(raw);
  return hasClock ? formatDateTime(raw, use) : formatDate(raw, use);
}

/** How long a cashier has been offline, in plain minutes and hours. */
export function formatElapsed(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return '';
  const total = Math.floor(seconds);
  if (total < 60) return 'under a minute';
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return minutes === 1 ? '1 minute' : `${minutes} minutes`;
  const hours = Math.floor(minutes / 60);
  const rem = minutes % 60;
  if (hours < 48) {
    const hourLabel = hours === 1 ? '1 hour' : `${hours} hours`;
    return rem ? `${hourLabel} ${rem} minutes` : hourLabel;
  }
  const days = Math.floor(hours / 24);
  return days === 1 ? '1 day' : `${days} days`;
}

const PLAIN_LABELS: Record<string, string> = {
  trialing: 'Trial',
  trial: 'Trial',
  active: 'Active',
  inactive: 'Inactive',
  grace: 'Grace period',
  grace_period: 'Grace period',
  suspended: 'Suspended',
  payment_required: 'Payment needed',
  past_due: 'Payment overdue',
  draft: 'Draft',
  pending: 'Pending',
  paid: 'Paid',
  unpaid: 'Unpaid',
  partial: 'Partly paid',
  overdue: 'Overdue',
  cancelled: 'Cancelled',
  canceled: 'Cancelled',
  in_progress: 'In progress',
  reconciled: 'Reconciled',
  delivered: 'Delivered',
  failed: 'Failed',
  pending_retry: 'Waiting to retry',
  revoked: 'Revoked',
  expired: 'Expired',
  daily: 'Daily',
  weekly: 'Weekly',
  monthly: 'Monthly',
  yearly: 'Yearly',
  yes: 'Yes',
  no: 'No',
};

/** Turn stored codes such as past_due into words a company user can read. */
export function plainLabel(value?: string | number | null): string {
  const key = String(value ?? '').trim().toLowerCase();
  if (!key) return '';
  if (PLAIN_LABELS[key]) return PLAIN_LABELS[key];
  return key
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
