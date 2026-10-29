'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '../../../lib/api';
import { printDocumentFromElement } from '../../../lib/documentPrint';
import { downloadAttachment } from '../../../lib/attachments';
import { getPrefetched } from '../../../lib/prefetchCache';
import { formatMoney, formatNumber, formatWhen, plainLabel } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import {
  REPORT_GROUP_ORDER,
  reportFromTabView,
  findReport,
  reportCopy,
  reportGroupLabel,
  reportHasFilter,
  reportVisible,
  reportsHref,
  reportsInGroup,
  type ReportDef,
} from '../../../lib/reportGroups';
import SalesReportSheets from '../../../components/SalesReportSheets';
import { getMe } from '../../../lib/meCache';
import { isHotelIndustry, tenantIsMultiStore } from '../../../lib/tenantNav';
import { normalizeIndustry } from '../../../lib/industries';
import { useStoreContext } from '../../../lib/storeContext';
import OfflineProvisionalNotice from '../../../components/OfflineProvisionalNotice';
import EmptyState from '../../../components/EmptyState';
import PageHeader from '../../../components/PageHeader';
import './report-ui.css';

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
  return message || 'Could not load this report.';
}

function fmtMoney(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return String(value);
  return formatMoney(n);
}

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

function isoDateOrEmpty(value: string): string {
  const trimmed = String(value || '').trim();
  return /^\d{4}-\d{2}-\d{2}$/.test(trimmed) ? trimmed : '';
}

// Readable store/branch name for report headers; never a raw id.
function placeLabel(rows: any[], id: unknown, kind: 'store' | 'branch'): string {
  const row = (rows || []).find((r) => String(r?.id) === String(id));
  return row?.name ? String(row.name) : kind === 'store' ? 'Selected store' : 'Selected branch';
}

