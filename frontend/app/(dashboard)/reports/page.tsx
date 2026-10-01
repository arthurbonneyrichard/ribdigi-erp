'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, getAccessToken } from '../../../lib/api';
import { formatDate, formatDateTime, formatNumber } from '../../../lib/format';
import {
  REPORT_GROUP_ORDER,
  reportFromTabView,
  reportHasFilter,
  reportsHref,
  reportsInGroup,
  type ReportDef,
} from '../../../lib/reportGroups';
import { useStoreContext } from '../../../lib/storeContext';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Tab =
  | 'summary'
  | 'sales'
  | 'salesperson'
  | 'customers'
  | 'stores'
  | 'departments'
  | 'inventory'
  | 'purchases'
  | 'expenses'
  | 'cashflow'
  | 'pnl'
  | 'trialbalance'
  | 'balancesheet'
  | 'accountstatement'
  | 'schedules';

const REPORT_TABS: Tab[] = [
  'summary',
  'sales',
  'salesperson',
  'customers',
  'stores',
  'departments',
  'inventory',
  'purchases',
  'expenses',
  'cashflow',
  'pnl',
  'trialbalance',
  'balancesheet',
  'accountstatement',
  'schedules',
];

function isReportTab(value: string | null): value is Tab {
  return Boolean(value && (REPORT_TABS as string[]).includes(value));
}

const TAB_EXPORT: Partial<Record<Exclude<Tab, 'schedules'>, string>> = {
  summary: 'summary',
  sales: 'sales_products',
  salesperson: 'sales_salesperson',
  customers: 'sales_customers',
  stores: 'sales_by_store',
  departments: 'sales_by_department',
  inventory: 'inventory_low_stock',
  purchases: 'purchases_summary',
  expenses: 'expenses_budget_vs_actual',
  cashflow: 'cash_flow',
  pnl: 'profit_loss',
  trialbalance: 'trial_balance',
  balancesheet: 'balance_sheet',
};

const REPORT_TYPES = [
  'summary',
  'sales_daily',
  'sales_monthly',
  'sales_products',
  'sales_salesperson',
  'sales_customers',
  'sales_returns',
  'sales_by_store',
  'sales_by_department',
  'inventory_balance',
  'inventory_valuation',
  'inventory_movements',
  'inventory_low_stock',
  'inventory_expiry',
  'pharmacy_rx_activity',
  'inventory_transfers',
  'inventory_stock_counts',
  'purchases_summary',
  'purchases_suppliers',
  'purchases_pending_orders',
  'purchases_returns',
  'expenses_summary',
  'expenses_budget_vs_actual',
  'cash_flow',
  'trial_balance',
  'profit_loss',
  'balance_sheet',
  'tax',
  'tax_filing',
  'tax_filing_gh',
];

type TabCache = {
  data: any;
  error: string;
  generatedAt: string;
  sectionErrors: Record<string, string>;
  loading: boolean;
};

function emptyTabCache(): TabCache {
  return { data: null, error: '', generatedAt: '', sectionErrors: {}, loading: false };
}

function formatReportError(err: unknown): string {
  const e = err as { message?: string; requestId?: string; status?: number };
  const message = (e?.message || 'Could not load this report.').trim();
  const rid = typeof e?.requestId === 'string' ? e.requestId.trim() : '';
  if (rid && !message.includes(rid)) return `${message} Request ID: ${rid}`;
  return message || 'Could not load this report.';
}

function fmtMoney(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  return formatNumber(n);
}

function fmtDate(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  const raw = String(value);
  const day = raw.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(day) && raw.length <= 10) {
    return formatDate(day) || raw;
  }
  return formatDateTime(raw) || raw;
}

async function fetchReport(path: string): Promise<{ data: any; error: string }> {
  try {
    const r = await api(path);
    return { data: r.data, error: '' };
  } catch (err: unknown) {
    return { data: null, error: formatReportError(err) };
  }
}

