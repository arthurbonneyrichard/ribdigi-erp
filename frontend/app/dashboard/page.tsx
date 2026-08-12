'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Subscription = {
  status?: string;
  trial_ends_at?: string | null;
  grace_ends_at?: string | null;
  days_remaining?: number | null;
  read_only?: boolean;
  trial_days?: number;
};

type TopProduct = {
  product_id: string;
  name: string;
  sku?: string | null;
  quantity: number;
  revenue: number;
};

type Dash = {
  total_sales?: number;
  total_purchases?: number;
  total_expenses?: number;
  products?: number;
  low_stock?: number;
  out_of_stock?: number;
  expiring_soon?: number;
  customers?: number;
  suppliers?: number;
  comparisons?: {
    sales_today?: number;
    sales_yesterday?: number;
    sales_today_pct?: number | null;
    sales_mtd?: number;
    sales_prev_month?: number;
    sales_mtd_pct?: number | null;
  };
  monthly_sales?: { label: string; total: number }[];
  daily_sales?: { label: string; sales: number; profit: number }[];
  recent_sales?: { reference: string; date: string; total: number; customer: string; type: string }[];
  top_products_by_revenue?: TopProduct[];
  top_products_by_quantity?: TopProduct[];
  links?: Record<string, string>;
  subscription?: Subscription;
};

// Monochrome line icons for panel headings (same style as the sidebar).
const PANEL_ICONS: Record<string, React.ReactNode> = {
  cashflow: (
    <>
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </>
  ),
  mix: (
    <>
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </>
  ),
  pie: (
    <>
      <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
      <path d="M22 12A10 10 0 0 0 12 2v10z" />
    </>
  ),
  daily: (
    <>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </>
  ),
  profit: (
    <>
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </>
  ),
  health: (
    <>
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <path d="M3.27 6.96 12 12.01l8.73-5.05" />
      <path d="M12 22.08V12" />
    </>
  ),
  recent: (
    <>
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </>
  ),
};

function PanelIcon({ name }: { name: string }) {
  return (
    <svg
      className="panel-ico"
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PANEL_ICONS[name]}
    </svg>
  );
}

