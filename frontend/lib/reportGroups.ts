/** Report picker catalog for /reports. Display-only; fetch paths stay in the page. */

export type ReportGroupId =
  | 'sales'
  | 'inventory'
  | 'purchases'
  | 'finance'
  | 'customers'
  | 'staff'
  | 'schedules';

export type ReportFilterKey =
  | 'dates'
  | 'store'
  | 'branch'
  | 'warehouse'
  | 'category'
  | 'department'
  | 'asOf'
  | 'compare'
  | 'account'
  | 'expiryDays'
  | 'valuation'
  | 'salesReturn'
  | 'purchaseReturn'
  | 'pendingPo'
  | 'transferStatus'
  | 'stockCountStatus';

export type ReportDef = {
  id: string;
  tab: string;
  view?: string;
  group: ReportGroupId;
  name: string;
  description: string;
  filters: ReportFilterKey[];
  exportType?: string;
  print?: boolean;
};

export const REPORT_GROUP_ORDER: { id: ReportGroupId; label: string }[] = [
  { id: 'sales', label: 'Sales' },
  { id: 'inventory', label: 'Inventory' },
  { id: 'purchases', label: 'Purchases' },
  { id: 'finance', label: 'Finance' },
  { id: 'customers', label: 'Customers' },
  { id: 'staff', label: 'Staff' },
  { id: 'schedules', label: 'Email Schedules' },
];

export const REPORT_CATALOG: ReportDef[] = [
  {
    id: 'summary',
    tab: 'summary',
    group: 'sales',
    name: 'Sales snapshot',
    description: 'Today and this month, plus low-stock and expense totals.',
    filters: ['dates', 'store'],
    exportType: 'summary',
    print: true,
  },
  {
    id: 'sales_products',
    tab: 'sales',
    view: 'products',
    group: 'sales',
    name: 'Sales by product',
    description: 'Quantity and revenue by product for the date range.',
    filters: ['dates', 'store', 'category'],
    exportType: 'sales_products',
    print: true,
  },
  {
    id: 'sales_returns',
    tab: 'sales',
    view: 'returns',
    group: 'sales',
    name: 'Sales returns',
    description: 'Returned sales by reason, status, quantity, and amount.',
    filters: ['dates', 'store', 'salesReturn'],
    exportType: 'sales_returns',
    print: true,
  },
  {
    id: 'stores',
    tab: 'stores',
    group: 'sales',
    name: 'Sales by store',
    description: 'Invoice and POS revenue grouped by store.',
    filters: ['dates', 'store', 'branch', 'department'],
    exportType: 'sales_by_store',
    print: true,
  },
  {
    id: 'departments',
    tab: 'departments',
    group: 'sales',
    name: 'Sales by department',
    description: 'Revenue grouped by department.',
    filters: ['dates', 'department', 'branch'],
    exportType: 'sales_by_department',
    print: true,
  },
  {
    id: 'inventory_low_stock',
    tab: 'inventory',
    view: 'low_stock',
    group: 'inventory',
    name: 'Low stock',
    description: 'Products at or below reorder, with draft purchase-request suggestions.',
    filters: ['store', 'warehouse'],
    exportType: 'inventory_low_stock',
    print: true,
  },
  {
    id: 'inventory_value',
    tab: 'inventory',
    view: 'value',
    group: 'inventory',
    name: 'Stock value',
    description: 'On-hand quantity and standard-cost value.',
    filters: ['store', 'warehouse', 'valuation'],
    exportType: 'inventory_valuation',
    print: true,
  },
  {
    id: 'inventory_movements',
    tab: 'inventory',
    view: 'movements',
    group: 'inventory',
    name: 'Stock movements',
    description: 'Receives, issues, counts, transfers, and adjustments.',
    filters: ['dates', 'store', 'warehouse'],
    exportType: 'inventory_movements',
    print: true,
  },
  {
    id: 'inventory_expiry',
    tab: 'inventory',
    view: 'expiry',
    group: 'inventory',
    name: 'Expiry',
    description: 'Batches nearing expiry or already expired.',
    filters: ['store', 'warehouse', 'expiryDays'],
    exportType: 'inventory_expiry',
    print: true,
  },
  {
    id: 'inventory_transfers',
    tab: 'inventory',
    view: 'transfers',
    group: 'inventory',
    name: 'Stock transfers',
    description: 'Inter-store transfer quantity, status, and route.',
    filters: ['dates', 'store', 'transferStatus'],
    exportType: 'inventory_transfers',
    print: true,
  },
  {
    id: 'inventory_counts',
    tab: 'inventory',
    view: 'counts',
    group: 'inventory',
    name: 'Stock count variances',
    description: 'Count sessions with expected vs counted differences.',
    filters: ['dates', 'store', 'warehouse', 'stockCountStatus'],
    exportType: 'inventory_stock_counts',
    print: true,
  },
  {
    id: 'purchases_overview',
    tab: 'purchases',
    view: 'overview',
    group: 'purchases',
    name: 'Purchases overview',
    description: 'Order count, spend, and outstanding for the period.',
    filters: ['dates', 'store'],
    exportType: 'purchases_summary',
    print: true,
  },
  {
    id: 'purchases_suppliers',
    tab: 'purchases',
    view: 'suppliers',
    group: 'purchases',
    name: 'Purchases by supplier',
    description: 'Order count and total by supplier.',
    filters: ['dates', 'store'],
    exportType: 'purchases_suppliers',
    print: true,
  },
  {
    id: 'purchases_pending',
    tab: 'purchases',
    view: 'pending',
    group: 'purchases',
    name: 'Pending purchase orders',
    description: 'Orders not fully received, with outstanding quantity.',
    filters: ['dates', 'store', 'pendingPo'],
    exportType: 'purchases_pending_orders',
    print: true,
  },
  {
    id: 'purchases_returns',
    tab: 'purchases',
    view: 'returns',
    group: 'purchases',
    name: 'Purchase returns',
    description: 'Returns to suppliers by reason, status, and amount.',
    filters: ['dates', 'store', 'purchaseReturn'],
    exportType: 'purchases_returns',
    print: true,
  },
  {
    id: 'expenses',
    tab: 'expenses',
    group: 'finance',
    name: 'Expenses vs budget',
    description: 'Approved spend compared with scaled category budgets.',
    filters: ['dates', 'store', 'branch', 'department'],
    exportType: 'expenses_budget_vs_actual',
    print: true,
  },
  {
    id: 'cashflow',
    tab: 'cashflow',
    group: 'finance',
    name: 'Cash flow',
    description: 'Cash inflows, outflows, and activity type.',
    filters: ['dates', 'store', 'branch'],
    exportType: 'cash_flow',
    print: true,
  },
  {
    id: 'pnl',
    tab: 'pnl',
    group: 'finance',
    name: 'Profit and loss',
    description: 'Income and expense totals for the period.',
    filters: ['dates', 'store', 'branch'],
    exportType: 'profit_loss',
    print: true,
  },
  {
    id: 'trialbalance',
    tab: 'trialbalance',
    group: 'finance',
    name: 'Trial balance',
    description: 'Debit and credit balances as of a date.',
    filters: ['asOf', 'store', 'branch'],
    exportType: 'trial_balance',
    print: true,
  },
  {
    id: 'balancesheet',
    tab: 'balancesheet',
    group: 'finance',
    name: 'Balance sheet',
    description: 'Assets, liabilities, and equity as of a date.',
    filters: ['asOf', 'compare', 'store', 'branch'],
    exportType: 'balance_sheet',
    print: true,
  },
  {
    id: 'accountstatement',
    tab: 'accountstatement',
    group: 'finance',
    name: 'Account statement',
    description: 'Movements and running balance for one account.',
    filters: ['dates', 'account', 'store', 'branch'],
    print: true,
  },
  {
    id: 'customers',
    tab: 'customers',
    group: 'customers',
    name: 'Sales by customer',
    description: 'Invoice and POS revenue by customer.',
    filters: ['dates', 'store'],
    exportType: 'sales_customers',
    print: true,
  },
  {
    id: 'salesperson',
    tab: 'salesperson',
    group: 'staff',
    name: 'Sales by staff',
    description: 'Invoice and POS revenue by salesperson.',
    filters: ['dates', 'store', 'department'],
    exportType: 'sales_salesperson',
    print: true,
  },
  {
    id: 'schedules',
    tab: 'schedules',
    group: 'schedules',
    name: 'Email schedules',
    description: 'Email a saved report daily or weekly (UTC hour).',
    filters: [],
  },
];

