'use client';

/**
 * The dashboard the bakery, FMCG, gym and HRM desks share: greeting, headline numbers with
 * yesterday beside them, one trend chart, "Needs you now", and shortcuts. Each desk passes
 * its own data; nothing here reads another desk.
 */

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import DashboardGreeting from './DashboardGreeting';
import DeskIcon from './DeskIcon';
import { formatMoney } from '../lib/format';
import './desk-dashboard.css';

export type DeskTile = {
  label: string;
  value: string | number;
  sub?: string;
  /** Compare with an earlier figure, shown as words and an arrow, never colour alone. */
  before?: { value: number; now: number; word: string };
  warn?: boolean;
  href?: string;
  icon?: string;
  /** A small line of recent values, oldest first. Decorative: the chart and table hold the numbers. */
  spark?: number[];
};
export type DeskTrend = { label: string; unit: 'money' | 'count'; step: 'day' | 'month'; points: { date: string; value: number }[] };
export type DeskAttention = { level: 'warning' | 'info'; text: string; href: string };
export type DeskAction = { label: string; href: string; primary?: boolean; icon?: string; hint?: string };

const fmt = (value: number, unit: 'money' | 'count') => (unit === 'money' ? formatMoney(value) : value.toLocaleString());

function pointLabel(raw: string, step: 'day' | 'month', long = false) {
  if (step === 'month') {
    const [y, m] = raw.split('-').map(Number);
    return new Date(y, m - 1, 1).toLocaleDateString([], { month: long ? 'long' : 'short', year: long ? 'numeric' : undefined });
  }
  const [y, m, d] = raw.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString([], long ? { weekday: 'long', day: 'numeric', month: 'long' } : { day: 'numeric', month: 'short' });
}

function niceMax(value: number) {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  const steps = [1, 2, 2.5, 5, 10];
  return (steps.find((s) => s * power >= value) || 10) * power;
}

function Change({ before }: { before: NonNullable<DeskTile['before']> }) {
  const { value, now, word } = before;
  if (!value && !now) return <small className="dd-change">Nothing {word} either</small>;
  if (!value) return <small className="dd-change">None {word}</small>;
  const pct = Math.round(((now - value) / Math.abs(value)) * 100);
  if (pct === 0) return <small className="dd-change">Same as {word}</small>;
  return (
    <small className="dd-change">
      <span aria-hidden="true">{pct > 0 ? '▲' : '▼'}</span> {Math.abs(pct)}% {pct > 0 ? 'up' : 'down'} on {word}
    </small>
  );
}

export function TrendChart({ trend }: { trend: DeskTrend }) {
  const [hover, setHover] = useState<number | null>(null);
  const [W, setW] = useState(640);
  const box = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = box.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const watch = new ResizeObserver(([entry]) => setW(Math.max(240, Math.round(entry.contentRect.width))));
    watch.observe(el);
    return () => watch.disconnect();
  }, []);
  const points = trend.points;
  const top = useMemo(() => {
    const raw = niceMax(Math.max(0, ...points.map((p) => p.value)));
    return trend.unit === 'count' ? Math.max(2, Math.ceil(raw / 2) * 2) : raw;
  }, [points, trend.unit]);
  const scaleText = (v: number) => fmt(v, trend.unit).replace(/\.00$/, '');
  const gutter = Math.ceil(Math.max(scaleText(top).length, 2) * 7) + 10;
  const H = 210;
  const pad = { l: gutter, r: 6, t: 14, b: 28 };
  const plotH = H - pad.t - pad.b;
  const slot = (W - pad.l - pad.r) / Math.max(points.length, 1);
  const barW = Math.max(4, Math.min(34, slot - 4));
  const total = points.reduce((s, p) => s + p.value, 0);
  const room = Math.max(1, Math.floor((W - pad.l) / 64));
  const every = Math.max(1, Math.ceil(points.length / room));
  const shown = hover != null ? points[hover] : null;
  const tipLeft = hover != null ? Math.min(Math.max(pad.l + (hover + 0.5) * slot, 80), W - 80) : 0;
  const tipTop = hover != null ? pad.t + plotH - (points[hover].value > 0 ? Math.max(2, (points[hover].value / top) * plotH) : 0) - 8 : 0;

  if (!points.length) return null;
  return (
    <figure className="dd-chart">
      <figcaption>
        <span className="dd-chart-title">{trend.label}</span>
        <span className="dd-chart-total">{fmt(total, trend.unit)} in all</span>
      </figcaption>
      <div className="dd-plot" ref={box} onMouseLeave={() => setHover(null)}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${trend.label}. ${fmt(total, trend.unit)} in all.`}>
          {[0.5, 1].map((f) => {
            const y = pad.t + plotH * (1 - f);
            const v = top * f;
            return (
              <g key={f}>
                <line x1={pad.l} x2={W - pad.r} y1={y} y2={y} className="dd-grid" />
                {trend.unit === 'count' && !Number.isInteger(v) ? null : (
                  <text x={pad.l - 6} y={y + 4} textAnchor="end" className="dd-tick">{scaleText(v)}</text>
                )}
              </g>
            );
          })}
          <line x1={pad.l} x2={W - pad.r} y1={pad.t + plotH} y2={pad.t + plotH} className="dd-axis" />
          <text x={pad.l - 6} y={pad.t + plotH + 4} textAnchor="end" className="dd-tick">0</text>
          {points.map((p, i) => {
            const h = p.value > 0 ? Math.max(2, (p.value / top) * plotH) : 0;
            const x = pad.l + i * slot + (slot - barW) / 2;
            const y = pad.t + plotH - h;
            const r = Math.min(4, h / 2, barW / 2);
            const last = i === points.length - 1;
            return (
              <g key={p.date}>
                {h > 0 ? (
                  <path
                    className={`dd-bar${hover === i ? ' on' : ''}`}
                    d={`M${x},${y + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + barW - r} Q${x + barW},${y} ${x + barW},${y + r} V${y + h} Z`}
                  />
                ) : null}
                <rect
                  className="dd-hit" x={pad.l + i * slot} y={pad.t} width={slot} height={plotH + pad.b}
                  onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} onBlur={() => setHover(null)} tabIndex={0}
                  aria-label={`${pointLabel(p.date, trend.step, true)}: ${fmt(p.value, trend.unit)}`}
                />
                {(points.length - 1 - i) % every === 0 ? (
                  <text x={pad.l + i * slot + slot / 2} y={H - 8} textAnchor={last ? 'end' : 'middle'} dx={last ? slot / 2 : 0} className={`dd-tick${last ? ' now' : ''}`}>
                    {last && trend.step === 'day' ? 'Today' : pointLabel(p.date, trend.step)}
                  </text>
                ) : null}
              </g>
            );
          })}
        </svg>
        {shown && hover != null ? (
          <div className="dd-tip" style={{ left: tipLeft, top: Math.max(tipTop, 52) }} role="status">
            <span>{pointLabel(shown.date, trend.step, true)}</span>
            <b>{fmt(shown.value, trend.unit)}</b>
          </div>
        ) : null}
      </div>
      <details className="dd-table">
        <summary>Show as a table</summary>
        <table>
          <tbody>
            {points.map((p) => <tr key={p.date}><td>{pointLabel(p.date, trend.step, true)}</td><td>{fmt(p.value, trend.unit)}</td></tr>)}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

function Spark({ values }: { values: number[] }) {
  if (values.length < 2 || values.every((v) => v === 0)) return null;
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 96 + 2},${30 - ((v - min) / span) * 26}`).join(' ');
  return (
    <svg className="dd-spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">
      <polyline points={pts} fill="none" />
    </svg>
  );
}

