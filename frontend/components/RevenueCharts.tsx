'use client';

type DailyPoint = { date: string; revenue: number };
type MonthlyPoint = { month: string; revenue: number };

function maxRevenue(values: number[]): number {
  return Math.max(1, ...values.map((v) => Number(v) || 0));
}

export function DailyRevenueLineChart({
  series,
  formatValue,
}: {
  series: DailyPoint[];
  formatValue: (n: number) => string;
}) {
  const width = 560;
  const height = 180;
  const pad = { top: 16, right: 12, bottom: 28, left: 44 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const points = series.length ? series : [];
  const maxY = maxRevenue(points.map((p) => p.revenue));
  const coords = points.map((p, i) => {
    const x = pad.left + (points.length <= 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
    const y = pad.top + innerH - (Number(p.revenue) / maxY) * innerH;
    return { x, y, ...p };
  });
  const path = coords.map((c, i) => `${i === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(' ');
  const mid = coords[Math.floor(coords.length / 2)];
  const last = coords[coords.length - 1];
  const total = points.reduce((s, p) => s + (Number(p.revenue) || 0), 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Daily revenue (30 days)</h3>
        <span className="muted">Σ {formatValue(total)}</span>
      </div>
      {points.length === 0 ? (
        <p className="muted">No revenue in the last 30 days</p>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Daily revenue line chart" style={{ width: '100%', height: 'auto' }}>
          <line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + innerH} stroke="#d6d3d1" />
          <line x1={pad.left} y1={pad.top + innerH} x2={pad.left + innerW} y2={pad.top + innerH} stroke="#d6d3d1" />
          <text x={4} y={pad.top + 4} className="muted" fontSize="10" fill="#57534e">
            {formatValue(maxY)}
          </text>
          {path && <path d={path} fill="none" stroke="#0f766e" strokeWidth="2" />}
          {coords.map((c) => (
            <circle key={c.date} cx={c.x} cy={c.y} r="2.5" fill="#0f766e">
              <title>
                {c.date}: {formatValue(c.revenue)}
              </title>
            </circle>
          ))}
          {coords[0] && (
            <text x={coords[0].x} y={height - 8} fontSize="10" fill="#57534e" textAnchor="start">
              {coords[0].date.slice(5)}
            </text>
          )}
          {mid && (
            <text x={mid.x} y={height - 8} fontSize="10" fill="#57534e" textAnchor="middle">
              {mid.date.slice(5)}
            </text>
          )}
          {last && (
            <text x={last.x} y={height - 8} fontSize="10" fill="#57534e" textAnchor="end">
              {last.date.slice(5)}
            </text>
          )}
        </svg>
      )}
    </div>
  );
}

export function MonthlyRevenueBarChart({
  series,
  formatValue,
}: {
  series: MonthlyPoint[];
  formatValue: (n: number) => string;
}) {
  const width = 560;
  const height = 180;
  const pad = { top: 16, right: 12, bottom: 28, left: 44 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const points = series.length ? series : [];
  const maxY = maxRevenue(points.map((p) => p.revenue));
  const gap = 4;
  const barW = points.length ? Math.max(4, (innerW - gap * (points.length - 1)) / points.length) : 0;
  const total = points.reduce((s, p) => s + (Number(p.revenue) || 0), 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 8 }}>
        <h3 style={{ margin: 0 }}>Monthly revenue (12 months)</h3>
        <span className="muted">Σ {formatValue(total)}</span>
      </div>
      {points.length === 0 ? (
        <p className="muted">No monthly revenue yet</p>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Monthly revenue bar chart" style={{ width: '100%', height: 'auto' }}>
          <line x1={pad.left} y1={pad.top} x2={pad.left} y2={pad.top + innerH} stroke="#d6d3d1" />
          <line x1={pad.left} y1={pad.top + innerH} x2={pad.left + innerW} y2={pad.top + innerH} stroke="#d6d3d1" />
          <text x={4} y={pad.top + 4} fontSize="10" fill="#57534e">
            {formatValue(maxY)}
          </text>
          {points.map((p, i) => {
            const h = (Number(p.revenue) / maxY) * innerH;
            const x = pad.left + i * (barW + gap);
            const y = pad.top + innerH - h;
            return (
              <g key={p.month}>
                <rect x={x} y={y} width={barW} height={Math.max(h, 0)} fill="#0f766e" opacity={0.85}>
                  <title>
                    {p.month}: {formatValue(p.revenue)}
                  </title>
                </rect>
                {(i === 0 || i === points.length - 1 || i === Math.floor(points.length / 2)) && (
                  <text x={x + barW / 2} y={height - 8} fontSize="10" fill="#57534e" textAnchor="middle">
                    {p.month.slice(2)}
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
