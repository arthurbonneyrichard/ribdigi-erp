'use client';

import { useState } from 'react';

type DayPoint = { date: string; value: number };

/** One measure by day. A second measure gets its own chart, never a second axis. */
export function DayBars({
  title,
  summary,
  points,
  format,
  dateLabel,
}: {
  title: string;
  summary: string;
  points: DayPoint[];
  format: (value: number) => string;
  dateLabel: (date: string) => string;
}) {
  const [at, setAt] = useState<number | null>(null);
  const top = Math.max(0, ...points.map((p) => p.value)) || 1;
  const shown = at === null ? null : points[at];
  const ticks = points.length > 1 ? [points[0], points[Math.floor((points.length - 1) / 2)], points[points.length - 1]] : points;
  return (
    <figure className="hchart">
      <figcaption>
        <b>{title}</b>
        <span aria-live="polite">{shown ? `${dateLabel(shown.date)}: ${format(shown.value)}` : summary}</span>
      </figcaption>
      <div className="hchart-frame">
        <span className="hchart-top">{format(top)}</span>
        <div className="hchart-plot" role="img" aria-label={`${title}. ${summary}`} onMouseLeave={() => setAt(null)}>
          {points.map((p, i) => (
            <span key={p.date} className={at === i ? 'hchart-col is-on' : 'hchart-col'} onMouseEnter={() => setAt(i)} onClick={() => setAt(i)}>
              <i style={{ height: p.value > 0 ? `${Math.max(2, (p.value / top) * 100)}%` : 0 }} />
            </span>
          ))}
        </div>
      </div>
      <div className="hchart-ticks" aria-hidden="true">
        {ticks.map((p) => (
          <span key={p.date}>{dateLabel(p.date)}</span>
        ))}
      </div>
    </figure>
  );
}

/** Biggest first, with the value written beside each bar. */
export function RankBars({ rows, format }: { rows: { label: string; value: number; note?: string }[]; format: (value: number) => string }) {
  const top = Math.max(0, ...rows.map((r) => r.value)) || 1;
  return (
    <ul className="hrank">
      {rows.map((r) => (
        <li key={r.label}>
          <span className="hrank-label">{r.label}</span>
          <span className="hrank-track" aria-hidden="true">
            <i style={{ width: r.value > 0 ? `${Math.max(1, (r.value / top) * 100)}%` : 0 }} />
          </span>
          <span className="hrank-value">
            {format(r.value)}
            {r.note ? <small>{r.note}</small> : null}
          </span>
        </li>
      ))}
    </ul>
  );
}
