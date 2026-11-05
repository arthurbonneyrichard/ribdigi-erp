'use client';

import { useEffect, useRef, type ReactNode, type RefObject } from 'react';
import Link from 'next/link';

/** Building blocks shared by the software owner console. Styled by platform-ui.css. */

const TENANT_STATUS: Record<string, { tone: string; label: string }> = {
  active: { tone: 'ok', label: 'Active' },
  trial: { tone: 'info', label: 'Trial' },
  grace: { tone: 'warn', label: 'Grace' },
  suspended: { tone: 'bad', label: 'Suspended' },
};

export function plainWords(value?: string | null) {
  const text = String(value || '').replace(/[_-]+/g, ' ').trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : '';
}

const MODULE_NAMES: Record<string, string> = {
  ai: 'AI assistant',
  pos: 'Point of sale',
  ecommerce: 'Online store',
  credit: 'Customer credit',
  stores: 'Multi-store',
  tax: 'Tax',
  fmcg: 'FMCG',
};

export function moduleName(code: string) {
  return MODULE_NAMES[code] || plainWords(code);
}

/** Tenant lifecycle state. Always a label and a dot, never colour alone. */
export function TenantStatus({ status }: { status?: string | null }) {
  const key = String(status || '').toLowerCase();
  const known = TENANT_STATUS[key];
  return (
    <span className={`plat-status is-${known?.tone || 'none'}`}>{known?.label || plainWords(key) || '—'}</span>
  );
}

export function Tag({ tone = 'none', children }: { tone?: 'ok' | 'info' | 'warn' | 'bad' | 'none'; children: ReactNode }) {
  return <span className={`plat-status is-${tone}`}>{children}</span>;
}

export function Avatar({ name }: { name?: string | null }) {
  const words = String(name || '?').trim().split(/\s+/);
  const initials = `${words[0]?.[0] || '?'}${words.length > 1 ? words[words.length - 1][0] : ''}`;
  return (
    <span className="plat-avatar" aria-hidden="true">
      {initials.toUpperCase()}
    </span>
  );
}

export function Metric({
  label,
  value,
  note,
  href,
  tone,
  children,
}: {
  label: string;
  value?: ReactNode;
  note?: ReactNode;
  href?: string;
  tone?: 'bad';
  children?: ReactNode;
}) {
  const body = (
    <>
      <span className="plat-metric-label">{label}</span>
      {children || <strong className="plat-metric-value">{value}</strong>}
      {note ? <span className="plat-metric-note">{note}</span> : null}
    </>
  );
  const className = `plat-metric${tone ? ` is-${tone}` : ''}`;
  return href ? (
    <Link href={href} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  );
}

export type PlatTab = { key: string; label: string; count?: number | null; alert?: boolean };

export function Tabs({
  tabs,
  active,
  onChange,
  label,
}: {
  tabs: PlatTab[];
  active: string;
  onChange: (key: string) => void;
  label: string;
}) {
  return (
    <div className="plat-tabs" role="tablist" aria-label={label}>
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          aria-selected={active === tab.key}
          className={active === tab.key ? 'is-on' : undefined}
          onClick={() => onChange(tab.key)}
        >
          {tab.label}
          {tab.count != null ? (
            <span className={`plat-tab-count${tab.alert ? ' is-alert' : ''}`}>{tab.count}</span>
          ) : null}
        </button>
      ))}
    </div>
  );
}

