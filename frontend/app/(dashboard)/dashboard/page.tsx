'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { industryLabel, normalizeIndustry } from '../../../lib/industries';
import {
  dashboardLayout,
  filterIndustryDashboardFeatures,
  industryDashboardFeatures,
  industryHomePath,
  isSoftwareOwnerIndustry,
  showsRetailOperations,
  softwareOwnerDashboardPath,
  type IndustryDashboardFeature,
} from '../../../lib/industryDashboard';
import { WholesaleDeskCards } from '../../../components/IndustryDashboardViews';
import { DailyBars, TrendLine } from '../../../components/RetailDashboardInfographic';
import { formatDate } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import { useStoreContext } from '../../../lib/storeContext';
import OfflineProvisionalNotice from '../../../components/OfflineProvisionalNotice';

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
  ar_total_due?: number;
  ap_total_due?: number;
  credit_outstanding?: number;
  ar_open_parties?: number;
  ap_open_parties?: number;
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
  gross_profit_7d?: number;
  gross_profit_30d?: number;
  rx_queue?: {
    received?: number;
    review?: number;
    approved?: number;
    dispensed?: number;
    cancelled?: number;
    open?: number;
  } | null;
  rx_only_count?: number | null;
  recent_sales?: { reference: string; date: string; total: number; customer: string; type: string }[];
  top_products_by_revenue?: TopProduct[];
  top_products_by_quantity?: TopProduct[];
  links?: Record<string, string>;
  subscription?: Subscription;
  scope?: string;
  store_id?: string | null;
  store_name?: string | null;
  industry?: string | null;
  industry_home?: string | null;
  industry_features?: IndustryDashboardFeature[];
  dashboard_layout?: string;
  show_retail_operations?: boolean;
  returns_count?: number;
  wholesale_desk?: {
    open_quotes?: number;
    open_orders?: number;
    reserved_qty?: number;
    ar_total_due?: number;
  } | null;
  pharmacy_desk?: {
    sales_today?: number;
    returns_today?: number;
    awaiting_review?: number;
    ready_to_dispense?: number;
    partially_dispensed?: number;
    low_stock?: number;
    out_of_stock?: number;
    expiring_soon?: number;
    expired_lots?: number;
    on_hand_lots?: number;
    quarantined?: number;
    recalled?: number;
    pending_purchase_orders?: number;
    rx_only_count?: number;
  } | null;
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

