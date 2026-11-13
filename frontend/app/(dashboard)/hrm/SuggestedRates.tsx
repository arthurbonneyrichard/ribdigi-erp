'use client';

/** Published Ghana PAYE / SSNIT / minimum-wage figures to check and add as dated rows. */

import React, { useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function SuggestedRates({ have, onAdded }: { have: string[]; onAdded: () => void }) {
  const [data, setData] = useState<Row | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  async function open() {
    setError('');
    try {
      setData((await api('/hrm/statutory-rates/suggested'))?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }

  async function add(row: Row) {
    setBusy(row.effective_from);
    setError('');
    try {
      await api('/hrm/statutory-rates', { method: 'POST', body: JSON.stringify(row) });
      onAdded();
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy('');
    }
  }

  if (!data) {
    return (
      <div className="hr-row">
        <button type="button" onClick={() => void open()}>Show suggested Ghana rates</button>
        {error ? <span className="hr-bad">{error}</span> : null}
      </div>
    );
  }
  return (
    <div>
      <p className="hr-muted">{data.note} Checked on {data.checked_on}. Sources: {(data.sources || []).map((s: string, i: number) => <React.Fragment key={s}>{i ? ', ' : ''}<a href={s} target="_blank" rel="noreferrer">{new URL(s).hostname}</a></React.Fragment>)}.</p>
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      <table aria-label="Suggested Ghana rates">
        <thead><tr><th>From</th><th>First PAYE band</th><th>SSNIT cap</th><th>Tier 2</th><th>Minimum wage a day</th><th>What changed</th><th /></tr></thead>
        <tbody>
          {data.rows.map((r: Row) => (
            <tr key={r.effective_from}>
              <td>{r.effective_from}</td><td className="hr-num">{r.paye_bands[0].width} at 0%</td><td className="hr-num">{r.insurable_cap}</td>
              <td>{r.tier2_percent}%</td><td className="hr-num">{r.minimum_daily_wage}</td><td>{r.source_note}</td>
              <td>
                {have.includes(r.effective_from) ? <span className="hr-muted">Added</span> : (
                  <button type="button" className="hr-primary" disabled={Boolean(busy)} aria-label={`Add rates from ${r.effective_from}`} onClick={() => void add(r)}>
                    {busy === r.effective_from ? 'Adding…' : 'Add'}
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
