'use client';

import Link from 'next/link';

type DeskStatus = 'loading' | 'ready' | 'error';

type Feature = { id: string; label: string; href: string };

function figure(status: DeskStatus, value: number | null | undefined): string {
  if (status !== 'ready') return '…';
  return String(value ?? 0);
}

function Card({
  label,
  value,
  href,
}: {
  label: string;
  value: string;
  href: string;
}) {
  return (
    <Link className="stat" href={href} style={{ textDecoration: 'none', color: 'inherit' }} aria-label={label}>
      <div className="label">{label}</div>
      <div className="val">{value}</div>
    </Link>
  );
}

export function WholesaleDeskCards({
  status,
  desk,
}: {
  status: DeskStatus;
  desk?: {
    open_quotes?: number;
    open_orders?: number;
    reserved_qty?: number;
    ar_total_due?: number;
  } | null;
}) {
  const empty =
    status === 'ready' &&
    !desk?.open_quotes &&
    !desk?.open_orders &&
    !desk?.reserved_qty &&
    !desk?.ar_total_due;
  return (
    <section aria-label="Wholesale" style={{ marginTop: 16 }}>
      <h2 style={{ margin: '0 0 8px', fontSize: 18 }}>Wholesale</h2>
      {status === 'loading' && (
        <p className="muted" role="status">
          Loading wholesale figures…
        </p>
      )}
      {status === 'error' && (
        <p className="login-error" role="alert">
          Wholesale figures are hidden until the dashboard reloads.
        </p>
      )}
      {empty && (
        <p className="muted">No open quotes, orders, or reserved stock yet.</p>
      )}
      {status === 'ready' && (
        <div className="stat-grid">
          <Card label="Open quotes" value={figure(status, desk?.open_quotes)} href="/sales?tab=quotations" />
          <Card label="Open orders" value={figure(status, desk?.open_orders)} href="/sales?tab=orders" />
          <Card label="Reserved stock" value={figure(status, desk?.reserved_qty)} href="/inventory" />
          <Card label="Receivables due" value={figure(status, desk?.ar_total_due)} href="/credit" />
        </div>
      )}
    </section>
  );
}

