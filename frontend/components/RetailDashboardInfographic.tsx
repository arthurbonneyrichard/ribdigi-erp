'use client';

import { useEffect, useState } from 'react';
import { api } from '../lib/api';

export function DailyBars({
  data,
  field,
  color,
}: {
  data: { label: string; sales: number; profit: number }[];
  field: 'sales' | 'profit';
  color: string;
}) {
  const n = data.length || 1;
  const max = Math.max(1, ...data.map((x) => x[field] || 0));
  const slot = 300 / n;
  const bw = Math.min(26, slot * 0.55);
  return (
    <svg viewBox="0 0 300 172" width="100%" height="172" role="img" aria-label={`Daily ${field}`}>
      <line x1="8" y1="138" x2="292" y2="138" stroke="#D4E5C4" />
      {data.map((t, i) => {
        const v = t[field] || 0;
        const h = Math.max(0, (v / max) * 112);
        const x = i * slot + (slot - bw) / 2;
        const y = 138 - h;
        return (
          <g key={t.label + i}>
            <rect x={x} y={y} width={bw} height={h} rx={5} fill={color} />
            <text x={x + bw / 2} y={y - 5} textAnchor="middle" className="vbar-val">
              {v ? new Intl.NumberFormat().format(Math.round(v)) : ''}
            </text>
            <text x={x + bw / 2} y={156} textAnchor="middle" className="vbar-label">
              {t.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function TrendLine({
  data,
  color,
}: {
  data: { label: string; sales: number }[];
  color: string;
}) {
  const max = Math.max(1, ...data.map((x) => x.sales || 0));
  const pts = data.map((t, i) => {
    const x = data.length <= 1 ? 150 : (i / (data.length - 1)) * 284 + 8;
    const y = 138 - ((t.sales || 0) / max) * 112;
    return `${x},${y}`;
  });
  return (
    <svg viewBox="0 0 300 172" width="100%" height="172" role="img" aria-label="30-day sales">
      <line x1="8" y1="138" x2="292" y2="138" stroke="#D4E5C4" />
      <polyline fill="none" stroke={color} strokeWidth="2.5" points={pts.join(' ')} />
      <text x="8" y="156" className="vbar-label">
        {data[0]?.label || ''}
      </text>
      <text x="292" y="156" textAnchor="end" className="vbar-label">
        {data[data.length - 1]?.label || ''}
      </text>
    </svg>
  );
}

type DayPoint = { label: string; sales: number; profit: number };

type DashSlice = {
  total_sales?: number;
  products?: number;
  low_stock?: number;
  out_of_stock?: number;
  expiring_soon?: number;
  comparisons?: {
    sales_today?: number;
    sales_yesterday?: number;
    sales_today_pct?: number | null;
    sales_mtd?: number;
    sales_prev_month?: number;
    sales_mtd_pct?: number | null;
  };
  daily_sales?: DayPoint[];
};

function num(v?: number) {
  return new Intl.NumberFormat().format(Math.round((v || 0) * 100) / 100);
}

function pctLabel(pct?: number | null) {
  if (pct == null) return '—';
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct}%`;
}

export default function RetailDashboardInfographic({ storeId }: { storeId?: string | null }) {
  const [d, setD] = useState<DashSlice | null>(null);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    const qs = storeId ? `?store_id=${encodeURIComponent(storeId)}` : '';
    setStatus('loading');
    api(`/dashboard${qs}`)
      .then((r) => {
        if (cancelled) return;
        setD((r.data || {}) as DashSlice);
        setStatus('ready');
      })
      .catch(() => {
        if (!cancelled) setStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, [storeId]);

  const cmp = d?.comparisons || {};
  const dailyAll = d?.daily_sales || [];
  const daily = dailyAll.slice(-7);
  const dailyEmpty = daily.every((x) => !x.sales && !x.profit);
  const trendEmpty = dailyAll.every((x) => !x.sales);

  return (
    <section className="tpos-cashier-dash" aria-label="Dashboard">
      {status === 'loading' && !d ? <p className="muted">Loading dashboard…</p> : null}
      {status === 'error' && !d ? (
        <p className="muted" role="status">
          Dashboard figures are unavailable right now.
        </p>
      ) : null}
      {d ? (
        <>
          <section className="stat-grid">
            <div className="stat s-sales">
              <span className="rail" />
              <div className="label">Sales today</div>
              <div className="val">{num(cmp.sales_today)}</div>
              <p className="hint" style={{ marginTop: 6, fontSize: 12 }}>
                Yesterday {num(cmp.sales_yesterday)}. Change versus yesterday: {pctLabel(cmp.sales_today_pct)}.
              </p>
            </div>
            <div className="stat s-sales">
              <span className="rail" />
              <div className="label">Sales this month</div>
              <div className="val">{num(cmp.sales_mtd)}</div>
              <p className="hint" style={{ marginTop: 6, fontSize: 12 }}>
                Last month {num(cmp.sales_prev_month)}. Change versus last month: {pctLabel(cmp.sales_mtd_pct)}.
              </p>
            </div>
            <div className="stat s-sales">
              <span className="rail" />
              <div className="label">Total sales</div>
              <div className="val">{num(d.total_sales)}</div>
              <p className="hint" style={{ marginTop: 6, fontSize: 12 }}>
                Recorded sales
              </p>
            </div>
            <div className="stat">
              <div className="label">Products</div>
              <div className="val">{num(d.products)}</div>
            </div>
            <div className="stat">
              <div className="label">Low stock</div>
              <div className="val">{num(d.low_stock)}</div>
            </div>
            <div className="stat">
              <div className="label">Out of stock</div>
              <div className="val">{num(d.out_of_stock)}</div>
            </div>
            <div className="stat">
              <div className="label">Expiring soon</div>
              <div className="val">{num(d.expiring_soon)}</div>
            </div>
          </section>
          <section className="info-grid">
            <div className="panel">
              <h3>Daily sales (7d)</h3>
              <p className="hint">Last 7 days</p>
              {dailyEmpty ? (
                <div className="empty">No sales in the last 7 days yet.</div>
              ) : (
                <DailyBars data={daily} field="sales" color="#4AB012" />
              )}
            </div>
            <div className="panel">
              <h3>Revenue trend (30d)</h3>
              <p className="hint">Sales each day for the last 30 days</p>
              {trendEmpty ? (
                <div className="empty">No sales in the last 30 days yet.</div>
              ) : (
                <TrendLine data={dailyAll} color="#4AB012" />
              )}
            </div>
          </section>
        </>
      ) : null}
    </section>
  );
}
