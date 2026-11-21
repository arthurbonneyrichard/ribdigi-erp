'use client';

/** RFID card readers and staff cards. A reader's token is shown once, when it is added. */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function Rfid({ canAddReader }: { canAddReader: boolean }) {
  const [people, setPeople] = useState<Row[]>([]);
  const [readers, setReaders] = useState<Row[]>([]);
  const [cards, setCards] = useState<Row[]>([]);
  const [f, setF] = useState<Record<string, string>>({});
  const [token, setToken] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setReaders((await api('/hrm/rfid/readers'))?.data || []);
      setCards((await api('/hrm/rfid/cards'))?.data || []);
      setPeople((await api('/hrm/employees'))?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function post(path: string, body: object | null, after?: (r: Row) => void) {
    setError('');
    try {
      const res = await api(path, { method: 'POST', body: JSON.stringify(body || {}) });
      after?.(res?.data || {});
      await load();
    } catch (err) {
      setError(problem(err));
    }
  }

  return (
    <section className="hr-box hr-scroll" aria-label="Card readers">
      <div className="hr-cardhead"><h2>Card readers and staff cards</h2></div>
      {error ? <p className="hr-bad" role="alert">{error}</p> : null}
      {token ? (
        <p role="status" className="hr-ok">
          Reader token (copy it now, it is not shown again): <code>{token}</code>. The reader sends each tap to <code>POST /api/v1/hrm/rfid/punch</code> with header <code>X-Reader-Token</code> and body <code>{'{"card_uid":"…","ref":"unique tap id"}'}</code>.
        </p>
      ) : null}
      <table>
        <thead><tr><th>Reader</th><th>Last heard</th><th>Status</th><th /></tr></thead>
        <tbody>
          {readers.map((r) => (
            <tr key={r.id}>
              <td>{r.name}</td><td>{r.last_seen_at ? r.last_seen_at.replace('T', ' ').slice(0, 16) : 'never'}</td><td>{r.active ? 'On' : 'Off'}</td>
              <td>{r.active && canAddReader ? <button type="button" className="btn-danger" aria-label={`Switch off reader ${r.name}`} onClick={() => void post(`/hrm/rfid/readers/${r.id}/off`, null)}>Switch off</button> : null}</td>
            </tr>
          ))}
          {readers.length === 0 ? <tr><td colSpan={4} className="hr-muted">No readers added.</td></tr> : null}
        </tbody>
      </table>
      {canAddReader ? (
        <div className="hr-row">
          <input placeholder="Reader name, e.g. Front door" aria-label="Reader name" value={f.rname || ''} onChange={(e) => setF({ ...f, rname: e.target.value })} />
          <button type="button" disabled={(f.rname || '').trim().length < 2}
            onClick={() => void post('/hrm/rfid/readers', { name: f.rname.trim() }, (r) => { setToken(r.token || ''); setF({ ...f, rname: '' }); })}>Add reader</button>
        </div>
      ) : null}
      <table>
        <thead><tr><th>Person</th><th>Card number</th></tr></thead>
        <tbody>
          {cards.map((c) => <tr key={c.employee_id}><td>{c.name}</td><td>{c.card_uid}</td></tr>)}
          {cards.length === 0 ? <tr><td colSpan={2} className="hr-muted">No cards issued.</td></tr> : null}
        </tbody>
      </table>
      <div className="hr-row">
        <select aria-label="Card holder" value={f.person || ''} onChange={(e) => setF({ ...f, person: e.target.value })}>
          <option value="">Choose a person…</option>
          {people.filter((p) => p.status === 'active').map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
        </select>
        <input placeholder="Card number" aria-label="Card number" value={f.uid || ''} onChange={(e) => setF({ ...f, uid: e.target.value })} />
        <button type="button" disabled={!f.person || (f.uid || '').trim().length < 4}
          onClick={() => void post('/hrm/rfid/cards', { employee_id: f.person, card_uid: f.uid.trim() }, () => setF({ ...f, uid: '' }))}>Issue card</button>
      </div>
      <p className="hr-muted">Taps arrive as clock times marked &quot;rfid&quot; for HR to check. A new card replaces the person&apos;s old one. Built and tested with simulated traffic; try it on your own reader before relying on it.</p>
    </section>
  );
}
