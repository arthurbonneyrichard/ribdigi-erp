'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import Shell from '../../components/Shell';
import { api, ApiError } from '../../lib/api';
import { formatNumber } from '../../lib/format';

type Insight = {
  insight_type: string;
  category: string;
  priority: string;
  title: string;
  message: string;
  recommendation?: string;
  action_href?: string;
  action_cta?: string;
  metric_value?: number | null;
  percentage_change?: number | null;
};

type Bundle = {
  generated_at: string;
  external_ai_required: boolean;
  health: {
    score: number;
    status: string;
    breakdown: Record<string, number>;
    formula: string;
  };
  attention: Insight[];
  sales: Record<string, unknown>;
  inventory: Record<string, unknown>;
  profit: Record<string, unknown>;
  expenses: Record<string, unknown>;
  credit: Record<string, unknown>;
  purchases: Record<string, unknown>;
  customers: Record<string, unknown>;
  opportunities: Insight[];
  reorder_recommendations: Array<Record<string, unknown>>;
  top_products: Array<Record<string, unknown>>;
  locations: Array<Record<string, unknown>>;
};

const PRIORITY_COLOR: Record<string, string> = {
  CRITICAL: '#b91c1c',
  WARNING: '#c2410c',
  ATTENTION: '#a16207',
  OPPORTUNITY: '#15803d',
  INFORMATION: '#334155',
};

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="card kpi">
      <div className="muted" style={{ fontSize: 12 }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
    </div>
  );
}

