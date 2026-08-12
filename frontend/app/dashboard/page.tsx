'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { DailyRevenueLineChart, MonthlyRevenueBarChart } from '../../components/RevenueCharts';
import { api } from '../../lib/api';
import { formatDateTime, formatNumber, type RegionalFormats } from '../../lib/format';

type Dash = {
  total_sales?: number;
  total_purchases?: number;
  total_expenses?: number;
  expenses_by_category?: { category: string; total: number }[];
  credit_outstanding?: number;
  ar_total_due?: number;
  ap_total_due?: number;
  ap_outstanding?: number;
  profit_summary?: number;
  income_mtd?: number;
  products?: number;
  low_stock?: number;
  out_of_stock?: number;
  expiring_batches?: number;
  customers?: number;
  suppliers?: number;
  daily_revenue?: number;
  yesterday_revenue?: number;
  dod_change_pct?: number | null;
  monthly_revenue?: number;
  prior_month_revenue?: number;
  mom_change_pct?: number | null;
  recent_sales?: { source: string; reference: string; total: number; at?: string }[];
  top_products?: { name: string; sku: string; quantity: number; revenue: number }[];
  daily_revenue_series?: { date: string; revenue: number }[];
  monthly_revenue_series?: { month: string; revenue: number }[];
  kpi_links?: Record<string, string>;
  view?: string;
  sections?: string[];
  role_label?: string;
  user_stats?: {
    total_users?: number;
    active_users?: number;
    inactive_users?: number;
    custom_roles?: number;
    system_roles?: number;
    recent_logins_7d?: number;
  };
};

type PosShift = {
  session_id?: string;
  status?: string;
  store_id?: string;
  opened_at?: string;
  opening_cash?: number;
} | null;

type InsightCard = {
  id: string;
  kind: string;
  severity: string;
  title: string;
  summary: string;
  action?: string | null;
  domains?: string[];
};

type Note = {
  id: string;
  category: string;
  group?: string;
  title: string;
  message: string;
  status: string;
  created_at?: string;
  entity_type?: string | null;
  entity_id?: string | null;
};

function notificationHref(note: Note): string | null {
  const t = (note.entity_type || '').toLowerCase();
  if (t === 'product' || t === 'warehouse_stock') return '/inventory?tab=products';
  if (t === 'sales_invoice') return '/sales?tab=invoices';
  if (t === 'sales_quotation') return '/sales?tab=quotations';
  if (t === 'purchase_invoice') return '/purchasing?tab=invoices';
  // Stage 99 C1 — purchase orders deep-link to Orders (not invoices)
  if (t === 'purchase_order') return '/purchasing?tab=orders';
  // Stage 101 E1 — expense / approval → pending queue; recurring → #recurring
  if (t === 'expense' || t === 'expense_approval') return '/expenses?status=pending';
  if (t === 'recurring_expense') return '/expenses#recurring';
  if (t.includes('stock') || t.includes('batch')) return '/inventory?tab=lowstock';
  return null;
}

type KpiCard = {
  key: string;
  label: string;
  value: number | string;
  href?: string;
};

