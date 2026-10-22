import { normalizeIndustry } from './industries';

export type IndustryDashboardFeature = {
  id: string;
  label: string;
  href: string;
  module: string;
};

/** Keep aligned with backend ``app.industry_dashboard``. Existing routes only. */
export const PHARMACY_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'expiry_lots', label: 'Expiring lots', href: '/inventory?tab=expiry', module: 'inventory' },
  { id: 'batches', label: 'Batches', href: '/inventory?tab=batches', module: 'inventory' },
  { id: 'rx_products', label: 'Rx-only products', href: '/inventory?tab=products&rx=1', module: 'inventory' },
  { id: 'prescriptions', label: 'Prescriptions', href: '/prescriptions', module: 'inventory' },
];

export const FMCG_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'fmcg_home', label: 'FMCG overview', href: '/fmcg', module: 'fmcg' },
  { id: 'fmcg_schemes', label: 'Trade schemes', href: '/fmcg?tab=schemes', module: 'fmcg' },
  { id: 'fmcg_routes', label: 'Routes', href: '/fmcg?tab=routes', module: 'fmcg' },
  { id: 'fmcg_deliveries', label: 'Deliveries', href: '/fmcg?tab=deliveries', module: 'fmcg' },
  { id: 'fmcg_packs', label: 'Pack convert', href: '/fmcg?tab=packs', module: 'fmcg' },
];

export const HOSPITAL_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'hospital_home', label: 'Patients and visits', href: '/hospital', module: 'hospital' },
];

export const HOTEL_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'hotel_home', label: 'Hotel dashboard', href: '/hotel', module: 'hotel' },
  { id: 'hotel_reservations', label: 'Reservations', href: '/hotel?tab=reservations', module: 'hotel' },
  { id: 'hotel_front_desk', label: 'Front desk', href: '/hotel?tab=front-desk', module: 'hotel' },
];

export const RESTAURANT_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'restaurant_home', label: 'Restaurant dashboard', href: '/restaurant', module: 'restaurant' },
  { id: 'restaurant_orders', label: 'Orders', href: '/restaurant?tab=orders', module: 'restaurant' },
  { id: 'restaurant_kitchen', label: 'Kitchen', href: '/restaurant?tab=kitchen', module: 'restaurant' },
  { id: 'printers', label: 'Printers', href: '/printers', module: 'printers' },
];

export const RETAIL_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [];

export const WHOLESALE_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'quotes', label: 'Quotations', href: '/sales?tab=quotations', module: 'sales' },
  { id: 'orders', label: 'Sales orders', href: '/sales?tab=orders', module: 'sales' },
  { id: 'credit', label: 'B2B credit', href: '/credit', module: 'credit' },
];

export const RETAIL_WHOLESALE_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'quotes', label: 'Wholesale quotes', href: '/sales?tab=quotations', module: 'sales' },
  { id: 'orders', label: 'Wholesale orders', href: '/sales?tab=orders', module: 'sales' },
  { id: 'credit', label: 'B2B credit', href: '/credit', module: 'credit' },
];

const BY_INDUSTRY: Record<string, readonly IndustryDashboardFeature[]> = {
  retail: RETAIL_DASHBOARD_FEATURES,
  hotel: HOTEL_DASHBOARD_FEATURES,
  restaurant: RESTAURANT_DASHBOARD_FEATURES,
  pharmacy: PHARMACY_DASHBOARD_FEATURES,
};

const PLATFORM_DASHBOARD_ROLES = new Set([
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
]);

/** Ribdigi House workspace. Not a pharmacy, retail, or other operating desk. */
export function isSoftwareOwnerIndustry(industry?: string | null): boolean {
  const raw = String(industry || '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
  return raw === 'software';
}

/**
 * Platform console for software-owner staff.
 * Empty role does not redirect (the account check owns that). A known non-platform role stays off
 * `/platform` so the console does not bounce them back onto this page.
 */
export function softwareOwnerDashboardPath(
  role?: string | null,
  industry?: string | null,
): '/platform' | null {
  const normalizedRole = String(role || '').trim().toLowerCase();
  if (!PLATFORM_DASHBOARD_ROLES.has(normalizedRole)) return null;
  if (isSoftwareOwnerIndustry(industry) || normalizedRole) return '/platform';
  return null;
}

/** Industries with a dedicated operations dashboard. Pharmacy is legacy (no sidebar item). */
export const CONFIGURED_DASHBOARD_INDUSTRIES = ['retail', 'hotel', 'restaurant', 'pharmacy'] as const;

export function dashboardLayout(industry?: string | null): string {
  if (isSoftwareOwnerIndustry(industry)) return 'platform';
  const ind = normalizeIndustry(industry);
  if (!ind || !(CONFIGURED_DASHBOARD_INDUSTRIES as readonly string[]).includes(ind)) {
    return 'unconfigured';
  }
  return ind;
}

/** Retail KPI grid is only the retail desk. */
export function showsRetailOperations(layoutOrIndustry?: string | null): boolean {
  const raw = String(layoutOrIndustry || '').trim().toLowerCase();
  if (raw === 'platform' || isSoftwareOwnerIndustry(raw)) return false;
  if (raw === 'retail') return true;
  return dashboardLayout(layoutOrIndustry) === 'retail';
}

export function industryHomePath(industry?: string | null): string {
  if (isSoftwareOwnerIndustry(industry)) return '/platform';
  const ind = normalizeIndustry(industry);
  if (ind === 'hotel') return '/hotel';
  if (ind === 'restaurant') return '/restaurant';
  return '/dashboard';
}

export function industryDashboardFeatures(
  industry?: string | null
): IndustryDashboardFeature[] {
  const ind = normalizeIndustry(industry);
  if (!ind) return [];
  return (BY_INDUSTRY[ind] || []).map((row) => ({ ...row }));
}

export function industryDashboardSectionLabel(industry?: string | null): string | null {
  const ind = normalizeIndustry(industry);
  if (ind === 'retail') return null;
  if (ind === 'pharmacy') return 'Lots and prescriptions';
  if (ind === 'restaurant') return 'Restaurant operations';
  if (ind === 'hotel') return 'Hotel dashboard';
  return null;
}

/** Drop other industries' verticals. Mart/retail have no extra tiles. */
export function filterIndustryDashboardFeatures(
  features: IndustryDashboardFeature[] | null | undefined,
  industry?: string | null
): IndustryDashboardFeature[] {
  const ind = normalizeIndustry(industry);
  const rows = Array.isArray(features) ? features : [];
  const allowed = new Set(industryDashboardFeatures(ind).map((f) => `${f.id}|${f.href}`));
  return rows.filter((feat) => allowed.has(`${feat.id}|${feat.href}`));
}