export function DeskTiles({ tiles }: { tiles: DeskTile[] }) {
  return (
    <div className="dd-tiles">
      {tiles.map((t) => {
        const body = (
          <>
            <span className="dd-tile-top">
              <span className="dd-tile-ico" aria-hidden="true"><DeskIcon name={t.warn ? 'alert' : t.icon || 'chart'} size={18} /></span>
              <span className="dd-tile-label">{t.label}</span>
            </span>
            <b className={String(t.value).length > 10 ? 'long' : undefined}>{t.value}</b>
            <span className="dd-tile-foot">
              {t.before ? <Change before={t.before} /> : t.sub ? <small>{t.sub}</small> : <small>&nbsp;</small>}
              {t.spark ? <Spark values={t.spark} /> : null}
            </span>
          </>
        );
        return t.href ? (
          <Link key={t.label} href={t.href} className={`dd-tile${t.warn ? ' warn' : ''}`}>{body}</Link>
        ) : (
          <div key={t.label} className={`dd-tile${t.warn ? ' warn' : ''}`}>{body}</div>
        );
      })}
    </div>
  );
}

/** The row of shortcut cards: the jobs done every day. Also used on the retail dashboard. */
export function DeskShortcuts({ actions }: { actions: DeskAction[] }) {
  if (!actions.length) return null;
  return (
    <nav className="dd-actions" aria-label="Shortcuts">
      {actions.map((a) => (
        <Link key={a.href + a.label} href={a.href} className={a.primary ? 'primary' : ''}>
          <span className="dd-act-ico" aria-hidden="true"><DeskIcon name={a.icon || 'arrow'} size={20} /></span>
          <span className="dd-act-text">
            <b>{a.label}</b>
            {a.hint ? <small>{a.hint}</small> : null}
          </span>
        </Link>
      ))}
    </nav>
  );
}

export default function DeskDashboard({
  desk,
  tiles,
  trend,
  attention,
  actions,
  children,
}: {
  desk: string;
  tiles: DeskTile[];
  trend?: DeskTrend | null;
  attention?: DeskAttention[];
  actions?: DeskAction[];
  children?: ReactNode;
}) {
  const items = attention || [];
  const warnings = items.filter((a) => a.level === 'warning').length;
  return (
    <div className="deskdash">
      <DashboardGreeting desk={desk} />
      {actions?.length ? <DeskShortcuts actions={actions} /> : null}
      <DeskTiles tiles={tiles} />
      <div className="dd-grid2">
        {trend ? <section className="dd-box"><TrendChart trend={trend} /></section> : null}
        <section className="dd-box" aria-label="Needs you now">
          <div className="dd-box-head">
            <h2>Needs you now</h2>
            {items.length ? <span className="dd-count">{warnings ? `${warnings} to act on` : `${items.length} to note`}</span> : null}
          </div>
          {items.length === 0 ? (
            <p className="dd-clear"><span className="dd-clear-ico" aria-hidden="true"><DeskIcon name="check" size={18} /></span> All clear. Nothing is waiting on you.</p>
          ) : (
            <ul className="dd-attn">
              {items.map((a) => (
                <li key={a.text} className={a.level}>
                  <Link href={a.href}>
                    <span className="dd-attn-mark" aria-hidden="true"><DeskIcon name={a.level === 'warning' ? 'alert' : 'clock'} size={16} /></span>
                    <span className="dd-attn-body">
                      <span className="dd-attn-word">{a.level === 'warning' ? 'Act now' : 'Note'}</span>
                      <span>{a.text}</span>
                    </span>
                    <span className="dd-go" aria-hidden="true"><DeskIcon name="arrow" size={16} /></span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      {children}
    </div>
  );
}
