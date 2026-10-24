/** Sidebar destinations → GET paths to warm before the desk mounts. */

export function hrefPath(href: string): string {
  return String(href || '').split('?')[0] || '';
}

const DESTINATION_GETS: Record<string, string[]> = {
  '/dashboard': ['/dashboard'],
  '/sales': [
    '/sales/made',
    '/sales/invoices',
    '/customers',
    '/products',
    '/catalog/units',
    '/sales/quotations',
    '/sales/orders',
    '/sales/returns',
    '/stores',
    '/sales/settings',
    '/customers/groups',
    '/tenants/me',
    '/sales/coupons',
  ],
  '/customers': ['/customers', '/customers/groups'],
  '/purchasing': [
    '/purchasing/orders',
    '/purchasing/requests',
    '/purchasing/requests/settings',
    '/suppliers',
    '/products',
    '/catalog/units',
    '/warehouses',
    '/purchasing/grn',
    '/purchasing/invoices',
    '/purchasing/returns',
  ],
  '/inventory': ['/products?limit=80', '/catalog/categories', '/catalog/brands', '/catalog/units', '/warehouses'],
  '/pos': ['/pos/sessions/current', '/pos/stores'],
  '/expenses': ['/expenses', '/expenses/categories', '/expenses/settings', '/expenses/recurring', '/stores', '/incomes'],
  '/credit': [
    '/credit/aging?kind=receivable',
    '/credit/aging?kind=payable',
    '/customers',
    '/suppliers',
    '/credit/settings',
    '/accounting/liquid-accounts',
    '/credit/exchange-rates',
  ],
  '/accounting': [
    '/accounting/accounts',
    '/accounting/journal-entries',
    '/accounting/trial-balance',
    '/accounting/profit-loss',
    '/accounting/liquid-accounts',
    '/accounting/bank-statements',
    '/accounting/bank-connections',
    '/accounting/transfers',
    '/accounting/opening-balances',
    '/stores',
    '/branches',
    '/accounting/period',
    '/credit/aging?kind=receivable',
    '/credit/aging?kind=payable',
  ],
  '/reports': ['/stores', '/branches', '/warehouses', '/catalog/categories', '/departments', '/accounting/accounts'],
  '/stores': ['/stores', '/warehouses', '/branches', '/departments', '/stores/entitlement'],
  '/users': ['/users', '/roles?include_inactive=true', '/branches', '/departments', '/stores'],
  '/company': ['/tenants/me', '/settings/email', '/settings/sms', '/settings/print'],
  '/company/billing': ['/billing/account', '/billing/invoices', '/tenants/me'],
  '/ecommerce': ['/ecommerce', '/ecommerce/listings', '/ecommerce/orders', '/ecommerce/connectors'],
  '/gift-cards': ['/gift-cards'],
  '/tax': ['/tax/rates'],
  '/security': ['/auth/2fa/status', '/auth/webauthn/credentials', '/auth/sessions'],
  '/notifications': ['/notifications?limit=100', '/notifications/settings'],
  '/support': ['/support/tickets?limit=100'],
  '/integrations': ['/api-keys', '/webhooks'],
  '/backup': ['/backup'],
  '/ai': ['/ai/status'],
  '/jobs': ['/jobs'],
  '/platform': ['/tenants', '/platform/activity'],
  '/platform/tenants': ['/tenants', '/packages'],
  '/platform/staff': ['/platform/staff', '/platform/roles'],
  '/platform/reports': ['/platform/reports'],
  '/platform/billing': ['/platform/billing/plans', '/platform/billing/attention'],
  '/platform/settings': ['/platform/settings'],
  '/platform/support': ['/support/tickets?limit=100'],
};

/** High-traffic desks to API-warm after idle, not every sidebar leaf. */
export const LIKELY_NEXT_HREFS = ['/dashboard', '/sales', '/customers', '/inventory', '/pos', '/purchasing'] as const;

export function prefetchPathsForHref(href: string): string[] {
  const path = hrefPath(href);
  return DESTINATION_GETS[path] || [];
}
