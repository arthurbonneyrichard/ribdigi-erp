'use client';

import { useEffect, useMemo, useState } from 'react';
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

type Dash = {
  total_sales?: number;
  total_purchases?: number;
  total_expenses?: number;
  products?: number;
  low_stock?: number;
  customers?: number;
  suppliers?: number;
  monthly_sales?: { label: string; total: number }[];
  subscription?: Subscription;
};

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
  const inStock = Math.max(0, products - low);
  const customers = d.customers || 0;
  const suppliers = d.suppliers || 0;

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

  const trend = d.monthly_sales || [];
  const trendMax = Math.max(1, ...trend.map((t) => t.total || 0));
  const trendEmpty = trend.every((t) => !t.total);

  const finItems = [
    { label: 'Sales', value: sales, color: '#22c55e' },
    { label: 'Purchases', value: purchases, color: '#38bdf8' },
    { label: 'Expenses', value: expenses, color: '#fb7185' },
  ].filter((x) => x.value > 0);
  const finTotal = finItems.reduce((s, i) => s + i.value, 0);
  const finSlices = pieSlices(finItems, 70, 70, 66);

  const stats = [
    { cls: 's-sales', ico: '\ud83d\udcb0', label: 'Total Sales', val: num(sales) },
    { cls: 's-buy', ico: '\ud83d\uded2', label: 'Purchases', val: num(purchases) },
    { cls: 's-exp', ico: '\ud83e\udde7', label: 'Expenses', val: num(expenses) },
    { cls: 's-net', ico: '\ud83d\udcc8', label: 'Net Position', val: num(net) },
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
            <div className={`stat ${s.cls}`} key={s.label}>
              <span className="rail" />
              <div className="ico">{s.ico}</div>
              <div className="label">{s.label}</div>
              <div className="val">{s.val}</div>
            </div>
          ))}
        </section>

        <section className="info-grid">
          <div className="panel">
            <h3>
              <span className="pico pi-flow" aria-hidden>
                {'\ud83d\udcb5'}
              </span>
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
              <span className="pico pi-mix" aria-hidden>
                {'\ud83e\udd1d'}
              </span>
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

        <section className="info-grid">
          <div className="panel">
            <h3>
              <span className="pico pi-trend" aria-hidden>
                {'\ud83d\udcc8'}
              </span>
              Revenue trend
            </h3>
            <p className="hint">Sales over the last 6 months</p>
            {trendEmpty ? (
              <div className="empty">No sales recorded in this period yet.</div>
            ) : (
              <svg viewBox="0 0 300 172" width="100%" height="172" role="img" aria-label="Monthly sales trend">
                <line x1="8" y1="138" x2="292" y2="138" stroke="#e5e7eb" />
                {trend.map((t, i) => {
                  const h = ((t.total || 0) / trendMax) * 112;
                  const x = i * 50 + 12;
                  const y = 138 - h;
                  return (
                    <g key={t.label + i}>
                      <rect x={x} y={y} width={26} height={h} rx={5} fill="#6366f1" />
                      <text x={x + 13} y={y - 5} textAnchor="middle" className="vbar-val">
                        {t.total ? num(t.total) : ''}
                      </text>
                      <text x={x + 13} y={156} textAnchor="middle" className="vbar-label">
                        {t.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            )}
          </div>

          <div className="panel">
            <h3>
              <span className="pico pi-pie" aria-hidden>
                {'\ud83e\udd67'}
              </span>
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
        </section>

        <section className="panel">
          <h3>
            <span className="pico pi-health" aria-hidden>
              {'\ud83d\udce6'}
            </span>
            Inventory health
          </h3>
          <p className="hint">In-stock vs items at or below reorder level</p>
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
                {products ? `${Math.round(healthFrac * 100)}%` : '\u2014'}
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
              <span className="pill">
                <span className="dot" style={{ background: '#fb7185', width: 12, height: 12, borderRadius: 4 }} />
                Low stock&nbsp;<b>{num(low)}</b>
              </span>
              <span className="pill">
                <span className="dot" style={{ background: '#94a3b8', width: 12, height: 12, borderRadius: 4 }} />
                Products&nbsp;<b>{num(products)}</b>
              </span>
            </div>
          </div>
        </section>
      </div>
    </Shell>
  );
}
