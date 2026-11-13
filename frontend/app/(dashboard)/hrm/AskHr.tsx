'use client';

/** Ask HR: plain-language questions answered from the HR records by rules (no AI model). */

import Link from 'next/link';
import React, { useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function AskHr({ examples }: { examples: string[] }) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [reply, setReply] = useState<Row | null>(null);
  const [error, setError] = useState('');

  async function ask(question: string) {
    setBusy(true);
    setError('');
    try {
      setReply((await api('/hrm/assistant', { method: 'POST', body: JSON.stringify({ question }) }))?.data || null);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="hr-box" aria-label="Ask HR">
      <div className="hr-cardhead"><h2>Ask HR</h2></div>
      <div className="hr-row">
        <input
          placeholder="e.g. How many leave days do I have?" value={q} maxLength={500} style={{ flex: '1 1 260px' }}
          onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && q.trim().length > 1) void ask(q.trim()); }}
          aria-label="Question for HR"
        />
        <button type="button" className="hr-primary" disabled={busy || q.trim().length < 2} onClick={() => void ask(q.trim())}>Ask</button>
      </div>
      <div className="hr-row">
        {examples.map((x) => <button key={x} type="button" disabled={busy} onClick={() => { setQ(x); void ask(x); }}>{x}</button>)}
      </div>
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      {reply ? (
        <p role="status">
          {reply.answer} {reply.link ? <Link href={reply.link}>Open</Link> : null}
        </p>
      ) : null}
      <p className="hr-muted">Answers come straight from the HR records. Pay amounts are only on your payslip.</p>
    </section>
  );
}