/** Right-hand panel for working on one record without losing the list behind it. */
export function Drawer({
  id,
  title,
  subtitle,
  badge,
  closeLabel,
  onClose,
  busy,
  panelRef,
  tabs,
  children,
}: {
  id?: string;
  title: string;
  subtitle?: ReactNode;
  badge?: ReactNode;
  closeLabel: string;
  onClose: () => void;
  busy?: boolean;
  panelRef?: RefObject<HTMLDivElement>;
  tabs?: ReactNode;
  children: ReactNode;
}) {
  const ownRef = useRef<HTMLDivElement>(null);
  const ref = panelRef || ownRef;
  const touched = useRef(false);
  const wasBusy = useRef(false);
  const close = useRef(onClose);
  close.current = onClose;
  // A finished save clears the unsaved flag, the same way FormModal does.
  if (wasBusy.current && !busy) touched.current = false;
  wasBusy.current = Boolean(busy);

  function requestClose() {
    if (wasBusy.current) return;
    if (touched.current && !window.confirm('You have unsaved changes. Discard them?')) return;
    close.current();
  }

  useEffect(() => {
    const panel = ref.current;
    const lastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panel?.focus();
    const onKey = (event: KeyboardEvent) => {
      // A dialog opened from inside the drawer owns Escape and Tab.
      if (document.querySelector('.erp-modal')) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        requestClose();
        return;
      }
      if (event.key !== 'Tab' || !panel) return;
      const list = Array.from(
        panel.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled])',
        ),
      );
      if (!list.length) return;
      const first = list[0];
      const last = list[list.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === panel)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    const onEdit = () => {
      touched.current = true;
    };
    document.addEventListener('keydown', onKey);
    panel?.addEventListener('input', onEdit, true);
    panel?.addEventListener('change', onEdit, true);
    return () => {
      document.removeEventListener('keydown', onKey);
      panel?.removeEventListener('input', onEdit, true);
      panel?.removeEventListener('change', onEdit, true);
      lastFocus?.focus?.();
    };
    // Bound once per open; requestClose reads the latest values through refs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="plat-drawer-root">
      <div className="plat-drawer-back" onClick={requestClose} aria-hidden="true" />
      <div ref={ref} id={id} className="plat-drawer" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1}>
        <div className="plat-drawer-head">
          <div className="plat-drawer-title">
            <Avatar name={title} />
            <div>
              <h2>{title}</h2>
              {subtitle ? <p className="muted">{subtitle}</p> : null}
            </div>
            {badge}
          </div>
          <button type="button" className="plat-icon-btn" onClick={requestClose} aria-label={closeLabel}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>
        {tabs ? <div className="plat-drawer-tabs">{tabs}</div> : null}
        <div className="plat-drawer-body">{children}</div>
      </div>
    </div>
  );
}

/** Friendly distance from now, e.g. "3 hours ago". Falls back to a date past a week. */
export function timeAgo(value?: string | null) {
  if (!value) return '—';
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return String(value);
  const minutes = Math.round((Date.now() - then) / 60000);
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} day${days === 1 ? '' : 's'} ago`;
  return new Date(then).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Days until a date, in words. Negative means the date has passed. */
export function daysLeft(days?: number | null) {
  if (days == null) return '—';
  if (days === 0) return 'Today';
  if (days < 0) return `${Math.abs(days)} day${days === -1 ? '' : 's'} overdue`;
  return `${days} day${days === 1 ? '' : 's'} left`;
}

/** The API sends UTC without a zone marker; without this, browsers read it as local time. */
function asUtc(value: string) {
  return /[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`;
}

export const QUIET_DAYS = 14;

/**
 * A paying or trial company nobody has used for QUIET_DAYS. Brand-new companies get that long
 * to sign in first. Suspended and grace companies already show up elsewhere.
 */
export function isQuiet(row: {
  slug?: string;
  status?: string;
  created_at?: string | null;
  last_active_at?: string | null;
}) {
  if (row.status !== 'active' && row.status !== 'trial') return false;
  if (row.slug === 'platform' || row.slug === 'ribdigi-platform') return false;
  const seen = row.last_active_at || row.created_at;
  if (!seen) return false;
  return Date.now() - new Date(asUtc(seen)).getTime() > QUIET_DAYS * 86400000;
}

export function lastActiveLabel(value?: string | null) {
  return value ? timeAgo(asUtc(value)) : 'Never';
}

function monthName(key: string) {
  const [year, month] = key.split('-').map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleDateString(undefined, {
    month: 'short',
    year: '2-digit',
    timeZone: 'UTC',
  });
}

/** Twelve months of one measure. One hue, baseline-anchored, value on hover. */
export function MonthBars({
  label,
  rows,
  format = (value) => String(value),
}: {
  label: string;
  rows: { month: string; value: number }[];
  format?: (value: number) => string;
}) {
  const max = Math.max(0, ...rows.map((row) => row.value));
  const last = rows[rows.length - 1];
  return (
    <figure className="plat-months-fig">
      <div
        className="plat-months"
        role="img"
        aria-label={`${label}, last ${rows.length} months: ${rows
          .map((row) => `${monthName(row.month)} ${format(row.value)}`)
          .join(', ')}`}
      >
        {rows.map((row) => (
          <div key={row.month} className="plat-month" data-tip={`${monthName(row.month)}: ${format(row.value)}`}>
            <span style={{ height: max ? `${Math.max(row.value ? 3 : 0, (row.value / max) * 100)}%` : 0 }} />
          </div>
        ))}
      </div>
      <figcaption className="plat-months-axis">
        <span>{rows.length ? monthName(rows[0].month) : ''}</span>
        <span>{last ? `${monthName(last.month)}: ${format(last.value)}` : ''}</span>
      </figcaption>
    </figure>
  );
}
