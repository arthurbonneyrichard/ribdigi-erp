/** Tenant business types — keep aligned with backend VALID_INDUSTRIES. */

export const INDUSTRIES = ['retail', 'hotel', 'restaurant'] as const;

export type IndustryKey = (typeof INDUSTRIES)[number];

/** Customer industries a new company can choose. Platform software is not in this list. */
export const PROVISION_INDUSTRIES = ['retail', 'hotel', 'restaurant'] as const;

/** Stored on older companies. Not offered when creating a company and not a sidebar item. */
export const LEGACY_INDUSTRIES = ['pharmacy'] as const;

export const INDUSTRY_LABELS: Record<string, string> = {
  retail: 'Retail',
  mart: 'Mart',
  hotel: 'Hotel',
  fmcg: 'FMCG',
  pharmacy: 'Pharmacy',
  restaurant: 'Restaurant',
  bakery: 'Bakery',
  wholesale: 'Wholesale',
  retail_wholesale: 'Retail + Wholesale',
  distribution: 'Distribution',
  general_trading: 'General Trading',
  manufacturing: 'Manufacturing',
  hospital: 'Hospital',
};

export function normalizeIndustry(value?: string | null): string | null {
  const raw = String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
  if (!raw) return null;
  const aliases: Record<string, string> = {
    hospitality: 'hotel',
    hotels: 'hotel',
    lodging: 'hotel',
    accommodation: 'hotel',
    guest_house: 'hotel',
    guesthouse: 'hotel',
    retail_mart: 'retail',
    resto: 'restaurant',
    food_service: 'restaurant',
    cafe: 'restaurant',
  };
  const mapped = aliases[raw] || raw;
  if ((INDUSTRIES as readonly string[]).includes(mapped)) return mapped;
  if ((LEGACY_INDUSTRIES as readonly string[]).includes(mapped)) return mapped;
  return null;
}

/** Inter-store / warehouse stock-transfer UI (retail POS-style). Hotel uses
 * Hotel inventory only and already omits Multi-Store — do not surface this. */
export function usesStoreStockTransfers(industry?: string | null): boolean {
  const ind = normalizeIndustry(industry);
  return Boolean(ind && ind !== 'hotel');
}

/** Wholesale desk: MOQ, qty price tiers, B2B quotes/orders. POS stays retail on combo. */
export function usesWholesaleTrade(industry?: string | null): boolean {
  const ind = normalizeIndustry(industry);
  return ind === 'wholesale' || ind === 'retail_wholesale';
}

export function industryLabel(value?: string | null): string {
  const key = normalizeIndustry(value) || String(value || '').trim().toLowerCase();
  if (!key) return 'Unknown';
  return INDUSTRY_LABELS[key] || key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function canDownloadStaffGuide(
  role?: string | null,
  permissions?: Record<string, string[]> | null
): boolean {
  const r = String(role || '');
  if (
    [
      'company_admin',
      'super_admin',
      'platform_owner',
      'platform_admin',
      'platform_support',
      'platform_finance',
    ].includes(r)
  ) {
    return true;
  }
  const perms = permissions || {};
  if (perms['*']?.includes('*')) return true;
  const sg = perms.staff_guide || [];
  return sg.includes('read') || sg.includes('download') || sg.includes('*');
}