export default function Page() {
  const [d, setD] = useState<Dash>({});
  const [insightCards, setInsightCards] = useState<InsightCard[]>([]);
  const [notes, setNotes] = useState<Note[]>([]);
  const [unread, setUnread] = useState(0);
  const [formats, setFormats] = useState<RegionalFormats>({});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [posShift, setPosShift] = useState<PosShift>(undefined as unknown as PosShift);
  const [posShiftLoaded, setPosShiftLoaded] = useState(false);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  async function exportDashboardCsv() {
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/dashboard/export`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
      });
      if (!res.ok) throw new Error('Dashboard CSV export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'tenant_dashboard_export.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('Dashboard aggregates CSV downloaded (Stage 153 B1)');
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }

  async function exportDashboardSliceCsv(path: string, filename: string, okMessage: string) {
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}${path}`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenant || '',
        },
      });
      if (!res.ok) throw new Error(`${filename} export failed`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(okMessage);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }

  useEffect(() => {
    api('/me')
      .then((r) =>
        setFormats({
          date_format: r.data?.date_format,
          number_format: r.data?.number_format,
          time_format: r.data?.time_format,
        }),
      )
      .catch(() => undefined);
    api('/dashboard')
      .then((r) => {
        const data = r.data || {};
        setD(data);
        if (data.view === 'cashier') {
          api('/pos/sessions/current')
            .then((sr) => {
              setPosShift(sr.data || null);
              setPosShiftLoaded(true);
            })
            .catch(() => {
              setPosShift(null);
              setPosShiftLoaded(true);
            });
        }
      })
      .catch((err) => setError(err.message));
    api('/ai/insights')
      .then((r) => setInsightCards(r.data?.cards || []))
      .catch(() => undefined);
    Promise.all([
      api('/notifications?status=unread').catch(() => ({ data: [] })),
      api('/notifications/unread-count').catch(() => ({ data: { count: 0 } })),
    ])
      .then(([list, count]) => {
        setNotes((list.data || []).slice(0, 8));
        setUnread(count.data?.count || 0);
      })
      .catch(() => undefined);
  }, []);

  const n = (v: number | string | null | undefined) => formatNumber(v, formats.number_format);
  const links = d.kpi_links || {};
  const view = d.view || 'executive';
  const has = (key: string) => Object.prototype.hasOwnProperty.call(d, key);

  const allCards: KpiCard[] = [
    { key: 'total_sales', label: 'Total Sales', value: d.total_sales ?? 0, href: links.total_sales },
    { key: 'daily_revenue', label: "Today's Sales", value: d.daily_revenue ?? 0, href: links.daily_revenue },
    { key: 'total_purchases', label: 'Purchases', value: d.total_purchases ?? 0, href: links.total_purchases },
    { key: 'total_expenses', label: 'Expenses', value: d.total_expenses ?? 0, href: links.total_expenses },
    {
      key: 'income_mtd',
      label: 'Income (MTD)',
      value: d.income_mtd ?? 0,
      href: links.income_mtd,
    },
    {
      key: 'profit_summary',
      label: 'Profit Summary (MTD)',
      value: d.profit_summary ?? 0,
      href: links.profit_summary,
    },
    {
      key: 'credit_outstanding',
      label: 'Receivables (AR)',
      value: d.credit_outstanding ?? d.ar_total_due ?? 0,
      href: links.credit_outstanding || links.ar_total_due,
    },
    {
      key: 'ap_total_due',
      label: 'Payables (AP)',
      value: d.ap_total_due ?? d.ap_outstanding ?? 0,
      href: links.ap_total_due || links.ap_outstanding,
    },
    { key: 'customers', label: 'Customers', value: d.customers ?? 0, href: links.customers },
    { key: 'suppliers', label: 'Suppliers', value: d.suppliers ?? 0, href: links.suppliers },
    { key: 'products', label: 'Products', value: d.products ?? 0, href: links.products },
    { key: 'low_stock', label: 'Low Stock', value: d.low_stock ?? 0, href: links.low_stock },
    { key: 'out_of_stock', label: 'Out of Stock', value: d.out_of_stock ?? 0, href: links.out_of_stock },
    {
      key: 'expiring_batches',
      label: 'Expiring (30d)',
      value: d.expiring_batches ?? 0,
      href: links.expiring_batches,
    },
    {
      key: 'yesterday_revenue',
      label: 'Yesterday Revenue',
      value: d.yesterday_revenue ?? 0,
      href: links.yesterday_revenue,
    },
    {
      key: 'dod_change_pct',
      label: 'DoD %',
      value: d.dod_change_pct == null ? '—' : `${n(d.dod_change_pct)}%`,
      href: links.dod_change_pct,
    },
    { key: 'monthly_revenue', label: 'Monthly Sales', value: d.monthly_revenue ?? 0, href: links.monthly_revenue },
    {
      key: 'prior_month_revenue',
      label: 'Prior Month',
      value: d.prior_month_revenue ?? 0,
      href: links.prior_month_revenue,
    },
    {
      key: 'mom_change_pct',
      label: 'MoM %',
      value: d.mom_change_pct == null ? '—' : `${n(d.mom_change_pct)}%`,
      href: links.mom_change_pct,
    },
  ];
  const cards = allCards.filter((c) => has(c.key));
  if (d.user_stats) {
    cards.push(
      { key: 'user_total', label: 'Tenant Users', value: d.user_stats.total_users ?? 0, href: links.user_stats },
      { key: 'user_active', label: 'Active Users', value: d.user_stats.active_users ?? 0, href: links.user_stats },
      { key: 'user_inactive', label: 'Inactive Users', value: d.user_stats.inactive_users ?? 0, href: links.user_stats },
      {
        key: 'user_roles',
        label: 'Custom Roles',
        value: d.user_stats.custom_roles ?? 0,
        href: links.custom_roles || '/admin/roles#custom',
      },
      {
        key: 'user_recent',
        label: 'Logins (7d)',
        value: d.user_stats.recent_logins_7d ?? 0,
        href: links.user_stats,
      },
    );
  }

  const maxTop = Math.max(1, ...(d.top_products || []).map((p) => Number(p.revenue) || 0));
  const title =
    view === 'cashier'
      ? 'Cashier Dashboard'
      : view === 'store_manager'
        ? 'Store Manager Dashboard'
        : 'Tenant Admin Dashboard';
  const subtitle =
    view === 'cashier'
      ? 'POS-focused KPIs for your shift — company accounting is hidden'
      : view === 'store_manager'
        ? 'Store operations KPIs from your tenant data'
        : `Business Overview for ${d.role_label || 'Tenant Admin'} — click a card to open the related module`;

  return (
    <Shell>
      <h1>{title}</h1>
      <p className="muted">{subtitle}</p>
      {view !== 'cashier' && (
        <p className="muted" style={{ marginTop: -4 }}>
          Business Overview · Today&apos;s Sales · Purchases · Expenses · Income · Profit · Receivables ·
          Payables · Stock alerts. Export via <code>GET /dashboard/export</code> (Stage 153 B1; real
          KPIs — no fabricated MRR).
        </p>
      )}
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}
      <p style={{ marginTop: 8 }}>
        <button type="button" onClick={exportDashboardCsv}>
          Export aggregates CSV
        </button>
      </p>
      <div className="grid">
        {cards.map((card) => {
          const body = (
            <>
              <div className="muted">{card.label}</div>
              <div className="kpi">{typeof card.value === 'number' ? n(card.value) : card.value}</div>
            </>
          );
          if (card.href) {
            return (
              <Link
                key={card.key}
                href={card.href}
                className="card"
                style={{ display: 'block', textDecoration: 'none', color: 'inherit' }}
              >
                {body}
              </Link>
            );
          }
          return (
            <div className="card" key={card.key}>
              {body}
            </div>
          );
        })}
      </div>

      {(has('daily_revenue_series') || has('monthly_revenue_series')) && (
        <div style={{ marginTop: 20 }}>
          <p className="muted">
            Sales-trend series export via <code>GET /dashboard/sales-trend/export</code> (Stage 157
            S1).
          </p>
          <p style={{ marginBottom: 8 }}>
            <button
              type="button"
              onClick={() =>
                exportDashboardSliceCsv(
                  '/dashboard/sales-trend/export',
                  'dashboard_sales_trend_export.csv',
                  'Dashboard sales-trend CSV downloaded (Stage 157 S1)',
                )
              }
            >
              Export sales-trend CSV
            </button>
          </p>
          <div className="grid">
            {has('daily_revenue_series') && (
              <div className="card">
                <DailyRevenueLineChart series={d.daily_revenue_series || []} formatValue={n} />
              </div>
            )}
            {has('monthly_revenue_series') && (
              <div className="card">
                <MonthlyRevenueBarChart series={d.monthly_revenue_series || []} formatValue={n} />
              </div>
            )}
          </div>
        </div>
      )}

      {view === 'cashier' && (
        <div className="card" style={{ marginTop: 20 }}>
          <h3 style={{ marginTop: 0 }}>POS</h3>
          {posShiftLoaded ? (
            posShift ? (
              <p>
                Shift open
                {posShift.opened_at ? (
                  <span className="muted">
                    {' '}
                    · since {formatDateTime(posShift.opened_at, formats.date_format, formats.time_format)}
                  </span>
                ) : null}
              </p>
            ) : (
              <p className="muted">No open POS shift — open the register to start selling.</p>
            )
          ) : (
            <p className="muted">Checking shift status…</p>
          )}
          <Link href="/pos" className="btn" style={{ display: 'inline-block', marginTop: 8 }}>
            {posShift ? 'Continue POS' : 'Open POS'}
          </Link>
          {!posShift && posShiftLoaded ? (
            <Link
              href="/pos#sessions"
              className="btn"
              style={{ display: 'inline-block', marginTop: 8, marginLeft: 8 }}
            >
              Session history
            </Link>
          ) : null}
        </div>
      )}

      {has('expenses_by_category') && view !== 'cashier' && (
        <div className="card" style={{ marginTop: 20 }}>
          <h3 style={{ marginTop: 0 }}>Expenses by category</h3>
          {(d.expenses_by_category || []).length === 0 ? (
            <p className="muted">No approved expenses yet</p>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {(d.expenses_by_category || []).map((row) => (
                  <tr key={row.category}>
                    <td>{row.category}</td>
                    <td>{n(row.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      <div className="card" style={{ marginTop: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'baseline' }}>
          <h3 style={{ margin: 0 }}>Notifications</h3>
          <Link href="/notifications" className="muted">
            {unread > 0 ? `${unread} unread · view all` : 'View history'}
          </Link>
        </div>
        <p className="muted" style={{ marginTop: 4 }}>
          Unread stream by category group (stock, orders, payments, system)
        </p>
        {notes.length === 0 ? (
          <p className="muted">No unread notifications</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Group</th>
                <th>Title</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {notes.map((note) => {
                const href = notificationHref(note);
                return (
                  <tr key={note.id}>
                    <td>{note.group || note.category}</td>
                    <td>
                      {href ? (
                        <Link href={href}>{note.title}</Link>
                      ) : (
                        note.title
                      )}
                    </td>
                    <td>{note.message}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {insightCards.length > 0 && view !== 'cashier' && (
        <div className="card" style={{ marginTop: 20 }}>
          <h3>AI insights</h3>
          <p className="muted" style={{ marginBottom: 8 }}>
            Rule-based business insights from actual Inventory, Sales, Purchases, and Expenses.
          </p>
          <div className="grid">
            {insightCards.slice(0, 6).map((c) => (
              <div key={c.id} style={{ borderTop: '1px solid #e5e7eb', paddingTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <strong>{c.title}</strong>
                  <span className="muted">{c.severity}</span>
                </div>
                <p style={{ margin: '6px 0' }}>{c.summary}</p>
                {c.action && <p className="muted">{c.action}</p>}
                {Array.isArray(c.domains) && c.domains.length > 0 && (
                  <p className="muted" style={{ marginTop: 4 }}>
                    Actuals: {c.domains.join(' · ')}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {(has('top_products') || has('recent_sales')) && (
        <div className="grid" style={{ marginTop: 20 }}>
          {has('top_products') && (
            <div className="card">
              <h3>Top products</h3>
              <p className="muted">
                Export via <code>GET /dashboard/top-products/export</code> (Stage 157 T1).
              </p>
              <button
                type="button"
                style={{ marginBottom: 8 }}
                onClick={() =>
                  exportDashboardSliceCsv(
                    '/dashboard/top-products/export',
                    'dashboard_top_products_export.csv',
                    'Dashboard top-products CSV downloaded (Stage 157 T1)',
                  )
                }
              >
                Export top-products CSV
              </button>
              {(d.top_products || []).length === 0 && <p className="muted">No posted invoice lines yet</p>}
              {(d.top_products || []).map((p) => (
                <div key={p.sku} style={{ marginBottom: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span>
                      {p.name} <span className="muted">({p.sku})</span>
                    </span>
                    <span>{n(p.revenue)}</span>
                  </div>
                  <div style={{ height: 6, background: '#e5e7eb', marginTop: 4 }}>
                    <div
                      style={{
                        height: 6,
                        width: `${Math.round((Number(p.revenue) / maxTop) * 100)}%`,
                        background: '#0f766e',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
          {has('recent_sales') && (
            <div className="card">
              <h3>Recent sales</h3>
              {(d.recent_sales || []).length === 0 && <p className="muted">No recent sales</p>}
              <table className="table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Ref</th>
                    <th>Source</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(d.recent_sales || []).map((r) => (
                    <tr key={`${r.source}-${r.reference}`}>
                      <td>{formatDateTime(r.at, formats.date_format, formats.time_format)}</td>
                      <td>{r.reference}</td>
                      <td>{r.source}</td>
                      <td>{n(r.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
