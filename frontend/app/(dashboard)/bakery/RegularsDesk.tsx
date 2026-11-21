'use client';

/**
 * Bakery regulars: people who order often, found from order phone numbers. Add a birthday and
 * whether they agreed to texts; a manager sends the day's birthday texts (once a year each).
 */

import React, { useCallback, useEffect, useState } from 'react';
import { bakeryApi } from '../../../lib/bakeryTill';
import { formatMoney } from '../../../lib/format';

type Row = Record<string, any>;
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export default function RegularsDesk({ isManager }: { isManager: boolean }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [soon, setSoon] = useState<Row[]>([]);
  const [edit, setEdit] = useState<{ phone: string; name: string; month: string; day: string; texts_ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([bakeryApi('/bakery/regulars'), bakeryApi('/bakery/regulars/birthdays?days=14')]);
      setRows(a?.data || []);
      setSoon(b?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  async function call(path: string, method: string, body?: object) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await bakeryApi(path, { method, body: body ? JSON.stringify(body) : undefined });
      await load();
      return res;
    } catch (err) {
      setError(problem(err));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!edit) return;
    const hasBirthday = edit.month !== '' && edit.day !== '';
    const res = await call('/bakery/regulars', 'PUT', {
      phone: edit.phone,
      name: edit.name.trim() || null,
      birth_month: hasBirthday ? Number(edit.month) : null,
      birth_day: hasBirthday ? Number(edit.day) : null,
      texts_ok: edit.texts_ok,
    });
    if (res) {
      setNotice('Saved');
      setEdit(null);
    }
  }

  async function sendTexts() {
    const res = await call('/bakery/regulars/birthday-texts', 'POST');
    if (!res) return;
    const d = res.data || {};
    const why = d.failed?.length ? ` Not sent: ${d.failed[0].reason}.` : '';
    setNotice(`${d.sent} birthday text(s) sent, ${d.already_texted} already texted this year.${why}`);
  }

  return (
    <div className="bk-trade">
      {error ? <div className="bk-banner bad" role="alert">{error}</div> : null}
      {notice ? <div className="bk-banner ok" role="status">{notice}</div> : null}

      <section className="bk-box" aria-label="Birthdays coming up">
        <div className="bk-row bk-spread">
          <b>Birthdays in the next 14 days</b>
          {isManager ? (
            <button type="button" className="bk-primary" disabled={busy} onClick={() => void sendTexts()} aria-label="Send today's birthday texts">Send today&apos;s birthday texts</button>
          ) : null}
        </div>
        {soon.length === 0 ? <p className="bk-muted">None. Add birthdays below; only people who agreed to texts are messaged.</p> : (
          <ul>
            {soon.map((r) => (
              <li key={r.phone}>{r.name || r.phone} · {r.in_days === 0 ? 'today' : `in ${r.in_days} day${r.in_days === 1 ? '' : 's'}`} {r.texts_ok ? '' : <span className="bk-pill">no texts</span>}</li>
            ))}
          </ul>
        )}
      </section>

      <section className="bk-box bk-scroll" aria-label="Regular customers">
        <table>
          <thead><tr><th>Customer</th><th>Orders</th><th>Spent</th><th>Last order</th><th>Birthday</th><th /></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.phone}>
                <td>{r.name || '—'}<div className="bk-muted">{r.phone}</div></td>
                <td className="bk-num">{r.orders}</td>
                <td className="bk-num">{formatMoney(r.spent)}</td>
                <td>{r.last_order || '—'}</td>
                <td>{r.birth_month ? `${r.birth_day} ${MONTHS[r.birth_month - 1]}` : '—'} {r.texts_ok ? <span className="bk-pill ok">texts ok</span> : null}</td>
                <td>
                  <button type="button" aria-label={`Edit ${r.name || r.phone}`} onClick={() => setEdit({ phone: r.phone, name: r.name || '', month: r.birth_month ? String(r.birth_month) : '', day: r.birth_day ? String(r.birth_day) : '', texts_ok: Boolean(r.texts_ok) })}>Edit</button>
                </td>
              </tr>
            ))}
            {rows.length === 0 ? <tr><td colSpan={6} className="bk-muted">Customers appear here after their first order with a phone number.</td></tr> : null}
          </tbody>
        </table>
      </section>

      {edit ? (
        <section className="bk-box" aria-label="Edit regular customer">
          <h3>{edit.name || edit.phone}</h3>
          <div className="bk-row">
            <input aria-label="Regular name" value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} />
            <select aria-label="Birthday month" value={edit.month} onChange={(e) => setEdit({ ...edit, month: e.target.value })}>
              <option value="">Month</option>
              {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
            <input type="number" min={1} max={31} placeholder="Day" aria-label="Birthday day" value={edit.day} onChange={(e) => setEdit({ ...edit, day: e.target.value })} style={{ width: 80 }} />
            <label className="bk-check"><input type="checkbox" checked={edit.texts_ok} onChange={(e) => setEdit({ ...edit, texts_ok: e.target.checked })} aria-label="Agreed to receive texts" /><span>They agreed to receive texts</span></label>
            <button type="button" className="bk-primary" disabled={busy} onClick={() => void save()} aria-label="Save regular customer">Save</button>
            <button type="button" onClick={() => setEdit(null)} aria-label="Cancel editing regular customer">Cancel</button>
          </div>
        </section>
      ) : null}
    </div>
  );
}
