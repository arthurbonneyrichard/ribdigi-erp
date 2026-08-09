'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { useTabQuery } from '../../lib/tabQuery';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Tab =
  | 'summary'
  | 'sales'
  | 'salesperson'
  | 'stores'
  | 'inventory'
  | 'purchases'
  | 'expenses'
  | 'pnl'
  | 'cashflow'
  | 'balancesheet'
  | 'schedules';
const REPORT_TABS: Tab[] = [
  'summary',
  'sales',
  'salesperson',
  'stores',
  'inventory',
  'purchases',
  'expenses',
  'pnl',
  'cashflow',
  'balancesheet',
  'schedules',
];

const TAB_EXPORT: Record<Exclude<Tab, 'schedules'>, string> = {
  summary: 'summary',
  sales: 'sales_products',
  salesperson: 'sales_salesperson',
  stores: 'sales_by_store',
  inventory: 'inventory_low_stock',
  purchases: 'purchases_summary',
  expenses: 'expenses_summary',
  pnl: 'profit_loss',
  cashflow: 'cash_flow',
  balancesheet: 'balance_sheet',
};

const REPORT_TYPES = [
  'summary',
  'sales_daily',
  'sales_monthly',
  'sales_products',
  'sales_salesperson',
  'sales_by_store',
  'inventory_balance',
  'inventory_low_stock',
  'purchases_summary',
  'expenses_summary',
  'profit_loss',
  'cash_flow',
  'balance_sheet',
  'tax',
  'tax_filing',
  'tax_filing_gh',
];

export default function Page() {
  const [tab, setTab] = useTabQuery(REPORT_TABS, 'summary');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
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
      if (nextTab === 'sales') path = `/reports/sales/products${qs()}`;
      if (nextTab === 'salesperson') path = `/reports/sales/salesperson${qs()}`;
      if (nextTab === 'stores') path = `/reports/sales/by-store${qs()}`;
      if (nextTab === 'inventory') path = '/reports/inventory/low-stock';
      if (nextTab === 'purchases') path = `/reports/purchases/summary${qs()}`;
      if (nextTab === 'expenses') path = `/reports/expenses/summary${qs()}`;
      if (nextTab === 'pnl') path = `/reports/profit-loss${qs()}`;
      if (nextTab === 'cashflow') path = `/reports/cash-flow${qs()}`;
      if (nextTab === 'balancesheet') path = '/reports/balance-sheet';
      const r = await api(path);
      if (nextTab === 'sales') {
        const [daily, monthly] = await Promise.all([
          api('/reports/sales/daily'),
          api('/reports/sales/monthly'),
        ]);
        setData({ products: r.data, daily: daily.data, monthly: monthly.data });
      } else if (nextTab === 'inventory') {
        const [balance, movements] = await Promise.all([
          api('/reports/inventory/balance'),
          api('/reports/inventory/movements'),
        ]);
        setData({ lowStock: r.data, balance: balance.data, movements: movements.data });
      } else if (nextTab === 'purchases') {
        const suppliers = await api(`/reports/purchases/suppliers${qs()}`);
        setData({ summary: r.data, suppliers: suppliers.data });
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
            ['stores', 'Stores'],
            ['inventory', 'Inventory'],
            ['purchases', 'Purchases'],
            ['expenses', 'Expenses'],
            ['pnl', 'P&L'],
            ['cashflow', 'Cash flow'],
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
          <h3 style={{ marginTop: 16 }}>Stock value: {data.balance?.total_value ?? 0}</h3>
          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Qty</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {(data.balance?.items || []).slice(0, 50).map((i: any) => (
                <tr key={i.product_id}>
                  <td>{i.sku}</td>
                  <td>{i.name}</td>
                  <td>{i.quantity}</td>
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
