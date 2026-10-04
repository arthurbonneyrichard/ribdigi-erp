/** Tenant business types — keep aligned with backend VALID_INDUSTRIES. */

export const INDUSTRIES = [
  'retail',
  'mart',
  'hotel',
  'fmcg',
  'pharmacy',
  'restaurant',
  'bakery',
  'wholesale',
  'distribution',
  'general_trading',
  'manufacturing',
] as const;

export type IndustryKey = (typeof INDUSTRIES)[number];

export const INDUSTRY_LABELS: Record<string, string> = {
  retail: 'Retail',
  mart: 'Mart',
  hotel: 'Hotel',
  fmcg: 'FMCG',
  pharmacy: 'Pharmacy',
  restaurant: 'Restaurant',
  bakery: 'Bakery',
  wholesale: 'Wholesale',
  distribution: 'Distribution',
  general_trading: 'General Trading',
  manufacturing: 'Manufacturing',
};

export function industryLabel(value?: string | null): string {
  const key = String(value || '')
    .trim()
    .toLowerCase();
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
