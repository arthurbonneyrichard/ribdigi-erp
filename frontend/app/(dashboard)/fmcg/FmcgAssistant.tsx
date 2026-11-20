'use client';

/**
 * FMCG assistant. Ask a question about sales, stock, money or deliveries and get an answer worked
 * out from your own records, with where it came from. It only reads. Forecast answers are marked
 * as estimates. It is not a chat with a language model, so it only answers the questions listed.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const ASSISTANT_TABS = ['assistant'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin'];
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const label = (k: string) => k.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

export default function FmcgAssistant({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [question, setQuestion] = useState('');
  const [examples, setExamples] = useState<string[]>([]);
  const [thread, setThread] = useState<Row[]>([]);
  const end = useRef<HTMLDivElement | null>(null);
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  useEffect(() => {
    if (manager) api('/fmcg/assistant/examples').then((r: Row) => setExamples(r?.data || [])).catch(() => setExamples([]));
  }, [manager]);

  useEffect(() => {
    end.current?.scrollIntoView?.({ block: 'nearest' });
  }, [thread]);

  const ask = useCallback(async (q: string) => {
    const text = q.trim();
    if (text.length < 3) return;
    setBusy(true);
    setError('');
    try {
      const res = await api('/fmcg/assistant/ask', { method: 'POST', body: JSON.stringify({ question: text }) });
      setThread((t) => [...t, res?.data]);
      setQuestion('');
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }, []);

  if (role && !manager) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">The assistant is for managers.</div>
      </div>
    );
  }

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <section className="fs-box" aria-label="Ask a question">
        <form onSubmit={(e) => { e.preventDefault(); ask(question); }} className="fs-form">
          <label><span>Your question</span>
            <input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={300} aria-label="Assistant question" placeholder="For example: What were my total sales today?" />
          </label>
          <button type="submit" className="fs-primary" disabled={busy || question.trim().length < 3}>Ask</button>
        </form>
        <p className="fs-muted">It reads your own records and never changes anything. Forecast answers are estimates, not sales. It can only answer the questions below.</p>
        <p>{examples.map((e) => <button key={e} type="button" disabled={busy} onClick={() => ask(e)} aria-label={`Ask: ${e}`}>{e}</button>)}</p>
      </section>

      {thread.map((a, i) => (
        <section className="fs-box fs-scroll" key={i} aria-label="Answer">
          <p className="fs-muted">You asked: {a.question}</p>
          <p><strong>{a.answer}</strong></p>
          {a.kind === 'estimate' ? <p><span className="fs-flag">Estimate</span> Worked out from past deliveries, not actual sales.</p> : null}
          {a.examples ? <ul>{a.examples.map((e: string) => <li key={e}>{e}</li>)}</ul> : null}
          {a.table && a.table.rows.length ? (
            <table>
              <thead><tr>{a.table.columns.map((c: string) => <th key={c}>{label(c)}</th>)}</tr></thead>
              <tbody>{a.table.rows.map((r: Row, j: number) => <tr key={j}>{a.table.columns.map((c: string) => <td key={c} className={typeof r[c] === 'number' ? 'fs-num' : ''}>{r[c] == null ? '-' : String(r[c])}</td>)}</tr>)}</tbody>
            </table>
          ) : null}
          {a.source ? <p className="fs-muted">Source: {a.source}{a.period ? ` · ${a.period.start} to ${a.period.end}` : ''}{a.link ? <> · <a href={a.link}>Open the screen</a></> : null}</p> : null}
        </section>
      ))}
      <div ref={end} />
    </div>
  );
}
