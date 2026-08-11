'use client';

import { useEffect, useMemo, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Dash = {
  total_sales?: number;
  total_purchases?: number;
  total_expenses?: number;
  products?: number;
  low_stock?: number;
  customers?: number;
  suppliers?: number;
};

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

  useEffect(() => {
    setNow(new Date());
    api('/dashboard')
      .then((r) => setD(r.data || {}))
      .catch(() => {});
  }, []);

  const tod = useMemo(() => timeOfDay(now ? now.getHours() : 9), [now]);
  const dateLabel = useMemo(
    () =>
      now
        ? now.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
        : '',
    [now],
  );

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
          <h1 className="greet">
            {tod.greeting} <span className="wave">{tod.icon}</span>
          </h1>
          <p className="greet-sub">{tod.sub}</p>
          <p className="greet-date">{dateLabel}</p>
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
            <h3>Cash flow</h3>
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
            <h3>Business mix</h3>
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

        <section className="panel">
          <h3>Inventory health</h3>
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
