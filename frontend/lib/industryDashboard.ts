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
  { id: 'pos', label: 'POS', href: '/pos', module: 'pos' },
  { id: 'rx_products', label: 'Rx-only products', href: '/inventory?tab=products&rx=1', module: 'inventory' },
  { id: 'prescriptions', label: 'Prescriptions', href: '/prescriptions', module: 'inventory' },
];

export const FMCG_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'fmcg_home', label: 'FMCG overview', href: '/fmcg', module: 'fmcg' },
  { id: 'fmcg_schemes', label: 'Trade schemes', href: '/fmcg?tab=schemes', module: 'fmcg' },
  { id: 'fmcg_routes', label: 'Routes', href: '/fmcg?tab=routes', module: 'fmcg' },
  { id: 'fmcg_deliveries', label: 'Deliveries', href: '/fmcg?tab=deliveries', module: 'fmcg' },
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
  { id: 'pos', label: 'POS', href: '/pos', module: 'pos' },
  { id: 'printers', label: 'Printers', href: '/printers', module: 'printers' },
];

export const RETAIL_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'pos', label: 'POS', href: '/pos', module: 'pos' },
  { id: 'inventory', label: 'Inventory', href: '/inventory', module: 'inventory' },
  { id: 'customers', label: 'Customers', href: '/customers', module: 'customers' },
];

export const WHOLESALE_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'quotes', label: 'Quotations', href: '/sales?tab=quotations', module: 'sales' },
  { id: 'orders', label: 'Sales orders', href: '/sales?tab=orders', module: 'sales' },
  { id: 'credit', label: 'B2B credit', href: '/credit', module: 'credit' },
  { id: 'customers', label: 'Customers', href: '/customers', module: 'customers' },
];

export const RETAIL_WHOLESALE_DASHBOARD_FEATURES: readonly IndustryDashboardFeature[] = [
  { id: 'pos', label: 'Retail POS', href: '/pos', module: 'pos' },
  { id: 'quotes', label: 'Wholesale quotes', href: '/sales?tab=quotations', module: 'sales' },
  { id: 'orders', label: 'Wholesale orders', href: '/sales?tab=orders', module: 'sales' },
  { id: 'credit', label: 'B2B credit', href: '/credit', module: 'credit' },
  { id: 'inventory', label: 'Shared stock', href: '/inventory', module: 'inventory' },
];

const BY_INDUSTRY: Record<string, readonly IndustryDashboardFeature[]> = {
  retail: RETAIL_DASHBOARD_FEATURES,
  pharmacy: PHARMACY_DASHBOARD_FEATURES,
  wholesale: WHOLESALE_DASHBOARD_FEATURES,
  retail_wholesale: RETAIL_WHOLESALE_DASHBOARD_FEATURES,
  fmcg: FMCG_DASHBOARD_FEATURES,
  hotel: HOTEL_DASHBOARD_FEATURES,
  hospital: HOSPITAL_DASHBOARD_FEATURES,
  restaurant: RESTAURANT_DASHBOARD_FEATURES,
};

export function industryHomePath(industry?: string | null): string {
  return normalizeIndustry(industry) === 'hotel' ? '/hotel' : '/dashboard';
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
  if (ind === 'pharmacy') return 'Pharmacy management';
  if (ind === 'wholesale') return 'Wholesale operations';
  if (ind === 'retail_wholesale') return 'Retail + wholesale';
  if (ind === 'retail') return 'Retail operations';
  if (ind === 'fmcg') return 'FMCG management';
  if (ind === 'restaurant') return 'Restaurant operations';
  if (ind === 'hotel') return 'Hotel dashboard';
  if (ind === 'hospital') return 'Hospital';
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