function InsightCard({ item }: { item: Insight }) {
  const color = PRIORITY_COLOR[item.priority] || '#334155';
  return (
    <div className="card" style={{ borderLeft: `4px solid ${color}` }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
        <strong>{item.title}</strong>
        <span className="badge" style={{ background: color, color: '#fff' }}>
          {item.priority}
        </span>
      </div>
      <p className="muted" style={{ marginTop: 8 }}>
        {item.message}
      </p>
      {item.recommendation ? (
        <p style={{ marginTop: 8 }}>
          <strong>Recommended Action:</strong> {item.recommendation}
        </p>
      ) : null}
      {item.action_href ? (
        <Link href={item.action_href} style={{ display: 'inline-block', marginTop: 8 }}>
          {item.action_cta || 'Open'}
        </Link>
      ) : null}
    </div>
  );
}

export default function BusinessInsightsPage() {
  const [data, setData] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api<Bundle>('/business-insights/overview');
      setData(res);
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Failed to load insights';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const sales = (data?.sales || {}) as Record<string, number | null>;
  const inventory = (data?.inventory || {}) as Record<string, number>;
  const expenses = (data?.expenses || {}) as Record<string, number | null>;
  const profit = (data?.profit || {}) as Record<string, unknown>;
  const credit = (data?.credit || {}) as Record<string, unknown>;

  return (
    <Shell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ margin: 0 }}>Business Insights</h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Smart Business Intelligence — Layer 1 (deterministic ERP analytics, no external AI)
          </p>
        </div>
        <button type="button" onClick={() => void load()} disabled={loading}>
          Refresh
        </button>
      </div>

      {error ? (
        <div className="card" style={{ marginTop: 16, border: '1px solid #fecaca', color: '#991b1b' }}>
          {error}
        </div>
      ) : null}

      {loading && !data ? <p className="muted">Loading insights…</p> : null}

      {data ? (
        <>
          <section style={{ marginTop: 20 }}>
            <h2>Business Health Score</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))' }}>
              <Kpi label="Score" value={`${data.health.score}/100`} />
              <Kpi label="Status" value={data.health.status} />
              {Object.entries(data.health.breakdown || {}).map(([k, v]) => (
                <Kpi key={k} label={k} value={String(v)} />
              ))}
            </div>
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              {data.health.formula}
            </p>
          </section>

          <section style={{ marginTop: 28 }}>
            <h2>What Needs My Attention?</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))' }}>
              {(data.attention || []).map((item, idx) => (
                <InsightCard key={`${item.insight_type}-${idx}`} item={item} />
              ))}
              {!data.attention?.length ? (
                <div className="card muted">No attention items right now.</div>
              ) : null}
            </div>
          </section>

          <section style={{ marginTop: 28 }}>
            <h2>Sales Insights</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
              <Kpi label="Today" value={formatNumber(Number(sales.today || 0))} />
              <Kpi label="Yesterday" value={formatNumber(Number(sales.yesterday || 0))} />
              <Kpi label="This week" value={formatNumber(Number(sales.this_week || 0))} />
              <Kpi label="This month" value={formatNumber(Number(sales.this_month || 0))} />
              <Kpi
                label="MoM %"
                value={sales.mom_change_pct == null ? '—' : `${sales.mom_change_pct}%`}
              />
              <Kpi label="Avg daily" value={formatNumber(Number(sales.avg_daily_sales || 0))} />
            </div>
          </section>

          <section style={{ marginTop: 28 }}>
            <h2>Inventory Insights</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
              <Kpi label="Low stock" value={String(inventory.low_stock_count || 0)} />
              <Kpi label="Out of stock" value={String(inventory.out_of_stock_count || 0)} />
              <Kpi label="Negative stock" value={String(inventory.negative_stock_count || 0)} />
              <Kpi label="Stock value" value={formatNumber(Number(inventory.stock_value || 0))} />
              <Kpi
                label="Reorder tips"
                value={String(data.reorder_recommendations?.length || 0)}
              />
            </div>
          </section>

          <section style={{ marginTop: 28 }}>
            <h2>Expense Insights</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
              <Kpi label="This month" value={formatNumber(Number(expenses.this_month || 0))} />
              <Kpi label="Last month" value={formatNumber(Number(expenses.last_month || 0))} />
              <Kpi
                label="MoM %"
                value={expenses.mom_change_pct == null ? '—' : `${expenses.mom_change_pct}%`}
              />
              <Kpi
                label="Expense / sales %"
                value={
                  expenses.expense_to_sales_pct == null
                    ? '—'
                    : `${expenses.expense_to_sales_pct}%`
                }
              />
            </div>
          </section>

          {!('restricted' in profit) ? (
            <section style={{ marginTop: 28 }}>
              <h2>Profit Insights</h2>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
                <Kpi
                  label="Revenue (30d)"
                  value={formatNumber(
                    Number((profit.current as Record<string, number> | undefined)?.revenue || 0)
                  )}
                />
                <Kpi
                  label="Gross profit"
                  value={formatNumber(
                    Number(
                      (profit.current as Record<string, number> | undefined)?.gross_profit || 0
                    )
                  )}
                />
                <Kpi
                  label="Net profit"
                  value={formatNumber(
                    Number((profit.current as Record<string, number> | undefined)?.net_profit || 0)
                  )}
                />
                <Kpi
                  label="Gross margin %"
                  value={String(
                    (profit.current as Record<string, number | null> | undefined)
                      ?.gross_margin_pct ?? '—'
                  )}
                />
              </div>
            </section>
          ) : null}

          {!('restricted' in credit) ? (
            <section style={{ marginTop: 28 }}>
              <h2>Credit Insights</h2>
              <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
                <Kpi label="Total due" value={formatNumber(Number(credit.total_due || 0))} />
              </div>
            </section>
          ) : null}

          <section style={{ marginTop: 28 }}>
            <h2>Purchase Insights</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
              <Kpi
                label="Current period"
                value={formatNumber(Number((data.purchases as Record<string, number>)?.current || 0))}
              />
              <Kpi
                label="Prior period"
                value={formatNumber(Number((data.purchases as Record<string, number>)?.prior || 0))}
              />
              <Kpi
                label="Change %"
                value={
                  (data.purchases as Record<string, number | null>)?.change_pct == null
                    ? '—'
                    : `${(data.purchases as Record<string, number | null>).change_pct}%`
                }
              />
            </div>
          </section>

          <section style={{ marginTop: 28 }}>
            <h2>Customer Insights</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))' }}>
              <Kpi
                label="Active customers"
                value={String((data.customers as Record<string, number>)?.total_customers || 0)}
              />
              <Kpi
                label="New (30d)"
                value={String((data.customers as Record<string, number>)?.new_customers || 0)}
              />
            </div>
            <p className="muted" style={{ fontSize: 12 }}>
              Dashboard summaries omit unnecessary personal customer details.
            </p>
          </section>

          <section style={{ marginTop: 28 }}>
            <h2>Smart Reorder Recommendations</h2>
            <p className="muted" style={{ fontSize: 12 }}>
              Deterministic stock + velocity recommendations — not ML predictions.
            </p>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))' }}>
              {(data.reorder_recommendations || []).slice(0, 8).map((row, idx) => (
                <div className="card" key={`reorder-${idx}`}>
                  <strong>{String(row.name || row.product_name || row.sku || 'Product')}</strong>
                  <p className="muted" style={{ marginTop: 6 }}>
                    Stock {String(row.current_stock ?? row.stock_qty ?? '—')} · Days left{' '}
                    {String(row.estimated_days_remaining ?? '—')} · Suggest qty{' '}
                    {String(row.recommended_reorder_qty ?? row.recommended_qty ?? '—')}
                  </p>
                </div>
              ))}
              {!data.reorder_recommendations?.length ? (
                <div className="card muted">No reorder recommendations right now.</div>
              ) : null}
            </div>
          </section>

          <section style={{ marginTop: 28 }}>
            <h2>Branch / Store Comparison</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))' }}>
              {(data.locations || []).slice(0, 8).map((loc, idx) => (
                <div className="card" key={`loc-${idx}`}>
                  <strong>{String(loc.store_name || loc.store_id || 'Location')}</strong>
                  <p style={{ marginTop: 6 }}>{formatNumber(Number(loc.sales_total || 0))}</p>
                </div>
              ))}
              {!data.locations?.length ? (
                <div className="card muted">No location sales in the comparison window.</div>
              ) : null}
            </div>
          </section>

          <section style={{ marginTop: 28 }}>
            <h2>Opportunities</h2>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))' }}>
              {(data.opportunities || []).map((item, idx) => (
                <InsightCard key={`opp-${idx}`} item={item} />
              ))}
              {!data.opportunities?.length ? (
                <div className="card muted">No opportunity insights right now.</div>
              ) : null}
            </div>
          </section>

          <p className="muted" style={{ marginTop: 24, fontSize: 12 }}>
            Generated {data.generated_at}. External AI required: {String(data.external_ai_required)}.
            All figures are calculated from Ribdigi ERP data only.
          </p>
        </>
      ) : null}
    </Shell>
  );
}