export function IndustryDashboardView({
  layout,
  status,
  error,
  companyName,
  features,
  pharmacyDesk,
  fmcgDesk,
  hospitalDesk,
  wholesaleDesk,
  rxQueue,
}: {
  layout: string;
  status: DeskStatus;
  error: string;
  companyName: string;
  features: Feature[];
  pharmacyDesk?: Record<string, number | undefined> | null;
  fmcgDesk?: Record<string, number | undefined> | null;
  hospitalDesk?: { patients?: number; open_visits?: number } | null;
  wholesaleDesk?: {
    open_quotes?: number;
    open_orders?: number;
    reserved_qty?: number;
    ar_total_due?: number;
  } | null;
  rxQueue?: {
    received?: number;
    review?: number;
    approved?: number;
    partially_dispensed?: number;
    dispensed?: number;
    cancelled?: number;
    open?: number;
  } | null;
}) {
  const title =
    layout === 'pharmacy'
      ? 'Pharmacy'
      : layout === 'fmcg'
        ? 'FMCG'
        : layout === 'wholesale'
          ? 'Wholesale'
          : layout === 'hospital'
            ? 'Hospital'
            : 'Company dashboard';

  if (layout === 'unconfigured') {
    return (
      <section aria-label="Industry configuration">
        <h1>{title}</h1>
        <p className="login-error" role="alert">
          This company does not have a configured industry dashboard. Set a supported industry on the Company page.
          Retail operations are not shown for an unrecognised industry.
        </p>
        <p>
          <Link href="/company">Open company settings</Link>
        </p>
      </section>
    );
  }

  return (
    <section aria-label={`${title} dashboard`}>
      <h1>
        {title}
        {companyName ? ` · ${companyName}` : ''}
      </h1>
      {status === 'loading' && (
        <p className="muted" role="status">
          Loading dashboard…
        </p>
      )}
      {status === 'error' && (
        <p className="login-error" role="alert">
          {error || 'Unable to load dashboard'}
        </p>
      )}
      {layout === 'pharmacy' && status === 'ready' && (
        <PharmacyBody desk={pharmacyDesk} rxQueue={rxQueue} />
      )}
      {layout === 'fmcg' && status === 'ready' && <FmcgBody desk={fmcgDesk} />}
      {layout === 'wholesale' && status === 'ready' && (
        <WholesaleDeskCards status="ready" desk={wholesaleDesk} />
      )}
      {layout === 'hospital' && status === 'ready' && <HospitalBody desk={hospitalDesk} />}
      {status === 'ready' && features.length > 0 && (
        <ul>
          {features.map((feature) => (
            <li key={feature.id}>
              <Link href={feature.href}>{feature.label}</Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function PharmacyBody({
  desk,
  rxQueue,
}: {
  desk?: Record<string, number | undefined> | null;
  rxQueue?: {
    received?: number;
    review?: number;
    approved?: number;
    partially_dispensed?: number;
    dispensed?: number;
    cancelled?: number;
    open?: number;
  } | null;
}) {
  const empty =
    !desk?.sales_today &&
    !desk?.returns_today &&
    !desk?.awaiting_review &&
    !desk?.ready_to_dispense &&
    !desk?.partially_dispensed &&
    !desk?.low_stock &&
    !desk?.out_of_stock &&
    !desk?.expiring_soon &&
    !desk?.expired_lots &&
    !desk?.quarantined &&
    !desk?.recalled &&
    !desk?.pending_purchase_orders &&
    !rxQueue?.open;
  return (
    <>
      {empty && (
        <p className="muted">
          No pharmacy activity yet. Lots, prescriptions, and expiry appear here once this company has them.
        </p>
      )}
      <div className="stat-grid">
        <Card label="Today's pharmacy sales" value={String(desk?.sales_today ?? 0)} href="/reports" />
        <Card label="Today's returns" value={String(desk?.returns_today ?? 0)} href="/sales" />
        <Card label="Awaiting review" value={String(desk?.awaiting_review ?? 0)} href="/prescriptions?status=review" />
        <Card label="Ready to dispense" value={String(desk?.ready_to_dispense ?? 0)} href="/prescriptions?status=approved" />
        <Card label="Partially dispensed" value={String(desk?.partially_dispensed ?? 0)} href="/prescriptions?status=partially_dispensed" />
        <Card label="Low-stock medicines" value={String(desk?.low_stock ?? 0)} href="/inventory?tab=lowstock" />
        <Card label="Out of stock" value={String(desk?.out_of_stock ?? 0)} href="/inventory?tab=products&stock=oos" />
        <Card label="Nearing expiry" value={String(desk?.expiring_soon ?? 0)} href="/inventory?tab=expiry&when=soon" />
        <Card label="Expired lots" value={String(desk?.expired_lots ?? 0)} href="/inventory?tab=expiry&when=expired" />
        <Card label="Quarantined" value={String(desk?.quarantined ?? 0)} href="/prescriptions?holds=quarantine#lot-holds" />
        <Card label="Recalled" value={String(desk?.recalled ?? 0)} href="/prescriptions?holds=recall#lot-holds" />
        <Card label="Pending purchase orders" value={String(desk?.pending_purchase_orders ?? 0)} href="/purchasing" />
      </div>
      {typeof rxQueue?.open === 'number' && (
        <p className="muted" aria-label="Prescription queue">
          Open prescriptions: {rxQueue.open}
        </p>
      )}
    </>
  );
}

function FmcgBody({ desk }: { desk?: Record<string, number | undefined> | null }) {
  const empty =
    !desk?.schemes_active &&
    !desk?.routes_active &&
    !desk?.route_stops &&
    !desk?.deliveries_pending &&
    !desk?.deliveries_completed &&
    !desk?.deliveries_failed &&
    !desk?.batches_expiring_30d;
  return (
    <>
      {empty && (
        <p className="muted">No trade schemes, routes, or van deliveries yet for this company.</p>
      )}
      <div className="stat-grid">
        <Card label="Active schemes" value={String(desk?.schemes_active ?? 0)} href="/fmcg?tab=schemes" />
        <Card label="Active routes" value={String(desk?.routes_active ?? 0)} href="/fmcg?tab=routes" />
        <Card label="Route stops" value={String(desk?.route_stops ?? 0)} href="/fmcg?tab=routes" />
        <Card label="Deliveries pending" value={String(desk?.deliveries_pending ?? 0)} href="/fmcg?tab=deliveries" />
        <Card label="Deliveries completed" value={String(desk?.deliveries_completed ?? 0)} href="/fmcg?tab=deliveries" />
        <Card label="Deliveries failed" value={String(desk?.deliveries_failed ?? 0)} href="/fmcg?tab=deliveries" />
        <Card label="Batches expiring in 30 days" value={String(desk?.batches_expiring_30d ?? 0)} href="/fmcg?tab=expiry" />
        <Card label="Active customers" value={String(desk?.customers_active ?? 0)} href="/fmcg" />
      </div>
    </>
  );
}

function HospitalBody({ desk }: { desk?: { patients?: number; open_visits?: number } | null }) {
  const empty = !desk?.patients && !desk?.open_visits;
  return (
    <>
      {empty && <p className="muted">No patients or open visits yet for this company.</p>}
      <div className="stat-grid">
        <Card label="Patients" value={String(desk?.patients ?? 0)} href="/hospital" />
        <Card label="Open visits" value={String(desk?.open_visits ?? 0)} href="/hospital" />
      </div>
    </>
  );
}
