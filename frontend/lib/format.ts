/** Tenant regional formatting helpers (Stage 1 E13 / BR-20.2). */

export type RegionalFormats = {
  date_format?: string | null;
  number_format?: string | null;
  time_format?: string | null;
};

/** Defaults are always concrete strings (Required alone does not strip `| null`). */
type ResolvedRegionalFormats = {
  [K in keyof Required<RegionalFormats>]: NonNullable<RegionalFormats[K]>;
};

const DEFAULTS: ResolvedRegionalFormats = {
  date_format: 'DD/MM/YYYY',
  number_format: '1,234.56',
  time_format: '24h',
};

function pad2(n: number) {
  return String(n).padStart(2, '0');
}

function asDate(value: string | number | Date | null | undefined): Date | null {
  if (value == null || value === '') return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatNumber(
  value: number | string | null | undefined,
  numberFormat: string | null | undefined = DEFAULTS.number_format,
): string {
  if (value == null || value === '') return '—';
  const num = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(num)) return String(value);
  const fmt = numberFormat || DEFAULTS.number_format;
  const fixed = Math.abs(num).toFixed(2);
  const [intPart, decPart] = fixed.split('.');
  let grouped = intPart;
  if (fmt === '1.234,56') {
    grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    return `${num < 0 ? '-' : ''}${grouped},${decPart}`;
  }
  if (fmt === '1 234.56') {
    grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    return `${num < 0 ? '-' : ''}${grouped}.${decPart}`;
  }
  // default 1,234.56
  grouped = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${num < 0 ? '-' : ''}${grouped}.${decPart}`;
}

export function formatDate(
  value: string | number | Date | null | undefined,
  dateFormat: string | null | undefined = DEFAULTS.date_format,
): string {
  const d = asDate(value);
  if (!d) return '—';
  const yyyy = d.getFullYear();
  const mm = pad2(d.getMonth() + 1);
  const dd = pad2(d.getDate());
  const fmt = (dateFormat || DEFAULTS.date_format).toUpperCase();
  if (fmt === 'MM/DD/YYYY') return `${mm}/${dd}/${yyyy}`;
  if (fmt === 'YYYY-MM-DD') return `${yyyy}-${mm}-${dd}`;
  return `${dd}/${mm}/${yyyy}`;
}

export function formatDateTime(
  value: string | number | Date | null | undefined,
  dateFormat: string | null | undefined = DEFAULTS.date_format,
  timeFormat: string | null | undefined = DEFAULTS.time_format,
): string {
  const d = asDate(value);
  if (!d) return '—';
  const datePart = formatDate(d, dateFormat);
  const hours = d.getHours();
  const minutes = pad2(d.getMinutes());
  const seconds = pad2(d.getSeconds());
  if ((timeFormat || DEFAULTS.time_format).toLowerCase() === '12h') {
    const h12 = hours % 12 || 12;
    const ampm = hours >= 12 ? 'PM' : 'AM';
    return `${datePart} ${pad2(h12)}:${minutes}:${seconds} ${ampm}`;
  }
  return `${datePart} ${pad2(hours)}:${minutes}:${seconds}`;
}
