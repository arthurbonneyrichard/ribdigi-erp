'use client';

/**
 * Bakery stock extras: an item's details (shelf life, day-old price, allergens, label text,
 * units, shelf level), what is on the shelf by bake, and suppliers with what is owed.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { bakeryApi, openPrintable } from '../../../lib/bakeryTill';
import { formatMoney } from '../../../lib/format';

type Row = Record<string, any>;
const money = (value: unknown) => formatMoney(Number(value || 0));
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';
const UNITS = ['each', 'kg', 'g', 'l', 'ml'];
const STATE: Record<string, { label: string; tone: string }> = {
  fresh: { label: 'Fresh', tone: 'ok' },
  day_old: { label: 'Day-old', tone: '' },
  last_day: { label: 'Last day', tone: 'bad' },
  expired: { label: 'Past its date', tone: 'bad' },
};

function useAction(after: () => Promise<void> | void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function run(path: string, body: object | null, done: string, method = 'POST') {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const res = await bakeryApi(path, { method, body: body ? JSON.stringify(body) : undefined });
      setNotice(done);
      await after();
      return res?.data ?? true;
    } catch (err) {
      setError(problem(err));
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, notice, run, setError };
}

export function ItemDetailsPanel({ stockItems, onSaved }: { stockItems: Row[]; onSaved: () => void }) {
  const [pick, setPick] = useState('');
  const [allergens, setAllergens] = useState<Row[]>([]);
  const [form, setForm] = useState<Row | null>(null);
  const [label, setLabel] = useState<Row | null>(null);
  const act = useAction(() => onSaved());

  useEffect(() => {
    bakeryApi('/bakery/allergens').then((r) => setAllergens(r?.data || [])).catch(() => setAllergens([]));
  }, []);
  useEffect(() => {
    if (!pick) {
      setForm(null);
      return;
    }
    bakeryApi(`/bakery/items/${pick}/details`)
      .then((r) => {
        const d = r?.data || {};
        setLabel(d.label || null);
        setForm({
          shelf_life_days: d.shelf_life_days ?? '',
          day_old_discount_pct: d.day_old_discount_pct ?? '',
          allergens: d.allergens || [],
          ingredients_text: d.ingredients_text || '',
          net_weight: d.net_weight || '',
          storage_note: d.storage_note || '',
          stock_unit: d.stock_unit || 'each',
          purchase_unit: d.purchase_unit || '',
          units_per_purchase: d.units_per_purchase ?? '',
          par_level: d.par_level ?? '',
          options_text: optionsToText(d.options || []),
        });
      })
      .catch((err) => act.setError(problem(err)));
  }, [pick]); // eslint-disable-line react-hooks/exhaustive-deps

  const item = stockItems.find((s) => s.id === pick);
  const num = (v: unknown) => (v === '' || v == null ? null : Number(v));
  const text = (v: unknown) => (String(v || '').trim() ? String(v).trim() : null);

  return (
    <section className="bk-box" aria-label="Item details">
      <div className="bk-row bk-spread">
        <h2>Item details</h2>
        <span className="bk-muted">Shelf life, day-old price, allergens, label, units and shelf level.</span>
      </div>
      <label><span>Item</span>
        <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Item to describe">
          <option value="">Choose</option>
          {stockItems.filter((s) => s.is_active).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.kind === 'item' ? 'for sale' : 'ingredient'})</option>)}
        </select>
      </label>
      {act.error ? <div className="bk-banner bad" role="alert">{act.error}</div> : null}
      {act.notice ? <div className="bk-banner ok" role="status">{act.notice}</div> : null}
      {form && item ? (
        <>
          <div className="bk-form">
            {item.kind === 'item' ? (
              <>
                <label><span>Shelf life (days)</span><input type="number" min="1" max="365" value={form.shelf_life_days} onChange={(e) => setForm({ ...form, shelf_life_days: e.target.value })} aria-label="Shelf life days" /></label>
                <label><span>Day-old price: % off</span><input type="number" min="0" max="90" value={form.day_old_discount_pct} onChange={(e) => setForm({ ...form, day_old_discount_pct: e.target.value })} aria-label="Day-old percent off" /></label>
                <label><span>Keep on the shelf each day</span><input type="number" min="0" value={form.par_level} onChange={(e) => setForm({ ...form, par_level: e.target.value })} aria-label="Shelf level" /></label>
                <label><span>Net weight</span><input value={form.net_weight} placeholder="e.g. 400 g" onChange={(e) => setForm({ ...form, net_weight: e.target.value })} aria-label="Net weight" /></label>
                <label className="bk-span2"><span>Storage note</span><input value={form.storage_note} placeholder="e.g. Keep in a cool dry place" onChange={(e) => setForm({ ...form, storage_note: e.target.value })} aria-label="Storage note" /></label>
                <label className="bk-span2"><span>Choices when ordering, one group per line, like Size*: 6 inch, 10 inch=60 (a * makes it required, =60 is the extra price)</span><textarea rows={3} value={form.options_text || ''} placeholder={'Size*: 6 inch, 10 inch=60\nFlavour: Vanilla, Red velvet=15'} onChange={(e) => setForm({ ...form, options_text: e.target.value })} aria-label="Order choices" /></label>
                <label className="bk-span2"><span>Ingredient list for the label (leave blank to use the recipe)</span><input value={form.ingredients_text} onChange={(e) => setForm({ ...form, ingredients_text: e.target.value })} aria-label="Label ingredients" /></label>
              </>
            ) : (
              <>
                <label><span>Kept in</span>
                  <select value={form.stock_unit} onChange={(e) => setForm({ ...form, stock_unit: e.target.value })} aria-label="Stock unit">
                    {UNITS.map((u) => <option key={u} value={u}>{u}</option>)}
                  </select>
                </label>
                <label><span>Bought in (e.g. 50 kg bag)</span><input value={form.purchase_unit} onChange={(e) => setForm({ ...form, purchase_unit: e.target.value })} aria-label="Purchase unit" /></label>
                <label><span>{form.stock_unit} in one {form.purchase_unit || 'purchase unit'}</span><input type="number" min="0" step="0.001" value={form.units_per_purchase} onChange={(e) => setForm({ ...form, units_per_purchase: e.target.value })} aria-label="Stock units per purchase unit" /></label>
              </>
            )}
          </div>
          <fieldset className="bk-allergens">
            <legend>Allergens it contains</legend>
            {allergens.map((a) => (
              <label key={a.id} className="bk-check">
                <input
                  type="checkbox" checked={form.allergens.includes(a.id)}
                  onChange={(e) => setForm({ ...form, allergens: e.target.checked ? [...form.allergens, a.id] : form.allergens.filter((x: string) => x !== a.id) })}
                /> <span>{a.label}</span>
              </label>
            ))}
          </fieldset>
          {item.kind === 'item' && label ? (
            <p className="bk-muted">
              On the label: {label.ingredients || 'no recipe yet'}. Allergens: {(label.allergen_names || []).join(', ') || 'none declared'}
              {' '}(includes the allergens of every ingredient in the recipe).
            </p>
          ) : null}
          <div className="bk-row">
            <button
              type="button" className="bk-primary" disabled={act.busy}
              onClick={() => act.run(`/bakery/items/${item.id}/details`, item.kind === 'item'
                ? {
                    shelf_life_days: num(form.shelf_life_days), day_old_discount_pct: num(form.day_old_discount_pct) || null,
                    par_level: num(form.par_level), net_weight: text(form.net_weight), storage_note: text(form.storage_note),
                    ingredients_text: text(form.ingredients_text), allergens: form.allergens,
                    options: textToOptions(form.options_text || ''),
                  }
                : {
                    stock_unit: form.stock_unit, purchase_unit: text(form.purchase_unit),
                    units_per_purchase: text(form.purchase_unit) ? num(form.units_per_purchase) : null, allergens: form.allergens,
                  }, `${item.name} saved`, 'PUT')}
            >Save details</button>
            {item.kind === 'item' ? <button type="button" onClick={() => void openPrintable(`/bakery/items/${item.id}/label?copies=8`)}>Print labels</button> : null}
          </div>
        </>
      ) : null}
    </section>
  );
}

export function ShelfPanel() {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    bakeryApi('/bakery/shelf').then((r) => setRows(r?.data || [])).catch(() => setRows([]));
  }, []);
  const dated = rows.filter((r) => r.best_before || r.state !== 'fresh');
  return (
    <section className="bk-box bk-scroll" aria-label="On the shelf">
      <div className="bk-row bk-spread">
        <h2>On the shelf, by bake</h2>
        <span className="bk-muted">Oldest bakes are taken to sell first.</span>
      </div>
      <table>
        <thead><tr><th>Item</th><th>Bake</th><th>Baked</th><th>Best before</th><th>How many</th><th>State</th><th /></tr></thead>
        <tbody>
          {dated.map((r) => (
            <tr key={r.batch_id}>
              <td>{r.name}</td><td>{r.batch_number}</td><td>{r.baked_on}</td><td>{r.best_before || '—'}</td><td>{r.quantity}</td>
              <td><span className={`bk-pill ${STATE[r.state]?.tone || ''}`}>{STATE[r.state]?.label || r.state}</span>{r.state === 'day_old' && r.day_old_discount_pct ? <div className="bk-muted">{r.day_old_discount_pct}% off at the counter</div> : null}</td>
              <td><button type="button" onClick={() => void openPrintable(`/bakery/items/${r.product_id}/label?batch_id=${r.batch_id}&copies=8`)} aria-label={`Labels for ${r.batch_number}`}>Labels</button></td>
            </tr>
          ))}
          {dated.length === 0 ? <tr><td colSpan={7} className="bk-muted">Nothing dated on the shelf. Set a shelf life on an item to track it.</td></tr> : null}
        </tbody>
      </table>
    </section>
  );
}

export function SuppliersPanel() {
  const [rows, setRows] = useState<Row[]>([]);
  const [form, setForm] = useState({ name: '', phone: '', terms_days: '' });
  const [pay, setPay] = useState<{ id: string; amount: string; method: string; from_till: boolean; reference: string } | null>(null);
  const load = useCallback(async () => {
    try {
      setRows((await bakeryApi('/bakery/suppliers'))?.data || []);
    } catch {
      setRows([]);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  const act = useAction(load);
  const owed = rows.reduce((t, r) => t + Number(r.owed || 0), 0);
  return (
    <section className="bk-box bk-scroll" aria-label="Suppliers">
      <div className="bk-row bk-spread">
        <h2>Suppliers</h2>
        <span className="bk-muted">You owe {money(owed)}</span>
      </div>
      {act.error ? <div className="bk-banner bad" role="alert">{act.error}</div> : null}
      {act.notice ? <div className="bk-banner ok" role="status">{act.notice}</div> : null}
      <table>
        <thead><tr><th>Supplier</th><th>Phone</th><th>Days to pay</th><th>You owe</th><th>Owed since</th><th /></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.name}</td><td>{r.phone || '—'}</td><td>{r.terms_days}</td>
              <td className="bk-num">{Number(r.owed) > 0 ? <b>{money(r.owed)}</b> : money(0)}</td>
              <td>{Number(r.owed) > 0 && r.oldest_credit ? String(r.oldest_credit).slice(0, 10) : '—'}</td>
              <td>{Number(r.owed) > 0 ? <button type="button" onClick={() => setPay({ id: r.id, amount: String(r.owed), method: 'bank_transfer', from_till: false, reference: '' })}>Pay</button> : null}</td>
            </tr>
          ))}
          {rows.length === 0 ? <tr><td colSpan={6} className="bk-muted">No suppliers yet. They are added when you buy on credit, or here.</td></tr> : null}
        </tbody>
      </table>
      {pay ? (
        <div className="bk-form" aria-label="Pay a supplier">
          <label><span>Amount</span><input type="number" min="0" step="0.01" value={pay.amount} onChange={(e) => setPay({ ...pay, amount: e.target.value })} aria-label="Supplier payment amount" /></label>
          <label><span>Paid by</span>
            <select value={pay.method} onChange={(e) => setPay({ ...pay, method: e.target.value, from_till: e.target.value === 'cash' && pay.from_till })} aria-label="Supplier payment method">
              <option value="bank_transfer">Bank transfer</option><option value="mobile_money">Mobile Money</option><option value="cash">Cash</option><option value="card">Card</option>
            </select>
          </label>
          <label><span>Reference</span><input value={pay.reference} onChange={(e) => setPay({ ...pay, reference: e.target.value })} aria-label="Supplier payment reference" /></label>
          {pay.method === 'cash' ? <label className="bk-check"><input type="checkbox" checked={pay.from_till} onChange={(e) => setPay({ ...pay, from_till: e.target.checked })} /> <span>Taken from the till</span></label> : null}
          <button type="button" className="bk-primary" disabled={act.busy || !(Number(pay.amount) > 0)} onClick={async () => {
            if (await act.run(`/bakery/suppliers/${pay.id}/payments`, { amount: Number(pay.amount), method: pay.method, from_till: pay.from_till, reference: pay.reference.trim() || null }, 'Supplier paid')) setPay(null);
          }}>Pay supplier</button>
          <button type="button" onClick={() => setPay(null)}>Go back</button>
        </div>
      ) : null}
      <h3 className="bk-sub">Add a supplier</h3>
      <div className="bk-form">
        <label><span>Name</span><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} aria-label="Supplier name" /></label>
        <label><span>Phone</span><input value={form.phone} placeholder="+233…" onChange={(e) => setForm({ ...form, phone: e.target.value })} aria-label="Supplier phone" /></label>
        <label><span>Days to pay</span><input type="number" min="0" max="120" value={form.terms_days} onChange={(e) => setForm({ ...form, terms_days: e.target.value })} aria-label="Supplier days to pay" /></label>
        <button type="button" disabled={act.busy || !form.name.trim()} onClick={async () => {
          if (await act.run('/bakery/suppliers', { name: form.name.trim(), phone: form.phone.replace(/[\s-]/g, '') || null, terms_days: form.terms_days ? Number(form.terms_days) : null }, 'Supplier added')) setForm({ name: '', phone: '', terms_days: '' });
        }}>Add supplier</button>
      </div>
    </section>
  );
}

/** Suppliers for the Buy stock form. */
export function useSuppliers(): Row[] {
  const [rows, setRows] = useState<Row[]>([]);
  useEffect(() => {
    bakeryApi('/bakery/suppliers').then((r) => setRows(r?.data || [])).catch(() => setRows([]));
  }, []);
  return rows;
}

// "Size*: 6 inch, 10 inch=60" <-> [{ name: 'Size', required: true, choices: [{ label, extra }] }]
function optionsToText(groups: any[]): string {
  return groups
    .map((g) => `${g.name}${g.required ? '*' : ''}: ${(g.choices || []).map((c: any) => (Number(c.extra) ? `${c.label}=${c.extra}` : c.label)).join(', ')}`)
    .join('\n');
}

function textToOptions(textValue: string) {
  return textValue
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [head, ...rest] = line.split(':');
      const name = head.trim();
      const required = name.endsWith('*');
      const choices = rest
        .join(':')
        .split(',')
        .map((c) => c.trim())
        .filter(Boolean)
        .map((c) => {
          const [label, extra] = c.split('=');
          return { label: label.trim(), extra: Number(extra) || 0 };
        });
      return { name: required ? name.slice(0, -1).trim() : name, required, choices };
    });
}
