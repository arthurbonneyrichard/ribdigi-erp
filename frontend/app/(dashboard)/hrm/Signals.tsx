'use client';

/** People signals: plain rules over HR records (no AI model). A reason to talk, not a judgement. */

import Link from 'next/link';
import React, { useEffect, useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;

export default function Signals() {
  const [rows, setRows] = useState<Row[] | null>(null);
  useEffect(() => {
    api('/hrm/insights').then((r) => setRows(r?.data || [])).catch(() => setRows([]));
  }, []);
  if (!rows) return null;
  return (
    <section className="hr-box hr-scroll" aria-label="People signals">
      <div className="hr-cardhead"><h2>People signals</h2></div>
      <p className="hr-muted">
        Worked out from leave, the clock, reviews and policies with simple rules. Each is a reason for a conversation, not a judgement.
      </p>
      {rows.length === 0 ? <p className="hr-muted">Nothing stands out right now.</p> : (
        <table>
          <thead><tr><th>Who</th><th>What</th><th>Why it shows</th><th /></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={`${r.employee_id}-${r.kind}-${i}`}>
                <td>{r.name}</td><td>{r.title}</td><td>{r.why}</td>
                <td><Link href={r.link}>Open</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
