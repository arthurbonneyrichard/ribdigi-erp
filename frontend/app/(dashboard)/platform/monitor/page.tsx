'use client';

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import PageSkeleton from '../../../../components/PageSkeleton';
import DeskIcon from '../../../../components/DeskIcon';
import { Tag } from '../../../../components/PlatformUi';
import { api } from '../../../../lib/api';
import { getMe } from '../../../../lib/meCache';
import './monitor.css';

const PLATFORM_ROLES = ['super_admin', 'platform_owner', 'platform_admin', 'platform_support', 'platform_finance'];
const ALERT_ROLES = ['super_admin', 'platform_owner', 'platform_admin'];
const REFRESH_MS = 30_000;

type Check = { key: string; label: string; status: 'ok' | 'warn' | 'critical' | 'unknown'; value: string; detail: string };
type Point = Record<string, any> & { t: string; s: string };
type Tone = 'ok' | 'warn' | 'bad' | 'none';

const TONE: Record<string, Tone> = { ok: 'ok', warn: 'warn', critical: 'bad', unknown: 'none' };
const STATUS_WORD: Record<string, string> = { ok: 'Healthy', warn: 'Needs a look', critical: 'Problem', unknown: 'Unknown' };
const CHECK_ICON: Record<string, string> = {
  cpu: 'chart',
  memory: 'box',
  disk: 'box',
  database: 'wallet',
  redis: 'flame',
  workers: 'users',
  scheduler: 'clock',
  latency: 'clock',
  errors: 'alert',
  backups: 'download',
  web: 'home',
  tls: 'check',
};

function bytes(n?: number | null) {
  if (n == null) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let v = Number(n);
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v >= 10 || i === 0 ? v.toFixed(0) : v.toFixed(1)} ${units[i]}`;
}

function duration(sec?: number | null) {
  if (sec == null) return '—';
  const s = Math.max(0, Math.floor(sec));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${m}m`;
}

function when(value?: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return value;
  }
}

function ago(date: Date | null, now: number) {
  if (!date) return '—';
  const s = Math.max(0, Math.round((now - date.getTime()) / 1000));
  return s < 5 ? 'just now' : s < 60 ? `${s}s ago` : `${Math.floor(s / 60)}m ago`;
}

const pct = (v?: number | null) => (v == null ? '—' : `${Number(v).toFixed(v < 10 ? 1 : 0)}%`);
const ms = (v?: number | null) => (v == null ? '—' : `${Math.round(Number(v))} ms`);

function levelTone(value: number | null | undefined, limit?: number, warnRatio = 0.85): Tone {
  if (value == null || !limit) return 'none';
  if (value >= limit) return 'bad';
  if (value >= limit * warnRatio) return 'warn';
  return 'ok';
}

/* ------------------------------------------------------------------ pieces */