function DailyBars({
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
      <line x1="8" y1="138" x2="292" y2="138" stroke="#e5e7eb" />
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

function TrendLine({
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
      <line x1="8" y1="138" x2="292" y2="138" stroke="#e5e7eb" />
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

function MonthlyBars({ data }: { data: { label: string; total: number }[] }) {
  const n = data.length || 1;
  const max = Math.max(1, ...data.map((x) => x.total || 0));
  const slot = 300 / n;
  const bw = Math.min(18, slot * 0.65);
  return (
    <svg viewBox="0 0 300 172" width="100%" height="172" role="img" aria-label="Monthly sales">
      <line x1="8" y1="138" x2="292" y2="138" stroke="#e5e7eb" />
      {data.map((t, i) => {
        const v = t.total || 0;
        const h = Math.max(0, (v / max) * 112);
        const x = i * slot + (slot - bw) / 2;
        const y = 138 - h;
        return (
          <g key={t.label + i}>
            <rect x={x} y={y} width={bw} height={h} rx={3} fill="#38bdf8" />
            {i % 2 === 0 && (
              <text x={x + bw / 2} y={156} textAnchor="middle" className="vbar-label">
                {t.label.split(' ')[0]}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function pctLabel(pct?: number | null) {
  if (pct == null) return '—';
  const sign = pct > 0 ? '+' : '';
  return `${sign}${pct}%`;
}

function polar(cx: number, cy: number, r: number, angle: number): [number, number] {
  return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}

function pieSlices(items: { label: string; value: number; color: string }[], cx: number, cy: number, r: number) {
  const total = items.reduce((s, i) => s + i.value, 0);
  if (total <= 0) return [];
  let a = -Math.PI / 2;
  return items.map((it) => {
    const frac = it.value / total;
    const a2 = a + frac * 2 * Math.PI;
    const [x1, y1] = polar(cx, cy, r, a);
    const [x2, y2] = polar(cx, cy, r, a2);
    const large = frac > 0.5 ? 1 : 0;
    const path = `M${cx} ${cy} L${x1.toFixed(2)} ${y1.toFixed(2)} A${r} ${r} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
    a = a2;
    return { path, color: it.color };
  });
}

function subStatus(sub?: Subscription) {
  const status = sub?.status;
  const days = sub?.days_remaining;
  const dayLabel = (n: number | null | undefined) =>
    `${n ?? 0} day${(n ?? 0) === 1 ? '' : 's'} left`;
  if (status === 'active') return { label: 'Active', cls: 'st-active', icon: '\u2705' };
  if (status === 'trial') return { label: `Trial \u00b7 ${dayLabel(days)}`, cls: 'st-trial', icon: '\u23f3' };
  if (status === 'grace')
    return { label: `Grace \u00b7 ${dayLabel(days)} \u00b7 read-only`, cls: 'st-grace', icon: '\u26a0\ufe0f' };
  if (status === 'suspended') return { label: 'Suspended', cls: 'st-suspended', icon: '\u26d4' };
  return null;
}

function fmtDate(value?: string | null) {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function num(v?: number) {
  return new Intl.NumberFormat().format(Math.round((v || 0) * 100) / 100);
}

function timeOfDay(hour: number): { greeting: string; icon: string; sub: string } {
  if (hour < 12) return { greeting: 'Good morning', icon: '\u2600\ufe0f', sub: 'A bright new day for your business.' };
  if (hour < 18) return { greeting: 'Good afternoon', icon: '\u26c5', sub: 'Keep the momentum going strong.' };
  return { greeting: 'Good evening', icon: '\ud83c\udf19', sub: "Here's how today wrapped up." };
}

// Donut / ring geometry
function arc(fraction: number, radius: number) {
  const c = 2 * Math.PI * radius;
  return { dash: `${Math.max(0, Math.min(1, fraction)) * c} ${c}`, c };
}

export default function Page() {
  const [d, setD] = useState<Dash>({});
  const [now, setNow] = useState<Date | null>(null);
  const [fullName, setFullName] = useState('');

  useEffect(() => {
    setNow(new Date());
    api('/dashboard')
      .then((r) => setD(r.data || {}))
      .catch(() => {});
    api('/me')
      .then((r) => setFullName(r.data?.full_name || ''))
      .catch(() => {});
  }, []);

  const firstName = fullName.trim().split(/\s+/)[0] || '';

  const tod = useMemo(() => timeOfDay(now ? now.getHours() : 9), [now]);
  const dateLabel = useMemo(
    () =>
      now
        ? now.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
        : '',
    [now],
  );

  const sub = d.subscription;
  const status = subStatus(sub);

  const sales = d.total_sales || 0;
  const purchases = d.total_purchases || 0;
  const expenses = d.total_expenses || 0;
  const net = sales - purchases - expenses;
  const products = d.products || 0;
  const low = d.low_stock || 0;
  const oos = d.out_of_stock || 0;
  const expiring = d.expiring_soon || 0;
  const inStock = Math.max(0, products - low);
  const customers = d.customers || 0;
  const suppliers = d.suppliers || 0;
  const cmp = d.comparisons || {};
  const links = d.links || {};
  const topRev = d.top_products_by_revenue || [];
  const monthly = d.monthly_sales || [];

  const flow = [
    { label: 'Sales', value: sales, color: '#22c55e' },
    { label: 'Purchases', value: purchases, color: '#38bdf8' },
    { label: 'Expenses', value: expenses, color: '#fb7185' },
  ];
  const flowMax = Math.max(1, ...flow.map((f) => f.value));
  const flowEmpty = sales === 0 && purchases === 0 && expenses === 0;

  const parties = customers + suppliers;
  const custFrac = parties ? customers / parties : 0;
  const r = 54;
  const custArc = arc(custFrac, r);
  const suppArc = arc(1 - custFrac, r);

  const rr = 52;
  const healthFrac = products ? inStock / products : 0;
  const healthArc = arc(healthFrac, rr);

  const dailyAll = d.daily_sales || [];
  const daily = dailyAll.slice(-7);
  const dailyEmpty = daily.every((x) => !x.sales && !x.profit);
  const recent = d.recent_sales || [];

  const finItems = [
    { label: 'Sales', value: sales, color: '#22c55e' },
    { label: 'Purchases', value: purchases, color: '#38bdf8' },
    { label: 'Expenses', value: expenses, color: '#fb7185' },
  ].filter((x) => x.value > 0);
  const finTotal = finItems.reduce((s, i) => s + i.value, 0);
  const finSlices = pieSlices(finItems, 70, 70, 66);

  const stats = [
    {
      cls: 's-sales',
      ico: '\ud83d\udcb0',
      label: 'Total Sales',
      val: num(sales),
      href: links.sales || '/sales',
      sub: `Today ${num(cmp.sales_today)} (${pctLabel(cmp.sales_today_pct)} vs yday) · MTD ${num(cmp.sales_mtd)} (${pctLabel(cmp.sales_mtd_pct)} vs last mo)`,
    },
    { cls: 's-buy', ico: '\ud83d\uded2', label: 'Purchases', val: num(purchases), href: links.purchases || '/purchasing' },
    { cls: 's-exp', ico: '\ud83e\udde7', label: 'Expenses', val: num(expenses), href: links.expenses || '/expenses' },
    { cls: 's-net', ico: '\ud83d\udcc8', label: 'Net Position', val: num(net), href: links.reports_sales || '/reports' },
  ];

  const countStats = [
    { label: 'Customers', val: customers, href: links.customers || '/sales' },
    { label: 'Suppliers', val: suppliers, href: links.suppliers || '/purchasing' },
    { label: 'Products', val: products, href: links.products || '/inventory' },
  ];

  return (
    <Shell>
      <div className="dash">
        <section className="dash-hero">
          <div className="sun" />
          <div className="cloud" />
          <div className="cloud c2" />
          {status && (
            <span className={`status-pill ${status.cls}`}>
              <span aria-hidden>{status.icon}</span> {status.label}
            </span>
          )}
          <h1 className="greet">
            {tod.greeting}
            {firstName ? `, ${firstName}` : ''} <span className="wave">{tod.icon}</span>
          </h1>
          <p className="greet-sub">{tod.sub}</p>
          <p className="greet-date">{dateLabel}</p>
          {sub?.status === 'trial' && sub?.trial_ends_at && (
            <p className="greet-date">Trial ends {fmtDate(sub.trial_ends_at)}</p>
          )}
          {sub?.status === 'grace' && sub?.grace_ends_at && (
            <p className="greet-date">Grace period ends {fmtDate(sub.grace_ends_at)}</p>
          )}
        </section>

        <section className="stat-grid">
          {stats.map((s) => (
            <Link className={`stat ${s.cls}`} key={s.label} href={s.href} style={{ textDecoration: 'none', color: 'inherit' }}>
              <span className="rail" />
              <div className="ico">{s.ico}</div>
              <div className="label">{s.label}</div>
              <div className="val">{s.val}</div>
              {s.sub && <p className="hint" style={{ marginTop: 6, fontSize: 12 }}>{s.sub}</p>}
            </Link>
          ))}
        </section>

        <section className="stat-grid" style={{ marginTop: 12 }}>
          {countStats.map((s) => (
            <Link className="stat" key={s.label} href={s.href} style={{ textDecoration: 'none', color: 'inherit' }}>
              <div className="label">{s.label}</div>
              <div className="val">{num(s.val)}</div>
            </Link>
          ))}
          <Link className="stat" href={links.low_stock || '/reports'} style={{ textDecoration: 'none', color: 'inherit' }}>
            <div className="label">Inventory alerts</div>
            <div className="val" style={{ fontSize: 16 }}>
              Low {num(low)} · OOS {num(oos)} · Exp {num(expiring)}
            </div>
          </Link>
        </section>

        <section className="info-grid">
          <div className="panel">
            <h3>
              <PanelIcon name="daily" />
              Daily sales (7d)
            </h3>
            <p className="hint">
              Last 7 days · <Link href={links.reports_sales || '/reports'}>Open reports</Link>
            </p>
            {dailyEmpty ? (
              <div className="empty">No sales in the last 7 days yet.</div>
            ) : (
              <DailyBars data={daily} field="sales" color="#22c55e" />
            )}
          </div>

          <div className="panel">
            <h3>
              <PanelIcon name="profit" />
              Revenue trend (30d)
            </h3>
            <p className="hint">Daily revenue line — last 30 days</p>
            {dailyAll.every((x) => !x.sales) ? (
              <div className="empty">No sales in the last 30 days yet.</div>
            ) : (
              <TrendLine data={dailyAll} color="#6366f1" />
            )}
          </div>

          <div className="panel">
            <h3>
              <PanelIcon name="cashflow" />
              Monthly sales (12 mo)
            </h3>
            <p className="hint">Bar chart of the last 12 calendar months</p>
            {monthly.every((x) => !x.total) ? (
              <div className="empty">No monthly sales yet.</div>
            ) : (
              <MonthlyBars data={monthly} />
            )}
          </div>

          <div className="panel">
            <h3>
              <PanelIcon name="health" />
              Inventory health
            </h3>
            <p className="hint">
              In-stock vs reorder · <Link href={links.products || '/inventory'}>Inventory</Link>
            </p>
            <div className="health">
              <svg width="130" height="130" viewBox="0 0 130 130" role="img" aria-label="Inventory health">
                <circle cx="65" cy="65" r={rr} fill="none" stroke="#fee2e2" strokeWidth="14" />
                <circle
                  cx="65"
                  cy="65"
                  r={rr}
                  fill="none"
                  stroke="#22c55e"
                  strokeWidth="14"
                  strokeDasharray={healthArc.dash}
                  strokeLinecap="round"
                  transform="rotate(-90 65 65)"
                />
                <text x="65" y="63" textAnchor="middle" className="donut-center">
                  {products ? `${Math.round(healthFrac * 100)}%` : '—'}
                </text>
                <text x="65" y="79" textAnchor="middle" className="donut-sub">
                  HEALTHY
                </text>
              </svg>
              <div className="nums">
                <span className="pill">
                  <span className="dot" style={{ background: '#22c55e', width: 12, height: 12, borderRadius: 4 }} />
                  In stock&nbsp;<b>{num(inStock)}</b>
                </span>
                <Link className="pill" href={links.low_stock || '/reports'} style={{ textDecoration: 'none', color: 'inherit' }}>
                  <span className="dot" style={{ background: '#fb7185', width: 12, height: 12, borderRadius: 4 }} />
                  Low stock&nbsp;<b>{num(low)}</b>
                </Link>
                <Link className="pill" href={links.products || '/inventory'} style={{ textDecoration: 'none', color: 'inherit' }}>
                  <span className="dot" style={{ background: '#f59e0b', width: 12, height: 12, borderRadius: 4 }} />
                  Out of stock&nbsp;<b>{num(oos)}</b>
                </Link>
                <Link className="pill" href={links.expiring || '/inventory'} style={{ textDecoration: 'none', color: 'inherit' }}>
                  <span className="dot" style={{ background: '#6366f1', width: 12, height: 12, borderRadius: 4 }} />
                  Expiring (30d)&nbsp;<b>{num(expiring)}</b>
                </Link>
              </div>
            </div>
          </div>

          <div className="panel">
            <h3>
              <PanelIcon name="cashflow" />
              Cash flow
            </h3>
            <p className="hint">Sales, purchases &amp; approved expenses to date</p>
            {flowEmpty ? (
              <div className="empty">No cash flow recorded yet — your first sale will appear here.</div>
            ) : (
              <div className="bars">
                {flow.map((f) => (
                  <div className="bar-row" key={f.label}>
                    <span className="bl">{f.label}</span>
                    <span className="bar-track">
                      <span
                        className="bar-fill"
                        style={{
                          width: `${(f.value / flowMax) * 100}%`,
                          minWidth: f.value > 0 ? 6 : 0,
                          background: f.color,
                        }}
                      />
                    </span>
                    <span className="bv">{num(f.value)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="panel">
            <h3>
              <PanelIcon name="pie" />
              Revenue vs costs
            </h3>
            <p className="hint">Share of sales, purchases &amp; expenses</p>
            <div className="mix">
              <svg width="140" height="140" viewBox="0 0 140 140" role="img" aria-label="Revenue vs costs">
                {finTotal <= 0 ? (
                  <circle cx="70" cy="70" r="66" fill="#eef1f7" />
                ) : finItems.length === 1 ? (
                  <circle cx="70" cy="70" r="66" fill={finItems[0].color} />
                ) : (
                  finSlices.map((s, i) => <path key={i} d={s.path} fill={s.color} stroke="#fff" strokeWidth="1.5" />)
                )}
              </svg>
              <div className="legend">
                {finTotal <= 0 ? (
                  <span className="li">No financial activity yet</span>
                ) : (
                  [
                    { label: 'Sales', value: sales, color: '#22c55e' },
                    { label: 'Purchases', value: purchases, color: '#38bdf8' },
                    { label: 'Expenses', value: expenses, color: '#fb7185' },
                  ].map((it) => (
                    <span className="li" key={it.label}>
                      <span className="dot" style={{ background: it.color }} /> {it.label} ·{' '}
                      <b>&nbsp;{num(it.value)}</b>
                    </span>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="panel">
            <h3>
              <PanelIcon name="mix" />
              Business mix
            </h3>
            <p className="hint">Customers vs suppliers</p>
            <div className="mix">
              <svg width="140" height="140" viewBox="0 0 140 140" role="img" aria-label="Customers vs suppliers">
                <circle cx="70" cy="70" r={r} fill="none" stroke="#eef1f7" strokeWidth="16" />
                {parties > 0 && (
                  <>
                    <circle
                      cx="70"
                      cy="70"
                      r={r}
                      fill="none"
                      stroke="#f59e0b"
                      strokeWidth="16"
                      strokeDasharray={custArc.dash}
                      strokeDashoffset={0}
                      strokeLinecap="round"
                      transform="rotate(-90 70 70)"
                    />
                    <circle
                      cx="70"
                      cy="70"
                      r={r}
                      fill="none"
                      stroke="#6366f1"
                      strokeWidth="16"
                      strokeDasharray={suppArc.dash}
                      strokeDashoffset={-custArc.c * custFrac}
                      strokeLinecap="round"
                      transform="rotate(-90 70 70)"
                    />
                  </>
                )}
                <text x="70" y="68" textAnchor="middle" className="donut-center">
                  {num(parties)}
                </text>
                <text x="70" y="84" textAnchor="middle" className="donut-sub">
                  PARTIES
                </text>
              </svg>
              <div className="legend">
                <span className="li">
                  <span className="dot" style={{ background: '#f59e0b' }} /> Customers · <b>&nbsp;{num(customers)}</b>
                </span>
                <span className="li">
                  <span className="dot" style={{ background: '#6366f1' }} /> Suppliers · <b>&nbsp;{num(suppliers)}</b>
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="panel" style={{ marginTop: 16 }}>
          <h3>
            <PanelIcon name="recent" />
            Top products (30d)
          </h3>
          <p className="hint">By revenue from POS/sales lines · <Link href={links.reports_sales || '/reports'}>Reports</Link></p>
          {topRev.length === 0 ? (
            <div className="empty">No product sales in the last 30 days yet.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th style={{ textAlign: 'right' }}>Qty</th>
                  <th style={{ textAlign: 'right' }}>Revenue</th>
                </tr>
              </thead>
              <tbody>
                {topRev.map((p) => (
                  <tr key={p.product_id}>
                    <td>{p.name}</td>
                    <td>{p.sku || '—'}</td>
                    <td style={{ textAlign: 'right' }}>{num(p.quantity)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{num(p.revenue)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="panel">
          <h3>
            <PanelIcon name="recent" />
            Recent sales
          </h3>
          <p className="hint">Latest 10 sales · <Link href={links.sales || '/sales'}>Sales</Link></p>
          {recent.length === 0 ? (
            <div className="empty">No sales yet — new sales will show up here.</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Reference</th>
                  <th>Customer</th>
                  <th>Type</th>
                  <th>Date</th>
                  <th style={{ textAlign: 'right' }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {recent.map((s) => (
                  <tr key={s.reference}>
                    <td>{s.reference}</td>
                    <td>{s.customer}</td>
                    <td>{s.type === 'pos_sale' ? 'POS' : 'Sale'}</td>
                    <td>{fmtDate(s.date)}</td>
                    <td style={{ textAlign: 'right', fontWeight: 600 }}>{num(s.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </Shell>
  );
}