export default function Page() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>('summary');
  const [view, setView] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [storeId, setStoreId] = useState('');
  const { storeId: ctxStoreId, setStoreId: setCtxStoreId } = useStoreContext();
  const [branchId, setBranchId] = useState('');
  const [stores, setStores] = useState<any[]>([]);
  const [branches, setBranches] = useState<any[]>([]);
  const [asOf, setAsOf] = useState('');
  const [compare, setCompare] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [categoryId, setCategoryId] = useState('');
  const [categories, setCategories] = useState<any[]>([]);
  const [departmentId, setDepartmentId] = useState('');
  const [departments, setDepartments] = useState<any[]>([]);
  const [coaAccounts, setCoaAccounts] = useState<any[]>([]);
  const [statementAccountId, setStatementAccountId] = useState('');
  const [expiryDays, setExpiryDays] = useState('30');
  const [valuationMethod, setValuationMethod] = useState<'standard'>('standard');
  const [stockCountStatus, setStockCountStatus] = useState<'draft' | 'completed' | 'cancelled'>('completed');
  const [transferStatus, setTransferStatus] = useState<
    '' | 'draft' | 'requested' | 'in_transit' | 'received' | 'cancelled'
  >('');
  const [pendingPoStatus, setPendingPoStatus] = useState<
    '' | 'draft' | 'sent' | 'partially_received'
  >('');
  const [salesReturnStatus, setSalesReturnStatus] = useState<
    '' | 'draft' | 'posted' | 'cancelled'
  >('');
  const [salesReturnReason, setSalesReturnReason] = useState<
    '' | 'damaged' | 'wrong_item' | 'defective' | 'customer_change' | 'other'
  >('');
  const [purchaseReturnStatus, setPurchaseReturnStatus] = useState<
    '' | 'draft' | 'posted' | 'cancelled'
  >('');
  const [purchaseReturnReason, setPurchaseReturnReason] = useState<
    '' | 'damaged' | 'wrong_item' | 'expiry' | 'quality' | 'other'
  >('');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [generatedAt, setGeneratedAt] = useState('');
  const [sectionErrors, setSectionErrors] = useState<Record<string, string>>({});
  const [loadingTabs, setLoadingTabs] = useState<Partial<Record<Tab, boolean>>>({});
  const tabRef = useRef<Tab>('summary');
  const loadGen = useRef<Partial<Record<Tab, number>>>({});
  const tabCacheRef = useRef<Partial<Record<Tab, TabCache>>>({});
  const [schedules, setSchedules] = useState<any[]>([]);
  const [scheduleManageFilter, setScheduleManageFilter] = useState<
    'all' | 'enabled' | 'disabled'
  >('all');
  const [scheduleFrequencyFilter, setScheduleFrequencyFilter] = useState<
    'all' | 'daily' | 'weekly'
  >('all');
  const managedSchedules = schedules.filter((s) => {
    if (scheduleManageFilter === 'enabled' && !s.enabled) return false;
    if (scheduleManageFilter === 'disabled' && s.enabled) return false;
    if (scheduleFrequencyFilter !== 'all' && (s.frequency || '') !== scheduleFrequencyFilter) {
      return false;
    }
    return true;
  });
  const [schedForm, setSchedForm] = useState({
    name: 'Daily sales summary',
    report_type: 'summary',
    format: 'xlsx',
    frequency: 'daily',
    weekday: '0',
    hour_utc: '6',
    recipients: '',
    enabled: true,
  });
  const [suggestSelected, setSuggestSelected] = useState<Record<string, boolean>>({});
  const [suggestBusy, setSuggestBusy] = useState(false);
  const [suggestNotes, setSuggestNotes] = useState('');
  tabRef.current = tab;
  const activeReport = useMemo(() => reportFromTabView(tab, view), [tab, view]);

  function qs(extra: Record<string, string> = {}) {
    const params = new URLSearchParams();
    if (fromDate) params.set('from_date', fromDate);
    if (toDate) params.set('to_date', toDate);
    // trim so UuidIdValue Query store/warehouse/branch/department do not 422
    // Prefer page store filter; fall back to Shell header store when page is "All stores"
    const storeTrim = (storeId || ctxStoreId || '').trim();
    const warehouseTrim = warehouseId.trim();
    const branchTrim = branchId.trim();
    const departmentTrim = departmentId.trim();
    if (storeTrim) params.set('store_id', storeTrim);
    if (branchTrim) params.set('branch_id', branchTrim);
    if (departmentTrim) params.set('department_id', departmentTrim);
    if (warehouseTrim) params.set('warehouse_id', warehouseTrim);
    // callers pass category_id (trimmed) in extra when needed
    Object.entries(extra).forEach(([k, v]) => v && params.set(k, v));
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  function balanceSheetQs() {
    const params = new URLSearchParams();
    const effectiveAsOf = asOf || toDate;
    if (effectiveAsOf) params.set('as_of', effectiveAsOf);
    if (compare) params.set('compare', compare);
    const storeTrim = (storeId || ctxStoreId || '').trim();
    const branchTrim = branchId.trim();
    if (storeTrim) params.set('store_id', storeTrim);
    if (branchTrim) params.set('branch_id', branchTrim);
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  function trialBalanceQs() {
    const params = new URLSearchParams();
    const effectiveAsOf = asOf || toDate;
    if (effectiveAsOf) params.set('as_of', effectiveAsOf);
    const storeTrim = (storeId || ctxStoreId || '').trim();
    const branchTrim = branchId.trim();
    if (storeTrim) params.set('store_id', storeTrim);
    if (branchTrim) params.set('branch_id', branchTrim);
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  async function load(nextTab: Tab = tab) {
    const gen = (loadGen.current[nextTab] || 0) + 1;
    loadGen.current[nextTab] = gen;
    const isStale = () => loadGen.current[nextTab] !== gen;

    function publish(patch: Partial<TabCache>) {
      if (isStale()) return;
      const prev = tabCacheRef.current[nextTab] || emptyTabCache();
      const next = { ...prev, ...patch };
      tabCacheRef.current[nextTab] = next;
      if (tabRef.current !== nextTab) return;
      setData(next.data);
      setError(next.error);
      setGeneratedAt(next.generatedAt);
      setSectionErrors(next.sectionErrors);
      setLoading(next.loading);
    }

    setLoadingTabs((prev) => ({ ...prev, [nextTab]: true }));
    publish({ loading: true, error: '', sectionErrors: {} });
    if (tabRef.current === nextTab) {
      setError('');
      setSectionErrors({});
      setLoading(true);
    }

    try {
      if (nextTab === 'schedules') {
        const r = await fetchReport('/reports/schedules');
        if (isStale()) return;
        if (r.error) {
          publish({
            loading: false,
            error: r.error,
            generatedAt: '',
            data: null,
          });
          return;
        }
        setSchedules(r.data || []);
        publish({
          loading: false,
          error: '',
          data: null,
          generatedAt: new Date().toISOString(),
          sectionErrors: {},
        });
        return;
      }

      if (nextTab === 'accountstatement') {
        const acct = statementAccountId.trim();
        if (!acct) {
          publish({
            loading: false,
            data: null,
            error: 'Select an account for the statement',
            generatedAt: '',
            sectionErrors: {},
          });
          return;
        }
      }

      const categoryTrim = categoryId.trim();
      const paths: Record<Exclude<Tab, 'schedules'>, string> = {
        summary: `/reports/summary${qs()}`,
        sales: `/reports/sales/products${qs(categoryTrim ? { category_id: categoryTrim } : {})}`,
        salesperson: `/reports/sales/salesperson${qs()}`,
        customers: `/reports/sales/customers${qs()}`,
        stores: `/reports/sales/by-store${qs()}`,
        departments: `/reports/sales/by-department${qs()}`,
        inventory: `/reports/inventory/low-stock${qs()}`,
        purchases: `/reports/purchases/summary${qs()}`,
        expenses: `/reports/expenses/budget-vs-actual${qs()}`,
        cashflow: `/reports/cash-flow${qs()}`,
        pnl: `/reports/profit-loss${qs()}`,
        trialbalance: `/reports/trial-balance${trialBalanceQs()}`,
        balancesheet: `/reports/balance-sheet${balanceSheetQs()}`,
        accountstatement: `/reports/account-statement${qs({ account_id: statementAccountId.trim() })}`,
      };
      const path = paths[nextTab as Exclude<Tab, 'schedules'>];

      if (nextTab === 'sales') {
        const [products, daily, monthly, returns] = await Promise.all([
          fetchReport(path),
          fetchReport(
            `/reports/sales/daily${qs(toDate || fromDate ? { date: toDate || fromDate } : {})}`
          ),
          fetchReport(`/reports/sales/monthly${qs()}`),
          fetchReport(
            `/reports/sales/returns${qs({
              ...(salesReturnStatus ? { status: salesReturnStatus } : {}),
              ...(salesReturnReason ? { reason: salesReturnReason } : {}),
            })}`
          ),
        ]);
        const sections: Record<string, string> = {};
        if (products.error) sections.products = products.error;
        if (daily.error) sections.daily = daily.error;
        if (monthly.error) sections.monthly = monthly.error;
        if (returns.error) sections.returns = returns.error;
        const payload = {
          products: products.data,
          daily: daily.data,
          monthly: monthly.data,
          returns: returns.data,
        };
        const hasData = Boolean(products.data || daily.data || monthly.data || returns.data);
        publish({
          loading: false,
          data: hasData ? payload : null,
          error: hasData ? '' : Object.values(sections)[0] || 'Could not load this report.',
          sectionErrors: sections,
          generatedAt: hasData ? new Date().toISOString() : '',
        });
        return;
      }

      if (nextTab === 'inventory') {
        const [lowStock, balance, valuation, movements, suggestions, transfers, expiry, stockCounts, rxActivity] =
          await Promise.all([
            fetchReport(path),
            fetchReport(`/reports/inventory/balance${qs()}`),
            fetchReport(`/reports/inventory/valuation${qs({ method: valuationMethod })}`),
            fetchReport(`/reports/inventory/movements${qs()}`),
            fetchReport(`/purchasing/suggestions/low-stock${qs()}`),
            fetchReport(
              `/reports/inventory/transfers${qs(transferStatus ? { status: transferStatus } : {})}`
            ),
            fetchReport(
              `/reports/inventory/expiry${qs({
                days: String(Math.max(1, Math.min(365, Number(expiryDays) || 30))),
              })}`
            ),
            fetchReport(
              `/reports/inventory/stock-counts${qs({
                variance_only: 'true',
                status: stockCountStatus,
              })}`
            ),
            fetchReport(`/reports/pharmacy/rx-activity${qs()}`),
          ]);
        const sections: Record<string, string> = {};
        if (lowStock.error) sections.lowStock = lowStock.error;
        if (balance.error) sections.balance = balance.error;
        if (valuation.error) sections.valuation = valuation.error;
        if (movements.error) sections.movements = movements.error;
        if (suggestions.error) sections.suggestions = suggestions.error;
        if (transfers.error) sections.transfers = transfers.error;
        if (expiry.error) sections.expiry = expiry.error;
        if (stockCounts.error) sections.stockCounts = stockCounts.error;
        const rxDenied = /403|INDUSTRY_MODULE/i.test(rxActivity.error || '');
        if (rxActivity.error && !rxDenied) sections.rxActivity = rxActivity.error;
        const payload = {
          lowStock: lowStock.data,
          balance: balance.data,
          valuation: valuation.data,
          movements: movements.data,
          suggestions: suggestions.data,
          transfers: transfers.data,
          expiry: expiry.data,
          stockCounts: stockCounts.data,
          rxActivity: rxDenied ? null : rxActivity.data,
        };
        const hasData = Object.values(payload).some((v) => v != null);
        if (hasData) setSuggestSelected({});
        publish({
          loading: false,
          data: hasData ? payload : null,
          error: hasData ? '' : Object.values(sections)[0] || 'Could not load this report.',
          sectionErrors: sections,
          generatedAt: hasData ? new Date().toISOString() : '',
        });
        return;
      }

      if (nextTab === 'purchases') {
        const [summary, suppliers, pending, returns] = await Promise.all([
          fetchReport(path),
          fetchReport(`/reports/purchases/suppliers${qs()}`),
          fetchReport(
            `/reports/purchases/pending-orders${qs(
              pendingPoStatus ? { status: pendingPoStatus } : {}
            )}`
          ),
          fetchReport(
            `/reports/purchases/returns${qs({
              ...(purchaseReturnStatus ? { status: purchaseReturnStatus } : {}),
              ...(purchaseReturnReason ? { reason: purchaseReturnReason } : {}),
            })}`
          ),
        ]);
        const sections: Record<string, string> = {};
        if (summary.error) sections.summary = summary.error;
        if (suppliers.error) sections.suppliers = suppliers.error;
        if (pending.error) sections.pending = pending.error;
        if (returns.error) sections.returns = returns.error;
        const payload = {
          summary: summary.data,
          suppliers: suppliers.data,
          pending: pending.data,
          returns: returns.data,
        };
        const hasData = Object.values(payload).some((v) => v != null);
        publish({
          loading: false,
          data: hasData ? payload : null,
          error: hasData ? '' : Object.values(sections)[0] || 'Could not load this report.',
          sectionErrors: sections,
          generatedAt: hasData ? new Date().toISOString() : '',
        });
        return;
      }

      const r = await fetchReport(path);
      if (isStale()) return;
      publish({
        loading: false,
        data: r.error ? null : r.data,
        error: r.error,
        sectionErrors: {},
        generatedAt: r.error ? '' : new Date().toISOString(),
      });
    } catch (err: unknown) {
      publish({
        loading: false,
        data: null,
        error: formatReportError(err),
        generatedAt: '',
        sectionErrors: {},
      });
    } finally {
      if (!isStale()) {
        setLoadingTabs((prev) => ({ ...prev, [nextTab]: false }));
      }
    }
  }

  useEffect(() => {
    load('summary');
    Promise.all([
      api('/stores').catch(() => ({ data: [] })),
      api('/branches').catch(() => ({ data: [] })),
      api('/warehouses').catch(() => ({ data: [] })),
      api('/catalog/categories').catch(() => ({ data: [] })),
      api('/departments').catch(() => ({ data: [] })),
      api('/accounting/accounts').catch(() => ({ data: [] })),
    ])
      .then(([st, br, wh, cats, deps, accts]) => {
        setStores(st.data || []);
        setBranches(br.data || []);
        setWarehouses(wh.data || []);
        setCategories(cats.data || []);
        setDepartments(deps.data || []);
        setCoaAccounts(accts.data || []);
        if (ctxStoreId && (st.data || []).some((s: any) => s.id === ctxStoreId)) {
          setStoreId(ctxStoreId);
        }
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (ctxStoreId) setStoreId(ctxStoreId);
  }, [ctxStoreId]);

  const effectiveStoreId = storeId || ctxStoreId || '';

  // When a store is selected, align branch filter to that store's branch.
  useEffect(() => {
    if (!effectiveStoreId || !stores.length) return;
    const st = stores.find((s) => s.id === effectiveStoreId);
    if (st?.branch_id) setBranchId(st.branch_id);
  }, [effectiveStoreId, stores]);

  // Clear warehouse when it is not attached to the active store filter.
  useEffect(() => {
    if (!warehouseId || !effectiveStoreId) return;
    const wh = warehouses.find((w) => w.id === warehouseId);
    if (wh && wh.store_id && wh.store_id !== effectiveStoreId) {
      setWarehouseId('');
    }
  }, [effectiveStoreId, warehouseId, warehouses]);

  // Clear department when it does not belong to the active branch.
  useEffect(() => {
    if (!departmentId || !branchId) return;
    const dep = departments.find((d) => d.id === departmentId);
    if (dep?.branch_id && dep.branch_id !== branchId) {
      setDepartmentId('');
    }
  }, [branchId, departmentId, departments]);

  function switchTab(t: Tab, nextView?: string) {
    tabRef.current = t;
    setTab(t);
    if (nextView !== undefined) setView(nextView);
    const cached = tabCacheRef.current[t];
    if (cached) {
      setData(cached.data);
      setError(cached.error);
      setGeneratedAt(cached.generatedAt);
      setSectionErrors(cached.sectionErrors);
      setLoading(cached.loading);
    } else {
      setData(null);
      setError('');
      setGeneratedAt('');
      setSectionErrors({});
      setLoading(false);
    }
    const href = reportsHref(reportFromTabView(t, nextView !== undefined ? nextView : view));
    router.replace(href, { scroll: false });
    load(t);
  }

  function selectReport(def: ReportDef) {
    const nextTab = def.tab as Tab;
    const nextView = def.view || '';
    if (nextTab === tab) {
      setView(nextView);
      router.replace(reportsHref(def), { scroll: false });
      const cached = tabCacheRef.current[nextTab];
      if (!cached || cached.loading) {
        load(nextTab);
      }
      return;
    }
    switchTab(nextTab, nextView);
  }

  function resetFilters() {
    setFromDate('');
    setToDate('');
    setAsOf('');
    setCompare('');
    setWarehouseId('');
    setCategoryId('');
    setDepartmentId('');
    setStatementAccountId('');
    setExpiryDays('30');
    setValuationMethod('standard');
    setStockCountStatus('completed');
    setTransferStatus('');
    setPendingPoStatus('');
    setSalesReturnStatus('');
    setSalesReturnReason('');
    setPurchaseReturnStatus('');
    setPurchaseReturnReason('');
    setStoreId(ctxStoreId || '');
    setBranchId('');
    setData(null);
    setGeneratedAt('');
    setError('');
    setSectionErrors({});
    setMessage('');
    tabCacheRef.current[tab] = emptyTabCache();
  }

  useEffect(() => {
    const next = searchParams.get('tab');
    const nextView = searchParams.get('view') || '';
    if (isReportTab(next) && next !== tab) {
      tabRef.current = next;
      setTab(next);
      setView(nextView);
      load(next);
    } else if (nextView !== view) {
      setView(nextView);
    }
    // load is stable enough for tab query changes from the sidebar
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  function suggestionKey(line: any) {
    return `${line.product_id}:${line.warehouse_id || 'product'}`;
  }

  async function createDraftPrsFromSuggestions() {
    const lines = (data?.suggestions?.lines || []).filter(
      (ln: any) => suggestSelected[suggestionKey(ln)]
    );
    if (!lines.length) {
      setError('Select at least one low-stock line');
      return;
    }
    setError('');
    setMessage('');
    setSuggestBusy(true);
    try {
      const r = await api('/purchasing/requests/from-low-stock', {
        method: 'POST',
        body: JSON.stringify({
          lines: lines.map((ln: any) => ({
            product_id: String(ln.product_id || '').trim(),
            quantity: ln.suggested_order_qty,
            warehouse_id: ln.warehouse_id ? String(ln.warehouse_id).trim() : null,
            preferred_supplier_id: ln.preferred_supplier_id
              ? String(ln.preferred_supplier_id).trim()
              : null,
          })),
          notes: suggestNotes.trim() || null,
        }),
      });
      const created = r.data?.created || [];
      const nums = created.map((p: any) => p.request_number).join(', ');
      setMessage(
        created.length
          ? `Created draft PR(s): ${nums}. Open Purchasing → Requests to submit.`
          : r.message || 'Done'
      );
      setSuggestNotes('');
      await load('inventory');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSuggestBusy(false);
    }
  }

  async function download(format: 'csv' | 'pdf' | 'xlsx', reportType?: string) {
    if (tab === 'schedules' || tab === 'accountstatement') return;
    setError('');
    setMessage('');
    try {
      const token = getAccessToken();
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      const exportType = reportType || activeReport.exportType || TAB_EXPORT[tab as Exclude<Tab, 'schedules'>];
      if (!exportType) return;
      params.set('report_type', exportType);
      params.set('format', format);
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      // trim so UuidIdValue Query filters do not 422 on whitespace
      const storeTrim = (storeId || ctxStoreId || '').trim();
      const branchTrim = branchId.trim();
      const departmentTrim = departmentId.trim();
      const warehouseTrim = warehouseId.trim();
      const categoryTrim = categoryId.trim();
      if (storeTrim) params.set('store_id', storeTrim);
      if (branchTrim) params.set('branch_id', branchTrim);
      if (departmentTrim) params.set('department_id', departmentTrim);
      if (warehouseTrim) params.set('warehouse_id', warehouseTrim);
      if (
        (reportType || TAB_EXPORT[tab]) === 'sales_products' ||
        (!reportType && tab === 'sales')
      ) {
        if (categoryTrim) params.set('category_id', categoryTrim);
      }
      if (
        (reportType || TAB_EXPORT[tab]) === 'balance_sheet' ||
        (reportType || TAB_EXPORT[tab]) === 'trial_balance'
      ) {
        const effectiveAsOf = asOf || toDate;
        if (effectiveAsOf) params.set('as_of', effectiveAsOf);
        if ((reportType || TAB_EXPORT[tab]) === 'balance_sheet' && compare) {
          params.set('compare', compare);
        }
      }
      if (
        (reportType || TAB_EXPORT[tab]) === 'inventory_valuation' ||
        (reportType || TAB_EXPORT[tab]) === 'inventory_balance' ||
        (reportType || TAB_EXPORT[tab]) === 'inventory_expiry'
      ) {
        if (warehouseId) params.set('warehouse_id', warehouseId);
      }
      if ((reportType || TAB_EXPORT[tab]) === 'inventory_expiry' && expiryDays) {
        const d = Math.max(1, Math.min(365, Number(expiryDays) || 30));
        params.set('days', String(d));
      }
      const res = await fetch(`${base}/reports/export?${params}`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Export failed');
      }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const filename = match?.[1] || `report.${format}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`${format.toUpperCase()} downloaded`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createSchedule() {
    setError('');
    setMessage('');
    try {
      await api('/reports/schedules', {
        method: 'POST',
        body: JSON.stringify({
          name: schedForm.name.trim(),
          report_type: schedForm.report_type,
          format: schedForm.format,
          frequency: schedForm.frequency,
          weekday: schedForm.frequency === 'weekly' ? Number(schedForm.weekday) : null,
          hour_utc: Number(schedForm.hour_utc),
          recipients: schedForm.recipients.trim(),
          enabled: schedForm.enabled,
        }),
      });
      setMessage('Schedule created');
      setSchedForm({ ...schedForm, recipients: '' });
      await load('schedules');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function toggleSchedule(row: any) {
    setError('');
    try {
      await api(`/reports/schedules/${row.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ enabled: !row.enabled }),
      });
      await load('schedules');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function runSchedule(id: string) {
    setError('');
    setMessage('');
    try {
      const r = await api(`/reports/schedules/${id}/run?force=true`, { method: 'POST' });
      setMessage(r.message || (r.data?.ran ? 'Report emailed' : r.data?.reason || 'Done'));
      await load('schedules');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deleteSchedule(id: string) {
    setError('');
    try {
      await api(`/reports/schedules/${id}`, { method: 'DELETE' });
      setMessage('Schedule deleted');
      await load('schedules');
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <>
      <h1>Reports</h1>
      <p className="muted">
        Company-scoped totals only (this tenant). Pick a report, set the filters that apply, then
        Generate. Export and print use the same filters.
      </p>
      <div className="reports-layout">
        <nav className="reports-nav" aria-label="Report groups">
          {REPORT_GROUP_ORDER.map((group) => (
            <div
              key={group.id}
              className={`reports-nav-group${activeReport.group === group.id ? ' is-active' : ''}`}
            >
              <h2 className="reports-nav-title">{group.label}</h2>
              {reportsInGroup(group.id).map((def) => {
                const selected = activeReport.id === def.id;
                const busy = !!loadingTabs[def.tab as Tab];
                return (
                  <button
                    key={def.id}
                    type="button"
                    className={`reports-nav-item${selected ? ' is-active' : ''}`}
                    onClick={() => (selected ? load(def.tab as Tab) : selectReport(def))}
                    disabled={busy && selected}
                    aria-pressed={selected}
                    aria-busy={busy && selected}
                    aria-label={selected ? `Retry ${def.name}` : `Show ${def.name}`}
                  >
                    <strong>{busy && selected ? `${def.name}…` : def.name}</strong>
                    <span>{def.description}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="reports-main">
          <p className="reports-crumb muted">
            {REPORT_GROUP_ORDER.find((g) => g.id === activeReport.group)?.label || 'Reports'} ·{' '}
            {activeReport.name}
          </p>
          <h2>{activeReport.name}</h2>
          <p className="muted">{activeReport.description}</p>
          {error && (
            <p style={{ color: '#b91c1c' }} role="alert">
              {error}{' '}
              <button
                type="button"
                onClick={() => load(tab)}
                disabled={!!loadingTabs[tab]}
                aria-label="Retry this report"
              >
                Retry
              </button>
            </p>
          )}
          {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}
          {generatedAt && !error ? (
            <p className="muted" style={{ fontSize: 13 }}>
              Generated {fmtDate(generatedAt)}
            </p>
          ) : null}

          {tab !== 'schedules' && (
            <div className="card reports-filters" style={{ marginBottom: 16 }}>
              {reportHasFilter(activeReport, 'dates') && (
                <>
                  <label>
                    From
                    <input
                      type="date"
                      value={fromDate}
                      onChange={(e) => setFromDate(e.target.value)}
                      title="From date (YYYY-MM-DD)"
                      aria-label="Report from date"
                    />
                  </label>
                  <label>
                    To
                    <input
                      type="date"
                      value={toDate}
                      onChange={(e) => setToDate(e.target.value)}
                      title="To date (YYYY-MM-DD)"
                      aria-label="Report to date"
                    />
                  </label>
                </>
              )}
              {reportHasFilter(activeReport, 'asOf') && (
                <label>
                  As of
                  <input
                    type="date"
                    value={asOf}
                    onChange={(e) => setAsOf(e.target.value)}
                    title="As of date (defaults to To date)"
                    aria-label="Report as of date"
                  />
                </label>
              )}
              {reportHasFilter(activeReport, 'compare') && (
                <label>
                  Compare
                  <select
                    value={compare}
                    onChange={(e) => setCompare(e.target.value)}
                    aria-label="Balance sheet compare"
                  >
                    <option value="">No compare</option>
                    <option value="prior_period">vs prior month-end</option>
                    <option value="prior_year">vs prior year</option>
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'account') && (
                <label>
                  Account
                  <select
                    value={statementAccountId}
                    onChange={(e) => setStatementAccountId(e.target.value)}
                    aria-label="Account for statement"
                  >
                    <option value="">Select account</option>
                    {coaAccounts.map((a: any) => (
                      <option key={a.id} value={a.id}>
                        {a.code} {a.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'branch') && (
                <label>
                  Branch
                  <select
                    value={branchId}
                    onChange={(e) => setBranchId(e.target.value)}
                    aria-label="Report financial branch filter"
                  >
                    <option value="">All branches</option>
                    {branches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.code} — {b.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'store') && (
                <label>
                  Store
                  <select
                    value={storeId || ctxStoreId}
                    onChange={(e) => {
                      setStoreId(e.target.value);
                      setCtxStoreId(e.target.value);
                      if (reportHasFilter(activeReport, 'warehouse')) setWarehouseId('');
                    }}
                    aria-label="Report store filter"
                  >
                    <option value="">All stores</option>
                    {stores
                      .filter((s) => s.is_active !== false)
                      .filter((s) => !branchId || s.branch_id === branchId)
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.code} — {s.name}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'warehouse') && (
                <label>
                  Warehouse
                  <select
                    value={warehouseId}
                    onChange={(e) => {
                      const next = e.target.value;
                      setWarehouseId(next);
                      if (next) {
                        const wh = warehouses.find((w) => w.id === next);
                        if (wh?.store_id) {
                          setStoreId(wh.store_id);
                          setCtxStoreId(wh.store_id);
                        }
                      }
                    }}
                    aria-label="Report warehouse filter"
                  >
                    <option value="">All warehouses</option>
                    {warehouses
                      .filter((w) => w.is_active !== false)
                      .filter((w) => !effectiveStoreId || w.store_id === effectiveStoreId)
                      .map((w) => (
                        <option key={w.id} value={w.id}>
                          {w.code} — {w.name}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'department') && (
                <label>
                  Department
                  <select
                    value={departmentId}
                    onChange={(e) => setDepartmentId(e.target.value)}
                    aria-label="Report department filter"
                  >
                    <option value="">All departments</option>
                    {departments
                      .filter((d) => !branchId || !d.branch_id || d.branch_id === branchId)
                      .map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.code} — {d.name}
                        </option>
                      ))}
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'category') && (
                <label>
                  Category
                  <select
                    value={categoryId}
                    onChange={(e) => setCategoryId(e.target.value)}
                    aria-label="Report sales category filter"
                  >
                    <option value="">All categories</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.code} — {c.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'expiryDays') && (
                <label>
                  Expiry days
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={expiryDays}
                    onChange={(e) => setExpiryDays(e.target.value)}
                    placeholder="Expiry days"
                    style={{ width: 110 }}
                    title="Expiry horizon (1–365 days)"
                    aria-label="Inventory expiry days"
                  />
                </label>
              )}
              {reportHasFilter(activeReport, 'valuation') && (
                <label>
                  Valuation
                  <select
                    aria-label="Valuation method"
                    value={valuationMethod}
                    onChange={(e) => setValuationMethod(e.target.value as 'standard')}
                  >
                    <option value="standard">standard</option>
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'salesReturn') && (
                <>
                  <label>
                    Return status
                    <select
                      aria-label="Sales return status"
                      value={salesReturnStatus}
                      onChange={(e) =>
                        setSalesReturnStatus(e.target.value as '' | 'draft' | 'posted' | 'cancelled')
                      }
                    >
                      <option value="">all</option>
                      <option value="draft">draft</option>
                      <option value="posted">posted</option>
                      <option value="cancelled">cancelled</option>
                    </select>
                  </label>
                  <label>
                    Return reason
                    <select
                      aria-label="Sales return reason"
                      value={salesReturnReason}
                      onChange={(e) =>
                        setSalesReturnReason(
                          e.target.value as
                            | ''
                            | 'damaged'
                            | 'wrong_item'
                            | 'defective'
                            | 'customer_change'
                            | 'other'
                        )
                      }
                    >
                      <option value="">all</option>
                      <option value="damaged">damaged</option>
                      <option value="wrong_item">wrong item</option>
                      <option value="defective">defective</option>
                      <option value="customer_change">customer change</option>
                      <option value="other">other</option>
                    </select>
                  </label>
                </>
              )}
              {reportHasFilter(activeReport, 'purchaseReturn') && (
                <>
                  <label>
                    Return status
                    <select
                      aria-label="Purchase return status"
                      value={purchaseReturnStatus}
                      onChange={(e) =>
                        setPurchaseReturnStatus(e.target.value as '' | 'draft' | 'posted' | 'cancelled')
                      }
                    >
                      <option value="">all</option>
                      <option value="draft">draft</option>
                      <option value="posted">posted</option>
                      <option value="cancelled">cancelled</option>
                    </select>
                  </label>
                  <label>
                    Return reason
                    <select
                      aria-label="Purchase return reason"
                      value={purchaseReturnReason}
                      onChange={(e) =>
                        setPurchaseReturnReason(
                          e.target.value as
                            | ''
                            | 'damaged'
                            | 'wrong_item'
                            | 'expiry'
                            | 'quality'
                            | 'other'
                        )
                      }
                    >
                      <option value="">all</option>
                      <option value="damaged">damaged</option>
                      <option value="wrong_item">wrong item</option>
                      <option value="expiry">expiry</option>
                      <option value="quality">quality</option>
                      <option value="other">other</option>
                    </select>
                  </label>
                </>
              )}
              {reportHasFilter(activeReport, 'pendingPo') && (
                <label>
                  Pending status
                  <select
                    aria-label="Pending status"
                    value={pendingPoStatus}
                    onChange={(e) =>
                      setPendingPoStatus(e.target.value as '' | 'draft' | 'sent' | 'partially_received')
                    }
                  >
                    <option value="">all pending</option>
                    <option value="draft">draft</option>
                    <option value="sent">sent</option>
                    <option value="partially_received">partially received</option>
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'transferStatus') && (
                <label>
                  Transfer status
                  <select
                    aria-label="Transfer status"
                    value={transferStatus}
                    onChange={(e) =>
                      setTransferStatus(
                        e.target.value as
                          | ''
                          | 'draft'
                          | 'requested'
                          | 'in_transit'
                          | 'received'
                          | 'cancelled'
                      )
                    }
                  >
                    <option value="">all</option>
                    <option value="draft">draft</option>
                    <option value="requested">requested</option>
                    <option value="in_transit">in transit</option>
                    <option value="received">received</option>
                    <option value="cancelled">cancelled</option>
                  </select>
                </label>
              )}
              {reportHasFilter(activeReport, 'stockCountStatus') && (
                <label>
                  Count status
                  <select
                    aria-label="Count status"
                    value={stockCountStatus}
                    onChange={(e) =>
                      setStockCountStatus(e.target.value as 'draft' | 'completed' | 'cancelled')
                    }
                  >
                    <option value="completed">completed</option>
                    <option value="draft">draft</option>
                    <option value="cancelled">cancelled</option>
                  </select>
                </label>
              )}
              <div className="reports-actions">
                <button
                  type="button"
                  onClick={() => load(tab)}
                  disabled={!!loadingTabs[tab]}
                  aria-label="Generate this report"
                >
                  {loadingTabs[tab] ? 'Generating…' : 'Generate'}
                </button>
                <button type="button" onClick={resetFilters} aria-label="Reset report filters">
                  Reset
                </button>
                {activeReport.exportType ? (
                  <>
                    <button
                      type="button"
                      onClick={() => download('csv')}
                      aria-label="Export report CSV"
                    >
                      Export CSV
                    </button>
                    <button
                      type="button"
                      onClick={() => download('xlsx')}
                      aria-label="Export report Excel"
                    >
                      Export Excel
                    </button>
                    <button
                      type="button"
                      onClick={() => download('pdf')}
                      aria-label="Export report PDF"
                    >
                      Export PDF
                    </button>
                  </>
                ) : null}
                {activeReport.print ? (
                  <button type="button" onClick={() => window.print()} aria-label="Print report">
                    Print
                  </button>
                ) : null}
              </div>
            </div>
          )}
          {loadingTabs[tab] ? (
            <p className="muted" role="status">
              Loading this report…
            </p>
          ) : null}
          {!loadingTabs[tab] && tab !== 'schedules' && !data && !error ? (
            <div className="list-empty">
              <p>This report has not been generated yet.</p>
              <p className="muted">Set any filters you need, then choose Generate.</p>
            </div>
          ) : null}

      {tab === 'summary' && data && (
        <div className="grid">
          <div className="card">
            <div className="muted">Today sales</div>
            <div className="kpi">{fmtMoney(data.today_sales?.total_revenue)}</div>
          </div>
          <div className="card">
            <div className="muted">Month sales</div>
            <div className="kpi">{fmtMoney(data.month_sales?.total_revenue)}</div>
            <p className="muted">vs prior: {data.month_sales?.change_pct ?? '—'}%</p>
          </div>
          <div className="card">
            <div className="muted">Low stock SKUs</div>
            <div className="kpi">{data.low_stock_report?.count ?? 0}</div>
          </div>
          <div className="card">
            <div className="muted">Approved expenses</div>
            <div className="kpi">{fmtMoney(data.expenses_summary?.total_amount)}</div>
          </div>
        </div>
      )}

      {tab === 'sales' && data && (
        <>
          {activeReport.view !== 'returns' && (
            <>
          {sectionErrors.daily ? <p style={{ color: '#b91c1c' }}>{sectionErrors.daily}</p> : null}
          {sectionErrors.monthly ? <p style={{ color: '#b91c1c' }}>{sectionErrors.monthly}</p> : null}
          <div className="grid">
            <div className="card">
              <h3>
                {data.daily?.date ? `Day · ${data.daily.date}` : 'Today'}
                {data.daily?.store_name ? ` · ${data.daily.store_name}` : ''}
              </h3>
              <p>Revenue: {data.daily?.total_revenue}</p>
              <p>Invoices: {data.daily?.invoice_count} · POS: {data.daily?.pos_count}</p>
            </div>
            <div className="card">
              <h3>This month{data.monthly?.store_name ? ` · ${data.monthly.store_name}` : ''}</h3>
              <p>Revenue: {data.monthly?.total_revenue}</p>
              <p>Change: {data.monthly?.change_pct ?? '—'}%</p>
            </div>
          </div>
          <h3 style={{ marginTop: 16 }}>Products</h3>
          {sectionErrors.products ? <p style={{ color: '#b91c1c' }}>{sectionErrors.products}</p> : null}
          <p className="muted">
            Qty {data.products?.total_quantity ?? 0} · revenue {data.products?.total_revenue ?? 0}
            {data.products?.total_profit != null ? ` · profit ${data.products.total_profit}` : ''}
            {data.products?.store_id ? ' · store filtered' : ''}
            {data.products?.category_name ? ` · ${data.products.category_name}` : ''}
          </p>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Category</th>
                <th>Qty</th>
                <th>Revenue</th>
                <th>Profit</th>
              </tr>
            </thead>
            <tbody>
              {(data.products?.products || []).map((p: any) => (
                <tr key={p.product_id}>
                  <td>{p.name}</td>
                  <td>{p.sku || '—'}</td>
                  <td>{p.category_name || '—'}</td>
                  <td>{p.quantity}</td>
                  <td>{fmtMoney(p.revenue)}</td>
                  <td>{p.profit != null ? fmtMoney(p.profit) : '—'}</td>
                </tr>
              ))}
              {!(data.products?.products || []).length ? (
                <tr>
                  <td colSpan={6} className="muted">
                    No product sales for this period.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          </div>
            </>
          )}
          {activeReport.view === 'returns' && (
            <>
          <h3 style={{ marginTop: 16 }}>Sales returns</h3>
          {sectionErrors.returns ? <p style={{ color: '#b91c1c' }}>{sectionErrors.returns}</p> : null}
          <p className="muted">
            {data.returns?.return_count ?? 0} returns · total {fmtMoney(data.returns?.total_amount)} ·
            posted {fmtMoney(data.returns?.posted_amount)} · qty {data.returns?.total_quantity ?? 0} ·
            refunded {fmtMoney(data.returns?.refunded_amount)}
            {data.returns?.store_name ? ` · ${data.returns.store_name}` : ''}
          </p>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Return</th>
                <th>Customer</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Qty</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.returns?.returns || []).map((ret: any) => (
                <tr key={ret.id}>
                  <td>{ret.return_number}</td>
                  <td>{ret.customer_name}</td>
                  <td>{ret.reason}</td>
                  <td>{ret.status}</td>
                  <td>{ret.quantity}</td>
                  <td>{ret.total_amount}</td>
                </tr>
              ))}
              {!data.returns?.returns?.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No sales returns
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
          {(data.returns?.by_reason || []).length > 0 && (
            <>
              <h4 style={{ marginTop: 12 }}>Returns by reason</h4>
              <ul>
                {data.returns.by_reason.map((x: any) => (
                  <li key={x.reason}>
                    {x.reason}: {x.return_count} · qty {x.quantity} · {x.total_amount}
                  </li>
                ))}
              </ul>
            </>
          )}
            </>
          )}
        </>
      )}

      {tab === 'salesperson' && data && (
        <>
          <div className="grid">
            <div className="card">
              <div className="muted">Total revenue{data.store_name ? ` · ${data.store_name}` : ''}</div>
              <div className="kpi">{data.total_revenue ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Sales count</div>
              <div className="kpi">{data.total_sales ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Invoice / POS</div>
              <div className="kpi">
                {data.invoice_revenue ?? 0} / {data.pos_revenue ?? 0}
              </div>
            </div>
          </div>
          <div className="list-table-wrap">
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Department</th>
                <th>Role</th>
                <th>Invoices</th>
                <th>POS</th>
                <th>Sales</th>
                <th>Revenue</th>
                <th>Avg ticket</th>
              </tr>
            </thead>
            <tbody>
              {(data.salespeople || []).map((s: any) => (
                <tr key={s.user_id || s.full_name}>
                  <td>{s.full_name}</td>
                  <td>{s.department_name || '—'}</td>
                  <td>{s.role || '—'}</td>
                  <td>
                    {s.invoice_count} ({s.invoice_revenue})
                  </td>
                  <td>
                    {s.pos_count} ({s.pos_revenue})
                  </td>
                  <td>{s.sale_count}</td>
                  <td>{s.revenue}</td>
                  <td>{s.avg_ticket}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'customers' && data && (
        <>
          <p className="muted">
            Top customers by revenue (invoices + POS)
            {data.store_id ? ` · store ${String(data.store_id).slice(0, 8)}…` : ''}
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Total revenue</div>
              <div className="kpi">{data.total_revenue ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Customers</div>
              <div className="kpi">{data.customer_count ?? data.customers?.length ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Sales / Invoice·POS</div>
              <div className="kpi">
                {data.total_sales ?? 0} · {data.invoice_revenue ?? 0}/{data.pos_revenue ?? 0}
              </div>
            </div>
          </div>
          <div className="list-table-wrap">
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Invoices</th>
                <th>POS</th>
                <th>Frequency</th>
                <th>Revenue</th>
                <th>Avg ticket</th>
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(data.customers) ? data.customers : []).map((c: any) => (
                <tr key={c.customer_id || c.name}>
                  <td>
                    {c.name}
                    {c.email ? (
                      <span className="muted" style={{ display: 'block', fontSize: 12 }}>
                        {c.email}
                      </span>
                    ) : null}
                  </td>
                  <td>
                    {c.invoice_count} ({c.invoice_revenue})
                  </td>
                  <td>
                    {c.pos_count} ({c.pos_revenue})
                  </td>
                  <td>{c.sale_count}</td>
                  <td>{c.revenue}</td>
                  <td>{c.avg_ticket}</td>
                </tr>
              ))}
              {!data.customers?.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No customer sales for this period
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'stores' && data && (
        <>
          <div className="grid">
            <div className="card">
              <div className="muted">Total revenue</div>
              <div className="kpi">{data.total_revenue ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Sales count</div>
              <div className="kpi">{data.total_sales ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Invoice / POS</div>
              <div className="kpi">
                {data.invoice_revenue ?? 0} / {data.pos_revenue ?? 0}
              </div>
            </div>
          </div>
          <div className="list-table-wrap">
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Store</th>
                <th>Code</th>
                <th>Invoices</th>
                <th>POS</th>
                <th>Sales</th>
                <th>Revenue</th>
                <th>Avg ticket</th>
              </tr>
            </thead>
            <tbody>
              {(data.stores || []).map((s: any) => (
                <tr key={s.store_id || s.name}>
                  <td>{s.name}</td>
                  <td>{s.code || '—'}</td>
                  <td>
                    {s.invoice_count} ({s.invoice_revenue})
                  </td>
                  <td>
                    {s.pos_count} ({s.pos_revenue})
                  </td>
                  <td>{s.sale_count}</td>
                  <td>{s.revenue}</td>
                  <td>{s.avg_ticket}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'departments' && data && (
        <>
          <div className="grid">
            <div className="card">
              <div className="muted">Total revenue</div>
              <div className="kpi">{data.total_revenue ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Sales count</div>
              <div className="kpi">{data.total_sales ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Invoice / POS</div>
              <div className="kpi">
                {data.invoice_revenue ?? 0} / {data.pos_revenue ?? 0}
              </div>
            </div>
          </div>
          {data.department_name ? (
            <p className="muted" style={{ marginTop: 12 }}>
              Filtered to {data.department_name}
            </p>
          ) : null}
          <div className="list-table-wrap">
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Department</th>
                <th>Code</th>
                <th>Invoices</th>
                <th>POS</th>
                <th>Sales</th>
                <th>Revenue</th>
                <th>Avg ticket</th>
              </tr>
            </thead>
            <tbody>
              {(data.departments || []).map((d: any) => (
                <tr key={d.department_id || d.name}>
                  <td>{d.name}</td>
                  <td>{d.code || '—'}</td>
                  <td>
                    {d.invoice_count} ({d.invoice_revenue})
                  </td>
                  <td>
                    {d.pos_count} ({d.pos_revenue})
                  </td>
                  <td>{d.sale_count}</td>
                  <td>{d.revenue}</td>
                  <td>{d.avg_ticket}</td>
                </tr>
              ))}
              {!data.departments?.length && (
                <tr>
                  <td colSpan={7} className="muted">
                    No department sales for this period
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'inventory' && data && (
        <>
          {sectionErrors.suggestions ? <p style={{ color: '#b91c1c' }}>{sectionErrors.suggestions}</p> : null}
          {sectionErrors.lowStock ? <p style={{ color: '#b91c1c' }}>{sectionErrors.lowStock}</p> : null}
          {sectionErrors.balance || sectionErrors.valuation ? (
            <p style={{ color: '#b91c1c' }}>{sectionErrors.balance || sectionErrors.valuation}</p>
          ) : null}
          {sectionErrors.movements ? <p style={{ color: '#b91c1c' }}>{sectionErrors.movements}</p> : null}
          {sectionErrors.expiry ? <p style={{ color: '#b91c1c' }}>{sectionErrors.expiry}</p> : null}
          {sectionErrors.transfers ? <p style={{ color: '#b91c1c' }}>{sectionErrors.transfers}</p> : null}
          {sectionErrors.stockCounts ? <p style={{ color: '#b91c1c' }}>{sectionErrors.stockCounts}</p> : null}
          {(activeReport.view || 'low_stock') === 'low_stock' && (
          <>
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <h3 style={{ margin: 0 }}>
                Low-stock suggestions ({data.suggestions?.count ?? data.lowStock?.count ?? 0})
              </h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                  value={suggestNotes}
                  onChange={(e) => setSuggestNotes(e.target.value)}
                  placeholder="Draft PR notes (optional)"
                  aria-label="Low-stock suggestion notes"
                  title="Optional notes for draft PRs (1–500 chars; letters/digits required)"
                  style={{ minWidth: 200 }}
                />
                <button
                  type="button"
                  onClick={createDraftPrsFromSuggestions}
                  disabled={suggestBusy || !(data.suggestions?.lines || []).length}
                  aria-label="Create draft PR from low-stock suggestions"
                >
                  {suggestBusy ? 'Creating…' : 'Create draft PR'}
                </button>
              </div>
            </div>
            <p className="muted" style={{ marginTop: 8 }}>
              Low stock {data.count ?? data.suggestions?.count ?? data.lowStock?.count ?? 0}
              {data.out_of_stock_count != null || data.lowStock?.out_of_stock_count != null
                ? ` · out of stock ${data.out_of_stock_count ?? data.lowStock?.out_of_stock_count}`
                : ''}
              . Select lines to raise draft purchase requests. Submit/approve remains in Purchasing.
            </p>
            {(data.suggestions?.lines || []).length === 0 ? (
              <p className="muted">No actionable low-stock lines (or all already on an open PR).</p>
            ) : (
              <div className="list-table-wrap">
              <table className="table" style={{ marginTop: 8 }}>
                <thead>
                  <tr>
                    <th></th>
                    <th>Product</th>
                    <th>SKU</th>
                    <th>On hand</th>
                    <th>Reorder</th>
                    <th>Suggest qty</th>
                    <th>Warehouse</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.suggestions?.lines || []).map((ln: any) => {
                    const key = suggestionKey(ln);
                    return (
                      <tr key={key}>
                        <td>
                          <input
                            type="checkbox"
                            aria-label="Low-stock suggestion select"
                            checked={!!suggestSelected[key]}
                            onChange={(e) =>
                              setSuggestSelected((prev) => ({ ...prev, [key]: e.target.checked }))
                            }
                          />
                        </td>
                        <td>{ln.name}</td>
                        <td>{ln.sku || '—'}</td>
                        <td>{ln.stock_qty}</td>
                        <td>{ln.reorder_level}</td>
                        <td>{ln.suggested_order_qty}</td>
                        <td>{ln.warehouse_name || '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
            )}
          </div>
          <div className="card" style={{ marginTop: 16 }}>
            <h3>Low stock products ({data.lowStock?.count ?? 0})</h3>
            <p className="muted" style={{ marginBottom: 8 }}>
              {data.lowStock?.store_name
                ? data.lowStock.store_name
                : data.lowStock?.warehouse_id
                  ? 'Warehouse filtered'
                  : 'Company-wide product reorder'}
            </p>
            <ul>
              {(data.lowStock?.products || []).map((p: any) => (
                <li key={p.id}>
                  {p.name}: {p.stock_qty} / reorder {p.reorder_level}
                  {p.suggested_order_qty ? ` · suggest ${p.suggested_order_qty}` : ''}
                </li>
              ))}
            </ul>
            {(data.lowStock?.warehouse_low_stock || []).length > 0 && (
              <>
                <h4 style={{ marginTop: 12 }}>Warehouse reorder breaches</h4>
                <ul>
                  {(data.lowStock.warehouse_low_stock || []).map((w: any) => (
                    <li key={`${w.warehouse_id}-${w.product_id}`}>
                      {w.name} @ {w.warehouse_name}: {w.quantity} / {w.reorder_level} · suggest{' '}
                      {w.suggested_order_qty}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
          </>
          )}
          {activeReport.view === 'value' && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3>Stock valuation (standard cost)</h3>
            <p className="muted">
              Method:{' '}
              <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
                Valuation method
                <select
                  aria-label="Valuation method"
                  value={valuationMethod}
                  onChange={(e) => setValuationMethod(e.target.value as 'standard')}
                >
                  <option value="standard">standard</option>
                </select>
              </label>
              {data.valuation?.store_name
                ? ` · ${data.valuation.store_name}`
                : data.valuation?.warehouse_name
                  ? ` · ${data.valuation.warehouse_name}`
                  : data.valuation?.warehouse_id
                    ? ' · warehouse filtered'
                    : ' · company stock'}
            </p>
            <div className="grid">
              <div>
                <div className="muted">Total qty</div>
                <div className="kpi">{data.valuation?.total_quantity ?? data.balance?.total_quantity ?? 0}</div>
              </div>
              <div>
                <div className="muted">Total value</div>
                <div className="kpi">{data.valuation?.total_value ?? data.balance?.total_value ?? 0}</div>
              </div>
            </div>
            <button
              type="button"
              style={{ marginTop: 8 }}
              onClick={() => download('xlsx', 'inventory_valuation')}
              aria-label="Export inventory valuation Excel"
            >
              Export valuation Excel
            </button>
          </div>
          )}
          {activeReport.view === 'movements' && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3>Stock movements</h3>
            <p className="muted">
              {data.movements?.count ?? 0} recent
              {data.movements?.store_name
                ? ` · ${data.movements.store_name}`
                : data.movements?.warehouse_name
                  ? ` · ${data.movements.warehouse_name}`
                  : ''}
            </p>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => download('xlsx', 'inventory_movements')}
                aria-label="Export inventory movements Excel"
              >
                Movements Excel
              </button>
              <button
                type="button"
                onClick={() => download('csv', 'inventory_movements')}
                aria-label="Export inventory movements CSV"
              >
                Movements CSV
              </button>
            </div>
            <div className="list-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>When</th>
                  <th>Type</th>
                  <th>Reason</th>
                  <th>Qty</th>
                  <th>Before → after</th>
                  <th>User</th>
                  <th>Ref</th>
                </tr>
              </thead>
              <tbody>
                {(data.movements?.movements || []).slice(0, 25).map((mv: any) => (
                  <tr key={mv.id}>
                    <td>{mv.product_name || (mv.product_id ? String(mv.product_id).slice(0, 8) : '—')}</td>
                    <td>{mv.product_sku || '—'}</td>
                    <td>{fmtDate(mv.created_at)}</td>
                    <td>{mv.movement_type}</td>
                    <td>{mv.reason || '—'}</td>
                    <td>{mv.quantity}</td>
                    <td>
                      {mv.quantity_before} → {mv.quantity_after}
                    </td>
                    <td>{mv.created_by_name || mv.created_by_email || '—'}</td>
                    <td>
                      {mv.reference_type || '—'}
                      {mv.reference_id ? ` ${String(mv.reference_id).slice(0, 8)}…` : ''}
                    </td>
                  </tr>
                ))}
                {!data.movements?.movements?.length && (
                  <tr>
                    <td colSpan={9} className="muted">
                      No stock movements for this filter.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            </div>
          </div>
          )}
          {activeReport.view === 'value' && (
          <>
          <h3 style={{ marginTop: 16 }}>
            Stock value: {fmtMoney(data.valuation?.total_value ?? data.balance?.total_value)}
          </h3>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Qty</th>
                <th>Unit cost</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {(data.valuation?.items || data.balance?.items || []).slice(0, 50).map((i: any) => (
                <tr key={i.product_id}>
                  <td>{i.name}</td>
                  <td>{i.sku || '—'}</td>
                  <td>{i.quantity}</td>
                  <td>{i.unit_cost ?? i.cost_price ?? '—'}</td>
                  <td>{i.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
          </>
          )}
          {activeReport.view === 'expiry' && (
          <>
          <h3 style={{ marginTop: 16 }}>Expiry</h3>
          <p className="muted">
            {data.expiry?.count ?? 0} batches within {data.expiry?.within_days ?? expiryDays} days ·
            expired {data.expiry?.expired_count ?? 0} · qty {data.expiry?.total_quantity ?? 0}
            {data.expiry?.store_name
              ? ` · ${data.expiry.store_name}`
              : data.expiry?.warehouse_name
                ? ` · ${data.expiry.warehouse_name}`
                : ''}
          </p>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => download('xlsx', 'inventory_expiry')}
              aria-label="Export inventory expiry Excel"
            >
              Expiry Excel
            </button>
            <button
              type="button"
              onClick={() => download('csv', 'inventory_expiry')}
              aria-label="Export inventory expiry CSV"
            >
              Expiry CSV
            </button>
          </div>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Batch</th>
                <th>Expiry</th>
                <th>Days</th>
                <th>Qty</th>
              </tr>
            </thead>
            <tbody>
              {(data.expiry?.batches || []).map((b: any) => (
                <tr key={b.id}>
                  <td>{b.name || '—'}</td>
                  <td>{b.sku || '—'}</td>
                  <td>{b.batch_number}</td>
                  <td>{fmtDate(b.expiry_date ? String(b.expiry_date).slice(0, 10) : '')}</td>
                  <td>{b.days_until_expiry ?? '—'}</td>
                  <td>{b.quantity}</td>
                </tr>
              ))}
                {!data.expiry?.batches?.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No batches nearing expiry for this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
          </>
          )}
          {activeReport.view === 'rx' && (
          <>
          <h3 style={{ marginTop: 16 }}>Rx activity</h3>
          <p className="muted">
            {data.rxActivity?.counts?.total ?? 0} prescriptions · open {data.rxActivity?.counts?.open ?? 0} ·
            dispensed qty {data.rxActivity?.qty_dispensed ?? 0} of {data.rxActivity?.qty_prescribed ?? 0}
          </p>
          {sectionErrors.rxActivity && <p className="muted">{sectionErrors.rxActivity}</p>}
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Rx</th>
                <th>Status</th>
                <th>Customer</th>
                <th>Sale</th>
                <th>Remaining</th>
              </tr>
            </thead>
            <tbody>
              {(data.rxActivity?.prescriptions || []).map((row: any) => (
                <tr key={row.id}>
                  <td>{row.rx_number}</td>
                  <td>{row.status}</td>
                  <td>{row.customer_name || '—'}</td>
                  <td>{row.sale_number || '—'}</td>
                  <td>{row.qty_remaining}</td>
                </tr>
              ))}
              {!data.rxActivity?.prescriptions?.length && (
                <tr>
                  <td colSpan={5} className="muted">
                    No prescription activity for this filter (pharmacy tenants only).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
          </>
          )}
          {activeReport.view === 'transfers' && (
          <>
          <h3 style={{ marginTop: 16 }}>Inter-store transfers</h3>
          <p className="muted">
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', marginRight: 8 }}>
              Transfer status
              <select
                aria-label="Transfer status"
                value={transferStatus}
                onChange={(e) =>
                  setTransferStatus(
                    e.target.value as
                      | ''
                      | 'draft'
                      | 'requested'
                      | 'in_transit'
                      | 'received'
                      | 'cancelled'
                  )
                }
              >
                <option value="">all</option>
                <option value="draft">draft</option>
                <option value="requested">requested</option>
                <option value="in_transit">in_transit</option>
                <option value="received">received</option>
                <option value="cancelled">cancelled</option>
              </select>
            </label>
            {data.transfers?.transfer_count ?? 0}{' '}
            {(data.transfers?.transfer_count ?? 0) === 1 ? 'transfer' : 'transfers'} · qty{' '}
            {data.transfers?.total_quantity ?? 0}
            {data.transfers?.store_name ? ` · ${data.transfers.store_name}` : ''}
          </p>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => download('xlsx', 'inventory_transfers')}
              aria-label="Export inventory transfers Excel"
            >
              Transfers Excel
            </button>
            <button
              type="button"
              onClick={() => download('csv', 'inventory_transfers')}
              aria-label="Export inventory transfers CSV"
            >
              Transfers CSV
            </button>
          </div>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Transfer</th>
                <th>From</th>
                <th>To</th>
                <th>Status</th>
                <th>Qty</th>
                <th>Shipped</th>
                <th>Received</th>
              </tr>
            </thead>
            <tbody>
              {(data.transfers?.transfers || []).map((t: any) => (
                <tr key={t.id}>
                  <td>{t.transfer_number}</td>
                  <td>
                    {t.from_store_code || t.from_store_name}
                  </td>
                  <td>{t.to_store_code || t.to_store_name}</td>
                  <td>{t.status}</td>
                  <td>{t.quantity}</td>
                  <td>{t.shipped_qty}</td>
                  <td>{t.received_qty}</td>
                </tr>
              ))}
              {!data.transfers?.transfers?.length && (
                <tr>
                  <td colSpan={7} className="muted">
                    No transfers for this filter
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
          {(data.transfers?.by_route || []).length > 0 && (
            <>
              <h4 style={{ marginTop: 12 }}>By route</h4>
              <ul>
                {data.transfers.by_route.map((r: any) => (
                  <li key={`${r.from_store_id}-${r.to_store_id}`}>
                    {r.from_store_code} → {r.to_store_code}: {r.transfer_count} · qty {r.quantity}
                  </li>
                ))}
              </ul>
            </>
          )}
          </>
          )}
          {activeReport.view === 'counts' && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3>Stock count variances</h3>
            <p className="muted">
              <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', marginRight: 8 }}>
                Count status
                <select
                  aria-label="Count status"
                  value={stockCountStatus}
                  onChange={(e) =>
                    setStockCountStatus(e.target.value as 'draft' | 'completed' | 'cancelled')
                  }
                >
                  <option value="completed">completed</option>
                  <option value="draft">draft</option>
                  <option value="cancelled">cancelled</option>
                </select>
              </label>
              {data.stockCounts?.count_sessions ?? 0} count
              {(data.stockCounts?.count_sessions ?? 0) === 1 ? '' : 's'} ·{' '}
              {data.stockCounts?.lines_with_variance ?? 0} variance line
              {(data.stockCounts?.lines_with_variance ?? 0) === 1 ? '' : 's'} · net qty{' '}
              {data.stockCounts?.total_variance_qty ?? 0}
              {data.stockCounts?.store_name
                ? ` · ${data.stockCounts.store_name}`
                : data.stockCounts?.warehouse_name
                  ? ` · ${data.stockCounts.warehouse_name}`
                  : ''}
            </p>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => download('xlsx', 'inventory_stock_counts')}
                aria-label="Export inventory stock counts Excel"
              >
                Count variances Excel
              </button>
              <button
                type="button"
                onClick={() => download('csv', 'inventory_stock_counts')}
                aria-label="Export inventory stock counts CSV"
              >
                Count variances CSV
              </button>
            </div>
            <div className="list-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Count</th>
                  <th>Warehouse</th>
                  <th>Expected</th>
                  <th>Counted</th>
                  <th>Variance</th>
                </tr>
              </thead>
              <tbody>
                {(data.stockCounts?.lines || []).slice(0, 40).map((line: any, idx: number) => (
                  <tr key={`${line.count_id}-${line.product_id}-${idx}`}>
                    <td>{line.name || '—'}</td>
                    <td>{line.sku || '—'}</td>
                    <td>{line.count_number}</td>
                    <td>{line.warehouse_name || '—'}</td>
                    <td>{line.expected_qty}</td>
                    <td>{line.counted_qty}</td>
                    <td>{line.variance}</td>
                  </tr>
                ))}
                {!data.stockCounts?.lines?.length && (
                  <tr>
                    <td colSpan={7} className="muted">
                      No stock count variances for this filter
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            </div>
          </div>
          )}
        </>
      )}

      {tab === 'purchases' && data && (
        <>
          {sectionErrors.summary ? <p style={{ color: '#b91c1c' }}>{sectionErrors.summary}</p> : null}
          {sectionErrors.suppliers ? <p style={{ color: '#b91c1c' }}>{sectionErrors.suppliers}</p> : null}
          {sectionErrors.pending ? <p style={{ color: '#b91c1c' }}>{sectionErrors.pending}</p> : null}
          {sectionErrors.returns ? <p style={{ color: '#b91c1c' }}>{sectionErrors.returns}</p> : null}
          {(activeReport.view || 'overview') === 'overview' && (
          <div className="grid">
            <div className="card">
              <div className="muted">
                Orders (period)
                {data.summary?.store_name
                  ? ` · ${data.summary.store_name}`
                  : data.summary?.warehouse_name
                    ? ` · ${data.summary.warehouse_name}`
                    : ''}
              </div>
              <div className="kpi">{data.summary?.order_count ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Total / outstanding</div>
              <div className="kpi">
                {fmtMoney(data.summary?.total_amount)} / {fmtMoney(data.summary?.outstanding_amount)}
              </div>
            </div>
          </div>
          )}
          {activeReport.view === 'returns' && (
          <>
          <p className="muted">
            {data.returns?.return_count ?? 0} returns · total {fmtMoney(data.returns?.total_amount)} ·
            posted {fmtMoney(data.returns?.posted_amount)} · qty {data.returns?.total_quantity ?? 0}
            {data.returns?.store_name
              ? ` · ${data.returns.store_name}`
              : data.returns?.warehouse_name
                ? ` · ${data.returns.warehouse_name}`
                : ''}
          </p>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Return</th>
                <th>Supplier</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Qty</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.returns?.returns || []).map((ret: any) => (
                <tr key={ret.id}>
                  <td>{ret.return_number}</td>
                  <td>{ret.supplier_name}</td>
                  <td>{ret.reason}</td>
                  <td>{ret.status}</td>
                  <td>{ret.quantity}</td>
                  <td>{ret.total_amount}</td>
                </tr>
              ))}
              {!data.returns?.returns?.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No purchase returns
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
          {(data.returns?.by_reason || []).length > 0 && (
            <>
              <h4 style={{ marginTop: 12 }}>Returns by reason</h4>
              <ul>
                {data.returns.by_reason.map((x: any) => (
                  <li key={x.reason}>
                    {x.reason}: {x.return_count} · {x.total_amount} (qty {x.quantity})
                  </li>
                ))}
              </ul>
            </>
          )}
          </>
          )}
          {activeReport.view === 'pending' && (
          <>
          <h3 style={{ marginTop: 16 }}>Pending orders (not fully received)</h3>
          <p className="muted">
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center', marginRight: 8 }}>
              Pending status
              <select
                aria-label="Pending status"
                value={pendingPoStatus}
                onChange={(e) =>
                  setPendingPoStatus(
                    e.target.value as '' | 'draft' | 'sent' | 'partially_received'
                  )
                }
              >
                <option value="">all pending</option>
                <option value="draft">draft</option>
                <option value="sent">sent</option>
                <option value="partially_received">partially_received</option>
              </select>
            </label>
            {data.pending?.order_count ?? 0}{' '}
            {(data.pending?.order_count ?? 0) === 1 ? 'order' : 'orders'} · qty open{' '}
            {data.pending?.total_outstanding_qty ?? 0}
          </p>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>PO</th>
                <th>Supplier</th>
                <th>Status</th>
                <th>Ordered</th>
                <th>Received</th>
                <th>Outstanding qty</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.pending?.orders || []).map((o: any) => (
                <tr key={o.id}>
                  <td>{o.po_number}</td>
                  <td>{o.supplier_name}</td>
                  <td>{o.status}</td>
                  <td>{o.ordered_qty}</td>
                  <td>{o.received_qty}</td>
                  <td>{o.outstanding_qty}</td>
                  <td>{o.total_amount}</td>
                </tr>
              ))}
              {!data.pending?.orders?.length && (
                <tr>
                  <td colSpan={7} className="muted">
                    No pending purchase orders
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
          </>
          )}
          {activeReport.view === 'suppliers' && (
          <>
          <h3 style={{ marginTop: 16 }}>By supplier</h3>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Supplier</th>
                <th>Orders</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {(data.suppliers?.suppliers || []).map((s: any) => (
                <tr key={s.supplier_id}>
                  <td>{s.name}</td>
                  <td>{s.order_count}</td>
                  <td>{fmtMoney(s.total_amount)}</td>
                </tr>
              ))}
              {!(data.suppliers?.suppliers || []).length ? (
                <tr>
                  <td colSpan={3} className="muted">
                    No supplier purchases for this period.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          </div>
          </>
          )}
        </>
      )}

      {tab === 'expenses' && data && (
        <>
          <p className="muted">
            Period {data.period_days ?? '—'} days · scaled budgets vs approved spend
            {data.branch_name ? ` · branch ${data.branch_name}` : ''}
            {data.department_name ? ` · dept ${data.department_name}` : ''}
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Budget (scaled)</div>
              <div className="kpi">{data.total_budget_scaled ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Actual</div>
              <div className="kpi">{data.total_actual ?? data.total_amount ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Variance</div>
              <div className="kpi">{data.total_variance ?? 0}</div>
            </div>
          </div>
          <h3 style={{ marginTop: 16 }}>Top categories</h3>
          <ul>
            {(data.top_categories || []).map((c: any) => (
              <li key={c.category_id || c.category}>
                {c.category}: {c.actual} ({c.status})
              </li>
            ))}
            {!data.top_categories?.length && <li className="muted">No spend yet</li>}
          </ul>
          <div className="list-table-wrap">
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Category</th>
                <th>Budget (scaled)</th>
                <th>Actual</th>
                <th>Variance</th>
                <th>%</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(data.rows || data.by_category || []).map((c: any) => (
                <tr key={c.category_id || c.category}>
                  <td>
                    {c.code ? `${c.code} — ` : ''}
                    {c.category}
                  </td>
                  <td>{c.budget_scaled ?? '—'}</td>
                  <td>{c.actual ?? c.amount}</td>
                  <td>{c.variance ?? '—'}</td>
                  <td>{c.variance_pct != null ? `${c.variance_pct}%` : '—'}</td>
                  <td>{c.status || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'cashflow' && data && (
        <>
          <p className="muted">
            Liquid GL cash movements
            {data.store_id ? ` · store ${String(data.store_id).slice(0, 8)}…` : ''}
            {data.branch_id ? ` · branch ${String(data.branch_id).slice(0, 8)}…` : ''}
            {data.store_id || data.branch_id
              ? ' (attributable operating cash; HQ transfers/openings omitted)'
              : ''}
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Inflows</div>
              <div className="kpi">{data.inflows}</div>
            </div>
            <div className="card">
              <div className="muted">Outflows</div>
              <div className="kpi">{data.outflows}</div>
            </div>
            <div className="card">
              <div className="muted">Net</div>
              <div className="kpi">{data.net}</div>
            </div>
          </div>
          <div className="grid" style={{ marginTop: 12 }}>
            {(
              [
                ['operating', 'Operating'],
                ['investing', 'Investing'],
                ['financing', 'Financing'],
                ['transfers', 'Transfers'],
              ] as const
            ).map(([key, label]) => (
              <div className="card" key={key}>
                <div className="muted">{label}</div>
                <div className="kpi">{data[key]?.net ?? 0}</div>
                <p className="muted" style={{ margin: 0 }}>
                  In {data[key]?.inflows ?? 0} · Out {data[key]?.outflows ?? 0}
                </p>
              </div>
            ))}
          </div>
          <div className="list-table-wrap">
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Date</th>
                <th>Entry</th>
                <th>Activity</th>
                <th>In</th>
                <th>Out</th>
              </tr>
            </thead>
            <tbody>
              {(data.lines || []).slice(0, 40).map((l: any, idx: number) => (
                <tr key={`${l.entry_number}-${idx}`}>
                  <td>{String(l.date)}</td>
                  <td>{l.entry_number}</td>
                  <td>{l.activity || '—'}</td>
                  <td>{l.inflow}</td>
                  <td>{l.outflow}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'pnl' && data && (
        <>
          <p className="muted">
            {data.mode === 'journals'
              ? 'Period / location from posted journals'
              : 'Lifetime account balances'}
            {data.store_id ? ` · store ${data.store_id.slice(0, 8)}…` : ''}
            {data.branch_id ? ` · branch ${data.branch_id.slice(0, 8)}…` : ''}
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Revenue</div>
              <div className="kpi">{data.revenue ?? data.income ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">COGS</div>
              <div className="kpi">{data.cogs ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Gross profit</div>
              <div className="kpi">{data.gross_profit ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Operating expenses</div>
              <div className="kpi">{data.operating_expenses ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Net profit</div>
              <div className="kpi">{data.net_profit ?? 0}</div>
            </div>
          </div>
          <div className="list-table-wrap">
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Type</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.accounts || []).map((a: any) => (
                <tr key={a.code}>
                  <td>{a.code}</td>
                  <td>{a.name}</td>
                  <td>{a.account_type}</td>
                  <td>{a.balance}</td>
                </tr>
              ))}
              {!data.accounts?.length && (
                <tr>
                  <td colSpan={4} className="muted">
                    No income/expense activity for this filter
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'trialbalance' && data && (
        <>
          <p className="muted">
            As of {data.as_of}
            {data.mode === 'journals' ? ' · reconstructed from posted journals' : ' · live balances'}
            {data.store_id ? ` · store ${String(data.store_id).slice(0, 8)}…` : ''}
            {data.branch_id ? ` · branch ${String(data.branch_id).slice(0, 8)}…` : ''}
            {data.store_id || data.branch_id
              ? ' · attributable journals only (sales / POS / expenses / returns)'
              : ''}
            {' · '}
            Balanced: {String(data.balanced)} | Dr {data.total_debit} / Cr {data.total_credit}
          </p>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Type</th>
                <th>Debit</th>
                <th>Credit</th>
              </tr>
            </thead>
            <tbody>
              {(data.rows || []).map((r: any) => (
                <tr key={r.account_id || r.code}>
                  <td>{r.code}</td>
                  <td>{r.name}</td>
                  <td>{r.account_type}</td>
                  <td>{r.debit}</td>
                  <td>{r.credit}</td>
                </tr>
              ))}
              {!data.rows?.length && (
                <tr>
                  <td colSpan={5} className="muted">
                    No balances for this as-of date
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'accountstatement' && data && (
        <>
          <p className="muted">
            {data.code} {data.name} · opening {data.opening_balance} · closing {data.closing_balance}
          </p>
          <div className="list-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Entry</th>
                  <th>Memo</th>
                  <th>Debit</th>
                  <th>Credit</th>
                  <th>Balance</th>
                </tr>
              </thead>
              <tbody>
                {(data.lines || []).map((l: any, idx: number) => (
                  <tr key={`${l.journal_entry_id}-${idx}`}>
                    <td>{String(l.date || '').slice(0, 10)}</td>
                    <td>{l.entry_number}</td>
                    <td>{l.description || '—'}</td>
                    <td>{l.debit}</td>
                    <td>{l.credit}</td>
                    <td>{l.balance}</td>
                  </tr>
                ))}
                {!(data.lines || []).length && (
                  <tr>
                    <td colSpan={6} className="muted">
                      No posted lines for this account in the date range
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'balancesheet' && data && (
        <>
          <p className="muted">
            As of {data.as_of}
            {data.mode === 'journals' ? ' · reconstructed from posted journals' : ' · live balances'}
            {data.store_id ? ` · store ${String(data.store_id).slice(0, 8)}…` : ''}
            {data.branch_id ? ` · branch ${String(data.branch_id).slice(0, 8)}…` : ''}
            {data.store_id || data.branch_id
              ? ' · attributable journals only (sales / POS / expenses / returns)'
              : ''}
            {data.compare
              ? ` · compare ${data.compare.mode} (${data.compare.as_of})`
              : ''}
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Total assets</div>
              <div className="kpi">{data.total_assets}</div>
              {data.compare && (
                <p className="muted">Δ {data.compare.deltas?.total_assets ?? 0}</p>
              )}
            </div>
            <div className="card">
              <div className="muted">Liabilities + equity</div>
              <div className="kpi">{data.total_liabilities_and_equity}</div>
              {data.compare && (
                <p className="muted">
                  Δ {data.compare.deltas?.total_liabilities_and_equity ?? 0}
                </p>
              )}
            </div>
            <div className="card">
              <div className="muted">Balanced</div>
              <div className="kpi">{String(data.balanced)}</div>
            </div>
          </div>
          {(['assets', 'liabilities', 'equity'] as const).map((section) => (
            <div key={section} style={{ marginTop: 16 }}>
              <h3>{section}</h3>
              <div className="list-table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Name</th>
                    <th>Balance</th>
                    {data.compare && (
                      <>
                        <th>Prior</th>
                        <th>Δ</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {(data[section] || []).map((r: any) => (
                    <tr key={`${section}-${r.code}`}>
                      <td>{r.code}</td>
                      <td>{r.name}</td>
                      <td>{r.balance}</td>
                      {data.compare && (
                        <>
                          <td>{r.prior_balance ?? 0}</td>
                          <td>{r.delta ?? 0}</td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              </div>
            </div>
          ))}
        </>
      )}

      {tab === 'schedules' && (
        <>
          <p className="muted">
            Company admins can schedule CSV, Excel, or PDF reports emailed on a daily or weekly cadence (UTC hour).
          </p>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <input
              placeholder="Schedule name"
              value={schedForm.name}
              onChange={(e) => setSchedForm({ ...schedForm, name: e.target.value })}
              aria-label="Report schedule name"
              title="Schedule name (2–120 chars; letters/digits required)"
            />
            <select
              value={schedForm.report_type}
              onChange={(e) => setSchedForm({ ...schedForm, report_type: e.target.value })}
              aria-label="Report schedule report type"
            >
              {REPORT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select
                value={schedForm.format}
                onChange={(e) => setSchedForm({ ...schedForm, format: e.target.value })}
                aria-label="Report schedule format"
              >
                <option value="xlsx">Excel</option>
                <option value="csv">CSV</option>
                <option value="pdf">PDF</option>
              </select>
              <select
                value={schedForm.frequency}
                onChange={(e) => setSchedForm({ ...schedForm, frequency: e.target.value })}
                aria-label="Report schedule frequency"
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
              {schedForm.frequency === 'weekly' && (
                <select
                  value={schedForm.weekday}
                  onChange={(e) => setSchedForm({ ...schedForm, weekday: e.target.value })}
                  aria-label="Report schedule weekday"
                >
                  {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((d, i) => (
                    <option key={d} value={String(i)}>
                      {d}
                    </option>
                  ))}
                </select>
              )}
              <label>
                Hour UTC{' '}
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={schedForm.hour_utc}
                  onChange={(e) => setSchedForm({ ...schedForm, hour_utc: e.target.value })}
                  style={{ width: 64 }}
                  aria-label="Report schedule hour UTC"
                />
              </label>
            </div>
            <input
              placeholder="Recipients (comma-separated emails)"
              value={schedForm.recipients}
              onChange={(e) => setSchedForm({ ...schedForm, recipients: e.target.value })}
              aria-label="Report schedule recipients"
              title="Comma-separated recipient emails"
            />
            <label>
              <input
                type="checkbox"
                checked={schedForm.enabled}
                onChange={(e) => setSchedForm({ ...schedForm, enabled: e.target.checked })}
                aria-label="Report schedule enabled"
              />{' '}
              Enabled
            </label>
            <button type="button" onClick={createSchedule} aria-label="Create report schedule">
              Create schedule
            </button>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            <select
              value={scheduleManageFilter}
              onChange={(e) =>
                setScheduleManageFilter(e.target.value as 'all' | 'enabled' | 'disabled')
              }
              title="Filter schedules by enabled flag"
              aria-label="Report schedule enabled filter"
            >
              <option value="all">All enabled/disabled</option>
              <option value="enabled">Enabled only</option>
              <option value="disabled">Disabled only</option>
            </select>
            <select
              value={scheduleFrequencyFilter}
              onChange={(e) =>
                setScheduleFrequencyFilter(e.target.value as 'all' | 'daily' | 'weekly')
              }
              title="Filter schedules by frequency"
              aria-label="Report schedule frequency filter"
            >
              <option value="all">All frequencies</option>
              <option value="daily">Daily only</option>
              <option value="weekly">Weekly only</option>
            </select>
          </div>
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Report</th>
                <th>When</th>
                <th>Recipients</th>
                <th>Last run</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {managedSchedules.length === 0 ? (
                <tr>
                  <td colSpan={6} className="muted">
                    No schedules for this filter
                  </td>
                </tr>
              ) : (
                managedSchedules.map((s) => (
                  <tr key={s.id}>
                    <td>
                      {s.name} {!s.enabled && <span className="muted">(off)</span>}
                    </td>
                    <td>
                      {s.report_type} / {s.format}
                    </td>
                    <td>
                      {s.frequency}
                      {s.frequency === 'weekly' ? ` dow=${s.weekday}` : ''} @ {s.hour_utc}:00 UTC
                    </td>
                    <td>{(s.recipients || []).join(', ')}</td>
                    <td>
                      {s.last_run_at ? String(s.last_run_at).slice(0, 19) : '—'}
                      {s.last_error ? (
                        <div style={{ color: '#b91c1c', fontSize: 12 }}>{s.last_error}</div>
                      ) : null}
                    </td>
                    <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <button onClick={() => runSchedule(s.id)} aria-label={`Run report schedule ${s.id}`}>
                        Run now
                      </button>
                      <button onClick={() => toggleSchedule(s)} aria-label={`${s.enabled ? 'Disable' : 'Enable'} report schedule ${s.id}`}>
                        {s.enabled ? 'Disable' : 'Enable'}
                      </button>
                      <button onClick={() => deleteSchedule(s.id)} aria-label={`Delete report schedule ${s.id}`}>Delete</button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          </div>
          {!schedules.length && !loading && <p className="muted">No schedules yet.</p>}
        </>
      )}
        </div>
      </div>
    </>
  );
}
