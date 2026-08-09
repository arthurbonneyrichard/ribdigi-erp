'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
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
};

type InsightCard = {
  id: string;
  kind: string;
  severity: string;
  title: string;
  summary: string;
  action?: string | null;
};

export default function Page() {
  const [d, setD] = useState<Dash>({});
  const [insightCards, setInsightCards] = useState<InsightCard[]>([]);
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
  }, []);

  const n = (v: number | string | null | undefined) => formatNumber(v, formats.number_format);

  const cards: [string, number | string][] = [
    ['Total Sales', d.total_sales ?? 0],
    ['Purchases', d.total_purchases ?? 0],
    ['Expenses', d.total_expenses ?? 0],
    ['Customers', d.customers ?? 0],
    ['Suppliers', d.suppliers ?? 0],
    ['Products', d.products ?? 0],
    ['Low Stock', d.low_stock ?? 0],
    ['Out of Stock', d.out_of_stock ?? 0],
    ['Expiring (30d)', d.expiring_batches ?? 0],
    ['Today Revenue', d.daily_revenue ?? 0],
    ['Month Revenue', d.monthly_revenue ?? 0],
    ['Prior Month', d.prior_month_revenue ?? 0],
    [
      'MoM %',
      d.mom_change_pct == null ? '—' : `${n(d.mom_change_pct)}%`,
    ],
  ];

  const maxTop = Math.max(1, ...(d.top_products || []).map((p) => Number(p.revenue) || 0));

  return (
    <Shell>
      <h1>Executive Dashboard</h1>
      <p className="muted">Live KPIs from your tenant data</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      <div className="grid">
        {cards.map(([label, v]) => (
          <div className="card" key={label}>
            <div className="muted">{label}</div>
            <div className="kpi">{typeof v === 'number' ? n(v) : v}</div>
          </div>
        ))}
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
