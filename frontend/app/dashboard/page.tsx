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
  products?: number;
  low_stock?: number;
  out_of_stock?: number;
  expiring_batches?: number;
  customers?: number;
  suppliers?: number;
  daily_revenue?: number;
  monthly_revenue?: number;
  prior_month_revenue?: number;
  mom_change_pct?: number | null;
  recent_sales?: { source: string; reference: string; total: number; at?: string }[];
  top_products?: { name: string; sku: string; quantity: number; revenue: number }[];
  daily_revenue_series?: { date: string; revenue: number }[];
  monthly_revenue_series?: { month: string; revenue: number }[];
  kpi_links?: Record<string, string>;
};

type InsightCard = {
  id: string;
  kind: string;
  severity: string;
  title: string;
  summary: string;
  action?: string | null;
};

type Note = {
  id: string;
  category: string;
  group?: string;
  title: string;
  message: string;
  status: string;
  created_at?: string;
};

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
      .then((r) => setD(r.data || {}))
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

  const cards: KpiCard[] = [
    { key: 'total_sales', label: 'Total Sales', value: d.total_sales ?? 0, href: links.total_sales },
    { key: 'total_purchases', label: 'Purchases', value: d.total_purchases ?? 0, href: links.total_purchases },
    { key: 'total_expenses', label: 'Expenses', value: d.total_expenses ?? 0, href: links.total_expenses },
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
    { key: 'daily_revenue', label: 'Today Revenue', value: d.daily_revenue ?? 0, href: links.daily_revenue },
    { key: 'monthly_revenue', label: 'Month Revenue', value: d.monthly_revenue ?? 0, href: links.monthly_revenue },
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

  const maxTop = Math.max(1, ...(d.top_products || []).map((p) => Number(p.revenue) || 0));

  return (
    <Shell>
      <h1>Executive Dashboard</h1>
      <p className="muted">Live KPIs from your tenant data — click a card to open the related report or module</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
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

      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card">
          <DailyRevenueLineChart series={d.daily_revenue_series || []} formatValue={n} />
        </div>
        <div className="card">
          <MonthlyRevenueBarChart series={d.monthly_revenue_series || []} formatValue={n} />
        </div>
      </div>

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
              {notes.map((note) => (
                <tr key={note.id}>
                  <td>{note.group || note.category}</td>
                  <td>{note.title}</td>
                  <td>{note.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {insightCards.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <h3>AI insights</h3>
          <p className="muted" style={{ marginBottom: 8 }}>
            Rule-based anomalies and restock suggestions from your sales, expenses, and stock.
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
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid" style={{ marginTop: 20 }}>
        <div className="card">
          <h3>Top products</h3>
          {(d.top_products || []).length === 0 && <p className="muted">No posted invoice lines yet</p>}
          {(d.top_products || []).map((p) => (
            <div key={p.sku} style={{ marginBottom: 10 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <span>
                  {p.name} <span className="muted">({p.sku})</span>
                </span>
                <span>{n(p.revenue)}</span>
              </div>
              <div
                style={{
                  height: 6,
                  background: '#e5e7eb',
                  marginTop: 4,
                }}
              >
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
                  <td>
                    {formatDateTime(r.at, formats.date_format, formats.time_format)}
                  </td>
                  <td>{r.reference}</td>
                  <td>{r.source}</td>
                  <td>{n(r.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Shell>
  );
}