export function reportsInGroup(group: ReportGroupId): ReportDef[] {
  return REPORT_CATALOG.filter((r) => r.group === group);
}

export function findReport(id: string | null | undefined): ReportDef | undefined {
  if (!id) return undefined;
  return REPORT_CATALOG.find((r) => r.id === id);
}

export function reportFromTabView(tab: string | null, view: string | null | undefined): ReportDef {
  const v = (view || '').trim();
  if (tab && v) {
    const both = REPORT_CATALOG.find((r) => r.tab === tab && r.view === v);
    if (both) return both;
  }
  if (tab) {
    const defaults: Record<string, string> = {
      sales: 'products',
      inventory: 'low_stock',
      purchases: 'overview',
    };
    const implied = defaults[tab];
    if (implied) {
      const match = REPORT_CATALOG.find((r) => r.tab === tab && r.view === implied);
      if (match) return match;
    }
    const byTab = REPORT_CATALOG.find((r) => r.tab === tab && !r.view);
    if (byTab) return byTab;
    const anyTab = REPORT_CATALOG.find((r) => r.tab === tab);
    if (anyTab) return anyTab;
  }
  return REPORT_CATALOG[0];
}

export function reportHasFilter(report: ReportDef, key: ReportFilterKey): boolean {
  return report.filters.includes(key);
}

export function reportsHref(report: ReportDef): string {
  const params = new URLSearchParams();
  params.set('tab', report.tab);
  if (report.view) params.set('view', report.view);
  return `/reports?${params.toString()}`;
}