function Ring({ value, size = 120, stroke = 10, tone = 'ok', children, label }: {
  value: number | null | undefined;
  size?: number;
  stroke?: number;
  tone?: Tone;
  children?: ReactNode;
  label: string;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className="mon-ring" style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
        <circle className="mon-ring-track" cx={size / 2} cy={size / 2} r={r} strokeWidth={stroke} />
        <circle
          className={`mon-ring-fill is-${tone}`}
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={stroke}
          strokeDasharray={`${(v / 100) * c} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="mon-ring-body">{children}</div>
    </div>
  );
}

/** Three-quarter arc gauge with the alert limit marked on the arc. */
function Gauge({ title, icon, value, limit, sub, foot }: {
  title: string;
  icon: string;
  value: number | null | undefined;
  limit?: number;
  sub: ReactNode;
  foot?: ReactNode;
}) {
  const size = 150;
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const arc = c * 0.75;
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const tone = levelTone(value, limit);
  const lim = Math.max(0, Math.min(100, limit ?? 100));
  const angle = (135 + (lim / 100) * 270) * (Math.PI / 180);
  const cx = size / 2;
  const tick = (d: number) => [cx + Math.cos(angle) * d, cx + Math.sin(angle) * d];
  const [x1, y1] = tick(r - stroke / 2 - 3);
  const [x2, y2] = tick(r + stroke / 2 + 3);
  return (
    <div className="mon-card mon-gauge">
      <div className="mon-card-head">
        <span className="mon-ico">
          <DeskIcon name={icon} size={16} />
        </span>
        <span>{title}</span>
        <span className={`mon-pill is-${tone}`}>{tone === 'bad' ? 'Over limit' : tone === 'warn' ? 'High' : 'Normal'}</span>
      </div>
      <div className="mon-gauge-dial" role="img" aria-label={`${title} ${pct(value)}, alert at ${limit}%`}>
        <svg viewBox={`0 0 ${size} ${size}`}>
          <circle className="mon-ring-track" cx={cx} cy={cx} r={r} strokeWidth={stroke}
            strokeDasharray={`${arc} ${c}`} transform={`rotate(135 ${cx} ${cx})`} />
          <circle className={`mon-ring-fill is-${tone}`} cx={cx} cy={cx} r={r} strokeWidth={stroke}
            strokeDasharray={`${(v / 100) * arc} ${c}`} transform={`rotate(135 ${cx} ${cx})`} />
          {limit ? <line className="mon-gauge-tick" x1={x1} y1={y1} x2={x2} y2={y2} /> : null}
        </svg>
        <div className="mon-gauge-value">
          <strong>{value == null ? '—' : Math.round(v)}</strong>
          <span>%</span>
        </div>
      </div>
      <p className="mon-gauge-sub">{sub}</p>
      {foot ? <p className="mon-gauge-foot">{foot}</p> : null}
    </div>
  );
}

function Spark({ points, field }: { points: Point[]; field: string }) {
  const vals = points.map((p) => (typeof p[field] === 'number' ? (p[field] as number) : null));
  const known = vals.filter((v): v is number => v != null);
  if (known.length < 2) return <div className="mon-spark is-empty" aria-hidden="true" />;
  const W = 160;
  const H = 40;
  const top = Math.max(...known) * 1.15 || 1;
  const x = (i: number) => (i / (vals.length - 1)) * W;
  const y = (v: number) => H - 2 - (v / top) * (H - 6);
  let line = '';
  let first = -1;
  let lastI = 0;
  vals.forEach((v, i) => {
    if (v == null) return;
    if (first < 0) first = i;
    lastI = i;
    line += `${line ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
  });
  const area = `${line}L${x(lastI).toFixed(1)},${H}L${x(first).toFixed(1)},${H}Z`;
  return (
    <svg className="mon-spark" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
      <path className="mon-area" d={area} />
      <path className="mon-line" d={line} />
    </svg>
  );
}

function Kpi({ title, icon, value, note, points, field, tone }: {
  title: string;
  icon: string;
  value: string;
  note: ReactNode;
  points: Point[];
  field: string;
  tone?: Tone;
}) {
  return (
    <div className={`mon-card mon-kpi${tone === 'bad' ? ' is-bad' : ''}`}>
      <div className="mon-card-head">
        <span className="mon-ico">
          <DeskIcon name={icon} size={16} />
        </span>
        <span>{title}</span>
      </div>
      <strong className="mon-kpi-value">{value}</strong>
      <span className="mon-kpi-note">{note}</span>
      <Spark points={points} field={field} />
    </div>
  );
}

function AreaChart({ title, points, field, format, limit, max }: {
  title: string;
  points: Point[];
  field: string;
  format: (v: number) => string;
  limit?: number;
  max?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 560;
  const H = 180;
  const pad = { l: 46, r: 12, t: 14, b: 24 };
  const vals = points.map((p) => (typeof p[field] === 'number' ? (p[field] as number) : null));
  const known = vals.filter((v): v is number => v != null);
  const top = max ?? Math.max(1, ...known, limit ?? 0) * 1.12;
  const x = (i: number) => pad.l + (points.length <= 1 ? 0 : (i / (points.length - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => pad.t + (1 - v / top) * (H - pad.t - pad.b);
  let line = '';
  let area = '';
  let run: number[] = [];
  const flush = () => {
    if (run.length) area += `L${x(run[run.length - 1]).toFixed(1)},${H - pad.b}L${x(run[0]).toFixed(1)},${H - pad.b}Z`;
    run = [];
  };
  vals.forEach((v, i) => {
    if (v == null) {
      flush();
      return;
    }
    const seg = `${run.length ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
    line += seg;
    area += seg;
    run.push(i);
  });
  flush();
  const last = known.length ? known[known.length - 1] : null;
  const peak = known.length ? Math.max(...known) : null;
  const avg = known.length ? known.reduce((a, b) => a + b, 0) / known.length : null;
  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - pad.l) / (W - pad.l - pad.r)) * (points.length - 1));
    setHover(Math.max(0, Math.min(points.length - 1, i)));
  };
  const hv = hover != null ? vals[hover] : null;
  const gid = `mon-grad-${field}`;
  return (
    <figure className="mon-card mon-chart">
      <figcaption className="mon-chart-head">
        <div>
          <span className="mon-chart-title">{title}</span>
          <strong>{last != null ? format(last) : '—'}</strong>
        </div>
        <dl className="mon-chart-stats">
          <div>
            <dt>Average</dt>
            <dd>{avg != null ? format(avg) : '—'}</dd>
          </div>
          <div>
            <dt>Peak</dt>
            <dd>{peak != null ? format(peak) : '—'}</dd>
          </div>
        </dl>
      </figcaption>
      {known.length === 0 ? (
        <p className="mon-empty">No readings yet for this range.</p>
      ) : (
        <div className="mon-chart-box">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`${title}: latest ${last != null ? format(last) : 'none'}, peak ${peak != null ? format(peak) : 'none'}`}
            onMouseMove={onMove}
            onMouseLeave={() => setHover(null)}
          >
            <defs>
              <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" className="mon-grad-a" />
                <stop offset="100%" className="mon-grad-b" />
              </linearGradient>
            </defs>
            {[0, top / 2, top].map((t) => (
              <g key={t}>
                <line className="mon-grid" x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} />
                <text className="mon-axis" x={pad.l - 8} y={y(t) + 4} textAnchor="end">
                  {format(t)}
                </text>
              </g>
            ))}
            {limit != null && limit < top ? (
              <g>
                <line className="mon-limit" x1={pad.l} x2={W - pad.r} y1={y(limit)} y2={y(limit)} />
                <text className="mon-axis" x={W - pad.r} y={y(limit) - 5} textAnchor="end">
                  Alert at {format(limit)}
                </text>
              </g>
            ) : null}
            <path d={area} fill={`url(#${gid})`} />
            <path className="mon-line" d={line} />
            {hover != null ? (
              <g>
                <line className="mon-cross" x1={x(hover)} x2={x(hover)} y1={pad.t} y2={H - pad.b} />
                {hv != null ? <circle className="mon-dot" cx={x(hover)} cy={y(hv)} r={5} /> : null}
              </g>
            ) : null}
            <text className="mon-axis" x={pad.l} y={H - 5}>
              {when(points[0]?.t)}
            </text>
            <text className="mon-axis" x={W - pad.r} y={H - 5} textAnchor="end">
              {when(points[points.length - 1]?.t)}
            </text>
          </svg>
          {hover != null ? (
            <div className="mon-tip" style={{ left: `${(x(hover) / W) * 100}%` }}>
              <span>{when(points[hover].t)}</span>
              <strong>{hv != null ? format(hv) : 'no reading'}</strong>
            </div>
          ) : null}
        </div>
      )}
    </figure>
  );
}

function HealthStrip({ points }: { points: Point[] }) {
  return (
    <div className="mon-strip" role="img" aria-label={`Health over time: ${points.filter((p) => p.s === 'critical').length} periods with a problem`}>
      {points.length ? (
        points.map((p) => <span key={p.t} className={`mon-strip-cell is-${TONE[p.s] || 'none'}`} title={`${when(p.t)}: ${STATUS_WORD[p.s] || p.s}`} />)
      ) : (
        <span className="mon-strip-cell is-none" />
      )}
    </div>
  );
}

function Service({ icon, title, tone, value, rows }: {
  icon: string;
  title: string;
  tone: Tone;
  value: string;
  rows: [string, ReactNode][];
}) {
  return (
    <div className="mon-card mon-service">
      <div className="mon-card-head">
        <span className="mon-ico">
          <DeskIcon name={icon} size={16} />
        </span>
        <span>{title}</span>
        <span className={`mon-dotlabel is-${tone}`}>{tone === 'ok' ? 'Up' : tone === 'bad' ? 'Down' : tone === 'warn' ? 'Check' : 'Off'}</span>
      </div>
      <strong className="mon-service-value">{value}</strong>
      <dl className="mon-service-rows">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function Bar({ value, limit, label }: { value?: number | null; limit?: number; label: string }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const tone = levelTone(value, limit);
  return (
    <span className="mon-bar" role="img" aria-label={`${label} ${pct(value)}`}>
      <span className={`mon-bar-fill is-${tone === 'none' ? 'ok' : tone}`} style={{ width: `${v}%` }} />
      {limit ? <span className="mon-bar-limit" style={{ left: `${Math.min(100, limit)}%` }} /> : null}
    </span>
  );
}

/* -------------------------------------------------------------------- page */

export default function ServerMonitorPage() {
  const router = useRouter();
  const [role, setRole] = useState('');
  const [tab, setTab] = useState('overview');
  const [live, setLive] = useState<any>(null);
  const [range, setRange] = useState<'1h' | '6h' | '24h' | '7d'>('24h');
  const [history, setHistory] = useState<any>(null);
  const [recent, setRecent] = useState<Point[]>([]);
  const [alerts, setAlerts] = useState<any>(null);
  const [launch, setLaunch] = useState<any>(null);
  const [showTable, setShowTable] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [updated, setUpdated] = useState<Date | null>(null);
  const [now, setNow] = useState(Date.now());

  const loadLive = useCallback(async () => {
    setLoading(true);
    try {
      const [r, h] = await Promise.all([api('/platform/monitor'), api('/platform/monitor/history?range=1h')]);
      setLive(r.data);
      setRecent(h.data?.points || []);
      setUpdated(new Date());
      setError('');
    } catch (e: any) {
      setError(e.message || 'Could not read the server');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async (rg: string) => {
    try {
      const r = await api(`/platform/monitor/history?range=${rg}`);
      setHistory(r.data);
    } catch (e: any) {
      setError(e.message || 'Could not load history');
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    try {
      const r = await api('/platform/monitor/alerts');
      setAlerts(r.data);
    } catch (e: any) {
      setError(e.message || 'Could not load alerts');
    }
  }, []);

  const loadLaunch = useCallback(async () => {
    setLaunch(null);
    try {
      const r = await api('/platform/monitor/launch-checks');
      setLaunch(r.data);
    } catch (e: any) {
      setError(e.message || 'Could not load launch checks');
    }
  }, []);

  useEffect(() => {
    (async () => {
      const me = await getMe().catch(() => null);
      const r = me?.data?.role || '';
      if (!PLATFORM_ROLES.includes(r)) {
        router.replace('/dashboard');
        return;
      }
      setRole(r);
      await loadLive();
    })();
  }, [router, loadLive]);

  useEffect(() => {
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(clock);
  }, []);

  useEffect(() => {
    if (!role) return;
    const timer = setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      loadLive();
      if (tab === 'history') loadHistory(range);
      if (tab === 'alerts') loadAlerts();
    }, REFRESH_MS);
    return () => clearInterval(timer);
  }, [role, tab, range, loadLive, loadHistory, loadAlerts]);

  useEffect(() => {
    if (!role) return;
    if (tab === 'history') loadHistory(range);
    if (tab === 'alerts') loadAlerts();
    if (tab === 'launch' && !launch) loadLaunch();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, tab, range]);

  async function testAlert() {
    setBusy(true);
    setNotice('');
    try {
      const r = await api('/platform/monitor/test-alert', { method: 'POST' });
      setNotice(r.message || 'Test alert sent');
      loadAlerts();
    } catch (e: any) {
      setError(e.message || 'Test alert failed');
    } finally {
      setBusy(false);
    }
  }

  const checks: Check[] = useMemo(
    () => [...(live?.checks || [])].sort((a: Check, b: Check) => (TONE[b.status] === 'bad' ? 2 : TONE[b.status] === 'warn' ? 1 : 0) - (TONE[a.status] === 'bad' ? 2 : TONE[a.status] === 'warn' ? 1 : 0)),
    [live],
  );
  const problems = checks.filter((c) => c.status === 'critical' || c.status === 'warn');
  const activeCount = Object.keys(live?.active_alerts || {}).length;
  const points: Point[] = history?.points || [];

  const launchGroups = useMemo(() => {
    const groups: Record<string, any[]> = {};
    for (const item of launch?.items || []) (groups[item.area] ||= []).push(item);
    return Object.entries(groups);
  }, [launch]);

  if (!live && !error) return <PageSkeleton label="Reading the server…" cards={4} />;

  const host = live?.host || {};
  const mem = host.memory || {};
  const perf = live?.performance || {};
  const db = live?.database || {};
  const th = live?.thresholds || {};
  const status: string = live?.status || 'unknown';
  const disks: any[] = host.disks || [];
  const worstDisk = disks.length ? disks.reduce((a, b) => (b.used_pct > a.used_pct ? b : a)) : null;
  const day = live?.uptime?.day?.healthy_pct;
  const week = live?.uptime?.week?.healthy_pct;
  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'history', label: 'History' },
    { key: 'alerts', label: 'Alerts', count: activeCount },
    { key: 'launch', label: 'Launch checks' },
  ];
  const maxSlow = Math.max(1, ...((perf.slowest || []) as any[]).map((r) => r.p95_ms || 0));
  const launchScore = launch ? Math.round((launch.counts.pass / Math.max(1, launch.items.length)) * 100) : null;

  return (
    <div className="plat mon">
      {/* ------------------------------------------------------------ hero */}
      <section className={`mon-hero is-${TONE[status]}`} aria-live="polite">
        <div className="mon-hero-main">
          <div className="mon-hero-top">
            <span className="mon-live">
              <span className="mon-live-dot" aria-hidden="true" />
              Live
            </span>
            <span className="mon-hero-kicker">Software owner · Server health</span>
          </div>
          <h1>
            {status === 'ok'
              ? 'All systems running normally'
              : status === 'unknown'
                ? 'Reading the server'
                : `${problems.length} ${problems.length === 1 ? 'thing needs' : 'things need'} attention`}
          </h1>
          <p className="mon-hero-sub">
            {status === 'ok'
              ? 'Machine, databases, workers, backups and the public site are all inside their limits.'
              : problems
                  .slice(0, 3)
                  .map((p) => `${p.label}: ${p.value}`)
                  .join(' · ')}
          </p>
          <ul className="mon-chips">
            <li>
              <DeskIcon name="home" size={14} /> {host.hostname || '—'}
            </li>
            <li>{host.os}{host.in_container ? ' · container' : ''}</li>
            <li>
              <DeskIcon name="clock" size={14} /> up {duration(host.uptime_seconds)}
            </li>
            <li>
              build {live?.build_id} · {live?.release_channel}
            </li>
          </ul>
        </div>
        <div className="mon-hero-side">
          <Ring value={day ?? 0} size={128} stroke={11} tone={day == null ? 'none' : day >= 99 ? 'ok' : day >= 95 ? 'warn' : 'bad'} label={`Healthy ${day ?? 'unknown'} percent of the last 24 hours`}>
            <strong>{day != null ? `${day}%` : '—'}</strong>
            <span>24 h healthy</span>
          </Ring>
          <div className="mon-hero-stats">
            <div>
              <span>7 days</span>
              <strong>{week != null ? `${week}%` : '—'}</strong>
            </div>
            <div>
              <span>Readings</span>
              <strong>{live?.uptime?.week?.samples ?? 0}</strong>
            </div>
            <button type="button" className={`mon-refresh${loading ? ' is-spin' : ''}`} aria-label="Refresh server health now" onClick={loadLive} disabled={loading}>
              <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">
                <path d="M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {ago(updated, now)}
            </button>
          </div>
        </div>
      </section>

      {error ? (
        <p className="login-error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="mon-notice" role="status">
          {notice}
        </p>
      ) : null}

      {/* ------------------------------------------------------------ tabs */}
      <div className="mon-seg" role="tablist" aria-label="Server health sections">
        {tabs.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} className={tab === t.key ? 'is-on' : undefined} onClick={() => setTab(t.key)}>
            {t.label}
            {t.count ? <span className="mon-seg-count">{t.count}</span> : null}
          </button>
        ))}
      </div>

      {/* -------------------------------------------------------- overview */}
      {tab === 'overview' && live ? (
        <>
          <div className="mon-grid-3">
            <Gauge
              title="Processor"
              icon="chart"
              value={host.cpu_pct}
              limit={th.cpu_pct}
              sub={`${host.cpu_cores} cores · load ${host.load_avg ? host.load_avg.join(' / ') : 'n/a'}`}
              foot={`Alert at ${th.cpu_pct}%`}
            />
            <Gauge
              title="Memory"
              icon="box"
              value={mem.used_pct}
              limit={th.memory_pct}
              sub={`${bytes(mem.used_bytes)} of ${bytes(mem.total_bytes)}`}
              foot={host.container_memory ? `Container cap ${bytes(host.container_memory.limit_bytes)} (${pct(host.container_memory.used_pct)} used)` : `Swap ${bytes(mem.swap_used_bytes)} of ${bytes(mem.swap_total_bytes)}`}
            />
            <Gauge
              title="Disk space"
              icon="download"
              value={worstDisk?.used_pct}
              limit={th.disk_pct}
              sub={worstDisk ? `${bytes(worstDisk.free_bytes)} free of ${bytes(worstDisk.total_bytes)}` : 'n/a'}
              foot={worstDisk ? `${worstDisk.label} · alert at ${th.disk_pct}%` : undefined}
            />
          </div>

          <div className="mon-grid-4">
            <Kpi title="Response time (p95)" icon="clock" field="p95" points={recent}
              value={perf.requests ? ms(perf.p95_ms) : '—'}
              note={perf.requests ? `median ${ms(perf.p50_ms)} · p99 ${ms(perf.p99_ms)}` : 'No requests in 15 min'}
              tone={levelTone(perf.p95_ms, th.p95_ms, 0.5)} />
            <Kpi title="Requests per minute" icon="arrow" field="rpm" points={recent}
              value={perf.requests_per_minute != null ? String(perf.requests_per_minute) : '—'}
              note={`${perf.requests || 0} in the last 15 min`} />
            <Kpi title="Server errors" icon="alert" field="err" points={recent}
              value={perf.requests ? pct(perf.error_rate_pct) : '—'}
              note={`${perf.server_errors || 0} errors · ${perf.client_errors || 0} refused`}
              tone={levelTone(perf.error_rate_pct, th.error_rate_pct, 0.4)} />
            <Kpi title="Database reply" icon="wallet" field="db" points={recent}
              value={ms(db.latency_ms)}
              note={db.size_bytes != null ? `${bytes(db.size_bytes)} stored` : db.engine || ''}
              tone={levelTone(db.latency_ms, th.db_latency_ms, 0.5)} />
          </div>

          <section className="mon-section">
            <div className="mon-section-head">
              <h2>Health checks</h2>
              <span className="mon-muted">
                {checks.length - problems.length} of {checks.length} passing
              </span>
            </div>
            <div className="mon-checks">
              {checks.map((c) => (
                <div key={c.key} className={`mon-check is-${TONE[c.status]}`}>
                  <span className="mon-check-ico" aria-hidden="true">
                    <DeskIcon name={CHECK_ICON[c.key.split(':')[0]] || (c.key.startsWith('desk_db') ? 'wallet' : 'check')} size={16} />
                  </span>
                  <div className="mon-check-body">
                    <span className="mon-check-label">{c.label}</span>
                    <strong>{c.value}</strong>
                    {c.detail ? <span className="mon-check-detail">{c.detail}</span> : null}
                  </div>
                  <span className={`mon-dotlabel is-${TONE[c.status]}`}>{STATUS_WORD[c.status] || c.status}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="mon-section">
            <div className="mon-section-head">
              <h2>Services</h2>
            </div>
            <div className="mon-grid-3">
              <Service
                icon="wallet"
                title="Main database"
                tone={db.status === 'ok' ? 'ok' : 'bad'}
                value={db.status === 'ok' ? ms(db.latency_ms) : 'Down'}
                rows={[
                  ['Engine', db.engine || '—'],
                  ['Size', bytes(db.size_bytes)],
                  ['Connections', db.connections != null ? (
                    <span className="mon-inline-bar">
                      {db.connections}/{db.max_connections}
                      <Bar value={db.connections_pct} limit={80} label="Connections used" />
                    </span>
                  ) : '—'],
                  ['Running / slow', db.active_queries != null ? `${db.active_queries} / ${db.slow_queries}` : '—'],
                  ...((live.desk_databases || []) as any[]).map((d): [string, ReactNode] => [`${d.desk} desk`, d.status === 'ok' ? ms(d.latency_ms) : 'down']),
                ]}
              />
              <Service
                icon="flame"
                title="Redis"
                tone={live.redis?.status === 'ok' ? 'ok' : live.redis?.status === 'skipped' ? 'none' : 'bad'}
                value={live.redis?.status === 'ok' ? ms(live.redis.latency_ms) : live.redis?.status === 'skipped' ? 'Not set up' : 'Down'}
                rows={[
                  ['Version', live.redis?.version || '—'],
                  ['Memory', bytes(live.redis?.used_memory_bytes)],
                  ['Clients', live.redis?.clients ?? '—'],
                  ['Up', duration(live.redis?.uptime_seconds)],
                ]}
              />
              <Service
                icon="users"
                title="Background workers"
                tone={live.workers?.status === 'ok' ? 'ok' : live.workers?.status === 'skipped' ? 'none' : 'bad'}
                value={
                  live.workers?.status === 'skipped'
                    ? 'Switched off'
                    : live.workers?.mode === 'eager'
                      ? 'In the API'
                      : live.workers?.status === 'ok'
                        ? `${live.workers.workers} running`
                        : 'Not answering'
                }
                rows={[
                  ['Last scheduled run', when(live.workers?.last_scheduled_run_at)],
                  ['Scheduler', live.workers?.scheduled_jobs_stale ? 'not seen recently' : 'on time'],
                ]}
              />
              <Service
                icon="download"
                title="Backups"
                tone={live.backups?.age_hours == null ? 'warn' : live.backups.age_hours > th.backup_max_age_hours ? 'bad' : live.backups.failed_last_24h ? 'warn' : 'ok'}
                value={live.backups?.age_hours != null ? `${Math.round(live.backups.age_hours)} h ago` : 'None yet'}
                rows={[
                  ['Last finished', when(live.backups?.last_success_at)],
                  ['Failed in 24 h', live.backups?.failed_last_24h ?? 0],
                  ['Companies scheduled', live.backups?.companies_scheduled ?? 0],
                ]}
              />
              <Service
                icon="home"
                title="Website & certificate"
                tone={live.web?.status === 'ok' ? (live.tls?.status === 'ok' && live.tls.days_left <= th.cert_days ? 'warn' : 'ok') : live.web?.status === 'skipped' ? 'none' : 'bad'}
                value={live.web?.status === 'ok' ? ms(live.web.latency_ms) : live.web?.status === 'skipped' ? 'Not checked' : 'Unreachable'}
                rows={[
                  ['Address', live.web?.url || '—'],
                  ['HTTP', live.web?.http_status ?? '—'],
                  ['Certificate', live.tls?.status === 'ok' ? `${live.tls.days_left} days left` : live.tls?.status === 'skipped' ? 'not https' : 'cannot read'],
                  ['Issuer', live.tls?.issuer || '—'],
                ]}
              />
              <Service
                icon="chart"
                title="API process"
                tone="ok"
                value={`up ${duration(live.process?.uptime_seconds)}`}
                rows={[
                  ['Memory', bytes(live.process?.rss_bytes)],
                  ['Threads', live.process?.threads ?? '—'],
                  ['Open files', live.process?.open_files ?? '—'],
                  ['Python', live.process?.python || '—'],
                ]}
              />
            </div>
          </section>

          <div className="mon-grid-2">
            <section className="mon-card">
              <div className="mon-section-head">
                <h2>Disks</h2>
              </div>
              {disks.map((d) => (
                <div key={d.label} className="mon-disk">
                  <div className="mon-disk-head">
                    <span>{d.label}</span>
                    <span className="mon-muted">
                      {pct(d.used_pct)} · {bytes(d.free_bytes)} free
                    </span>
                  </div>
                  <Bar value={d.used_pct} limit={th.disk_pct} label={`${d.label} used`} />
                </div>
              ))}
            </section>
            <section className="mon-card">
              <div className="mon-section-head">
                <h2>Slowest areas</h2>
                <span className="mon-muted">p95, last 15 min, this API worker</span>
              </div>
              {perf.slowest?.length ? (
                <ul className="mon-slow">
                  {perf.slowest.map((row: any) => (
                    <li key={row.path_group}>
                      <div className="mon-slow-head">
                        <code>{row.path_group.replace('/api/v1/', '/')}</code>
                        <span>
                          <strong>{ms(row.p95_ms)}</strong>
                          <span className="mon-muted"> · {row.requests} req{row.errors ? ` · ${row.errors} err` : ''}</span>
                        </span>
                      </div>
                      <span className="mon-slow-bar">
                        <span style={{ width: `${(row.p95_ms / maxSlow) * 100}%` }} />
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mon-empty">No requests yet in this window.</p>
              )}
            </section>
          </div>
        </>
      ) : null}

      {/* --------------------------------------------------------- history */}
      {tab === 'history' ? (
        <>
          <section className="mon-card">
            <div className="mon-section-head mon-history-head">
              <div>
                <h2>Health timeline</h2>
                <span className="mon-muted">
                  Healthy {history?.uptime?.healthy_pct != null ? `${history.uptime.healthy_pct}%` : '—'} of {history?.uptime?.samples || 0} readings
                </span>
              </div>
              <div className="mon-seg is-small" role="group" aria-label="History range">
                {(['1h', '6h', '24h', '7d'] as const).map((r) => (
                  <button key={r} type="button" className={range === r ? 'is-on' : undefined} aria-pressed={range === r} onClick={() => setRange(r)}>
                    {r === '7d' ? '7 days' : r}
                  </button>
                ))}
              </div>
              <button type="button" className="mon-ghost" aria-label="Show history as a table" aria-pressed={showTable} onClick={() => setShowTable((v) => !v)}>
                {showTable ? 'Show charts' : 'Show table'}
              </button>
            </div>
            <HealthStrip points={points} />
            <div className="mon-legend">
              <span><i className="is-ok" /> Healthy</span>
              <span><i className="is-warn" /> Needs a look</span>
              <span><i className="is-bad" /> Problem</span>
            </div>
          </section>
          {showTable ? (
            <section className="mon-card mon-table-card">
              <div className="mon-table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>State</th>
                      <th className="col-right">CPU</th>
                      <th className="col-right">Memory</th>
                      <th className="col-right">Disk</th>
                      <th className="col-right">p95</th>
                      <th className="col-right">Database</th>
                      <th className="col-right">Req/min</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...points].reverse().map((p) => (
                      <tr key={p.t}>
                        <td>{when(p.t)}</td>
                        <td>
                          <Tag tone={TONE[p.s]}>{STATUS_WORD[p.s] || p.s}</Tag>
                        </td>
                        <td className="col-right">{pct(p.cpu)}</td>
                        <td className="col-right">{pct(p.mem)}</td>
                        <td className="col-right">{pct(p.disk)}</td>
                        <td className="col-right">{ms(p.p95)}</td>
                        <td className="col-right">{ms(p.db)}</td>
                        <td className="col-right">{p.rpm ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : (
            <div className="mon-grid-2">
              <AreaChart title="Processor" points={points} field="cpu" format={(v) => `${v.toFixed(0)}%`} limit={th.cpu_pct} max={100} />
              <AreaChart title="Memory" points={points} field="mem" format={(v) => `${v.toFixed(0)}%`} limit={th.memory_pct} max={100} />
              <AreaChart title="Response time (p95)" points={points} field="p95" format={(v) => `${v.toFixed(0)} ms`} limit={th.p95_ms} />
              <AreaChart title="Database reply" points={points} field="db" format={(v) => `${v.toFixed(0)} ms`} limit={th.db_latency_ms} />
              <AreaChart title="Requests per minute" points={points} field="rpm" format={(v) => v.toFixed(v < 10 ? 1 : 0)} />
              <AreaChart title="Disk used" points={points} field="disk" format={(v) => `${v.toFixed(0)}%`} limit={th.disk_pct} max={100} />
            </div>
          )}
        </>
      ) : null}

      {/* ---------------------------------------------------------- alerts */}
      {tab === 'alerts' ? (
        <div className="mon-grid-side">
          <section className="mon-card">
            <div className="mon-section-head">
              <h2>Alert history</h2>
            </div>
            {alerts?.events?.length ? (
              <ol className="mon-timeline">
                {alerts.events.map((e: any, i: number) => {
                  const tone: Tone = e.kind === 'alert' ? 'bad' : e.kind === 'recovered' ? 'ok' : 'none';
                  return (
                    <li key={`${e.at}-${e.key}-${i}`} className={`is-${tone}`}>
                      <span className="mon-timeline-dot" aria-hidden="true" />
                      <div>
                        <div className="mon-timeline-head">
                          <strong>{e.label}</strong>
                          <span className={`mon-pill is-${tone}`}>{e.kind === 'alert' ? 'Alert' : e.kind === 'recovered' ? 'Recovered' : 'Test'}</span>
                        </div>
                        <span className="mon-muted">
                          {when(e.at)} · {e.value}
                          {e.detail ? ` · ${e.detail}` : ''}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ol>
            ) : (
              <div className="mon-empty-state">
                <DeskIcon name="check" size={26} />
                <p>No alerts recorded yet.</p>
              </div>
            )}
          </section>
          <aside className="mon-stack">
            <section className={`mon-card mon-now ${Object.keys(alerts?.active || {}).length ? 'is-bad' : 'is-ok'}`}>
              <h2>Failing now</h2>
              {Object.keys(alerts?.active || {}).length ? (
                <ul>
                  {Object.entries(alerts.active).map(([key, info]: [string, any]) => (
                    <li key={key}>
                      <span className="mon-dotlabel is-bad">{info.label}</span>
                      <span className="mon-muted">since {when(info.since)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mon-now-ok">
                  <DeskIcon name="check" size={18} /> Nothing is failing.
                </p>
              )}
            </section>
            <section className="mon-card">
              <h2 className="mon-h2">How alerts reach you</h2>
              <p className="mon-muted mon-p">
                Platform staff get an in-app note and an email (each person can change this under Notifications). An alert repeats at most every{' '}
                {th.cooldown_minutes} minutes, and a recovered note follows.
              </p>
              <ul className="mon-limits">
                <li><span>Processor</span><strong>{th.cpu_pct}%</strong></li>
                <li><span>Memory</span><strong>{th.memory_pct}%</strong></li>
                <li><span>Disk</span><strong>{th.disk_pct}%</strong></li>
                <li><span>Database</span><strong>{th.db_latency_ms} ms</strong></li>
                <li><span>Response p95</span><strong>{th.p95_ms} ms</strong></li>
                <li><span>Server errors</span><strong>{th.error_rate_pct}%</strong></li>
                <li><span>Backup age</span><strong>{th.backup_max_age_hours} h</strong></li>
                <li><span>Certificate</span><strong>{th.cert_days} days</strong></li>
              </ul>
              <p className="mon-muted mon-p">
                Change limits with the <code>MONITOR_*</code> server settings.
              </p>
              {ALERT_ROLES.includes(role) ? (
                <button type="button" className="btn-primary mon-full" aria-label="Send a test server alert" disabled={busy} onClick={testAlert}>
                  {busy ? 'Sending…' : 'Send test alert'}
                </button>
              ) : null}
            </section>
          </aside>
        </div>
      ) : null}

      {/* ---------------------------------------------------------- launch */}
      {tab === 'launch' ? (
        !launch ? (
          <section className="mon-card">
            <p className="mon-empty">Checking…</p>
          </section>
        ) : (
          <>
            <section className={`mon-card mon-score ${launch.ready ? 'is-ok' : 'is-bad'}`}>
              <Ring value={launchScore} size={116} stroke={11} tone={launch.ready ? 'ok' : launch.counts.fail > 3 ? 'bad' : 'warn'} label={`Launch readiness ${launchScore} percent`}>
                <strong>{launchScore}%</strong>
                <span>ready</span>
              </Ring>
              <div className="mon-score-body">
                <h2>{launch.ready ? 'Ready to take paying customers' : 'Not ready for paying customers yet'}</h2>
                <p className="mon-muted">
                  Fix the red items first; amber ones are strongly recommended. Each item says how to fix it.
                </p>
                <div className="mon-score-counts">
                  <span className="mon-pill is-ok">{launch.counts.pass} passed</span>
                  <span className="mon-pill is-warn">{launch.counts.warn} to improve</span>
                  <span className="mon-pill is-bad">{launch.counts.fail} to fix</span>
                </div>
              </div>
              <button type="button" className="mon-ghost" aria-label="Run launch checks again" onClick={loadLaunch}>
                Check again
              </button>
            </section>
            <div className="mon-grid-2">
              {launchGroups.map(([area, items]) => (
                <section key={area} className="mon-card">
                  <div className="mon-section-head">
                    <h2>{area}</h2>
                    <span className="mon-muted">
                      {items.filter((i: any) => i.status === 'pass').length}/{items.length}
                    </span>
                  </div>
                  <ul className="mon-launch">
                    {items.map((item: any) => {
                      const tone: Tone = item.status === 'pass' ? 'ok' : item.status === 'warn' ? 'warn' : 'bad';
                      return (
                        <li key={item.key} className={`is-${tone}`}>
                          <span className="mon-launch-mark" aria-hidden="true">
                            {tone === 'ok' ? '✓' : tone === 'warn' ? '!' : '×'}
                          </span>
                          <div>
                            <strong>{item.label}</strong>
                            {item.fix ? <p>{item.fix}</p> : null}
                          </div>
                          <span className={`mon-pill is-${tone}`}>{tone === 'ok' ? 'Pass' : tone === 'warn' ? 'Improve' : 'Fix'}</span>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              ))}
            </div>
          </>
        )
      ) : null}
    </div>
  );
}
