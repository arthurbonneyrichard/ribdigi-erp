import { normalizeIndustry } from './industries';

/** Keep aligned with backend `app.printers.GENERAL_PURPOSES`. */
export const GENERAL_PRINTER_PURPOSES = ['barcode', 'customer_receipt', 'invoice'] as const;

/** Extra destinations by saved tenant industry. Hotel has none — do not invent kitchen/bar. */
export const INDUSTRY_PRINTER_PURPOSES: Record<string, readonly string[]> = {
  restaurant: ['bar', 'kitchen'],
};

export const PRINTER_PURPOSE_LABELS: Record<string, string> = {
  customer_receipt: 'Receipt',
  invoice: 'Invoice',
  barcode: 'Barcode',
  kitchen: 'Kitchen',
  bar: 'Bar',
};

export function printerPurposesForIndustry(industry?: string | null): string[] {
  const ind = normalizeIndustry(industry);
  const extra = ind ? INDUSTRY_PRINTER_PURPOSES[ind] || [] : [];
  return [...GENERAL_PRINTER_PURPOSES, ...extra].sort();
}

/** Intersect API capabilities with the saved tenant industry so a stale payload cannot show kitchen. */
export function resolvePrinterPurposes(
  industry?: string | null,
  apiPurposes?: string[] | null
): string[] {
  const allowed = printerPurposesForIndustry(industry);
  const allowedSet = new Set(allowed);
  if (apiPurposes && apiPurposes.length) {
    const filtered = apiPurposes.filter((p) => allowedSet.has(p));
    return filtered.length ? filtered : allowed;
  }
  return allowed;
}

export function printerPurposeLabel(purpose: string): string {
  return PRINTER_PURPOSE_LABELS[purpose] || purpose.replace(/_/g, ' ');
}

/** Hide leftover kitchen/bar rows (and those purposes) for non-restaurant industries. */
export function printerRowVisible(purposes: string[] | null | undefined, allowedPurposes: string[]): boolean {
  const allowed = new Set(allowedPurposes);
  return (purposes || []).some((p) => allowed.has(p));
}

export function filterListedPrinterPurposes(
  purposes: string[] | null | undefined,
  allowedPurposes: string[]
): string[] {
  const allowed = new Set(allowedPurposes);
  return (purposes || []).filter((p) => allowed.has(p));
}
