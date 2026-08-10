'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { useTabQuery } from '../../lib/tabQuery';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Tab =
  | 'summary'
  | 'sales'
  | 'customers'
  | 'salesperson'
  | 'stores'
  | 'inventory'
  | 'purchases'
  | 'expenses'
  | 'pnl'
  | 'cashflow'
  | 'balancesheet'
  | 'credit'
  | 'tax'
  | 'transfers'
  | 'schedules';
const REPORT_TABS: Tab[] = [
  'summary',
  'sales',
  'customers',
  'salesperson',
  'stores',
  'inventory',
  'purchases',
  'expenses',
  'pnl',
  'cashflow',
  'balancesheet',
  'credit',
  'tax',
  'transfers',
  'schedules',
];

const TAB_EXPORT: Record<Exclude<Tab, 'schedules'>, string> = {
  summary: 'summary',
  sales: 'sales_products',
  customers: 'sales_customers',
  salesperson: 'sales_salesperson',
  stores: 'sales_by_store',
  inventory: 'inventory_valuation',
  purchases: 'purchases_summary',
  expenses: 'expenses_summary',
  pnl: 'profit_loss',
  cashflow: 'cash_flow',
  balancesheet: 'balance_sheet',
  credit: 'credit_aging',
  tax: 'tax',
  transfers: 'transfer_history',
};

const REPORT_TYPES = [
  'summary',
  'sales_daily',
  'sales_monthly',
  'sales_products',
  'sales_customers',
  'sales_salesperson',
  'sales_by_store',
  'inventory_balance',
  'inventory_low_stock',
  'inventory_valuation',
  'purchases_summary',
  'purchases_pending_orders',
  'purchases_returns',
  'expenses_summary',
  'profit_loss',
  'cash_flow',
  'balance_sheet',
  'credit_aging',
  'tax',
  'tax_filing',
  'tax_filing_gh',
  'tax_filing_ke',
  'tax_filing_ng',
  'transfer_history',
];

