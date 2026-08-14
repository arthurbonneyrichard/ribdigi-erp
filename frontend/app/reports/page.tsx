'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

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
  | 'schedules';

const TAB_EXPORT: Record<Exclude<Tab, 'schedules'>, string> = {
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
  'inventory_low_stock',
  'inventory_expiry',
  'inventory_transfers',
  'purchases_summary',
  'purchases_pending_orders',
  'purchases_returns',
  'expenses_summary',
  'expenses_budget_vs_actual',
  'cash_flow',
  'trial_balance',
  'balance_sheet',
  'tax',
  'tax_filing',
  'tax_filing_gh',
];

export default function Page() {
  const [tab, setTab] = useState<Tab>('summary');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [storeId, setStoreId] = useState('');
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
  const [expiryDays, setExpiryDays] = useState('30');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [schedules, setSchedules] = useState<any[]>([]);
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

  function qs(extra: Record<string, string> = {}) {
    const params = new URLSearchParams();
    if (fromDate) params.set('from_date', fromDate);
    if (toDate) params.set('to_date', toDate);
    if (storeId) params.set('store_id', storeId);
    if (branchId) params.set('branch_id', branchId);
    if (departmentId) params.set('department_id', departmentId);
    Object.entries(extra).forEach(([k, v]) => v && params.set(k, v));
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  function balanceSheetQs() {
    const params = new URLSearchParams();
    const effectiveAsOf = asOf || toDate;
    if (effectiveAsOf) params.set('as_of', effectiveAsOf);
    if (compare) params.set('compare', compare);
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  function trialBalanceQs() {
    const params = new URLSearchParams();
    const effectiveAsOf = asOf || toDate;
    if (effectiveAsOf) params.set('as_of', effectiveAsOf);
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  async function load(nextTab: Tab = tab) {
    setLoading(true);
    setError('');
    try {
      if (nextTab === 'schedules') {
        const r = await api('/reports/schedules');
        setSchedules(r.data || []);
        setData(null);
        return;
      }
      let path = '/reports/summary';
      if (nextTab === 'sales') {
        path = `/reports/sales/products${qs(categoryId ? { category_id: categoryId } : {})}`;
      }
      if (nextTab === 'salesperson') path = `/reports/sales/salesperson${qs()}`;
      if (nextTab === 'customers') path = `/reports/sales/customers${qs()}`;
      if (nextTab === 'stores') path = `/reports/sales/by-store${qs()}`;
      if (nextTab === 'departments') path = `/reports/sales/by-department${qs()}`;
      if (nextTab === 'inventory') path = '/reports/inventory/low-stock';
      if (nextTab === 'purchases') path = `/reports/purchases/summary${qs()}`;
      if (nextTab === 'expenses') path = `/reports/expenses/budget-vs-actual${qs()}`;
      if (nextTab === 'cashflow') path = `/reports/cash-flow${qs()}`;
      if (nextTab === 'pnl') path = `/reports/profit-loss${qs()}`;
      if (nextTab === 'trialbalance') path = `/reports/trial-balance${trialBalanceQs()}`;
      if (nextTab === 'balancesheet') path = `/reports/balance-sheet${balanceSheetQs()}`;
      const r = await api(path);
      if (nextTab === 'sales') {
        const [daily, monthly, returns] = await Promise.all([
          api('/reports/sales/daily'),
          api('/reports/sales/monthly'),
          api(`/reports/sales/returns${qs()}`),
        ]);
        setData({
          products: r.data,
          daily: daily.data,
          monthly: monthly.data,
          returns: returns.data,
        });
      } else if (nextTab === 'inventory') {
        const whQs = warehouseId ? `?warehouse_id=${encodeURIComponent(warehouseId)}` : '';
        const days = expiryDays || '30';
        const expiryQs = new URLSearchParams({ days });
        if (warehouseId) expiryQs.set('warehouse_id', warehouseId);
        const [balance, valuation, movements, suggestions, transfers, expiry] = await Promise.all([
          api(`/reports/inventory/balance${whQs}`),
          api(`/reports/inventory/valuation?method=standard${warehouseId ? `&warehouse_id=${encodeURIComponent(warehouseId)}` : ''}`),
          api('/reports/inventory/movements'),
          api('/purchasing/suggestions/low-stock').catch(() => ({ data: null })),
          api(`/reports/inventory/transfers${qs()}`),
          api(`/reports/inventory/expiry?${expiryQs}`),
        ]);
        setData({
          lowStock: r.data,
          balance: balance.data,
          valuation: valuation.data,
          movements: movements.data,
          suggestions: suggestions.data,
          transfers: transfers.data,
          expiry: expiry.data,
        });
        setSuggestSelected({});
      } else if (nextTab === 'purchases') {
        const [suppliers, pending, returns] = await Promise.all([
          api(`/reports/purchases/suppliers${qs()}`),
          api(`/reports/purchases/pending-orders${qs()}`),
          api(`/reports/purchases/returns${qs()}`),
        ]);
        setData({
          summary: r.data,
          suppliers: suppliers.data,
          pending: pending.data,
          returns: returns.data,
        });
      } else {
        setData(r.data);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
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
    ])
      .then(([st, br, wh, cats, deps]) => {
        setStores(st.data || []);
        setBranches(br.data || []);
        setWarehouses(wh.data || []);
        setCategories(cats.data || []);
        setDepartments(deps.data || []);
      })
      .catch(() => undefined);
  }, []);

  function switchTab(t: Tab) {
    setTab(t);
    load(t);
  }

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
            product_id: ln.product_id,
            quantity: ln.suggested_order_qty,
            warehouse_id: ln.warehouse_id || null,
            preferred_supplier_id: ln.preferred_supplier_id || null,
          })),
          notes: 'Created from low-stock suggestions',
        }),
      });
      const created = r.data?.created || [];
      const nums = created.map((p: any) => p.request_number).join(', ');
      setMessage(
        created.length
          ? `Created draft PR(s): ${nums}. Open Purchasing → Requests to submit.`
          : r.message || 'Done'
      );
      await load('inventory');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSuggestBusy(false);
    }
  }

  async function download(format: 'csv' | 'pdf' | 'xlsx', reportType?: string) {
    if (tab === 'schedules') return;
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const params = new URLSearchParams();
      params.set('report_type', reportType || TAB_EXPORT[tab]);
      params.set('format', format);
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      if (storeId) params.set('store_id', storeId);
      if (branchId) params.set('branch_id', branchId);
      if (departmentId) params.set('department_id', departmentId);
      if (
        (reportType || TAB_EXPORT[tab]) === 'sales_products' ||
        (!reportType && tab === 'sales')
      ) {
        if (categoryId) params.set('category_id', categoryId);
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
        params.set('days', expiryDays);
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
          name: schedForm.name,
          report_type: schedForm.report_type,
          format: schedForm.format,
          frequency: schedForm.frequency,
          weekday: schedForm.frequency === 'weekly' ? Number(schedForm.weekday) : null,
          hour_utc: Number(schedForm.hour_utc),
          recipients: schedForm.recipients,
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
    <Shell>
      <h1>Reports & Analytics</h1>
      <p className="muted">Sales, inventory, purchases, expenses, cash flow, and balance sheet</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {(
          [
            ['summary', 'Summary'],
            ['sales', 'Sales'],
            ['salesperson', 'Salespeople'],
            ['customers', 'Customers'],
            ['stores', 'Stores'],
            ['departments', 'Departments'],
            ['inventory', 'Inventory'],
            ['purchases', 'Purchases'],
            ['expenses', 'Expenses'],
            ['cashflow', 'Cash flow'],
            ['pnl', 'P&L'],
            ['trialbalance', 'Trial balance'],
            ['balancesheet', 'Balance sheet'],
            ['schedules', 'Email schedules'],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button key={id} onClick={() => switchTab(id)} disabled={tab === id}>
            {label}
          </button>
        ))}
      </div>

      {tab !== 'schedules' && (
      <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        {(tab === 'balancesheet' || tab === 'trialbalance') && (
          <>
            <input
              type="date"
              value={asOf}
              onChange={(e) => setAsOf(e.target.value)}
              title="As of date (defaults to To date)"
            />
            {tab === 'balancesheet' && (
              <select value={compare} onChange={(e) => setCompare(e.target.value)}>
                <option value="">No compare</option>
                <option value="prior_period">vs prior month-end</option>
                <option value="prior_year">vs prior year</option>
              </select>
            )}
          </>
        )}
        {tab === 'inventory' && (
          <>
            <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              <option value="">All warehouses (company stock)</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={0}
              max={3650}
              value={expiryDays}
              onChange={(e) => setExpiryDays(e.target.value)}
              placeholder="Expiry days"
              style={{ width: 110 }}
              title="Expiry horizon (days)"
            />
          </>
        )}
        {(tab === 'pnl' || tab === 'stores' || tab === 'sales' || tab === 'expenses' || tab === 'cashflow') && (
          <>
            {(tab === 'pnl' || tab === 'stores' || tab === 'expenses' || tab === 'cashflow') && (
              <select value={branchId} onChange={(e) => setBranchId(e.target.value)}>
                <option value="">All branches</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.code} — {b.name}
                  </option>
                ))}
              </select>
            )}
            {tab !== 'expenses' && (
              <select value={storeId} onChange={(e) => setStoreId(e.target.value)}>
                <option value="">All stores</option>
                {stores
                  .filter((s) => !branchId || s.branch_id === branchId)
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.code} — {s.name}
                    </option>
                  ))}
              </select>
            )}
          </>
        )}
        {(tab === 'salesperson' ||
          tab === 'stores' ||
          tab === 'departments' ||
          tab === 'expenses') && (
          <select
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value)}
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
        )}
        {tab === 'sales' && (
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code} — {c.name}
              </option>
            ))}
          </select>
        )}
        <button onClick={() => load()} disabled={loading}>
          {loading ? 'Loading…' : 'Apply filters'}
        </button>
        <button onClick={() => download('csv')}>Export CSV</button>
        <button onClick={() => download('xlsx')}>Export Excel</button>
        <button onClick={() => download('pdf')}>Export PDF</button>
        {tab === 'sales' && (
          <>
            <button onClick={() => download('csv', 'sales_daily')}>Daily CSV</button>
            <button onClick={() => download('xlsx', 'sales_salesperson')}>Salespeople Excel</button>
            <button onClick={() => download('xlsx', 'trial_balance')}>Trial balance Excel</button>
            <button onClick={() => download('csv', 'trial_balance')}>Trial balance CSV</button>
            <button onClick={() => download('pdf', 'profit_loss')}>P&amp;L PDF</button>
          </>
        )}
        {tab === 'salesperson' && (
          <button onClick={() => download('xlsx', 'sales_salesperson')}>Export Excel</button>
        )}
        {tab === 'customers' && (
          <button onClick={() => download('xlsx', 'sales_customers')}>Export Excel</button>
        )}
        {tab === 'stores' && (
          <button onClick={() => download('xlsx', 'sales_by_store')}>Export Excel</button>
        )}
      </div>
      )}

      {tab === 'summary' && data && (
        <div className="grid">
          <div className="card">
            <div className="muted">Today sales</div>
            <div className="kpi">{data.today_sales?.total_revenue ?? 0}</div>
          </div>
          <div className="card">
            <div className="muted">Month sales</div>
            <div className="kpi">{data.month_sales?.total_revenue ?? 0}</div>
            <p className="muted">vs prior: {data.month_sales?.change_pct ?? '—'}%</p>
          </div>
          <div className="card">
            <div className="muted">Low stock SKUs</div>
            <div className="kpi">{data.low_stock_report?.count ?? 0}</div>
          </div>
          <div className="card">
            <div className="muted">Approved expenses</div>
            <div className="kpi">{data.expenses_summary?.total_amount ?? 0}</div>
          </div>
        </div>
      )}

      {tab === 'sales' && data && (
        <>
          <div className="grid">
            <div className="card">
              <h3>Today</h3>
              <p>Revenue: {data.daily?.total_revenue}</p>
              <p>Invoices: {data.daily?.invoice_count} · POS: {data.daily?.pos_count}</p>
            </div>
            <div className="card">
              <h3>This month</h3>
              <p>Revenue: {data.monthly?.total_revenue}</p>
              <p>Change: {data.monthly?.change_pct ?? '—'}%</p>
            </div>
          </div>
          <h3 style={{ marginTop: 16 }}>Products</h3>
          <p className="muted">
            Qty {data.products?.total_quantity ?? 0} · revenue {data.products?.total_revenue ?? 0}
            {data.products?.store_id ? ' · store filtered' : ''}
            {data.products?.category_name ? ` · ${data.products.category_name}` : ''}
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Category</th>
                <th>Qty</th>
                <th>Revenue</th>
              </tr>
            </thead>
            <tbody>
              {(data.products?.products || []).map((p: any) => (
                <tr key={p.product_id}>
                  <td>{p.sku}</td>
                  <td>{p.name}</td>
                  <td>{p.category_name || '—'}</td>
                  <td>{p.quantity}</td>
                  <td>{p.revenue}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ display: 'flex', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
            <button onClick={() => download('xlsx', 'sales_returns')}>Returns Excel</button>
            <button onClick={() => download('csv', 'sales_returns')}>Returns CSV</button>
          </div>
          <h3 style={{ marginTop: 16 }}>Sales returns</h3>
          <p className="muted">
            {data.returns?.return_count ?? 0} returns · total {data.returns?.total_amount ?? 0} ·
            posted {data.returns?.posted_amount ?? 0} · qty {data.returns?.total_quantity ?? 0} ·
            refunded {data.returns?.refunded_amount ?? 0}
          </p>
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

      {tab === 'salesperson' && data && (
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
        </>
      )}

      {tab === 'customers' && data && (
        <>
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
              {(data.customers || []).map((c: any) => (
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
        </>
      )}

      {tab === 'inventory' && data && (
        <>
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
              <h3 style={{ margin: 0 }}>
                Low-stock suggestions ({data.suggestions?.count ?? data.lowStock?.count ?? 0})
              </h3>
              <button
                type="button"
                onClick={createDraftPrsFromSuggestions}
                disabled={suggestBusy || !(data.suggestions?.lines || []).length}
              >
                {suggestBusy ? 'Creating…' : 'Create draft PR'}
              </button>
            </div>
            <p className="muted" style={{ marginTop: 8 }}>
              Select lines to raise draft purchase requests. Submit/approve remains in Purchasing.
            </p>
            {(data.suggestions?.lines || []).length === 0 ? (
              <p className="muted">No actionable low-stock lines (or all already on an open PR).</p>
            ) : (
              <table className="table" style={{ marginTop: 8 }}>
                <thead>
                  <tr>
                    <th></th>
                    <th>SKU</th>
                    <th>Name</th>
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
                            checked={!!suggestSelected[key]}
                            onChange={(e) =>
                              setSuggestSelected((prev) => ({ ...prev, [key]: e.target.checked }))
                            }
                          />
                        </td>
                        <td>{ln.sku}</td>
                        <td>{ln.name}</td>
                        <td>{ln.stock_qty}</td>
                        <td>{ln.reorder_level}</td>
                        <td>{ln.suggested_order_qty}</td>
                        <td>{ln.warehouse_name || '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
          <div className="card" style={{ marginTop: 16 }}>
            <h3>Low stock products ({data.lowStock?.count ?? 0})</h3>
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
          <div className="card" style={{ marginTop: 16 }}>
            <h3>Stock valuation (standard cost)</h3>
            <p className="muted">
              Method: {data.valuation?.method || 'standard'}
              {data.valuation?.warehouse_id ? ' · warehouse filtered' : ' · company stock'}
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
            >
              Export valuation Excel
            </button>
          </div>
          <h3 style={{ marginTop: 16 }}>
            Stock value: {data.valuation?.total_value ?? data.balance?.total_value ?? 0}
          </h3>
          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Qty</th>
                <th>Unit cost</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {(data.valuation?.items || data.balance?.items || []).slice(0, 50).map((i: any) => (
                <tr key={i.product_id}>
                  <td>{i.sku}</td>
                  <td>{i.name}</td>
                  <td>{i.quantity}</td>
                  <td>{i.unit_cost ?? i.cost_price ?? '—'}</td>
                  <td>{i.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3 style={{ marginTop: 16 }}>Expiry</h3>
          <p className="muted">
            {data.expiry?.count ?? 0} batches within {data.expiry?.within_days ?? expiryDays} days ·
            expired {data.expiry?.expired_count ?? 0} · qty {data.expiry?.total_quantity ?? 0}
          </p>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={() => download('xlsx', 'inventory_expiry')}>
              Expiry Excel
            </button>
            <button type="button" onClick={() => download('csv', 'inventory_expiry')}>
              Expiry CSV
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
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
                  <td>
                    {b.sku || '—'} {b.name ? `· ${b.name}` : ''}
                  </td>
                  <td>{b.batch_number}</td>
                  <td>{b.expiry_date ? String(b.expiry_date).slice(0, 10) : '—'}</td>
                  <td>{b.days_until_expiry ?? '—'}</td>
                  <td>{b.quantity}</td>
                </tr>
              ))}
              {!data.expiry?.batches?.length && (
                <tr>
                  <td colSpan={5} className="muted">
                    No batches nearing expiry
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <h3 style={{ marginTop: 16 }}>Inter-store transfers</h3>
          <p className="muted">
            {data.transfers?.transfer_count ?? 0} transfers · qty {data.transfers?.total_quantity ?? 0}
          </p>
          <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={() => download('xlsx', 'inventory_transfers')}>
              Transfers Excel
            </button>
            <button type="button" onClick={() => download('csv', 'inventory_transfers')}>
              Transfers CSV
            </button>
          </div>
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

      {tab === 'purchases' && data && (
        <>
          <div className="grid">
            <div className="card">
              <div className="muted">Orders (period)</div>
              <div className="kpi">{data.summary?.order_count ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Total / outstanding $</div>
              <div className="kpi">
                {data.summary?.total_amount ?? 0} / {data.summary?.outstanding_amount ?? 0}
              </div>
            </div>
            <div className="card">
              <div className="muted">Pending POs</div>
              <div className="kpi">{data.pending?.order_count ?? 0}</div>
              <p className="muted">
                Qty open {data.pending?.total_outstanding_qty ?? 0} · amt{' '}
                {data.pending?.total_amount ?? 0}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            <button onClick={() => download('xlsx', 'purchases_pending_orders')}>
              Pending orders Excel
            </button>
            <button onClick={() => download('csv', 'purchases_pending_orders')}>
              Pending orders CSV
            </button>
            <button onClick={() => download('xlsx', 'purchases_returns')}>
              Returns Excel
            </button>
            <button onClick={() => download('csv', 'purchases_returns')}>
              Returns CSV
            </button>
          </div>
          <h3 style={{ marginTop: 16 }}>Purchase returns</h3>
          <p className="muted">
            {data.returns?.return_count ?? 0} returns · total {data.returns?.total_amount ?? 0} ·
            posted {data.returns?.posted_amount ?? 0} · qty {data.returns?.total_quantity ?? 0}
          </p>
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
          <h3 style={{ marginTop: 16 }}>Pending orders (not fully received)</h3>
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
          <h3 style={{ marginTop: 16 }}>By supplier</h3>
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
                  <td>{s.total_amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
        </>
      )}

      {tab === 'trialbalance' && data && (
        <>
          <p className="muted">
            As of {data.as_of}
            {data.mode === 'journals' ? ' · reconstructed from posted journals' : ' · live balances'}
            {' · '}
            Balanced: {String(data.balanced)} | Dr {data.total_debit} / Cr {data.total_credit}
          </p>
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
        </>
      )}

      {tab === 'balancesheet' && data && (
        <>
          <p className="muted">
            As of {data.as_of}
            {data.mode === 'journals' ? ' · reconstructed from posted journals' : ' · live balances'}
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
            />
            <select
              value={schedForm.report_type}
              onChange={(e) => setSchedForm({ ...schedForm, report_type: e.target.value })}
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
              >
                <option value="xlsx">Excel</option>
                <option value="csv">CSV</option>
                <option value="pdf">PDF</option>
              </select>
              <select
                value={schedForm.frequency}
                onChange={(e) => setSchedForm({ ...schedForm, frequency: e.target.value })}
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
              </select>
              {schedForm.frequency === 'weekly' && (
                <select
                  value={schedForm.weekday}
                  onChange={(e) => setSchedForm({ ...schedForm, weekday: e.target.value })}
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
                />
              </label>
            </div>
            <input
              placeholder="Recipients (comma-separated emails)"
              value={schedForm.recipients}
              onChange={(e) => setSchedForm({ ...schedForm, recipients: e.target.value })}
            />
            <label>
              <input
                type="checkbox"
                checked={schedForm.enabled}
                onChange={(e) => setSchedForm({ ...schedForm, enabled: e.target.checked })}
              />{' '}
              Enabled
            </label>
            <button onClick={createSchedule}>Create schedule</button>
          </div>
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
              {schedules.map((s) => (
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
                    <button onClick={() => runSchedule(s.id)}>Run now</button>
                    <button onClick={() => toggleSchedule(s)}>{s.enabled ? 'Disable' : 'Enable'}</button>
                    <button onClick={() => deleteSchedule(s.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!schedules.length && !loading && <p className="muted">No schedules yet.</p>}
        </>
      )}
    </Shell>
  );
}
