'use client';

/** Lightweight SVG charts for platform/tenant dashboards (no hard-coded business values). */

type Slice = { label: string; value: number };
type SeriesPoint = { label: string; value: number };

const PALETTE = ['#0f766e', '#0369a1', '#b45309', '#7c3aed', '#be123c', '#15803d', '#475569'];

function maxOf(values: number[]): number {
  return Math.max(1, ...values.map((v) => Number(v) || 0));
}

export function BarChart({
  title,
  series,
  emptyLabel = 'No data yet',
}: {
  title: string;
  series: SeriesPoint[];
  emptyLabel?: string;
}) {
  const width = 560;
  const height = 180;
  const pad = { top: 16, right: 12, bottom: 36, left: 40 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const points = series || [];
  const maxY = maxOf(points.map((p) => p.value));
  const barW = points.length ? innerW / points.length : innerW;

  return (
    <div>
      <h3 style={{ margin: '0 0 8px' }}>{title}</h3>
      {points.length === 0 ? (
        <p className="muted">{emptyLabel}</p>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title} style={{ width: '100%', height: 'auto' }}>
          <line x1={pad.left} y1={pad.top + innerH} x2={pad.left + innerW} y2={pad.top + innerH} stroke="#d6d3d1" />
          {points.map((p, i) => {
            const h = (Number(p.value) / maxY) * innerH;
            const x = pad.left + i * barW + barW * 0.15;
            const y = pad.top + innerH - h;
            return (
              <g key={`${p.label}-${i}`}>
                <rect x={x} y={y} width={barW * 0.7} height={h} fill={PALETTE[i % PALETTE.length]}>
                  <title>
                    {p.label}: {p.value}
                  </title>
                </rect>
                {(i === 0 || i === points.length - 1 || i === Math.floor(points.length / 2)) && (
                  <text x={x + barW * 0.35} y={height - 10} fontSize="10" fill="#57534e" textAnchor="middle">
                    {p.label.length > 7 ? p.label.slice(2) : p.label}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

export function DonutChart({
  title,
  slices,
  emptyLabel = 'No data yet',
}: {
  title: string;
  slices: Slice[];
  emptyLabel?: string;
}) {
  const data = (slices || []).filter((s) => Number(s.value) > 0);
  const total = data.reduce((s, x) => s + Number(x.value || 0), 0);
  const cx = 90;
  const cy = 90;
  const r = 70;
  const ir = 42;
  let angle = -Math.PI / 2;

  function arc(start: number, end: number, outer: number, inner: number) {
    const x1 = cx + Math.cos(start) * outer;
    const y1 = cy + Math.sin(start) * outer;
    const x2 = cx + Math.cos(end) * outer;
    const y2 = cy + Math.sin(end) * outer;
    const x3 = cx + Math.cos(end) * inner;
    const y3 = cy + Math.sin(end) * inner;
    const x4 = cx + Math.cos(start) * inner;
    const y4 = cy + Math.sin(start) * inner;
    const large = end - start > Math.PI ? 1 : 0;
    return `M ${x1} ${y1} A ${outer} ${outer} 0 ${large} 1 ${x2} ${y2} L ${x3} ${y3} A ${inner} ${inner} 0 ${large} 0 ${x4} ${y4} Z`;
  }

  return (
    <div>
      <h3 style={{ margin: '0 0 8px' }}>{title}</h3>
      {total <= 0 ? (
        <p className="muted">{emptyLabel}</p>
      ) : (
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <svg viewBox="0 0 180 180" width={160} height={160} role="img" aria-label={title}>
            {data.map((s, i) => {
              const sweep = (Number(s.value) / total) * Math.PI * 2;
              const start = angle;
              const end = angle + sweep;
              angle = end;
              return (
                <path key={s.label} d={arc(start, end, r, ir)} fill={PALETTE[i % PALETTE.length]}>
                  <title>
                    {s.label}: {s.value}
                  </title>
                </path>
              );
            })}
            <text x={cx} y={cy + 4} textAnchor="middle" fontSize="14" fill="#1c1917">
              {total}
            </text>
          </svg>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {data.map((s, i) => (
              <li key={s.label} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: PALETTE[i % PALETTE.length],
                    display: 'inline-block',
                  }}
                />
                <span>
                  {s.label}: {s.value}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