export default function Page() {
  const [tab, setTab] = useTabQuery(REPORT_TABS, 'summary');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [storeId, setStoreId] = useState('');
  const [branchId, setBranchId] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [transferScope, setTransferScope] = useState('all');
  const [transferStatus, setTransferStatus] = useState('');
  const [stores, setStores] = useState<{ id: string; code: string; name: string; branch_id?: string | null }[]>([]);
  const [branches, setBranches] = useState<{ id: string; code: string; name: string }[]>([]);
  const [categories, setCategories] = useState<{ id: string; name: string }[]>([]);
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

  function qs(extra: Record<string, string> = {}) {
    const params = new URLSearchParams();
    if (fromDate) params.set('from_date', fromDate);
    if (toDate) params.set('to_date', toDate);
    Object.entries(extra).forEach(([k, v]) => v && params.set(k, v));
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  useEffect(() => {
    Promise.all([
      api('/stores').catch(() => ({ data: [] })),
      api('/branches').catch(() => ({ data: [] })),
      api('/catalog/categories').catch(() => ({ data: [] })),
    ]).then(([s, b, c]) => {
      setStores(s.data || []);
      setBranches(b.data || []);
      setCategories(c.data || []);
    });
  }, []);

  const financialTab = tab === 'pnl' || tab === 'cashflow' || tab === 'balancesheet';
  const storeOptions = branchId
    ? stores.filter((s) => s.branch_id === branchId)
    : stores;

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
        path = `/reports/sales/products${qs({
          store_id: storeId,
          category_id: categoryId,
        })}`;
      }
      if (nextTab === 'customers') path = `/reports/sales/customers${qs()}`;
      if (nextTab === 'salesperson') path = `/reports/sales/salesperson${qs()}`;
      if (nextTab === 'stores') path = `/reports/sales/by-store${qs()}`;
      if (nextTab === 'inventory') path = '/reports/inventory/low-stock';
      if (nextTab === 'purchases') path = `/reports/purchases/summary${qs()}`;
      if (nextTab === 'expenses') path = `/reports/expenses/summary${qs()}`;
      if (nextTab === 'pnl') {
        path = `/reports/profit-loss${qs({ store_id: storeId, branch_id: branchId })}`;
      }
      if (nextTab === 'cashflow') {
        path = `/reports/cash-flow${qs({ store_id: storeId, branch_id: branchId })}`;
      }
      if (nextTab === 'balancesheet') {
        path = `/reports/balance-sheet${qs({
          as_of_date: toDate,
          store_id: storeId,
          branch_id: branchId,
        })}`;
      }
      if (nextTab === 'credit') {
        const [ar, ap] = await Promise.all([
          api('/credit/aging?kind=receivable'),
          api('/credit/aging?kind=payable'),
        ]);
        setData({ ar: ar.data, ap: ap.data });
        return;
      }
      if (nextTab === 'tax') {
        const [taxReport, filing] = await Promise.all([
          api(`/reports/tax${qs()}`),
          api(`/reports/tax/filing${qs()}`),
        ]);
        setData({ tax: taxReport.data, filing: filing.data });
        return;
      }
      if (nextTab === 'transfers') {
        const r = await api(
          `/reports/transfers${qs({
            store_id: storeId,
            scope: transferScope,
            status: transferStatus,
          })}`
        );
        setData(r.data);
        return;
      }
      const r = await api(path);
      if (nextTab === 'sales') {
        const [daily, monthly] = await Promise.all([
          api('/reports/sales/daily'),
          api('/reports/sales/monthly'),
        ]);
        setData({ products: r.data, daily: daily.data, monthly: monthly.data });
      } else if (nextTab === 'inventory') {
        const [balance, movements, valuation] = await Promise.all([
          api('/reports/inventory/balance'),
          api('/reports/inventory/movements'),
          api(`/reports/inventory/valuation${qs({ store_id: storeId })}`),
        ]);
        setData({
          lowStock: r.data,
          balance: balance.data,
          movements: movements.data,
          valuation: valuation.data,
        });
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
  }, []);

  function switchTab(t: Tab) {
    setTab(t);
    load(t);
  }

  async function download(format: 'csv' | 'pdf' | 'xlsx', reportType?: string, extra: Record<string, string> = {}) {
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
      if (toDate) params.set('as_of_date', toDate);
      if (storeId) params.set('store_id', storeId);
      if (branchId) params.set('branch_id', branchId);
      if (categoryId) params.set('category_id', categoryId);
      if (tab === 'transfers') {
        if (transferScope) params.set('scope', transferScope);
        if (transferStatus) params.set('status', transferStatus);
      }
      Object.entries(extra).forEach(([k, v]) => v && params.set(k, v));
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
      <p className="muted">
        Sales, inventory, purchases, expenses, financials, credit, tax, and transfer history — plus email
        schedules
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {(
          [
            ['summary', 'Summary'],
            ['sales', 'Sales'],
            ['customers', 'Customers'],
            ['salesperson', 'Salespeople'],
            ['stores', 'Stores'],
            ['inventory', 'Inventory'],
            ['purchases', 'Purchases'],
            ['expenses', 'Expenses'],
            ['pnl', 'P&L'],
            ['cashflow', 'Cash flow'],
            ['balancesheet', 'Balance sheet'],
            ['credit', 'Credit'],
            ['tax', 'Tax'],
            ['transfers', 'Transfers'],
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
        {financialTab && (
          <select
            value={branchId}
            onChange={(e) => {
              setBranchId(e.target.value);
              setStoreId('');
            }}
            aria-label="Branch filter"
          >
            <option value="">All branches</option>
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.code} — {b.name}
              </option>
            ))}
          </select>
        )}
        {(tab === 'sales' || tab === 'inventory' || tab === 'transfers' || financialTab) && (
          <select value={storeId} onChange={(e) => setStoreId(e.target.value)} aria-label="Store filter">
            <option value="">All stores</option>
            {storeOptions.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
        )}
        {tab === 'transfers' && (
          <>
            <select
              value={transferScope}
              onChange={(e) => setTransferScope(e.target.value)}
              aria-label="Transfer scope"
            >
              <option value="all">All scopes</option>
              <option value="inter_store">Inter-store</option>
              <option value="warehouse">Warehouse</option>
            </select>
            <select
              value={transferStatus}
              onChange={(e) => setTransferStatus(e.target.value)}
              aria-label="Transfer status"
            >
              <option value="">Any status</option>
              <option value="draft">Draft</option>
              <option value="requested">Requested</option>
              <option value="in_transit">In transit</option>
              <option value="received">Received</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </>
        )}
        {tab === 'sales' && (
          <select
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
            aria-label="Category filter"
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
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
        {tab === 'customers' && (
          <button onClick={() => download('xlsx', 'sales_customers')}>Customers Excel</button>
        )}
        {tab === 'salesperson' && (
          <button onClick={() => download('xlsx', 'sales_salesperson')}>Export Excel</button>
        )}
        {tab === 'stores' && (
          <button onClick={() => download('xlsx', 'sales_by_store')}>Export Excel</button>
        )}
        {tab === 'credit' && (
          <>
            <button onClick={() => download('xlsx', 'credit_aging', { kind: 'receivable' })}>
              AR aging Excel
            </button>
            <button onClick={() => download('xlsx', 'credit_aging', { kind: 'payable' })}>
              AP aging Excel
            </button>
          </>
        )}
        {tab === 'tax' && (
          <>
            <button onClick={() => download('xlsx', 'tax')}>Tax Excel</button>
            <button onClick={() => download('xlsx', 'tax_filing')}>Filing pack Excel</button>
          </>
        )}
        {tab === 'transfers' && (
          <button onClick={() => download('xlsx', 'transfer_history')}>Transfers Excel</button>
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
              <p className="muted">
                vs {data.daily?.previous_date || 'prior day'}: {data.daily?.change_pct ?? '—'}%
              </p>
            </div>
            <div className="card">
              <h3>This month</h3>
              <p>Revenue: {data.monthly?.total_revenue}</p>
              <p className="muted">vs prior month: {data.monthly?.change_pct ?? '—'}%</p>
            </div>
          </div>
          <h3 style={{ marginTop: 16 }}>Products</h3>
          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Qty</th>
                <th>Revenue</th>
              </tr>
            </thead>
            <tbody>
              {(data.products?.products || []).map((p: any) => (
                <tr key={p.product_id}>
                  <td>{p.sku}</td>
                  <td>{p.name}</td>
                  <td>{p.quantity}</td>
                  <td>{p.revenue}</td>
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
              <div className="muted">Sales count</div>
              <div className="kpi">{data.total_sales ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Customers</div>
              <div className="kpi">{data.customer_count ?? 0}</div>
            </div>
          </div>
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Customer</th>
                <th>Sales</th>
                <th>Invoices</th>
                <th>POS</th>
                <th>Revenue</th>
                <th>Avg ticket</th>
              </tr>
            </thead>
            <tbody>
              {(data.customers || []).map((c: any) => (
                <tr key={c.customer_id || 'walk_in'}>
                  <td>{c.name}</td>
                  <td>{c.sale_count}</td>
                  <td>{c.invoice_count}</td>
                  <td>{c.pos_count}</td>
                  <td>{c.revenue}</td>
                  <td>{c.avg_ticket}</td>
                </tr>
              ))}
            </tbody>
          </table>
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

      {tab === 'inventory' && data && (
        <>
          <div className="card">
            <h3>Low stock ({data.lowStock?.count ?? 0})</h3>
            <ul>
              {(data.lowStock?.products || []).map((p: any) => (
                <li key={p.id}>
                  {p.name}: {p.stock_qty} / reorder {p.reorder_level}
                </li>
              ))}
            </ul>
          </div>

          <h3 style={{ marginTop: 16 }}>
            Stock valuation: {data.valuation?.total_value ?? data.balance?.total_value ?? 0}
          </h3>
          <p className="muted">
            {data.valuation?.costing_method_note ||
              'Value = quantity × product cost price (standard cost).'}
          </p>
          {(data.valuation?.by_warehouse || []).length > 0 && (
            <table className="table" style={{ marginBottom: 12 }}>
              <thead>
                <tr>
                  <th>Warehouse</th>
                  <th>Lines</th>
                  <th>Qty</th>
                  <th>Value</th>
                </tr>
              </thead>
              <tbody>
                {data.valuation.by_warehouse.map((w: any) => (
                  <tr key={w.warehouse_id}>
                    <td>
                      {w.warehouse_code} — {w.warehouse_name}
                    </td>
                    <td>{w.line_count}</td>
                    <td>{w.total_quantity}</td>
                    <td>{w.total_value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Warehouse</th>
                <th>Qty</th>
                <th>Cost</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {(data.valuation?.items || data.balance?.items || []).slice(0, 50).map((i: any) => (
                <tr key={`${i.warehouse_id || 'all'}-${i.product_id}`}>
                  <td>{i.sku}</td>
                  <td>{i.name}</td>
                  <td>{i.warehouse_code || '—'}</td>
                  <td>{i.quantity}</td>
                  <td>{i.cost_price ?? '—'}</td>
                  <td>{i.value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'purchases' && data && (
        <>
          <div className="card">
            <p>Orders: {data.summary?.order_count}</p>
            <p>Total: {data.summary?.total_amount}</p>
            <p>Outstanding: {data.summary?.outstanding_amount}</p>
          </div>
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

          <h3 style={{ marginTop: 16 }}>
            Pending orders ({data.pending?.count ?? 0}) — open qty {data.pending?.open_qty ?? 0}
          </h3>
          <table className="table">
            <thead>
              <tr>
                <th>PO</th>
                <th>Supplier</th>
                <th>Status</th>
                <th>Ordered</th>
                <th>Received</th>
                <th>Open</th>
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
                  <td>{o.open_qty}</td>
                  <td>{o.total_amount}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3 style={{ marginTop: 16 }}>
            Purchase returns ({data.returns?.return_count ?? 0}) — posted{' '}
            {data.returns?.posted_amount ?? 0}
          </h3>
          <table className="table">
            <thead>
              <tr>
                <th>Reason</th>
                <th>Count</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.returns?.by_reason || []).map((r: any) => (
                <tr key={r.reason}>
                  <td>{r.reason}</td>
                  <td>{r.return_count}</td>
                  <td>{r.total_amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <table className="table" style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Return</th>
                <th>Supplier</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.returns?.returns || []).map((r: any) => (
                <tr key={r.id}>
                  <td>{r.return_number}</td>
                  <td>{r.supplier_name}</td>
                  <td>{r.reason}</td>
                  <td>{r.status}</td>
                  <td>{r.total_amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'expenses' && data && (
        <>
          <div className="kpi">{data.total_amount ?? 0}</div>
          <table className="table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.by_category || []).map((c: any) => (
                <tr key={c.category}>
                  <td>{c.category}</td>
                  <td>{c.amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'pnl' && data && (
        <>
          <div className="grid">
            <div className="card">
              <div className="muted">Revenue</div>
              <div className="kpi">{data.revenue ?? data.income}</div>
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
              <div className="kpi">{data.net_profit}</div>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 8 }}>
            Period: {data.from_date || 'all'} → {data.to_date || 'all'}
          </p>
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Bucket</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.accounts || []).map((a: any) => (
                <tr key={a.account_id || a.code}>
                  <td>{a.code}</td>
                  <td>{a.name}</td>
                  <td>{a.bucket || a.account_type}</td>
                  <td>{a.balance}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'cashflow' && data && (
        <>
          <div className="grid">
            <div className="card">
              <div className="muted">Opening cash</div>
              <div className="kpi">{data.opening_cash ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Operating</div>
              <div className="kpi">{data.operating?.net ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Investing</div>
              <div className="kpi">{data.investing?.net ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Financing</div>
              <div className="kpi">{data.financing?.net ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Net change</div>
              <div className="kpi">{data.net_change ?? data.net}</div>
            </div>
            <div className="card">
              <div className="muted">Closing cash</div>
              <div className="kpi">{data.closing_cash ?? data.net}</div>
            </div>
          </div>
          <p className="muted" style={{ marginTop: 8 }}>
            Transfers (cash↔bank): {data.transfers?.net ?? 0} · Period: {data.from_date || 'all'} →{' '}
            {data.to_date || 'all'}
          </p>
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

      {tab === 'balancesheet' && data && (
        <>
          <p className="muted" style={{ marginBottom: 8 }}>
            As of {data.as_of || '—'} (set To date above as the as-of date)
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Total assets</div>
              <div className="kpi">{data.total_assets}</div>
            </div>
            <div className="card">
              <div className="muted">Liabilities + equity</div>
              <div className="kpi">{data.total_liabilities_and_equity}</div>
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
                  </tr>
                </thead>
                <tbody>
                  {(data[section] || []).map((r: any) => (
                    <tr key={`${section}-${r.code}`}>
                      <td>{r.code}</td>
                      <td>{r.name}</td>
                      <td>{r.balance}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </>
      )}

      {tab === 'credit' && data && (
        <>
          <p className="muted">
            Credit aging surfaces the same AR/AP engine as the Credit module (no parallel report).{' '}
            <a href="/credit">Open Credit module →</a>
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">AR total due</div>
              <div className="kpi">{data.ar?.total_due ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">AP total due</div>
              <div className="kpi">{data.ap?.total_due ?? 0}</div>
            </div>
          </div>
          <h3 style={{ marginTop: 16 }}>Receivables (parties)</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Customer</th>
                <th>Total due</th>
                <th>Balance</th>
                <th>Limit</th>
              </tr>
            </thead>
            <tbody>
              {(data.ar?.parties || []).slice(0, 25).map((p: any) => (
                <tr key={`ar-${p.party_id}`}>
                  <td>{p.name}</td>
                  <td>{p.total_due}</td>
                  <td>{p.balance}</td>
                  <td>{p.credit_limit}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h3 style={{ marginTop: 16 }}>Payables (parties)</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Supplier</th>
                <th>Total due</th>
                <th>Balance</th>
              </tr>
            </thead>
            <tbody>
              {(data.ap?.parties || []).slice(0, 25).map((p: any) => (
                <tr key={`ap-${p.party_id}`}>
                  <td>{p.name}</td>
                  <td>{p.total_due}</td>
                  <td>{p.balance}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'tax' && data && (
        <>
          <p className="muted">
            Tax report and filing pack use the same endpoints as Tax Management.{' '}
            <a href="/tax">Open Tax module →</a>
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Output tax</div>
              <div className="kpi">{data.tax?.output_tax ?? data.filing?.output_tax ?? '—'}</div>
            </div>
            <div className="card">
              <div className="muted">Input tax</div>
              <div className="kpi">{data.tax?.input_tax ?? data.filing?.input_tax ?? '—'}</div>
            </div>
            <div className="card">
              <div className="muted">Net payable</div>
              <div className="kpi">
                {data.tax?.net_tax_payable ?? data.filing?.net_tax_payable ?? '—'}
              </div>
            </div>
          </div>
          <h3 style={{ marginTop: 16 }}>Filing boxes</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Box</th>
                <th>Label</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(data.filing?.filing_boxes?.boxes || data.filing?.boxes || []).map((b: any) => (
                <tr key={`box-${b.box}`}>
                  <td>{b.box}</td>
                  <td>{b.label}</td>
                  <td>{b.amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'transfers' && data && (
        <>
          <p className="muted">
            Consolidated transfer history for inter-store and warehouse moves (BR-13.2).{' '}
            <a href="/stores">Open Stores →</a>
          </p>
          <div className="grid">
            <div className="card">
              <div className="muted">Transfers</div>
              <div className="kpi">{data.count ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Qty requested</div>
              <div className="kpi">{data.total_qty_requested ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Qty received</div>
              <div className="kpi">{data.total_qty_received ?? 0}</div>
            </div>
          </div>
          <h3 style={{ marginTop: 16 }}>Transfer history</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Status</th>
                <th>From store</th>
                <th>To store</th>
                <th>Items</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {(data.transfers || []).map((t: any) => (
                <tr key={t.id}>
                  <td>{t.transfer_number}</td>
                  <td>{t.status}</td>
                  <td>{t.from_store_id || '—'}</td>
                  <td>{t.to_store_id || '—'}</td>
                  <td>{(t.items || []).length}</td>
                  <td>{t.created_at ? String(t.created_at).slice(0, 19) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'schedules' && (
        <>
          <p className="muted">
            Company admins can schedule CSV, Excel, or PDF reports emailed on a daily or weekly cadence (UTC hour).
          </p>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 640 }}>
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