function MonthlyBars({ data }: { data: { label: string; total: number }[] }) {
  const n = data.length || 1;
  const max = Math.max(1, ...data.map((x) => x.total || 0));
  const slot = 300 / n;
  const bw = Math.min(18, slot * 0.65);
  return (
    <svg viewBox="0 0 300 172" width="100%" height="172" role="img" aria-label="Monthly sales">
      <line x1="8" y1="138" x2="292" y2="138" stroke="#D4E5C4" />
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
  const router = useRouter();
  const { storeId: headerStoreId } = useStoreContext();
  const [d, setD] = useState<Dash>({});
  const [now, setNow] = useState<Date | null>(null);
  const [fullName, setFullName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [dashStatus, setDashStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [dashError, setDashError] = useState('');
  const [dashTick, setDashTick] = useState(0);
  const [hotelHome, setHotelHome] = useState(false);
  const [industry, setIndustry] = useState<string | null>(null);
  const [industryRaw, setIndustryRaw] = useState<string | null>(null);
  const [accountRole, setAccountRole] = useState('');
  const [meReady, setMeReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getMe()
      .then((me) => {
        if (cancelled) return;
        const role = String(me.data?.role || '');
        const raw = String(me.data?.industry_raw || me.data?.industry || '').trim() || null;
        setAccountRole(role);
        setIndustryRaw(raw);
        const ind = normalizeIndustry(me.data?.industry);
        setIndustry(ind);
        if (role === 'cashier') {
          router.replace('/pos');
          return;
        }
        if (softwareOwnerDashboardPath(role, raw)) {
          setHotelHome(false);
          return;
        }
        const home = industryHomePath(ind);
        if (home !== '/dashboard' && home !== '/platform') {
          setHotelHome(true);
          router.replace(home);
        } else {
          setHotelHome(false);
        }
      })
      .catch(() => {
        if (!cancelled) setIndustry(null);
      })
      .finally(() => {
        if (!cancelled) setMeReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (!meReady || accountRole === 'cashier' || hotelHome) return;
    let cancelled = false;
    setNow(new Date());
    setDashStatus('loading');
    setDashError('');
    const qs = headerStoreId ? `?store_id=${encodeURIComponent(headerStoreId)}` : '';
    api(`/dashboard${qs}`)
      .then((r) => {
        if (cancelled) return;
        setD(r.data || {});
        setDashStatus('ready');
        const payloadIndustry = normalizeIndustry((r.data || {}).industry);
        if (payloadIndustry) setIndustry(payloadIndustry);
        const rawPayload = String((r.data || {}).industry || '').trim();
        if (isSoftwareOwnerIndustry(rawPayload)) setIndustryRaw(rawPayload);
        const payloadHome = industryHomePath((r.data || {}).industry);
        const serverHome = (r.data || {}).industry_home;
        const home = serverHome && serverHome !== '/dashboard' ? serverHome : payloadHome;
        if (home === '/platform') return;
        if (home && home !== '/dashboard') {
          setHotelHome(true);
          router.replace(home);
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setD({});
        setDashError(err instanceof Error ? err.message : 'Unable to load dashboard');
        setDashStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, [headerStoreId, dashTick, hotelHome, meReady, accountRole]);

  useEffect(() => {
    getMe()
      .then((r) => {
        setFullName(r.data?.full_name || '');
        setCompanyName(String(r.data?.company_name || r.data?.tenant?.company_name || '').trim());
      })
      .catch(() => {
        setCompanyName('');
      });
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    let lastTenant = localStorage.getItem('tenant') || '';
    const applyTenantChange = () => {
      const next = localStorage.getItem('tenant') || '';
      if (next === lastTenant) return;
      lastTenant = next;
      void getMe({ force: true })
        .then((r) => {
          setCompanyName(String(r.data?.company_name || r.data?.tenant?.company_name || '').trim());
          const role = String(r.data?.role || '');
          const raw = String(r.data?.industry_raw || r.data?.industry || '').trim() || null;
          setAccountRole(role);
          setIndustryRaw(raw);
          const ind = normalizeIndustry(r.data?.industry);
          setIndustry(ind);
          setD({});
          setDashStatus('loading');
          if (role === 'cashier') {
            router.replace('/pos');
            return;
          }
          if (softwareOwnerDashboardPath(role, raw)) {
            setHotelHome(false);
            return;
          }
          const home = industryHomePath(ind);
          if (home !== '/dashboard' && home !== '/platform') {
            setHotelHome(true);
            router.replace(home);
          } else {
            setHotelHome(false);
            setDashTick((n) => n + 1);
          }
        })
        .catch(() => undefined);
    };
    window.addEventListener('storage', applyTenantChange);
    const id = window.setInterval(applyTenantChange, 800);
    return () => {
      window.removeEventListener('storage', applyTenantChange);
      window.clearInterval(id);
    };
  }, [router]);

  const signedInName = fullName.trim();
  const formatPrefs = useCompanyFormat();

  const tod = useMemo(() => timeOfDay(now ? now.getHours() : 9), [now]);
  const dateLabel = useMemo(() => (now ? formatDate(now, formatPrefs) : ''), [now, formatPrefs]);

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
  const inStock = Math.max(0, products - low - oos);
  const customers = d.customers || 0;
  const suppliers = d.suppliers || 0;
  const cmp = d.comparisons || {};
  const links = d.links || {};
  const topRev = d.top_products_by_revenue || [];
  const monthly = d.monthly_sales || [];

  const flow = [
    { label: 'Sales', value: sales, color: '#4AB012' },
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
    {
      cls: 's-sales',
      ico: '\ud83d\udcc8',
      label: 'Gross profit (7d)',
      val: num(d.gross_profit_7d),
      href: links.reports_sales || '/reports',
      sub: `30d ${num(d.gross_profit_30d)} · from posted sale lines (price − cost)`,
    },
  ];

  const serverLayout = typeof d.dashboard_layout === 'string' ? d.dashboard_layout : '';
  const rawIndustry = industryRaw || (typeof d.industry === 'string' ? d.industry : null) || industry;
  const ownerHome = softwareOwnerDashboardPath(accountRole, rawIndustry);
  const platformLayout = serverLayout === 'platform' || isSoftwareOwnerIndustry(rawIndustry);
  const layout = serverLayout || (meReady ? dashboardLayout(d.industry || industry) : '');

  useEffect(() => {
    if (!ownerHome) return;
    router.replace(ownerHome);
  }, [ownerHome, router]);
  const showRetail = serverLayout
    ? d.show_retail_operations === true
    : meReady && showsRetailOperations(layout);

  const countStats = [
    { label: 'Products', val: products, href: links.products || '/inventory' },
    { label: 'Low stock', val: low, href: links.low_stock || '/inventory?tab=lowstock' },
    { label: 'Out of stock', val: oos, href: links.out_of_stock || '/inventory?tab=products&stock=oos' },
    { label: 'Expiring soon', val: expiring, href: links.expiring || '/inventory?tab=expiry' },
  ];
  if (showRetail && typeof d.returns_count === 'number') {
    countStats.push({
      label: 'Posted returns',
      val: d.returns_count,
      href: '/sales?tab=returns',
    });
  }

  const liveIndustry = normalizeIndustry(d.industry) || industry;
  const featureCards = filterIndustryDashboardFeatures(
    d.industry_features && d.industry_features.length
      ? d.industry_features
      : industryDashboardFeatures(liveIndustry),
    liveIndustry
  ).filter((f) => f.id !== 'pos' && f.id !== 'inventory' && f.id !== 'customers');

  if (ownerHome || platformLayout) {
    return (
      <p className="muted" role="status">
        {ownerHome
          ? 'Opening platform console…'
          : accountRole
            ? 'This workspace uses the platform console.'
            : 'Loading dashboard…'}
      </p>
    );
  }

  if (!meReady && !serverLayout) {
    return (
      <p className="muted" role="status">
        Loading dashboard…
      </p>
    );
  }

  if (accountRole === 'cashier') {
    return (
      <p className="muted" role="status">
        Opening POS…
      </p>
    );
  }

  const awayHome = industryHomePath(d.industry || industry);
  if (awayHome !== '/platform' && (hotelHome || (awayHome && awayHome !== '/dashboard'))) {
    const opening =
      awayHome === '/restaurant'
        ? 'restaurant'
        : awayHome === '/fmcg'
          ? 'FMCG'
          : awayHome === '/hospital'
            ? 'hospital'
            : 'hotel';
    return (
      <p className="muted" role="status">
        Opening {opening} dashboard…
      </p>
    );
  }

  return (
    <>
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
            {signedInName ? `, ${signedInName}` : ''}{' '}
            <span className="wave">{tod.icon}</span>
          </h1>
          <p className="greet-sub">{tod.sub}</p>
          <p className="greet-date">{dateLabel}</p>
          <OfflineProvisionalNotice />
          {liveIndustry && liveIndustry !== 'retail' && (
            <p className="greet-date">{industryLabel(liveIndustry)} dashboard</p>
          )}
          {sub?.status === 'trial' && sub?.trial_ends_at && (
            <p className="greet-date">Trial ends {formatDate(sub.trial_ends_at, formatPrefs)}</p>
          )}
          {sub?.status === 'grace' && sub?.grace_ends_at && (
            <p className="greet-date">Grace period ends {formatDate(sub.grace_ends_at, formatPrefs)}</p>
          )}
          {dashStatus === 'loading' && (
            <p className="greet-date" role="status">
              Loading dashboard…
            </p>
          )}
          {dashStatus === 'error' && (
            <p className="greet-date" role="alert">
              {dashError || 'Unable to load dashboard'}{' '}
              <button type="button" onClick={() => setDashTick((n) => n + 1)} aria-label="Retry dashboard">
                Retry
              </button>
            </p>
          )}
        </section>
        {dashStatus !== 'ready' ? (
          <section className="stat-grid" aria-busy={dashStatus === 'loading'}>
            <div className="stat">
              <div className="label">{dashStatus === 'error' ? 'Figures hidden until reload succeeds' : 'Waiting for figures'}</div>
              <div className="val">{dashStatus === 'error' ? '—' : '…'}</div>
            </div>
          </section>
        ) : (
        <>
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
        </section>

        {liveIndustry === 'pharmacy' && d.pharmacy_desk && (
          <section aria-label="Pharmacy" style={{ marginTop: 16 }}>
            <h2 style={{ margin: '0 0 8px', fontSize: 18 }}>Pharmacy</h2>
            <div className="stat-grid">
              {[
                { label: "Today's pharmacy sales", val: num(d.pharmacy_desk.sales_today), href: '/reports' },
                { label: "Today's returns", val: num(d.pharmacy_desk.returns_today), href: '/sales' },
                { label: 'Awaiting review', val: num(d.pharmacy_desk.awaiting_review), href: '/prescriptions?status=review' },
                { label: 'Ready to dispense', val: num(d.pharmacy_desk.ready_to_dispense), href: '/prescriptions?status=approved' },
                { label: 'Partially dispensed', val: num(d.pharmacy_desk.partially_dispensed), href: '/prescriptions?status=partially_dispensed' },
                { label: 'Low-stock medicines', val: num(d.pharmacy_desk.low_stock), href: '/inventory?tab=lowstock' },
                { label: 'Out of stock', val: num(d.pharmacy_desk.out_of_stock), href: '/inventory?tab=products&stock=oos' },
                { label: 'Nearing expiry', val: num(d.pharmacy_desk.expiring_soon), href: '/inventory?tab=expiry&when=soon' },
                { label: 'Expired lots', val: num(d.pharmacy_desk.expired_lots), href: '/inventory?tab=expiry&when=expired' },
                { label: 'Quarantined', val: num(d.pharmacy_desk.quarantined), href: '/prescriptions?holds=quarantine#lot-holds' },
                { label: 'Recalled', val: num(d.pharmacy_desk.recalled), href: '/prescriptions?holds=recall#lot-holds' },
                { label: 'Pending purchase orders', val: num(d.pharmacy_desk.pending_purchase_orders), href: '/purchasing' },
              ].map((card) => (
                <Link className="stat" key={card.label} href={card.href} style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div className="label">{card.label}</div>
                  <div className="val">{card.val}</div>
                </Link>
              ))}
            </div>
            <div className="plat-actions" style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <Link href="/prescriptions?new=1">New prescription</Link>
              <Link href="/prescriptions?status=approved">Dispense prescription</Link>
              <Link href="/inventory?tab=products">New medicine</Link>
              <Link href="/purchasing">Receive stock</Link>
              <Link href="/pos">Pharmacy POS</Link>
              <Link href="/reports">Pharmacy reports</Link>
            </div>
          </section>
        )}

        {featureCards.length > 0 && (
          <section className="stat-grid" style={{ marginTop: 12 }} aria-label="Company shortcuts">
            {featureCards.map((f) => {
              let value = 'Open';
              if (f.id === 'expiry_lots') value = num(expiring);
              if (f.id === 'batches') value = num(d.pharmacy_desk?.on_hand_lots ?? 0);
              if (f.id === 'prescriptions') value = num(d.rx_queue?.open ?? 0);
              if (f.id === 'rx_products') value = num(d.rx_only_count ?? 0);
              return (
              <Link
                className="stat"
                key={f.id}
                href={f.href}
                style={{ textDecoration: 'none', color: 'inherit' }}
              >
                <div className="label">{f.label}</div>
                <div className="val">{value}</div>
              </Link>
              );
            })}
          </section>
        )}

        {(layout === 'wholesale' || layout === 'retail_wholesale') && (
          <WholesaleDeskCards status={dashStatus} desk={d.wholesale_desk} />
        )}

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
              <DailyBars data={daily} field="sales" color="#4AB012" />
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
              <TrendLine data={dailyAll} color="#4AB012" />
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
                  stroke="#4AB012"
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
                  <span className="dot" style={{ background: '#4AB012', width: 12, height: 12, borderRadius: 4 }} />
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
                <Link className="pill" href={links.expiring || '/inventory?tab=expiry'} style={{ textDecoration: 'none', color: 'inherit' }}>
                  <span className="dot" style={{ background: '#13612E', width: 12, height: 12, borderRadius: 4 }} />
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
              <PanelIcon name="mix" />
              Business mix
            </h3>
            <p className="hint">Customers vs suppliers</p>
            <div className="mix">
              <svg width="140" height="140" viewBox="0 0 140 140" role="img" aria-label="Customers vs suppliers">
                <circle cx="70" cy="70" r={r} fill="none" stroke="#EAF8D8" strokeWidth="16" />
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
                      stroke="#13612E"
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
                  <span className="dot" style={{ background: '#13612E' }} /> Suppliers · <b>&nbsp;{num(suppliers)}</b>
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
        <p className="muted">A Ribdigi House product</p>
        </>
        )}
      </div>
    </>
  );
}
