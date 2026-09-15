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