function fmtDate(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  return formatWhen(String(value)) || '—';
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
  useCompanyFormat();
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTabParam = searchParams.get('tab');
  const initialTab: Tab = isReportTab(initialTabParam) ? initialTabParam : 'summary';
  const initialView = searchParams.get('view') || '';
  const [tab, setTab] = useState<Tab>(initialTab);
  const [view, setView] = useState(initialView);
  const [reportPage, setReportPage] = useState(0);
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [storeId, setStoreId] = useState('');
  const { storeId: ctxStoreId, setStoreId: setCtxStoreId } = useStoreContext();
  const [branchId, setBranchId] = useState('');
  const [multiStore, setMultiStore] = useState(true);
  const [industry, setIndustry] = useState('');
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
  const tabRef = useRef<Tab>(initialTab);
  const viewRef = useRef(initialView);
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
    const from = isoDateOrEmpty(fromDate);
    const to = isoDateOrEmpty(toDate);
    if (from) params.set('from_date', from);
    if (to) params.set('to_date', to);
    // trim so UuidIdValue Query store/warehouse/branch/department do not 422
    // Prefer page store filter; fall back to Shell header store when page is "All stores"
    const storeTrim = multiStore ? (storeId || ctxStoreId || '').trim() : '';
    const warehouseTrim = warehouseId.trim();
    const branchTrim = multiStore ? branchId.trim() : '';
    const departmentTrim = departmentId.trim();
    if (storeTrim) params.set('store_id', storeTrim);
    if (branchTrim) params.set('branch_id', branchTrim);
    if (departmentTrim) params.set('department_id', departmentTrim);
    if (warehouseTrim) params.set('warehouse_id', warehouseTrim);
    // callers pass category_id (trimmed) in extra when needed
    Object.entries(extra).forEach(([k, v]) => {
      const raw = String(v ?? '').trim();
      if (!raw) return;
      if (k === 'date' || k === 'from_date' || k === 'to_date' || k === 'as_of') {
        const iso = isoDateOrEmpty(raw);
        if (iso) params.set(k, iso);
        return;
      }
      params.set(k, raw);
    });
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  function balanceSheetQs() {
    const params = new URLSearchParams();
    const effectiveAsOf = isoDateOrEmpty(asOf) || isoDateOrEmpty(toDate);
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
    const effectiveAsOf = isoDateOrEmpty(asOf) || isoDateOrEmpty(toDate);
    if (effectiveAsOf) params.set('as_of', effectiveAsOf);
    const storeTrim = (storeId || ctxStoreId || '').trim();
    const branchTrim = branchId.trim();
    if (storeTrim) params.set('store_id', storeTrim);
    if (branchTrim) params.set('branch_id', branchTrim);
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  async function load(nextTab: Tab = tab, viewOverride?: string) {
    const activeView = viewOverride !== undefined ? viewOverride : view;
    viewRef.current = activeView;
    const gen = (loadGen.current[nextTab] || 0) + 1;
    loadGen.current[nextTab] = gen;
    const isStale = () => loadGen.current[nextTab] !== gen || viewRef.current !== activeView;

    function publish(patch: Partial<TabCache>) {
      if (isStale()) return;
      const prev = tabCacheRef.current[nextTab] || emptyTabCache();
      const next = { ...prev, ...patch };
      tabCacheRef.current[nextTab] = next;
      if (tabRef.current !== nextTab || viewRef.current !== activeView) return;
      setData(next.data);
      setError(next.error);
      setGeneratedAt(next.generatedAt);
      setSectionErrors(next.sectionErrors);
      setLoading(next.loading);
    }

    setLoadingTabs((prev) => ({ ...prev, [nextTab]: true }));
    const viewSensitive = nextTab === 'sales' || nextTab === 'inventory' || nextTab === 'purchases';
    publish({
      loading: true,
      error: '',
      sectionErrors: {},
      ...(viewSensitive ? { data: null, generatedAt: '' } : {}),
    });
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
            error: restaurantReports
              ? 'Choose an account, then choose Generate.'
              : 'Select an account for the statement',
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
        const report = reportFromTabView('sales', activeView);
        const categoryTrim = categoryId.trim();
        const extra: Record<string, string> = {};
        if (categoryTrim) extra.category_id = categoryTrim;
        if (report.id === 'sales_summary') {
          const anchor = isoDateOrEmpty(toDate) || isoDateOrEmpty(fromDate);
          const monthQuery: Record<string, string> = {};
          if (anchor && /^\d{4}-\d{2}/.test(anchor)) {
            const [y, m] = anchor.slice(0, 7).split('-');
            monthQuery.year = y;
            monthQuery.month = String(Number(m));
          }
          const [daily, monthly] = await Promise.all([
            fetchReport(`/reports/sales/daily${qs(anchor ? { date: toDate || fromDate } : {})}`),
            fetchReport(`/reports/sales/monthly${qs(monthQuery)}`),
          ]);
          const sections: Record<string, string> = {};
          if (daily.error) sections.daily = daily.error;
          if (monthly.error) sections.monthly = monthly.error;
          const hasData = Boolean(daily.data || monthly.data);
          publish({
            loading: false,
            data: hasData ? { daily: daily.data, monthly: monthly.data } : null,
            error: hasData ? '' : Object.values(sections)[0] || 'Could not load this report.',
            sectionErrors: sections,
            generatedAt: hasData ? new Date().toISOString() : '',
          });
          return;
        }
        let salesPath = `/reports/sales/products${qs(extra)}`;
        if (report.id === 'sales_returns') {
          salesPath = `/reports/sales/returns${qs({
            ...(salesReturnStatus ? { status: salesReturnStatus } : {}),
            ...(salesReturnReason ? { reason: salesReturnReason } : {}),
          })}`;
        } else if (report.id === 'sales_lines') salesPath = `/reports/sales/lines${qs(extra)}`;
        else if (report.id === 'sales_transactions') salesPath = `/reports/sales/transactions${qs()}`;
        else if (report.id === 'sales_payments') salesPath = `/reports/sales/payments${qs()}`;
        else if (report.id === 'sales_discounts') salesPath = `/reports/sales/discounts${qs()}`;
        else if (report.id === 'sales_credit') salesPath = `/reports/sales/credit${qs()}`;
        else if (report.id === 'sales_quotations') salesPath = `/reports/sales/quotations${qs()}`;
        else if (report.id === 'sales_pos') salesPath = `/reports/sales/pos${qs()}`;
        else if (report.id === 'sales_brand') salesPath = `/reports/sales/products${qs()}`;
        const result = await fetchReport(salesPath);
        publish({
          loading: false,
          data: result.data,
          error: result.data ? '' : result.error || 'Could not load this report.',
          sectionErrors: result.error ? { report: result.error } : {},
          generatedAt: result.data ? new Date().toISOString() : '',
        });
        return;
      }

      if (nextTab === 'inventory') {
        const report = reportFromTabView('inventory', activeView);
        const expiryHorizon = String(Math.max(1, Math.min(365, Number(expiryDays) || 30)));
        if (report.view === 'low_stock' || !report.view) {
          const [lowStock, suggestions] = await Promise.all([
            fetchReport(`/reports/inventory/low-stock${qs()}`),
            fetchReport(`/purchasing/suggestions/low-stock${qs()}`),
          ]);
          const sections: Record<string, string> = {};
          if (lowStock.error) sections.lowStock = lowStock.error;
          if (suggestions.error) sections.suggestions = suggestions.error;
          const payload = { lowStock: lowStock.data, suggestions: suggestions.data };
          const hasData = lowStock.data != null || suggestions.data != null;
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
        let result = { data: null as any, error: '' };
        let key = 'valuation';
        if (report.view === 'value') {
          key = 'valuation';
          result = await fetchReport(`/reports/inventory/valuation${qs({ method: valuationMethod })}`);
        } else if (report.view === 'movements') {
          key = 'movements';
          result = await fetchReport(`/reports/inventory/movements${qs()}`);
        } else if (report.view === 'expiry') {
          key = 'expiry';
          result = await fetchReport(`/reports/inventory/expiry${qs({ days: expiryHorizon })}`);
        } else if (report.view === 'rx') {
          key = 'rxActivity';
          result = await fetchReport(`/reports/pharmacy/rx-activity${qs()}`);
        } else if (report.view === 'transfers') {
          key = 'transfers';
          result = await fetchReport(
            `/reports/inventory/transfers${qs(transferStatus ? { status: transferStatus } : {})}`
          );
        } else if (report.view === 'counts') {
          key = 'stockCounts';
          result = await fetchReport(
            `/reports/inventory/stock-counts${qs({
              variance_only: 'true',
              status: stockCountStatus,
            })}`
          );
        }
        const rxDenied = key === 'rxActivity' && /403|INDUSTRY_MODULE/i.test(result.error || '');
        const sections: Record<string, string> = {};
        if (result.error && !rxDenied) sections[key] = result.error;
        const payload = { [key]: rxDenied ? null : result.data };
        const hasData = payload[key] != null;
        publish({
          loading: false,
          data: hasData ? payload : null,
          error: hasData ? '' : result.error || 'Could not load this report.',
          sectionErrors: sections,
          generatedAt: hasData ? new Date().toISOString() : '',
        });
        return;
      }

      if (nextTab === 'purchases') {
        const report = reportFromTabView('purchases', activeView);
        let result = { data: null as any, error: '' };
        let key = 'summary';
        if (report.view === 'suppliers') {
          key = 'suppliers';
          result = await fetchReport(`/reports/purchases/suppliers${qs()}`);
        } else if (report.view === 'pending') {
          key = 'pending';
          result = await fetchReport(
            `/reports/purchases/pending-orders${qs(
              pendingPoStatus ? { status: pendingPoStatus } : {}
            )}`
          );
        } else if (report.view === 'returns') {
          key = 'returns';
          result = await fetchReport(
            `/reports/purchases/returns${qs({
              ...(purchaseReturnStatus ? { status: purchaseReturnStatus } : {}),
              ...(purchaseReturnReason ? { reason: purchaseReturnReason } : {}),
            })}`
          );
        } else {
          key = 'summary';
          result = await fetchReport(`/reports/purchases/summary${qs()}`);
        }
        const sections: Record<string, string> = {};
        if (result.error) sections[key] = result.error;
        const payload = { [key]: result.data };
        const hasData = result.data != null;
        publish({
          loading: false,
          data: hasData ? payload : null,
          error: hasData ? '' : result.error || 'Could not load this report.',
          sectionErrors: sections,
          generatedAt: hasData ? new Date().toISOString() : '',
        });
        return;
      }

      if (nextTab === 'summary') {
        const summary = await fetchReport(path);
        if (isStale()) return;
        let payload = summary.data;
        if (payload && !payload.products_sold) {
          const range =
            !fromDate && !toDate
              ? (() => {
                  const now = new Date();
                  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
                  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0));
                  const iso = (d: Date) => d.toISOString().slice(0, 10);
                  return { from_date: iso(start), to_date: iso(end) };
                })()
              : {};
          const products = await fetchReport(`/reports/sales/products${qs(range)}`);
          if (products.data) payload = { ...payload, products_sold: products.data };
        }
        publish({
          loading: false,
          data: summary.error ? null : payload,
          error: summary.error,
          sectionErrors: {},
          generatedAt: summary.error ? '' : new Date().toISOString(),
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
    getMe()
      .then((me) => {
        setMultiStore(tenantIsMultiStore(me?.data));
        setIndustry(String(me?.data?.industry || ''));
      })
      .catch(() => setMultiStore(true));
    load(tab, view);
    Promise.all([
      getPrefetched('/stores').catch(() => ({ data: [] })),
      getPrefetched('/branches').catch(() => ({ data: [] })),
      getPrefetched('/warehouses').catch(() => ({ data: [] })),
      getPrefetched('/catalog/categories').catch(() => ({ data: [] })),
      getPrefetched('/departments').catch(() => ({ data: [] })),
      getPrefetched('/accounting/accounts').catch(() => ({ data: [] })),
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
    const resolvedView = nextView !== undefined ? nextView : view;
    viewRef.current = resolvedView;
    setTab(t);
    if (nextView !== undefined) setView(nextView);
    const viewSensitive = t === 'sales' || t === 'inventory' || t === 'purchases';
    const cached = viewSensitive ? undefined : tabCacheRef.current[t];
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
    load(t, nextView);
  }

  function selectReport(def: ReportDef) {
    const nextTab = def.tab as Tab;
    const nextView = def.view || '';
    setReportPage(0);
    if (nextTab === tab) {
      viewRef.current = nextView;
      setView(nextView);
      router.replace(reportsHref(def), { scroll: false });
      if (nextTab === 'sales' || nextTab === 'inventory' || nextTab === 'purchases') {
        tabCacheRef.current[nextTab] = emptyTabCache();
      }
      load(nextTab, nextView);
      return;
    }
    switchTab(nextTab, nextView);
  }

  useEffect(() => {
    if (reportVisible(activeReport, { industry, multiStore })) return;
    const fallback =
      activeReport.group === 'inventory' ? findReport('inventory_low_stock') : findReport('summary');
    if (fallback && fallback.id !== activeReport.id) selectReport(fallback);
  }, [industry, multiStore, activeReport.id]);

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
      setReportPage(0);
      load(next, nextView);
    } else if (nextView !== view) {
      const active = isReportTab(next) ? next : tab;
      viewRef.current = nextView;
      setView(nextView);
      setReportPage(0);
      if (active === 'sales' || active === 'inventory' || active === 'purchases') {
        tabCacheRef.current[active] = emptyTabCache();
        load(active, nextView);
      }
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
      setError(hotelReports ? 'Select at least one low-supply line' : restaurantReports ? 'Select at least one low-ingredient line' : 'Select at least one low-stock line');
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
      const params = new URLSearchParams();
      const exportType = reportType || activeReport.exportType || TAB_EXPORT[tab as Exclude<Tab, 'schedules'>];
      if (!exportType) return;
      params.set('report_type', exportType);
      params.set('format', format);
      const fromIso = isoDateOrEmpty(fromDate);
      const toIso = isoDateOrEmpty(toDate);
      if (fromIso) params.set('from_date', fromIso);
      if (toIso) params.set('to_date', toIso);
      // trim so UuidIdValue Query filters do not 422 on whitespace
      const storeTrim = multiStore ? (storeId || ctxStoreId || '').trim() : '';
      const branchTrim = multiStore ? branchId.trim() : '';
      const departmentTrim = departmentId.trim();
      const warehouseTrim = warehouseId.trim();
      const categoryTrim = categoryId.trim();
      if (storeTrim) params.set('store_id', storeTrim);
      if (branchTrim) params.set('branch_id', branchTrim);
      if (exportType === 'sales_daily') {
        const anchor = toIso || fromIso;
        if (anchor) params.set('date', anchor);
      }
      if (exportType === 'sales_monthly') {
        const anchor = toIso || fromIso;
        if (anchor && /^\d{4}-\d{2}/.test(anchor)) {
          const [y, m] = anchor.slice(0, 7).split('-');
          params.set('year', y);
          params.set('month', String(Number(m)));
        }
      }
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
        const effectiveAsOf = isoDateOrEmpty(asOf) || toIso;
        if (effectiveAsOf) params.set('as_of', effectiveAsOf);
        if ((reportType || TAB_EXPORT[tab]) === 'balance_sheet' && compare) {
          params.set('compare', compare);
        }
      }
      if (exportType === 'sales_returns') {
        if (salesReturnStatus) params.set('status', salesReturnStatus);
        if (salesReturnReason) params.set('reason', salesReturnReason);
      }
      if (exportType === 'purchases_returns') {
        if (purchaseReturnStatus) params.set('status', purchaseReturnStatus);
        if (purchaseReturnReason) params.set('reason', purchaseReturnReason);
      }
      if (exportType === 'purchases_pending_orders' && pendingPoStatus) {
        params.set('status', pendingPoStatus);
      }
      if (exportType === 'inventory_transfers' && transferStatus) {
        params.set('status', transferStatus);
      }
      if (exportType === 'inventory_stock_counts' && stockCountStatus) {
        params.set('status', stockCountStatus);
      }
      if ((reportType || TAB_EXPORT[tab]) === 'inventory_expiry' && expiryDays) {
        const d = Math.max(1, Math.min(365, Number(expiryDays) || 30));
        params.set('days', String(d));
      }
      await downloadAttachment(`/reports/export?${params}`, `report.${format}`);
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

  const hotelReports = isHotelIndustry(industry);
  const restaurantReports = !hotelReports && normalizeIndustry(industry) === 'restaurant';
  useEffect(() => {
    if (tab !== 'accountstatement' || statementAccountId.trim() || !industry) return;
    const next = restaurantReports
      ? 'Choose an account, then choose Generate.'
      : 'Select an account for the statement';
    setError((current) =>
      current === '' ||
      current === 'Select an account for the statement' ||
      current === 'Choose an account, then choose Generate.'
        ? next
        : current,
    );
  }, [tab, statementAccountId, industry, restaurantReports]);
  const posHeading = hotelReports ? 'Shop till' : restaurantReports ? 'Restaurant till' : 'POS';
  const invoicePosHeading = hotelReports
    ? 'Checkout invoice / shop till'
    : restaurantReports
      ? 'Bills / restaurant till'
      : 'Invoice / POS';
  const locationScopeNote = hotelReports
    ? ' · this location only (checkout invoices, shop till, expenses, returns)'
    : restaurantReports
      ? ' · this location only (bills, restaurant till, costs, returns)'
      : ' · this location only (sales, till, expenses, returns)';

  return (
    <div className="report-ui-page">
      <PageHeader
        className="no-print"
        title="Reports"
        subtitle={
          isHotelIndustry(industry)
            ? 'Occupancy and room revenue are on Hotel reports. These company reports use the same dates. Export and print use the same filters.'
            : 'Totals for this company. Choose a report, set the dates, then Generate. Export and print use the same filters.'
        }
      />
      <div className="no-print">
        <OfflineProvisionalNotice />
      </div>
      <div className="reports-layout report-ui-layout">
        <nav className="reports-nav" aria-label="Report groups">
          {REPORT_GROUP_ORDER.map((group) => {
            const visibleDefs = reportsInGroup(group.id).filter((def) =>
              reportVisible(def, { industry, multiStore }),
            );
            const groupActive = activeReport.group === group.id;
            return (
            <div
              key={group.id}
              data-group={group.id}
              className={`reports-nav-group${groupActive ? ' is-active' : ''}`}
            >
              <button
                type="button"
                className="reports-nav-cat"
                aria-pressed={groupActive}
                aria-label={`Show ${reportGroupLabel(group.id, group.label, industry)} reports`}
                onClick={() => {
                  if (groupActive) return;
                  const first = visibleDefs[0];
                  if (first) selectReport(first);
                }}
              >
                {reportGroupLabel(group.id, group.label, industry)}
              </button>
              {visibleDefs.map((def) => {
                const id = def.id;
                const selected = activeReport.id === id;
                const busy = !!loadingTabs[def.tab as Tab];
                const shown = reportCopy(def, industry);
                return (
                  <button
                    key={id}
                    type="button"
                    className={`reports-nav-item${selected ? ' is-active' : ''}`}
                    onClick={() => (selected ? load(def.tab as Tab, def.view || '') : selectReport(def))}
                    disabled={busy && selected}
                    aria-pressed={selected}
                    aria-busy={busy && selected}
                    aria-label={`Show reports ${id} tab`}
                  >
                    <strong>{busy && selected ? `${shown.name}…` : shown.name}</strong>
                    <span>{shown.description}</span>
                  </button>
                );
              })}
            </div>
            );
          })}
        </nav>
        <div className="reports-main report-ui-main" data-group={activeReport.group}>
          <p className="reports-crumb muted">
            {reportGroupLabel(
              activeReport.group,
              REPORT_GROUP_ORDER.find((g) => g.id === activeReport.group)?.label || 'Reports',
              industry,
            )}{' '}
            · {reportCopy(activeReport, industry).name}
          </p>
          <h2>{reportCopy(activeReport, industry).name}</h2>
          <p className="muted">{reportCopy(activeReport, industry).description}</p>
          {error && (
            <p style={{ color: '#b91c1c' }} role="alert">
              {error}{' '}
              <button
                type="button"
                onClick={() => load(tab, view)}
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
            <div className="card reports-filters report-ui-filters" style={{ marginBottom: 16 }}>
              {reportHasFilter(activeReport, 'dates') && (
                <>
                  <label>
                    From
                    <input
                      type="date"
                      value={fromDate}
                      onChange={(e) => setFromDate(e.target.value)}
                      title="From date"
                      aria-label="Report from date"
                    />
                  </label>
                  <label>
                    To
                    <input
                      type="date"
                      value={toDate}
                      onChange={(e) => setToDate(e.target.value)}
                      title="To date"
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
              {multiStore && reportHasFilter(activeReport, 'branch') && (
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
              {multiStore && reportHasFilter(activeReport, 'store') && activeReport.group === 'inventory' && (
                <label>
                  Store
                  <select
                    value={storeId || ctxStoreId}
                    onChange={(e) => {
                      setStoreId(e.target.value);
                      setCtxStoreId(e.target.value);
                      if (reportHasFilter(activeReport, 'warehouse')) setWarehouseId('');
                    }}
                    aria-label="Report inventory store filter"
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
              {multiStore && reportHasFilter(activeReport, 'store') && activeReport.group === 'purchases' && (
                <label>
                  Store
                  <select
                    value={storeId || ctxStoreId}
                    onChange={(e) => {
                      setStoreId(e.target.value);
                      setCtxStoreId(e.target.value);
                      if (reportHasFilter(activeReport, 'warehouse')) setWarehouseId('');
                    }}
                    aria-label="Report purchases store filter"
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
              {multiStore &&
                reportHasFilter(activeReport, 'store') &&
                activeReport.group !== 'inventory' &&
                activeReport.group !== 'purchases' && (
                <label>
                  Store
                  <select
                    value={storeId || ctxStoreId}
                    onChange={(e) => {
                      setStoreId(e.target.value);
                      setCtxStoreId(e.target.value);
                      if (reportHasFilter(activeReport, 'warehouse')) setWarehouseId('');
                    }}
                    aria-label="Report financial store filter"
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
              {reportHasFilter(activeReport, 'warehouse') && activeReport.group === 'inventory' && (
                <label>
                  {hotelReports ? 'Location' : restaurantReports ? 'Warehouse' : 'Warehouse'}
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
                    aria-label="Report inventory warehouse filter"
                  >
                    <option value="">{hotelReports ? 'All locations' : restaurantReports ? 'All warehouses' : 'All warehouses'}</option>
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
              {reportHasFilter(activeReport, 'warehouse') && activeReport.group === 'purchases' && (
                <label>
                  {hotelReports ? 'Location' : restaurantReports ? 'Warehouse' : 'Warehouse'}
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
                    aria-label="Report purchases warehouse filter"
                  >
                    <option value="">{hotelReports ? 'All locations' : restaurantReports ? 'All warehouses' : 'All warehouses'}</option>
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
              {reportHasFilter(activeReport, 'warehouse') &&
                activeReport.group !== 'inventory' &&
                activeReport.group !== 'purchases' && (
                <label>
                  {hotelReports ? 'Location' : restaurantReports ? 'Warehouse' : 'Warehouse'}
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
                    <option value="">{hotelReports ? 'All locations' : restaurantReports ? 'All warehouses' : 'All warehouses'}</option>
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
                      <option value="wrong_item">{hotelReports ? 'wrong supply' : restaurantReports ? 'wrong menu item' : 'wrong item'}</option>
                      <option value="defective">defective</option>
                      <option value="customer_change">{hotelReports ? 'guest change' : restaurantReports ? 'diner change' : 'customer change'}</option>
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
                      <option value="wrong_item">{hotelReports ? 'wrong supply' : restaurantReports ? 'wrong ingredient' : 'wrong item'}</option>
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
                  onClick={() => load(tab, view)}
                  disabled={!!loadingTabs[tab]}
                  aria-label="Apply report filters"
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
                    {activeReport.id === 'customers' && (
                      <button type="button" onClick={() => download('xlsx', 'sales_customers')} aria-label="Export sales customers Excel">
                        Customers Excel
                      </button>
                    )}
                    {activeReport.id === 'stores' && (
                      <button type="button" onClick={() => download('xlsx', 'sales_by_store')} aria-label="Export sales by store Excel">
                        Stores Excel
                      </button>
                    )}
                    {activeReport.id === 'salesperson' && (
                      <button type="button" onClick={() => download('xlsx', 'sales_salesperson')} aria-label="Export salespeople Excel">
                        Salespeople Excel
                      </button>
                    )}
                    {activeReport.id === 'sales_returns' && (
                      <>
                        <button type="button" onClick={() => download('xlsx', 'sales_returns')} aria-label="Export sales returns Excel">
                          Returns Excel
                        </button>
                        <button type="button" onClick={() => download('csv', 'sales_returns')} aria-label="Export sales returns CSV">
                          Returns CSV
                        </button>
                      </>
                    )}
                    {activeReport.id === 'trialbalance' && (
                      <>
                        <button type="button" onClick={() => download('xlsx', 'trial_balance')} aria-label="Export trial balance Excel">
                          Trial balance Excel
                        </button>
                        <button type="button" onClick={() => download('csv', 'trial_balance')} aria-label="Export trial balance CSV">
                          Trial balance CSV
                        </button>
                      </>
                    )}
                    {activeReport.id === 'pnl' && (
                      <button type="button" onClick={() => download('pdf', 'profit_loss')} aria-label="Export P&L PDF">
                        P&L PDF
                      </button>
                    )}
                    {activeReport.id === 'purchases_pending' && (
                      <>
                        <button type="button" onClick={() => download('xlsx', 'purchases_pending_orders')} aria-label="Export purchases pending orders Excel">
                          Pending orders Excel
                        </button>
                        <button type="button" onClick={() => download('csv', 'purchases_pending_orders')} aria-label="Export purchases pending orders CSV">
                          Pending orders CSV
                        </button>
                      </>
                    )}
                    {activeReport.id === 'purchases_returns' && (
                      <>
                        <button type="button" onClick={() => download('xlsx', 'purchases_returns')} aria-label="Export purchases returns Excel">
                          Purchase returns Excel
                        </button>
                        <button type="button" onClick={() => download('csv', 'purchases_returns')} aria-label="Export purchases returns CSV">
                          Purchase returns CSV
                        </button>
                      </>
                    )}
                  </>
                ) : null}
                {activeReport.id === 'sales_summary' ? (
                  <>
                    <button type="button" onClick={() => download('csv', 'sales_daily')} aria-label="Export sales daily CSV">
                      Day CSV
                    </button>
                    <button type="button" onClick={() => download('xlsx', 'sales_daily')} aria-label="Export sales daily Excel">
                      Day Excel
                    </button>
                    <button type="button" onClick={() => download('csv', 'sales_monthly')} aria-label="Export sales monthly CSV">
                      Month CSV
                    </button>
                    <button type="button" onClick={() => download('xlsx', 'sales_monthly')} aria-label="Export sales monthly Excel">
                      Month Excel
                    </button>
                  </>
                ) : null}
                {activeReport.print ? (
                  <button
                    type="button"
                    onClick={() => {
                      const sheet = document.querySelector('.report-ui-page .report-sheet');
                      if (!(sheet instanceof HTMLElement) || !printDocumentFromElement(sheet, activeReport.name || 'Report')) {
                        setError('Print failed');
                      }
                    }}
                    aria-label="Print report"
                  >
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
            <EmptyState title="Set the dates and filters you need, then choose Generate." />
          ) : null}

      {tab === 'summary' && data && (
        <div className="report-sheet">
        <div className="grid">
          <div className="card">
            <div className="muted">Today sales</div>
            <div className="kpi">{fmtMoney(data.today_sales?.total_revenue)}</div>
            {restaurantReports ? (
              <p className="muted">A restaurant till return comes off today sales. The original receipt stays on the till report.</p>
            ) : null}
          </div>
          <div className="card">
            <div className="muted">Month sales</div>
            <div className="kpi">{fmtMoney(data.month_sales?.total_revenue)}</div>
            {data.month_sales?.change_pct != null ? (
              <p className="muted">
                {Number(data.month_sales.change_pct) >= 0 ? '+' : ''}
                {data.month_sales.change_pct}% on last month
              </p>
            ) : null}
          </div>
          <div className="card no-print">
            <div className="muted">{hotelReports ? 'Low supplies' : restaurantReports ? 'Low ingredients' : 'Low stock SKUs'}</div>
            <div className="kpi">{data.low_stock_report?.count ?? 0}</div>
          </div>
          <div className="card no-print">
            <div className="muted">Approved expenses</div>
            <div className="kpi">{fmtMoney(data.expenses_summary?.total_amount)}</div>
          </div>
        </div>
        <h3 style={{ marginTop: 16 }}>{hotelReports ? 'Items sold' : restaurantReports ? 'Menu items sold' : 'Products sold'}</h3>
        <p className="muted">
          Qty {formatNumber(data.products_sold?.total_quantity)} · revenue {fmtMoney(data.products_sold?.total_revenue)}
        </p>
        {restaurantReports ? (
          <>
            <p className="muted">Menu item cost uses the ingredient cost. A menu item with no recipe uses its own cost. A restaurant till return comes off menu items sold. The original receipt stays on the till report.</p>
            <p className="muted">A restaurant till tax stays off this menu amount. The till receipt keeps the tax.</p>
          </>
        ) : null}
        <div className={restaurantReports ? 'list-table-wrap rest-sold-table' : 'list-table-wrap'}>
          <table className="table">
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '52%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '30%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {hotelReports ? <th>Supply</th> : restaurantReports ? <th>Menu item</th> : <th>Product</th>}
                {restaurantReports ? null : <th>SKU</th>}
                {restaurantReports ? <th>Sold</th> : <th>Qty</th>}
                <th>Revenue</th>
              </tr>
            </thead>
            <tbody>
              {(data.products_sold?.products || []).map((p: any) => (
                <tr key={p.product_id}>
                  {restaurantReports ? (
                    <td data-label="Menu item">
                      {p.name}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {p.sku || 'No code'}
                      </span>
                    </td>
                  ) : (
                    <td>{p.name}</td>
                  )}
                  {restaurantReports ? null : <td>{p.sku || '—'}</td>}
                  <td data-label={restaurantReports ? 'Sold' : undefined}>{formatNumber(p.quantity)}</td>
                  <td data-label={restaurantReports ? 'Revenue' : undefined}>{fmtMoney(p.revenue)}</td>
                </tr>
              ))}
              {(data.products_sold?.products || []).length === 0 && (
                <tr>
                  <td colSpan={restaurantReports ? 3 : 4} className="muted">
                    {hotelReports ? 'No items sold in this period' : restaurantReports ? 'No menu items sold in this period' : 'No products sold in this period'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        </div>
      )}

      {tab === 'sales' && data && (
        <div className="report-sheet">
          <SalesReportSheets
            view={activeReport.view || 'products'}
            data={data}
            sectionErrors={sectionErrors}
            multiStore={multiStore}
            hotel={hotelReports}
            restaurant={restaurantReports}
            fmtMoney={fmtMoney}
            formatWhen={formatWhen}
            page={reportPage}
            onPage={setReportPage}
          />
        </div>
      )}

      {tab === 'salesperson' && data && (
        <>
          {restaurantReports ? (
            <>
              <p className="muted">A restaurant till return comes off this staff member. The original receipt stays on the till report.</p>
              <p className="muted">A completed restaurant bill is included for the staff member who rang it.</p>
            </>
          ) : null}
          <div className="grid">
            <div className="card">
              <div className="muted">Total revenue{data.store_name ? ` · ${data.store_name}` : ''}</div>
              <div className="kpi">{fmtMoney(data.total_revenue ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">Sales count</div>
              <div className="kpi">{data.total_sales ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">{invoicePosHeading}</div>
              <div className="kpi">
                {fmtMoney(data.invoice_revenue ?? 0)} / {fmtMoney(data.pos_revenue ?? 0)}
              </div>
            </div>
          </div>
          <div className={restaurantReports ? 'list-table-wrap rest-staff-sales' : 'list-table-wrap'}>
          <table className="table" style={{ marginTop: 16 }}>
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '34%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '22%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {restaurantReports ? <th>Staff</th> : <th>Name</th>}
                {restaurantReports ? null : <th>Department</th>}
                {restaurantReports ? null : <th>Role</th>}
                {restaurantReports ? <th>Bills</th> : <th>Invoices</th>}
                {restaurantReports ? <th>Restaurant till</th> : <th>{posHeading}</th>}
                {restaurantReports ? null : <th>Sales</th>}
                <th>Revenue</th>
                {restaurantReports ? null : <th>Avg ticket</th>}
              </tr>
            </thead>
            <tbody>
              {(data.salespeople || []).map((s: any) => (
                <tr key={s.user_id || s.full_name}>
                  {restaurantReports ? (
                    <td data-label="Staff">
                      {s.full_name}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {s.department_name || 'No department'}
                        {s.role ? ` · ${s.role}` : ' · No role'}
                      </span>
                    </td>
                  ) : (
                    <td>{s.full_name}</td>
                  )}
                  {restaurantReports ? null : <td>{s.department_name || '—'}</td>}
                  {restaurantReports ? null : <td>{s.role || '—'}</td>}
                  {restaurantReports ? (
                    <td data-label="Bills">
                      {s.invoice_count}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {fmtMoney(s.invoice_revenue)}
                      </span>
                    </td>
                  ) : (
                    <td>
                      {s.invoice_count} ({fmtMoney(s.invoice_revenue)})
                    </td>
                  )}
                  {restaurantReports ? (
                    <td data-label="Restaurant till">
                      {s.pos_count}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {fmtMoney(s.pos_revenue)}
                      </span>
                    </td>
                  ) : (
                    <td>
                      {s.pos_count} ({fmtMoney(s.pos_revenue)})
                    </td>
                  )}
                  {restaurantReports ? null : <td>{s.sale_count}</td>}
                  {restaurantReports ? (
                    <td data-label="Revenue">
                      {fmtMoney(s.revenue)}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        Average bill {fmtMoney(s.avg_ticket)}
                      </span>
                    </td>
                  ) : (
                    <>
                      <td>{fmtMoney(s.revenue)}</td>
                      <td>{fmtMoney(s.avg_ticket)}</td>
                    </>
                  )}
                </tr>
              ))}
              {!(data.salespeople || []).length ? (
                <tr>
                  <td colSpan={restaurantReports ? 4 : 8} className="muted">
                    {restaurantReports
                      ? 'No staff sales for these dates. Widen the dates, then choose Generate.'
                      : 'No staff sales for these dates; widen the dates, then choose Generate.'}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'customers' && data && (
        <>
          <p className="muted">
            Top customers by revenue ({hotelReports ? 'checkout invoices + shop till' : restaurantReports ? 'bills + restaurant till' : 'invoices + POS'})
            {data.store_id ? ` · ${placeLabel(stores, data.store_id, 'store')}` : ''}
          </p>
          {restaurantReports ? (
            <>
              <p className="muted">A restaurant till return comes off this customer. The original receipt stays on the till report.</p>
              <p className="muted">A completed restaurant bill is included for this customer.</p>
            </>
          ) : null}
          <div className="grid">
            <div className="card">
              <div className="muted">Total revenue</div>
              <div className="kpi">{fmtMoney(data.total_revenue ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">Customers</div>
              <div className="kpi">{data.customer_count ?? data.customers?.length ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">{hotelReports ? 'Sales / checkout invoice·shop till' : restaurantReports ? 'Sales / bill·restaurant till' : 'Sales / Invoice·POS'}</div>
              <div className="kpi">
                {data.total_sales ?? 0} · {fmtMoney(data.invoice_revenue ?? 0)}/{fmtMoney(data.pos_revenue ?? 0)}
              </div>
            </div>
          </div>
          <div className={restaurantReports ? 'list-table-wrap rest-cust-sales' : 'list-table-wrap'}>
          <table className="table" style={{ marginTop: 16 }}>
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '34%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '22%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                <th>Customer</th>
                {restaurantReports ? <th>Bills</th> : <th>Invoices</th>}
                {restaurantReports ? <th>Restaurant till</th> : <th>{posHeading}</th>}
                {restaurantReports ? null : <th>Frequency</th>}
                <th>Revenue</th>
                {restaurantReports ? null : <th>Avg ticket</th>}
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(data.customers) ? data.customers : []).map((c: any) => (
                <tr key={c.customer_id || c.name}>
                  {restaurantReports ? (
                    <td data-label="Customer">
                      {c.name}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {c.email || 'No email'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        Visits {c.sale_count}
                      </span>
                    </td>
                  ) : (
                    <td>
                      {c.name}
                      {c.email ? (
                        <span className="muted" style={{ display: 'block', fontSize: 12 }}>
                          {c.email}
                        </span>
                      ) : null}
                    </td>
                  )}
                  {restaurantReports ? (
                    <td data-label="Bills">
                      {c.invoice_count}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {fmtMoney(c.invoice_revenue)}
                      </span>
                    </td>
                  ) : (
                    <td>
                      {c.invoice_count} ({fmtMoney(c.invoice_revenue)})
                    </td>
                  )}
                  {restaurantReports ? (
                    <td data-label="Restaurant till">
                      {c.pos_count}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {fmtMoney(c.pos_revenue)}
                      </span>
                    </td>
                  ) : (
                    <td>
                      {c.pos_count} ({fmtMoney(c.pos_revenue)})
                    </td>
                  )}
                  {restaurantReports ? null : <td>{c.sale_count}</td>}
                  {restaurantReports ? (
                    <td data-label="Revenue">
                      {fmtMoney(c.revenue)}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        Average bill {fmtMoney(c.avg_ticket)}
                      </span>
                    </td>
                  ) : (
                    <>
                      <td>{fmtMoney(c.revenue)}</td>
                      <td>{fmtMoney(c.avg_ticket)}</td>
                    </>
                  )}
                </tr>
              ))}
              {!data.customers?.length && (
                <tr>
                  <td colSpan={restaurantReports ? 4 : 6} className="muted">
                    {restaurantReports
                      ? 'No customer sales for these dates. Widen the dates, then choose Generate.'
                      : 'No customer sales for these dates; widen the dates, then choose Generate.'}
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
          {restaurantReports ? (
            <>
              <p className="muted">A restaurant till return comes off this store. The original receipt stays on the till report.</p>
              <p className="muted">A completed restaurant bill is included for the store on the bill.</p>
            </>
          ) : null}
          <div className="grid">
            <div className="card">
              <div className="muted">Total revenue</div>
              <div className="kpi">{fmtMoney(data.total_revenue ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">Sales count</div>
              <div className="kpi">{data.total_sales ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">{invoicePosHeading}</div>
              <div className="kpi">
                {fmtMoney(data.invoice_revenue ?? 0)} / {fmtMoney(data.pos_revenue ?? 0)}
              </div>
            </div>
          </div>
          <div className="list-table-wrap">
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>{hotelReports ? 'Location' : restaurantReports ? 'Store' : 'Store'}</th>
                <th>Code</th>
                <th>Invoices</th>
                <th>{posHeading}</th>
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
                    {s.invoice_count} ({fmtMoney(s.invoice_revenue)})
                  </td>
                  <td>
                    {s.pos_count} ({fmtMoney(s.pos_revenue)})
                  </td>
                  <td>{s.sale_count}</td>
                  <td>{fmtMoney(s.revenue)}</td>
                  <td>{fmtMoney(s.avg_ticket)}</td>
                </tr>
              ))}
              {!(data.stores || []).length ? (
                <tr>
                  <td colSpan={7} className="muted">
                    {hotelReports
                      ? 'No location sales for these dates; widen the dates, then choose Generate.'
                      : 'No store sales for these dates; widen the dates, then choose Generate.'}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'departments' && data && (
        <>
          {restaurantReports ? (
            <>
              <p className="muted">A restaurant till return comes off this department. The original receipt stays on the till report.</p>
              <p className="muted">A completed restaurant bill is included for the department of the staff member who rang it.</p>
            </>
          ) : null}
          <div className="grid">
            <div className="card">
              <div className="muted">Total revenue</div>
              <div className="kpi">{fmtMoney(data.total_revenue ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">Sales count</div>
              <div className="kpi">{data.total_sales ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">{invoicePosHeading}</div>
              <div className="kpi">
                {fmtMoney(data.invoice_revenue ?? 0)} / {fmtMoney(data.pos_revenue ?? 0)}
              </div>
            </div>
          </div>
          {data.department_name ? (
            <p className="muted" style={{ marginTop: 12 }}>
              Filtered to {data.department_name}
            </p>
          ) : null}
          <div className={restaurantReports ? 'list-table-wrap rest-dept-sales' : 'list-table-wrap'}>
          <table className="table" style={{ marginTop: 16 }}>
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '34%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '22%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                <th>Department</th>
                {restaurantReports ? null : <th>Code</th>}
                {restaurantReports ? <th>Bills</th> : <th>Invoices</th>}
                {restaurantReports ? <th>Restaurant till</th> : <th>{posHeading}</th>}
                {restaurantReports ? null : <th>Sales</th>}
                <th>Revenue</th>
                {restaurantReports ? null : <th>Avg ticket</th>}
              </tr>
            </thead>
            <tbody>
              {(data.departments || []).map((d: any) => (
                <tr key={d.department_id || d.name}>
                  {restaurantReports ? (
                    <td data-label="Department">
                      {d.name}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {d.code || 'No code'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        Sales {d.sale_count}
                      </span>
                    </td>
                  ) : (
                    <td>{d.name}</td>
                  )}
                  {restaurantReports ? null : <td>{d.code || '—'}</td>}
                  {restaurantReports ? (
                    <td data-label="Bills">
                      {d.invoice_count}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {fmtMoney(d.invoice_revenue)}
                      </span>
                    </td>
                  ) : (
                    <td>
                      {d.invoice_count} ({fmtMoney(d.invoice_revenue)})
                    </td>
                  )}
                  {restaurantReports ? (
                    <td data-label="Restaurant till">
                      {d.pos_count}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {fmtMoney(d.pos_revenue)}
                      </span>
                    </td>
                  ) : (
                    <td>
                      {d.pos_count} ({fmtMoney(d.pos_revenue)})
                    </td>
                  )}
                  {restaurantReports ? null : <td>{d.sale_count}</td>}
                  {restaurantReports ? (
                    <td data-label="Revenue">
                      {fmtMoney(d.revenue)}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        Average bill {fmtMoney(d.avg_ticket)}
                      </span>
                    </td>
                  ) : (
                    <>
                      <td>{fmtMoney(d.revenue)}</td>
                      <td>{fmtMoney(d.avg_ticket)}</td>
                    </>
                  )}
                </tr>
              ))}
              {!data.departments?.length && (
                <tr>
                  <td colSpan={restaurantReports ? 4 : 7} className="muted">
                    {restaurantReports
                      ? 'No department sales for these dates. Widen the dates, then choose Generate.'
                      : 'No department sales for these dates; widen the dates, then choose Generate.'}
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
                {hotelReports ? 'Low-supply suggestions' : restaurantReports ? 'Low-ingredient suggestions' : 'Low-stock suggestions'} ({data.suggestions?.count ?? data.lowStock?.count ?? 0})
              </h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                  value={suggestNotes}
                  onChange={(e) => setSuggestNotes(e.target.value)}
                  placeholder="Notes for the purchase request (optional)"
                  aria-label="Low-stock suggestion notes"
                  title="Notes for the purchase request (optional)"
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
              {hotelReports ? 'Low supplies' : restaurantReports ? 'Low ingredients' : 'Low stock'} {data.count ?? data.suggestions?.count ?? data.lowStock?.count ?? 0}
              {data.out_of_stock_count != null || data.lowStock?.out_of_stock_count != null
                ? hotelReports
                  ? ` · none left ${data.out_of_stock_count ?? data.lowStock?.out_of_stock_count}`
                  : ` · out of stock ${data.out_of_stock_count ?? data.lowStock?.out_of_stock_count}`
                : ''}
              . {hotelReports
                ? 'Select supplies to create draft purchase requests, then approve them in Purchasing.'
                : restaurantReports
                  ? 'Select ingredients to create draft purchase requests, then approve them in Purchasing.'
                  : 'Select items to create draft purchase requests, then approve them in Purchasing.'}
            </p>
            {(data.suggestions?.lines || []).length === 0 ? (
              <p className="muted">
                {hotelReports
                  ? 'No supplies need reordering (or all are already on an open purchase request).'
                  : restaurantReports
                    ? 'No ingredients need reordering (or all are already on an open purchase request).'
                    : 'No actionable low-stock lines (or all already on an open PR).'}
              </p>
            ) : (
              <div className="list-table-wrap">
              <table className="table" style={{ marginTop: 8 }}>
                <thead>
                  <tr>
                    <th></th>
                    <th>{hotelReports ? 'Supply' : restaurantReports ? 'Ingredient' : 'Product'}</th>
                    <th>SKU</th>
                    <th>On hand</th>
                    <th>Reorder</th>
                    <th>Suggest qty</th>
                    <th>{hotelReports ? 'Location' : restaurantReports ? 'Warehouse' : 'Warehouse'}</th>
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
            <h3>{hotelReports ? 'Low supplies' : restaurantReports ? 'Low ingredients' : 'Low stock products'} ({data.lowStock?.count ?? 0})</h3>
            <p className="muted" style={{ marginBottom: 8 }}>
              {data.lowStock?.store_name
                ? data.lowStock.store_name
                : data.lowStock?.warehouse_id
                  ? hotelReports
                    ? 'Location filtered'
                    : 'Warehouse filtered'
                  : hotelReports
                    ? 'Company-wide supply reorder'
                    : restaurantReports
                      ? 'Company-wide ingredient reorder'
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
                <h4 style={{ marginTop: 12 }}>{hotelReports ? 'Location reorder breaches' : restaurantReports ? 'Warehouse reorder breaches' : 'Warehouse reorder breaches'}</h4>
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
            <h3>{hotelReports ? 'Supply valuation (standard cost)' : restaurantReports ? 'Ingredient valuation (standard cost)' : 'Stock valuation (standard cost)'}</h3>
            <p className="muted">
              Method: standard
              {data.valuation?.store_name
                ? ` · ${data.valuation.store_name}`
                : data.valuation?.warehouse_name
                  ? ` · ${data.valuation.warehouse_name}`
                  : data.valuation?.warehouse_id
                    ? hotelReports
                      ? ' · location filtered'
                      : ' · warehouse filtered'
                    : hotelReports
                      ? ' · company supplies'
                      : restaurantReports
                        ? ' · company ingredients'
                        : ' · company stock'}
            </p>
            <div className="grid">
              <div>
                <div className="muted">Total qty</div>
                <div className="kpi">{formatNumber(data.valuation?.total_quantity ?? 0)}</div>
              </div>
              <div>
                <div className="muted">Total value</div>
                <div className="kpi">{fmtMoney(data.valuation?.total_value ?? 0)}</div>
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
            <h3>{hotelReports ? 'Supply movements' : restaurantReports ? 'Ingredient movements' : 'Stock movements'}</h3>
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
            <div className={restaurantReports ? 'list-table-wrap rest-ing-move' : 'list-table-wrap'}>
            <table className="table">
              {restaurantReports ? (
                <colgroup>
                  <col style={{ width: '34%' }} />
                  <col style={{ width: '24%' }} />
                  <col style={{ width: '20%' }} />
                  <col style={{ width: '22%' }} />
                </colgroup>
              ) : null}
              <thead>
                <tr>
                  <th>{hotelReports ? 'Supply' : restaurantReports ? 'Ingredient' : 'Product'}</th>
                  {restaurantReports ? null : <th>SKU</th>}
                  <th>When</th>
                  {restaurantReports ? <th>Change</th> : <th>Type</th>}
                  {restaurantReports ? <th>Record</th> : <th>Reason</th>}
                  {restaurantReports ? null : <th>Qty</th>}
                  {restaurantReports ? null : <th>Before → after</th>}
                  {restaurantReports ? null : <th>User</th>}
                  {restaurantReports ? null : <th>Ref</th>}
                </tr>
              </thead>
              <tbody>
                {(data.movements?.movements || []).slice(0, 25).map((mv: any) => (
                  <tr key={mv.id}>
                    {restaurantReports ? (
                      <td data-label="Ingredient">
                        {mv.product_name || (mv.product_id ? String(mv.product_id).slice(0, 8) : 'No ingredient')}
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {mv.product_sku || 'No code'}
                        </span>
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {mv.created_by_name || mv.created_by_email || 'No person'}
                        </span>
                      </td>
                    ) : (
                      <td>{mv.product_name || (mv.product_id ? String(mv.product_id).slice(0, 8) : '—')}</td>
                    )}
                    {restaurantReports ? null : <td>{mv.product_sku || '—'}</td>}
                    {restaurantReports ? (
                      <td data-label="When">
                        {fmtDate(mv.created_at)}
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {mv.movement_type ? plainLabel(mv.movement_type) : 'No type'}
                          {' · '}
                          {mv.reason ? plainLabel(mv.reason) : 'No reason'}
                        </span>
                      </td>
                    ) : (
                      <td>{fmtDate(mv.created_at)}</td>
                    )}
                    {restaurantReports ? (
                      <td data-label="Change">
                        {mv.quantity}
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          Was {mv.quantity_before} · Now {mv.quantity_after}
                        </span>
                      </td>
                    ) : (
                      <td>{mv.movement_type}</td>
                    )}
                    {restaurantReports ? (
                      <td data-label="Record">
                        {mv.reference_type ? plainLabel(mv.reference_type) : 'No record'}
                        {mv.reference_id ? ` ${String(mv.reference_id).slice(0, 8)}` : ''}
                      </td>
                    ) : (
                      <td>{mv.reason || '—'}</td>
                    )}
                    {restaurantReports ? null : <td>{mv.quantity}</td>}
                    {restaurantReports ? null : (
                      <td>
                        {mv.quantity_before} → {mv.quantity_after}
                      </td>
                    )}
                    {restaurantReports ? null : <td>{mv.created_by_name || mv.created_by_email || '—'}</td>}
                    {restaurantReports ? null : (
                      <td>
                        {mv.reference_type || '—'}
                        {mv.reference_id ? ` ${String(mv.reference_id).slice(0, 8)}…` : ''}
                      </td>
                    )}
                  </tr>
                ))}
                {!data.movements?.movements?.length && (
                  <tr>
                    <td colSpan={restaurantReports ? 4 : 9} className="muted">
                      {hotelReports
                        ? 'No supply movements for these dates; widen the dates, then choose Generate.'
                        : restaurantReports
                          ? 'No ingredient movements for these dates. Widen the dates, then choose Generate.'
                          : 'No stock movements for these dates; widen the dates, then choose Generate.'}
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
            {hotelReports ? 'Supply value' : restaurantReports ? 'Ingredient value' : 'Stock value'}: {fmtMoney(data.valuation?.total_value)}
          </h3>
          {restaurantReports ? (
            <>
            <p className="muted">A completed restaurant bill takes this store value down when the stock sits in that store's warehouse.</p>
            <p className="muted">A restaurant till return puts the stock back in the store on the original receipt.</p>
            </>
          ) : null}
          <div className={restaurantReports ? 'list-table-wrap rest-ing-value' : 'list-table-wrap'}>
          <table className="table">
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '20%' }} />
                <col style={{ width: '22%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                <th>{hotelReports ? 'Supply' : restaurantReports ? 'Ingredient' : 'Product'}</th>
                {restaurantReports ? null : <th>SKU</th>}
                {restaurantReports ? <th>On hand</th> : <th>Qty</th>}
                <th>Unit cost</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {(data.valuation?.items || []).slice(0, 50).map((i: any) => (
                <tr key={i.product_id}>
                  {restaurantReports ? (
                    <td data-label="Ingredient">
                      {i.name}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {i.sku || 'No code'}
                      </span>
                    </td>
                  ) : (
                    <td>{i.name}</td>
                  )}
                  {restaurantReports ? null : <td>{i.sku || '—'}</td>}
                  <td data-label={restaurantReports ? 'On hand' : undefined}>{formatNumber(i.quantity)}</td>
                  <td data-label={restaurantReports ? 'Unit cost' : undefined}>
                    {i.unit_cost != null || i.cost_price != null
                      ? fmtMoney(i.unit_cost ?? i.cost_price)
                      : restaurantReports
                        ? 'No cost'
                        : '—'}
                  </td>
                  <td data-label={restaurantReports ? 'Value' : undefined}>{fmtMoney(i.value)}</td>
                </tr>
              ))}
              {restaurantReports && !(data.valuation?.items || []).length ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No ingredients to value yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          </div>
          </>
          )}
          {activeReport.view === 'expiry' && (
          <>
          <h3 style={{ marginTop: 16 }}>{restaurantReports ? 'Lots nearing expiry' : 'Expiry'}</h3>
          <p className="muted">
            {data.expiry?.count ?? 0} {hotelReports ? 'lots' : restaurantReports ? 'lots' : 'batches'} within {data.expiry?.within_days ?? expiryDays} days ·
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
          <div className={restaurantReports ? 'list-table-wrap rest-expiry' : 'list-table-wrap'}>
          <table className="table">
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '24%' }} />
                <col style={{ width: '18%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                <th>{hotelReports ? 'Supply' : restaurantReports ? 'Ingredient' : 'Product'}</th>
                {restaurantReports ? null : <th>SKU</th>}
                <th>{hotelReports ? 'Lot' : restaurantReports ? 'Lot' : 'Batch'}</th>
                <th>Expiry</th>
                {restaurantReports ? null : <th>Days</th>}
                <th>Qty</th>
              </tr>
            </thead>
            <tbody>
              {(data.expiry?.batches || []).map((b: any) => (
                <tr key={b.id}>
                  {restaurantReports ? (
                    <td data-label="Ingredient">
                      {b.name || 'No ingredient'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {b.sku || 'No code'}
                      </span>
                    </td>
                  ) : (
                    <td>{b.name || '—'}</td>
                  )}
                  {restaurantReports ? null : <td>{b.sku || '—'}</td>}
                  <td data-label={restaurantReports ? 'Lot' : undefined}>{b.batch_number || (restaurantReports ? 'No lot' : '—')}</td>
                  {restaurantReports ? (
                    <td data-label="Expiry">
                      {b.expiry_date ? fmtDate(b.expiry_date) : 'No date'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {b.days_until_expiry == null
                          ? 'No day count'
                          : Number(b.days_until_expiry) < 0
                            ? `Expired ${Math.abs(Number(b.days_until_expiry))} days`
                            : `Days left ${b.days_until_expiry}`}
                      </span>
                    </td>
                  ) : (
                    <td>{fmtDate(b.expiry_date)}</td>
                  )}
                  {restaurantReports ? null : <td>{b.days_until_expiry ?? '—'}</td>}
                  <td data-label={restaurantReports ? 'Qty' : undefined}>{b.quantity}</td>
                </tr>
              ))}
                {!data.expiry?.batches?.length && (
                <tr>
                  <td colSpan={restaurantReports ? 4 : 6} className="muted">
                    {restaurantReports
                      ? 'No lots nearing expiry for this filter.'
                      : 'No batches nearing expiry for this filter.'}
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
                  <td>{plainLabel(row.status)}</td>
                  <td>{row.customer_name || '—'}</td>
                  <td>{row.sale_number || '—'}</td>
                  <td>{row.qty_remaining}</td>
                </tr>
              ))}
              {!data.rxActivity?.prescriptions?.length && (
                <tr>
                  <td colSpan={5} className="muted">
                    No prescriptions for these dates.
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
                    No transfers for these filters; change the dates or status, then choose Generate.
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
            <h3>{hotelReports ? 'Supply count variances' : restaurantReports ? 'Ingredient count variances' : 'Stock count variances'}</h3>
            <p className="muted">
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
            <div className={restaurantReports ? 'list-table-wrap rest-count-var' : 'list-table-wrap'}>
            <table className="table">
              {restaurantReports ? (
                <colgroup>
                  <col style={{ width: '40%' }} />
                  <col style={{ width: '22%' }} />
                  <col style={{ width: '20%' }} />
                  <col style={{ width: '18%' }} />
                </colgroup>
              ) : null}
              <thead>
                <tr>
                  <th>{hotelReports ? 'Supply' : restaurantReports ? 'Ingredient' : 'Product'}</th>
                  {restaurantReports ? null : <th>SKU</th>}
                  {restaurantReports ? null : <th>Count</th>}
                  {restaurantReports ? <th>Warehouse</th> : <th>{hotelReports ? 'Location' : 'Warehouse'}</th>}
                  {restaurantReports ? <th>Counted</th> : <th>Expected</th>}
                  {restaurantReports ? <th>Variance</th> : <th>Counted</th>}
                  {restaurantReports ? null : <th>Variance</th>}
                </tr>
              </thead>
              <tbody>
                {(data.stockCounts?.lines || []).slice(0, 40).map((line: any, idx: number) => (
                  <tr key={`${line.count_id}-${line.product_id}-${idx}`}>
                    {restaurantReports ? (
                      <td data-label="Ingredient">
                        {line.name || 'No ingredient'}
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {line.sku || 'No code'}
                        </span>
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {line.count_number || 'No count'}
                        </span>
                      </td>
                    ) : (
                      <td>{line.name || '—'}</td>
                    )}
                    {restaurantReports ? null : <td>{line.sku || '—'}</td>}
                    {restaurantReports ? null : <td>{line.count_number}</td>}
                    <td data-label={restaurantReports ? 'Warehouse' : undefined}>
                      {line.warehouse_name || (restaurantReports ? 'No warehouse' : '—')}
                    </td>
                    {restaurantReports ? (
                      <td data-label="Counted">
                        {line.counted_qty}
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          Expected {line.expected_qty}
                        </span>
                      </td>
                    ) : (
                      <td>{line.expected_qty}</td>
                    )}
                    {restaurantReports ? (
                      <td data-label="Variance">{line.variance}</td>
                    ) : (
                      <td>{line.counted_qty}</td>
                    )}
                    {restaurantReports ? null : <td>{line.variance}</td>}
                  </tr>
                ))}
                {!data.stockCounts?.lines?.length && (
                  <tr>
                    <td colSpan={restaurantReports ? 4 : 7} className="muted">
                      {hotelReports
                        ? 'No supply count variances for this filter'
                        : restaurantReports
                          ? 'No ingredient count variances for this filter.'
                          : 'No stock count variances for this filter'}
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
            {restaurantReports ? (
              <>
                {data.returns?.return_count ?? 0}{' '}
                {(data.returns?.return_count ?? 0) === 1 ? 'return' : 'returns'}
                {' · Total '}
                {fmtMoney(data.returns?.total_amount)}
                {' · Posted '}
                {fmtMoney(data.returns?.posted_amount)}
                {' · Quantity '}
                {data.returns?.total_quantity ?? 0}
              </>
            ) : (
              <>
                {data.returns?.return_count ?? 0} returns · total {fmtMoney(data.returns?.total_amount)} ·
                posted {fmtMoney(data.returns?.posted_amount)} · qty {data.returns?.total_quantity ?? 0}
              </>
            )}
            {data.returns?.store_name
              ? ` · ${data.returns.store_name}`
              : data.returns?.warehouse_name
                ? ` · ${data.returns.warehouse_name}`
                : ''}
          </p>
          <div className={restaurantReports ? 'list-table-wrap rest-po-return' : 'list-table-wrap'}>
          <table className="table">
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '24%' }} />
                <col style={{ width: '16%' }} />
                <col style={{ width: '20%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                <th>Return</th>
                {restaurantReports ? null : <th>Supplier</th>}
                <th>Reason</th>
                {restaurantReports ? null : <th>Status</th>}
                <th>Qty</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.returns?.returns || []).map((ret: any) => (
                <tr key={ret.id}>
                  {restaurantReports ? (
                    <td data-label="Return">
                      {ret.return_number || 'No return'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {ret.supplier_name || 'No supplier'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {ret.status ? plainLabel(String(ret.status)) : 'No status'}
                      </span>
                    </td>
                  ) : (
                    <td>{ret.return_number}</td>
                  )}
                  {restaurantReports ? null : <td>{ret.supplier_name}</td>}
                  <td data-label={restaurantReports ? 'Reason' : undefined}>
                    {restaurantReports
                      ? (ret.reason ? plainLabel(String(ret.reason)) : 'No reason')
                      : ret.reason}
                  </td>
                  {restaurantReports ? null : <td>{ret.status}</td>}
                  <td data-label={restaurantReports ? 'Qty' : undefined}>{ret.quantity}</td>
                  <td data-label={restaurantReports ? 'Amount' : undefined}>{fmtMoney(ret.total_amount)}</td>
                </tr>
              ))}
              {!data.returns?.returns?.length && (
                <tr>
                  <td colSpan={restaurantReports ? 4 : 6} className="muted">
                    {restaurantReports
                      ? 'No returns to suppliers for these dates. Change the dates or status, then choose Generate.'
                      : 'No purchase returns for these filters; change the dates or status, then choose Generate.'}
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
                    {x.reason}: {x.return_count} · {fmtMoney(x.total_amount)} (qty {formatNumber(x.quantity)})
                  </li>
                ))}
              </ul>
            </>
          )}
          </>
          )}
          {activeReport.view === 'pending' && (
          <>
          <h3 style={{ marginTop: 16 }}>{restaurantReports ? 'Orders still to receive' : 'Pending orders (not fully received)'}</h3>
          <p className="muted">
            {data.pending?.order_count ?? 0}{' '}
            {(data.pending?.order_count ?? 0) === 1 ? 'order' : 'orders'} · qty open{' '}
            {data.pending?.total_outstanding_qty ?? 0}
          </p>
          <div className={restaurantReports ? 'list-table-wrap rest-po-pending' : 'list-table-wrap'}>
          <table className="table">
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '18%' }} />
                <col style={{ width: '24%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {restaurantReports ? <th>Order</th> : <th>PO</th>}
                {restaurantReports ? null : <th>Supplier</th>}
                {restaurantReports ? null : <th>Status</th>}
                <th>Ordered</th>
                {restaurantReports ? <th>Still open</th> : <th>Received</th>}
                {restaurantReports ? null : <th>Outstanding qty</th>}
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.pending?.orders || []).map((o: any) => (
                <tr key={o.id}>
                  {restaurantReports ? (
                    <td data-label="Order">
                      {o.po_number}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {o.supplier_name || 'No supplier'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {o.status ? plainLabel(o.status) : 'No status'}
                      </span>
                    </td>
                  ) : (
                    <td>{o.po_number}</td>
                  )}
                  {restaurantReports ? null : <td>{o.supplier_name}</td>}
                  {restaurantReports ? null : <td>{o.status}</td>}
                  {restaurantReports ? (
                    <td data-label="Ordered">
                      {o.ordered_qty}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        Received {o.received_qty}
                      </span>
                    </td>
                  ) : (
                    <td>{o.ordered_qty}</td>
                  )}
                  {restaurantReports ? (
                    <td data-label="Still open">{o.outstanding_qty}</td>
                  ) : (
                    <td>{o.received_qty}</td>
                  )}
                  {restaurantReports ? null : <td>{o.outstanding_qty}</td>}
                  <td data-label={restaurantReports ? 'Amount' : undefined}>
                    {restaurantReports ? fmtMoney(o.total_amount) : o.total_amount}
                  </td>
                </tr>
              ))}
              {!data.pending?.orders?.length && (
                <tr>
                  <td colSpan={restaurantReports ? 4 : 7} className="muted">
                    {restaurantReports
                      ? 'No orders are still waiting to be received.'
                      : 'No pending purchase orders for these filters; change the dates or status, then choose Generate.'}
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
                    No supplier purchases for these dates; widen the dates, then choose Generate.
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
            {restaurantReports
              ? 'Approved costs compared with the budget for this period.'
              : (
                <>
                  Period {data.period_days ?? '—'} days · scaled budgets vs approved spend
                  {data.branch_name ? ` · branch ${data.branch_name}` : ''}
                  {data.department_name ? ` · dept ${data.department_name}` : ''}
                </>
              )}
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">{restaurantReports ? 'Budget' : 'Budget (scaled)'}</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.total_budget_scaled ?? 0) : (data.total_budget_scaled ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">{restaurantReports ? 'Spent' : 'Actual'}</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.total_actual ?? data.total_amount ?? 0) : (data.total_actual ?? data.total_amount ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">{restaurantReports ? 'Difference' : 'Variance'}</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.total_variance ?? 0) : (data.total_variance ?? 0)}</div>
            </div>
          </div>
          <h3 style={{ marginTop: 16 }}>{restaurantReports ? 'Costs against the budget' : 'Top categories'}</h3>
          <ul>
            {(data.top_categories || []).map((c: any) => (
              <li key={c.category_id || c.category}>
                {restaurantReports
                  ? `${c.category}: ${fmtMoney(c.actual)} · ${c.status ? plainLabel(String(c.status)) : 'No status'}`
                  : `${c.category}: ${c.actual} (${c.status})`}
              </li>
            ))}
            {!data.top_categories?.length && <li className="muted">{restaurantReports ? 'No costs yet.' : 'No spend yet'}</li>}
          </ul>
          <div className={restaurantReports ? 'list-table-wrap rest-exp-budget' : 'list-table-wrap'}>
          <table className="table" style={{ marginTop: 16 }}>
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '40%' }} />
                <col style={{ width: '20%' }} />
                <col style={{ width: '22%' }} />
                <col style={{ width: '18%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {restaurantReports ? <th>Cost group</th> : <th>Category</th>}
                {restaurantReports ? <th>Budget</th> : <th>Budget (scaled)</th>}
                {restaurantReports ? <th>Spent</th> : <th>Actual</th>}
                {restaurantReports ? null : <th>Variance</th>}
                {restaurantReports ? null : <th>%</th>}
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(data.rows || data.by_category || []).map((c: any) => (
                <tr key={c.category_id || c.category}>
                  {restaurantReports ? (
                    <td data-label="Cost group">
                      {c.category || 'No cost group'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {c.code || 'No code'}
                      </span>
                    </td>
                  ) : (
                    <td>
                      {c.code ? `${c.code} — ` : ''}
                      {c.category}
                    </td>
                  )}
                  <td data-label={restaurantReports ? 'Budget' : undefined}>
                    {restaurantReports ? fmtMoney(c.budget_scaled) : (c.budget_scaled ?? '—')}
                  </td>
                  {restaurantReports ? (
                    <td data-label="Spent">
                      {fmtMoney(c.actual ?? c.amount)}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {c.variance == null ? 'No difference' : `Difference ${fmtMoney(c.variance)}`}
                      </span>
                    </td>
                  ) : (
                    <td>{c.actual ?? c.amount}</td>
                  )}
                  {restaurantReports ? null : <td>{c.variance ?? '—'}</td>}
                  {restaurantReports ? null : <td>{c.variance_pct != null ? `${c.variance_pct}%` : '—'}</td>}
                  {restaurantReports ? (
                    <td data-label="Status">
                      {c.status ? plainLabel(String(c.status)) : 'No status'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {c.variance_pct != null ? `${c.variance_pct}% of budget` : 'No percent'}
                      </span>
                    </td>
                  ) : (
                    <td>{c.status || '—'}</td>
                  )}
                </tr>
              ))}
              {restaurantReports && !(data.rows || data.by_category || []).length ? (
                <tr>
                  <td colSpan={4} className="muted">
                    No cost groups to compare yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'cashflow' && data && (
        <>
          <p className="muted">
            {restaurantReports ? 'Money in and out of cash and the bank' : 'Cash and bank movements'}
            {data.store_id ? ` · ${placeLabel(stores, data.store_id, 'store')}` : ''}
            {data.branch_id ? ` · ${placeLabel(branches, data.branch_id, 'branch')}` : ''}
            {data.store_id || data.branch_id
              ? ' (this location only; head-office transfers and opening balances are not included)'
              : ''}
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Inflows</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.inflows) : data.inflows}</div>
            </div>
            <div className="card">
              <div className="muted">Outflows</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.outflows) : data.outflows}</div>
            </div>
            <div className="card">
              <div className="muted">Net</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.net) : data.net}</div>
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
                <div className="kpi">{restaurantReports ? fmtMoney(data[key]?.net ?? 0) : (data[key]?.net ?? 0)}</div>
                <p className="muted" style={{ margin: 0 }}>
                  {restaurantReports
                    ? `In ${fmtMoney(data[key]?.inflows ?? 0)} · Out ${fmtMoney(data[key]?.outflows ?? 0)}`
                    : `In ${data[key]?.inflows ?? 0} · Out ${data[key]?.outflows ?? 0}`}
                </p>
              </div>
            ))}
          </div>
          <div className={restaurantReports ? 'list-table-wrap rest-cash-flow' : 'list-table-wrap'}>
          <table className="table" style={{ marginTop: 16 }}>
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '46%' }} />
                <col style={{ width: '27%' }} />
                <col style={{ width: '27%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {restaurantReports ? <th>Movement</th> : <th>Date</th>}
                {restaurantReports ? null : <th>Entry</th>}
                {restaurantReports ? null : <th>Activity</th>}
                <th>In</th>
                <th>Out</th>
              </tr>
            </thead>
            <tbody>
              {(data.lines || []).slice(0, 40).map((l: any, idx: number) => (
                <tr key={`${l.entry_number}-${idx}`}>
                  {restaurantReports ? (
                    <td data-label="Movement">
                      {l.date ? fmtDate(l.date) : 'No date'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {l.entry_number || 'No entry'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {l.activity ? plainLabel(String(l.activity)) : 'No activity'}
                      </span>
                    </td>
                  ) : (
                    <td>{String(l.date)}</td>
                  )}
                  {restaurantReports ? null : <td>{l.entry_number}</td>}
                  {restaurantReports ? null : <td>{l.activity || '—'}</td>}
                  <td data-label={restaurantReports ? 'In' : undefined}>{restaurantReports ? fmtMoney(l.inflow) : l.inflow}</td>
                  <td data-label={restaurantReports ? 'Out' : undefined}>{restaurantReports ? fmtMoney(l.outflow) : l.outflow}</td>
                </tr>
              ))}
              {restaurantReports && !(data.lines || []).length ? (
                <tr>
                  <td colSpan={3} className="muted">
                    No cash movements in this period.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          </div>
        </>
      )}

      {tab === 'pnl' && data && (
        <>
          <p className="muted">
            {restaurantReports
              ? (data.mode === 'journals' ? 'Income and costs for this period' : 'Balances so far')
              : (data.mode === 'journals' ? 'For the selected period' : 'All-time balances')}
            {data.store_id ? ` · ${placeLabel(stores, data.store_id, 'store')}` : ''}
            {data.branch_id ? ` · ${placeLabel(branches, data.branch_id, 'branch')}` : ''}
          </p>
          {restaurantReports ? (
            <>
              <p className="muted">A completed restaurant bill is included in profit and loss for the store on the bill.</p>
              <p className="muted">Restaurant waste at this store is included in these operating expenses.</p>
              <p className="muted">A restaurant till return follows the store on the original receipt.</p>
            </>
          ) : null}
          <div className="grid">
            <div className="card">
              <div className="muted">Revenue</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.revenue ?? data.income ?? 0) : (data.revenue ?? data.income ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">{restaurantReports ? 'Ingredient cost' : 'COGS'}</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.cogs ?? 0) : (data.cogs ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">Gross profit</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.gross_profit ?? 0) : (data.gross_profit ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">{restaurantReports ? 'Running costs' : 'Operating expenses'}</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.operating_expenses ?? 0) : (data.operating_expenses ?? 0)}</div>
            </div>
            <div className="card">
              <div className="muted">Net profit</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.net_profit ?? 0) : (data.net_profit ?? 0)}</div>
            </div>
          </div>
          <div className={restaurantReports ? 'list-table-wrap rest-pnl' : 'list-table-wrap'}>
          <table className="table" style={{ marginTop: 16 }}>
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '68%' }} />
                <col style={{ width: '32%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {restaurantReports ? <th>Account</th> : <th>Code</th>}
                {restaurantReports ? null : <th>Name</th>}
                {restaurantReports ? null : <th>Type</th>}
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.accounts || []).map((a: any) => (
                <tr key={a.code}>
                  {restaurantReports ? (
                    <td data-label="Account">
                      {a.name || 'No account'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {a.code || 'No code'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {a.account_type ? plainLabel(String(a.account_type)) : 'No type'}
                      </span>
                    </td>
                  ) : (
                    <td>{a.code}</td>
                  )}
                  {restaurantReports ? null : <td>{a.name}</td>}
                  {restaurantReports ? null : <td>{a.account_type}</td>}
                  <td data-label={restaurantReports ? 'Amount' : undefined}>
                    {restaurantReports ? fmtMoney(a.balance) : a.balance}
                  </td>
                </tr>
              ))}
              {!data.accounts?.length && (
                <tr>
                  <td colSpan={restaurantReports ? 2 : 4} className="muted">
                    {restaurantReports
                      ? 'No income or costs for this period.'
                      : 'No income/expense activity for this filter'}
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
            As of {fmtDate(data.as_of)}
            {data.store_id ? ` · ${placeLabel(stores, data.store_id, 'store')}` : ''}
            {data.branch_id ? ` · ${placeLabel(branches, data.branch_id, 'branch')}` : ''}
            {data.store_id || data.branch_id
              ? locationScopeNote
              : ''}
            {' · '}
            {restaurantReports
              ? (data.balanced ? 'In balance' : 'Out of balance')
              : (data.balanced ? 'Balanced' : 'Not balanced')} · Debit {fmtMoney(data.total_debit)} · Credit {fmtMoney(data.total_credit)}
          </p>
          <div className={restaurantReports ? 'list-table-wrap rest-trial' : 'list-table-wrap'}>
          <table className="table">
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '52%' }} />
                <col style={{ width: '24%' }} />
                <col style={{ width: '24%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {restaurantReports ? <th>Account</th> : <th>Code</th>}
                {restaurantReports ? null : <th>Name</th>}
                {restaurantReports ? null : <th>Type</th>}
                <th>Debit</th>
                <th>Credit</th>
              </tr>
            </thead>
            <tbody>
              {(data.rows || []).map((r: any) => (
                <tr key={r.account_id || r.code}>
                  {restaurantReports ? (
                    <td data-label="Account">
                      {r.name || 'No account'}
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {r.code || 'No code'}
                      </span>
                      <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                        {r.account_type ? plainLabel(String(r.account_type)) : 'No type'}
                      </span>
                    </td>
                  ) : (
                    <td>{r.code}</td>
                  )}
                  {restaurantReports ? null : <td>{r.name}</td>}
                  {restaurantReports ? null : <td>{r.account_type}</td>}
                  <td data-label={restaurantReports ? 'Debit' : undefined}>{fmtMoney(r.debit)}</td>
                  <td data-label={restaurantReports ? 'Credit' : undefined}>{fmtMoney(r.credit)}</td>
                </tr>
              ))}
              {!data.rows?.length && (
                <tr>
                  <td colSpan={restaurantReports ? 3 : 5} className="muted">
                    {restaurantReports
                      ? 'No balances for this date. Change the date, then choose Generate.'
                      : 'No balances for this as-of date; change the date, then choose Generate.'}
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
            {restaurantReports ? (
              <>
                {data.name || 'No account'}
                {data.code ? ` · ${data.code}` : ' · No code'}
                {' · Opening '}
                {fmtMoney(data.opening_balance)}
                {' · Closing '}
                {fmtMoney(data.closing_balance)}
              </>
            ) : (
              <>
                {data.code} {data.name} · opening {data.opening_balance} · closing {data.closing_balance}
              </>
            )}
          </p>
          <div className={restaurantReports ? 'list-table-wrap rest-acct-lines' : 'list-table-wrap'}>
            <table className="table">
              {restaurantReports ? (
                <colgroup>
                  <col style={{ width: '46%' }} />
                  <col style={{ width: '18%' }} />
                  <col style={{ width: '18%' }} />
                  <col style={{ width: '18%' }} />
                </colgroup>
              ) : null}
              <thead>
                <tr>
                  {restaurantReports ? <th>When</th> : <th>Date</th>}
                  {restaurantReports ? null : <th>Entry</th>}
                  {restaurantReports ? null : <th>Memo</th>}
                  <th>Debit</th>
                  <th>Credit</th>
                  <th>Balance</th>
                </tr>
              </thead>
              <tbody>
                {(data.lines || []).map((l: any, idx: number) => (
                  <tr key={`${l.journal_entry_id}-${idx}`}>
                    {restaurantReports ? (
                      <td data-label="When">
                        {l.date ? fmtDate(l.date) : 'No date'}
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {l.entry_number || 'No entry'}
                        </span>
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {l.description ? plainLabel(String(l.description)) : 'No memo'}
                        </span>
                      </td>
                    ) : (
                      <td>{fmtDate(l.date)}</td>
                    )}
                    {restaurantReports ? null : <td>{l.entry_number}</td>}
                    {restaurantReports ? null : <td>{l.description || '—'}</td>}
                    <td data-label={restaurantReports ? 'Debit' : undefined}>
                      {restaurantReports ? fmtMoney(l.debit) : l.debit}
                    </td>
                    <td data-label={restaurantReports ? 'Credit' : undefined}>
                      {restaurantReports ? fmtMoney(l.credit) : l.credit}
                    </td>
                    <td data-label={restaurantReports ? 'Balance' : undefined}>
                      {restaurantReports ? fmtMoney(l.balance) : l.balance}
                    </td>
                  </tr>
                ))}
                {!(data.lines || []).length && (
                  <tr>
                    <td colSpan={restaurantReports ? 4 : 6} className="muted">
                      {restaurantReports
                        ? 'No movements for this account in these dates.'
                        : 'No posted lines for this account in the date range'}
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
            As of {fmtDate(data.as_of)}
            {data.store_id ? ` · ${placeLabel(stores, data.store_id, 'store')}` : ''}
            {data.branch_id ? ` · ${placeLabel(branches, data.branch_id, 'branch')}` : ''}
            {data.store_id || data.branch_id
              ? locationScopeNote
              : ''}
            {data.compare
              ? ` · compared with ${String(data.compare.mode).replace(/_/g, ' ')} (${fmtDate(data.compare.as_of)})`
              : ''}
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Total assets</div>
              <div className="kpi">{restaurantReports ? fmtMoney(data.total_assets) : data.total_assets}</div>
              {data.compare && (
                <p className="muted">
                  {restaurantReports ? 'Change ' : 'Δ '}
                  {restaurantReports ? fmtMoney(data.compare.deltas?.total_assets ?? 0) : (data.compare.deltas?.total_assets ?? 0)}
                </p>
              )}
            </div>
            <div className="card">
              <div className="muted">{restaurantReports ? 'Owed and owner stake' : 'Liabilities + equity'}</div>
              <div className="kpi">
                {restaurantReports ? fmtMoney(data.total_liabilities_and_equity) : data.total_liabilities_and_equity}
              </div>
              {data.compare && (
                <p className="muted">
                  {restaurantReports ? 'Change ' : 'Δ '}
                  {restaurantReports
                    ? fmtMoney(data.compare.deltas?.total_liabilities_and_equity ?? 0)
                    : (data.compare.deltas?.total_liabilities_and_equity ?? 0)}
                </p>
              )}
            </div>
            <div className="card">
              <div className="muted">{restaurantReports ? 'Books' : 'Balanced'}</div>
              <div className="kpi">
                {restaurantReports
                  ? (data.balanced ? 'In balance' : 'Out of balance')
                  : String(data.balanced)}
              </div>
            </div>
          </div>
          {(['assets', 'liabilities', 'equity'] as const).map((section) => (
            <div key={section} style={{ marginTop: 16 }}>
              <h3>
                {restaurantReports
                  ? (section === 'assets' ? 'Assets' : section === 'liabilities' ? 'Liabilities' : 'Equity')
                  : section}
              </h3>
              <div className={restaurantReports ? `list-table-wrap rest-bs${data.compare ? ' rest-bs-compare' : ''}` : 'list-table-wrap'}>
              <table className="table">
                {restaurantReports ? (
                  <colgroup>
                    <col style={{ width: data.compare ? '46%' : '68%' }} />
                    <col style={{ width: data.compare ? '18%' : '32%' }} />
                    {data.compare ? (
                      <>
                        <col style={{ width: '18%' }} />
                        <col style={{ width: '18%' }} />
                      </>
                    ) : null}
                  </colgroup>
                ) : null}
                <thead>
                  <tr>
                    {restaurantReports ? <th>Account</th> : <th>Code</th>}
                    {restaurantReports ? null : <th>Name</th>}
                    <th>Balance</th>
                    {data.compare && (
                      restaurantReports ? (
                        <>
                          <th>Prior</th>
                          <th>Change</th>
                        </>
                      ) : (
                        <>
                          <th>Prior</th>
                          <th>Δ</th>
                        </>
                      )
                    )}
                  </tr>
                </thead>
                <tbody>
                  {(data[section] || []).map((r: any) => (
                    <tr key={`${section}-${r.code}`}>
                      {restaurantReports ? (
                        <td data-label="Account">
                          {r.name || 'No account'}
                          <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                            {r.code || 'No code'}
                          </span>
                        </td>
                      ) : (
                        <td>{r.code}</td>
                      )}
                      {restaurantReports ? null : <td>{r.name}</td>}
                      <td data-label={restaurantReports ? 'Balance' : undefined}>
                        {restaurantReports ? fmtMoney(r.balance) : r.balance}
                      </td>
                      {data.compare && (
                        restaurantReports ? (
                          <>
                            <td data-label="Prior">{fmtMoney(r.prior_balance ?? 0)}</td>
                            <td data-label="Change">{fmtMoney(r.delta ?? 0)}</td>
                          </>
                        ) : (
                          <>
                            <td>{r.prior_balance ?? 0}</td>
                            <td>{r.delta ?? 0}</td>
                          </>
                        )
                      )}
                    </tr>
                  ))}
                  {restaurantReports && !(data[section] || []).length && (
                    <tr>
                      <td colSpan={data.compare ? 4 : 2} className="muted">
                        {section === 'assets'
                          ? 'No assets yet.'
                          : section === 'liabilities'
                            ? 'Nothing owed yet.'
                            : 'No equity yet.'}
                      </td>
                    </tr>
                  )}
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
            Email a saved report every day or once a week. Times are in GMT (Ghana time).
          </p>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <input
              placeholder="Schedule name"
              value={schedForm.name}
              onChange={(e) => setSchedForm({ ...schedForm, name: e.target.value })}
              aria-label="Report schedule name"
              title="Schedule name"
            />
            <select
              value={schedForm.report_type}
              onChange={(e) => setSchedForm({ ...schedForm, report_type: e.target.value })}
              aria-label="Report schedule report type"
            >
              {REPORT_TYPES.filter(
                (t) =>
                  (industry === 'pharmacy' || t !== 'pharmacy_rx_activity') &&
                  (multiStore || t !== 'inventory_transfers'),
              ).map((t) => (
                <option key={t} value={t}>
                  {plainLabel(t)}
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
                Hour (GMT){' '}
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
              <option value="all">{restaurantReports ? 'All schedules' : 'All enabled/disabled'}</option>
              <option value="enabled">{restaurantReports ? 'On' : 'Enabled only'}</option>
              <option value="disabled">{restaurantReports ? 'Not in use' : 'Disabled only'}</option>
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
          <div className={restaurantReports ? 'list-table-wrap rest-report-sched' : 'list-table-wrap'}>
          <table className="table">
            {restaurantReports ? (
              <colgroup>
                <col style={{ width: '34%' }} />
                <col style={{ width: '28%' }} />
                <col style={{ width: '16%' }} />
                <col style={{ width: '22%' }} />
              </colgroup>
            ) : null}
            <thead>
              <tr>
                {restaurantReports ? <th>Schedule</th> : <th>Name</th>}
                {restaurantReports ? null : <th>Report</th>}
                <th>When</th>
                {restaurantReports ? null : <th>Recipients</th>}
                <th>Last run</th>
                {restaurantReports ? <th>Actions</th> : <th />}
              </tr>
            </thead>
            <tbody>
              {managedSchedules.length === 0 ? (
                <tr>
                  <td colSpan={restaurantReports ? 4 : 6} className="muted">
                    {restaurantReports
                      ? (schedules.length
                        ? 'No schedules for this filter. Choose All schedules and All frequencies to see every schedule.'
                        : 'No email reports yet. Create a schedule when you want a report sent on its own.')
                      : 'No schedules for this filter'}
                  </td>
                </tr>
              ) : (
                managedSchedules.map((s) => (
                  <tr key={s.id}>
                    {restaurantReports ? (
                      <td data-label="Schedule">
                        {s.name}
                        {!s.enabled ? ' · Not in use' : ''}
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {plainLabel(s.report_type)} · {String(s.format || '').toUpperCase()}
                        </span>
                      </td>
                    ) : (
                    <td>
                      {s.name} {!s.enabled && <span className="muted">(off)</span>}
                    </td>
                    )}
                    {restaurantReports ? null : (
                    <td>
                      {plainLabel(s.report_type)} · {String(s.format || '').toUpperCase()}
                    </td>
                    )}
                    {restaurantReports ? (
                      <td data-label="When">
                        {plainLabel(s.frequency)}
                        {s.frequency === 'weekly' ? `, ${WEEKDAYS[Number(s.weekday)] || ''}` : ''}
                        {` at ${String(s.hour_utc ?? 0).padStart(2, '0')}:00 GMT`}
                        <span className="list-secondary" style={{ display: 'block', fontWeight: 600 }}>
                          {(s.recipients || []).join(', ') || 'No recipients'}
                        </span>
                      </td>
                    ) : (
                    <td>
                      {plainLabel(s.frequency)}
                      {s.frequency === 'weekly' ? `, ${WEEKDAYS[Number(s.weekday)] || ''}` : ''}
                      {` at ${String(s.hour_utc ?? 0).padStart(2, '0')}:00 UTC`}
                    </td>
                    )}
                    {restaurantReports ? null : <td>{(s.recipients || []).join(', ')}</td>}
                    <td data-label={restaurantReports ? 'Last run' : undefined}>
                      {restaurantReports
                        ? (s.last_run_at ? formatWhen(s.last_run_at) : 'Not run yet')
                        : (s.last_run_at ? formatWhen(s.last_run_at) : '—')}
                      {s.last_error ? (
                        <div style={{ color: '#b91c1c', fontSize: 12 }}>{s.last_error}</div>
                      ) : null}
                    </td>
                    <td
                      data-label={restaurantReports ? 'Actions' : undefined}
                      style={restaurantReports ? undefined : { display: 'flex', gap: 6, flexWrap: 'wrap' }}
                    >
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
          {!schedules.length && !loading && !restaurantReports && <p className="muted">No schedules yet.</p>}
        </>
      )}
        </div>
      </div>
    </div>
  );
}
