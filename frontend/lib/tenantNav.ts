import { industryAllowsModule, INDUSTRY_SPECIFIC_MODULES } from './industryModules';
import { normalizeIndustry } from './industries';

export type NavItem = [label: string, href: string, module: string];
export type NavGroup = { id: string; label: string; items: NavItem[] };

/** Hotel tenants use one flat Hotel Management list. Shared ERP pages are
 * reached only through Hotel-labeled items (no duplicate Reports/Settings). */
export const HOTEL_OMIT_NAV_GROUP_IDS = new Set([
  'dashboard',
  'company',
  'inventory',
  'sales',
  'purchases',
  'finance',
  'stores',
  'reports',
  'people',
  'notifications',
  'settings',
  'industry',
]);

export const HOTEL_INVENTORY_PARENT_HREF = '/hotel?tab=supplies';

/** Shared ERP inventory/purchasing destinations, hotel-labeled. No second stock ledger. */
export const HOTEL_INVENTORY_PROCUREMENT_CHILDREN: NavItem[] = [
  ['Products and stock', '/inventory?tab=products', 'inventory'],
  ['Low stock', '/inventory?tab=lowstock', 'inventory'],
  ['Stock adjustments', '/inventory?tab=adjust', 'inventory'],
  ['Purchase orders', '/purchasing?tab=orders', 'purchasing'],
  ['Goods received', '/purchasing?tab=grn', 'purchasing'],
  ['Suppliers', '/purchasing?tab=suppliers', 'purchasing'],
  ['Purchase history', '/purchasing?tab=history', 'purchasing'],
];

export const HOTEL_NAV_ITEMS: NavItem[] = [
  ['Hotel Dashboard', '/hotel', 'hotel'],
  ['Reservations and Booking', '/hotel?tab=reservations', 'hotel'],
  ['Front Desk', '/hotel?tab=front-desk', 'hotel'],
  ['Rooms and Rates', '/hotel?tab=rooms', 'hotel'],
  ['Housekeeping', '/hotel?tab=housekeeping', 'hotel'],
  ['Maintenance', '/hotel?tab=maintenance', 'hotel'],
  ['Guests and CRM', '/hotel?tab=guests', 'hotel'],
  ['Hotel Services', '/hotel?tab=services', 'hotel'],
  ['Restaurant and POS', '/pos', 'pos'],
  ['Billing and Guest Folios', '/hotel?tab=billing', 'hotel'],
  ['Hotel Finance and Cashiering', '/hotel?tab=cashier', 'hotel'],
  ['Inventory and Procurement', HOTEL_INVENTORY_PARENT_HREF, 'inventory'],
  ['Staff and Permissions', '/users', 'users'],
  ['Hotel Reports', '/hotel?tab=reports', 'hotel'],
  ['Events and Banquets', '/hotel?tab=events', 'hotel'],
  ['Notifications', '/notifications', 'notifications'],
  ['Hotel Profile and Settings', '/hotel?tab=settings', 'hotel'],
  ['Company profile', '/company', 'company'],
  ['Integrations', '/integrations', 'company'],
];

export const FMCG_NAV_ITEMS: NavItem[] = [
  ['FMCG overview', '/fmcg', 'fmcg'],
  ['Trade schemes', '/fmcg?tab=schemes', 'fmcg'],
  ['Routes', '/fmcg?tab=routes', 'fmcg'],
  ['Deliveries', '/fmcg?tab=deliveries', 'fmcg'],
];

export function isHotelIndustry(industry: string | null | undefined): boolean {
  return normalizeIndustry(industry) === 'hotel';
}

export function hotelNavLabels(items: NavItem[] = HOTEL_NAV_ITEMS): string[] {
  return items.map(([label]) => label);
}

export function groupedTenantNav(groups: NavGroup[], visible: NavItem[], industry: string | null): NavGroup[] {
  const allowed = new Set(visible.map(([, href]) => href));
  const ind = normalizeIndustry(industry);
  const mapped = groups
    .map((group) => {
      if (ind === 'hotel' && HOTEL_OMIT_NAV_GROUP_IDS.has(group.id)) {
        return { ...group, items: [] as NavItem[] };
      }
      if (group.id === 'inventory') {
        return {
          ...group,
          label: 'Inventory',
          items: group.items.filter(([, href]) => allowed.has(href)),
        };
      }
      if (group.id === 'industry') {
        if (ind === 'fmcg') {
          return {
            id: 'industry',
            label: 'FMCG management',
            items: FMCG_NAV_ITEMS.filter(([, href]) => allowed.has(href)),
          };
        }
        return { ...group, items: [] };
      }
      return {
        ...group,
        items: group.items.filter(([, href]) => allowed.has(href)),
      };
    })
    .filter((group) => group.items.length > 0);

  if (ind !== 'hotel') return mapped;

  const hotelItems = HOTEL_NAV_ITEMS.filter(([, href, module]) => {
    if (module === 'hotel' && !industryAllowsModule(ind, 'hotel')) return false;
    return allowed.has(href);
  });
  if (!hotelItems.length) return mapped;

  const invChildren = HOTEL_INVENTORY_PROCUREMENT_CHILDREN.filter(([, href]) => allowed.has(href));
  const showInvParent = hotelItems.some(([, href]) => href === HOTEL_INVENTORY_PARENT_HREF);
  const splitAt = HOTEL_NAV_ITEMS.findIndex(([, href]) => href === HOTEL_INVENTORY_PARENT_HREF);
  const beforeHrefs = new Set(HOTEL_NAV_ITEMS.slice(0, Math.max(0, splitAt)).map(([, href]) => href));
  const hotelFlat = hotelItems.filter(([, href]) => href !== HOTEL_INVENTORY_PARENT_HREF);
  const before = hotelFlat.filter(([, href]) => beforeHrefs.has(href));
  const after = hotelFlat.filter(([, href]) => !beforeHrefs.has(href));

  const hotelGroups: NavGroup[] = [];
  if (before.length) hotelGroups.push({ id: 'hotel', label: '', items: before });
  if (showInvParent && invChildren.length) {
    hotelGroups.push({
      id: 'hotel-inventory',
      label: 'Inventory and Procurement',
      items: invChildren,
    });
  } else if (showInvParent) {
    hotelGroups.push({
      id: 'hotel-inventory',
      label: '',
      items: hotelItems.filter(([, href]) => href === HOTEL_INVENTORY_PARENT_HREF),
    });
  }
  if (after.length) hotelGroups.push({ id: 'hotel-rest', label: '', items: after });
  if (!hotelGroups.length) return mapped;

  // Hotel-only: flat ops items, plus an accordion for shared inventory/purchasing.
  return [...hotelGroups, ...mapped];
}

export function industrySpecificHrefAllowed(
  href: string,
  industry: string | null,
  enabledModules: string[] | null
): boolean {
  const path = href.split('?')[0];
  const packageSet =
    enabledModules && enabledModules.length > 0
      ? new Set(enabledModules.map((m) => m.toLowerCase()))
      : null;
  for (const mod of INDUSTRY_SPECIFIC_MODULES) {
    if (path === `/${mod}` || path.startsWith(`/${mod}/`)) {
      if (!industryAllowsModule(industry, mod)) return false;
      if (!packageSet || !packageSet.has(mod)) return false;
    }
  }
  return true;
}
