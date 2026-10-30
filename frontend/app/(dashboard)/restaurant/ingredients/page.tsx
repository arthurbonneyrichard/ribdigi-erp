'use client';

/**
 * Restaurant stock: ingredients (what the kitchen uses) and menu items (what guests buy),
 * kept apart. Uses the shared stock engine (products, stock-in, adjust) with restaurant words.
 */

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../../../lib/api';
import { money, problem, type Row } from '../../../../lib/restaurantDesk';
import '../restaurant-desk.css';

type Tab = 'ingredients' | 'menu';
type Sheet =
  | { kind: 'receive' | 'count' | 'edit'; row: Row }
  | { kind: 'add-ingredient' }
  | { kind: 'add-dish' }
  | { kind: 'edit-dish'; row: Row }
  | null;

function qty(value: unknown) {
  const n = Number(value || 0);
  return Number.isInteger(n) ? String(n) : n.toFixed(2);
}

function isLow(row: Row) {
  return Number(row.reorder_level || 0) > 0 && Number(row.stock_qty || 0) <= Number(row.reorder_level || 0);
}

export default function RestaurantStockPage() {
  const router = useRouter();
  const tab: Tab = useSearchParams().get('tab') === 'menu' ? 'menu' : 'ingredients';
  const setTab = (next: Tab) => router.replace(next === 'ingredients' ? '?' : `?tab=${next}`, { scroll: false });
  const [products, setProducts] = useState<Row[]>([]);
  const [recipes, setRecipes] = useState<Row[]>([]);
  const [units, setUnits] = useState<Row[]>([]);
  const [soldOut, setSoldOut] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [filter, setFilter] = useState<'all' | 'low' | 'out'>('all');
  const [search, setSearch] = useState('');
  const [sheet, setSheet] = useState<Sheet>(null);

  const load = useCallback(async () => {
    try {
      const [productRes, recipeRes, unitRes, soldRes] = await Promise.all([
        api('/products?is_active=true'),
        api('/restaurant/recipes').catch(() => ({ data: [] })),
        api('/catalog/units').catch(() => ({ data: [] })),
        api('/restaurant/sold-out').catch(() => ({ data: { items: [] } })),
      ]);
      const list = productRes?.data;
      setProducts(Array.isArray(list) ? list : list?.items || []);
      setRecipes(recipeRes?.data || []);
      const unitList = unitRes?.data;
      setUnits((Array.isArray(unitList) ? unitList : unitList?.items || []).filter((u: Row) => u.is_active !== false));
      setSoldOut(((soldRes?.data?.items as Row[]) || []).map((r) => r.id));
      setError('');
    } catch (err) {
      setError(problem(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // A menu item is something guests buy: it has a recipe or a kitchen/bar station. Everything else is an ingredient.
  const recipeMenu = useMemo(() => new Set(recipes.map((r) => r.product_id)), [recipes]);
  const usedIn = useMemo(() => {
    const out: Record<string, number> = {};
    for (const r of recipes) for (const line of r.lines || []) out[line.ingredient_id] = (out[line.ingredient_id] || 0) + 1;
    return out;
  }, [recipes]);
  const menu = products.filter((p) => recipeMenu.has(p.id) || p.prep_station === 'kitchen' || p.prep_station === 'bar');
  const ingredients = products.filter((p) => !menu.includes(p));

  const shownIngredients = ingredients
    .filter((p) => (filter === 'low' ? isLow(p) : filter === 'out' ? Number(p.stock_qty || 0) <= 0 : true))
    .filter((p) => !search.trim() || String(p.name).toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) => Number(isLow(b)) - Number(isLow(a)) || String(a.name).localeCompare(String(b.name)));
  const shownMenu = menu
    .filter((p) => !search.trim() || String(p.name).toLowerCase().includes(search.trim().toLowerCase()))
    .sort((a, b) => String(a.category).localeCompare(String(b.category)) || String(a.name).localeCompare(String(b.name)));

  const stockValue = ingredients.reduce((s, p) => s + Number(p.cost_price || 0) * Math.max(0, Number(p.stock_qty || 0)), 0);
  const lowCount = ingredients.filter(isLow).length;
  const outCount = ingredients.filter((p) => Number(p.stock_qty || 0) <= 0).length;

  async function done(message: string) {
    setSheet(null);
    setNotice(message);
    await load();
  }

  async function toggleSoldOut(row: Row) {
    const next = soldOut.includes(row.id) ? soldOut.filter((id) => id !== row.id) : [...soldOut, row.id];
    try {
      await api('/restaurant/sold-out', { method: 'PUT', body: JSON.stringify({ product_ids: next }) });
      setSoldOut(next);
      setNotice(next.includes(row.id) ? `${row.name} is sold out today` : `${row.name} is back on the menu`);
    } catch (err) {
      setError(problem(err));
    }
  }

  return (
    <div className="rdesk">
      <header className="rd-head">
        <div>
          <h1>Stock</h1>
          <p>Ingredients the kitchen uses, and the dishes and drinks on your menu.</p>
        </div>
        <div className="rd-head-actions">
          <input className="rd-search" type="search" placeholder="Search" aria-label="Search stock" value={search} onChange={(e) => setSearch(e.target.value)} />
          <Link className="rd-linkish" href="/restaurant/purchasing">Order from suppliers →</Link>
          {tab === 'ingredients' ? (
            <button type="button" className="rd-primary" aria-label="Add an ingredient" onClick={() => setSheet({ kind: 'add-ingredient' })}>
              + Ingredient
            </button>
          ) : (
            <button type="button" className="rd-primary" aria-label="Add a menu item" onClick={() => setSheet({ kind: 'add-dish' })}>
              + Menu item
            </button>
          )}
        </div>
      </header>

      <div className="rd-tabs" role="tablist" aria-label="Stock sections">
        <button type="button" role="tab" aria-selected={tab === 'ingredients'} className={tab === 'ingredients' ? 'on' : ''} onClick={() => setTab('ingredients')}>
          Ingredients <small>{ingredients.length}</small>
        </button>
        <button type="button" role="tab" aria-selected={tab === 'menu'} className={tab === 'menu' ? 'on' : ''} onClick={() => setTab('menu')}>
          Menu items <small>{menu.length}</small>
        </button>
      </div>

      {notice ? <div className="rd-notice" role="status" onClick={() => setNotice('')}>{notice}</div> : null}
      {error ? <div className="rd-error" role="alert">{error}</div> : null}
      {loading ? <div className="rd-empty">Loading stock…</div> : null}

      {!loading && tab === 'ingredients' ? (
        <>
          <div className="rd-kpis">
            <div className="rd-kpi hero">
              <span>Stock value (at cost)</span>
              <strong>{money(stockValue)}</strong>
            </div>
            <button type="button" className={`rd-kpi rd-kpi-btn${filter === 'low' ? ' on' : ''}`} onClick={() => setFilter(filter === 'low' ? 'all' : 'low')}>
              <span>Running low</span>
              <strong>{lowCount}</strong>
            </button>
            <button type="button" className={`rd-kpi rd-kpi-btn${filter === 'out' ? ' on' : ''}`} onClick={() => setFilter(filter === 'out' ? 'all' : 'out')}>
              <span>Out of stock</span>
              <strong>{outCount}</strong>
            </button>
            <div className="rd-kpi">
              <span>Ingredients</span>
              <strong>{ingredients.length}</strong>
            </div>
          </div>
          <div className="rd-chips" role="tablist" aria-label="Which ingredients">
            {(['all', 'low', 'out'] as const).map((f) => (
              <button key={f} type="button" role="tab" aria-selected={filter === f} className={filter === f ? 'on' : ''} onClick={() => setFilter(f)}>
                {f === 'all' ? 'All' : f === 'low' ? 'Running low' : 'Out of stock'}
              </button>
            ))}
          </div>
          <div className="rd-list" aria-label="Ingredients">
            {shownIngredients.length === 0 ? (
              <div className="rd-empty">
                <strong>{ingredients.length ? 'Nothing here' : 'No ingredients yet'}</strong>
                {ingredients.length ? 'Try another filter.' : 'Add rice, chicken, oil and the rest, with their cost and how much you have.'}
              </div>
            ) : null}
            {shownIngredients.map((row) => {
              const low = isLow(row);
              const out = Number(row.stock_qty || 0) <= 0;
              return (
                <div key={row.id} className={`rd-stock-row${low ? ' low' : ''}${out ? ' out' : ''}`}>
                  <div className="what">
                    <strong>{row.name}</strong>
                    <small>
                      {row.unit_name ? `per ${row.unit_name} · ` : ''}cost {money(row.cost_price)}
                      {usedIn[row.id] ? ` · in ${usedIn[row.id]} ${usedIn[row.id] === 1 ? 'recipe' : 'recipes'}` : ' · not in a recipe'}
                    </small>
                  </div>
                  <div className="onhand">
                    <strong>{qty(row.stock_qty)}</strong>
                    <small>{out ? 'Out' : low ? `Low · reorder at ${qty(row.reorder_level)}` : Number(row.reorder_level) ? `reorder at ${qty(row.reorder_level)}` : 'on hand'}</small>
                  </div>
                  <span className="value">{money(Number(row.cost_price || 0) * Math.max(0, Number(row.stock_qty || 0)))}</span>
                  <div className="acts">
                    <button type="button" className="rd-go" aria-label={`Receive ${row.name}`} onClick={() => setSheet({ kind: 'receive', row })}>Receive</button>
                    <button type="button" aria-label={`Count ${row.name}`} onClick={() => setSheet({ kind: 'count', row })}>Count</button>
                    <button type="button" aria-label={`Edit ${row.name}`} onClick={() => setSheet({ kind: 'edit', row })}>Edit</button>
                  </div>
                </div>
              );
            })}
          </div>
          <p className="rd-hint-line">
            Spoiled or dropped something? Record it under <Link href="/restaurant?tab=waste">Waste</Link> so the cost is booked.
          </p>
        </>
      ) : null}

      {!loading && tab === 'menu' ? (
        <div className="rd-list" aria-label="Menu items">
          {shownMenu.length === 0 ? (
            <div className="rd-empty">
              <strong>No menu items yet</strong>Add the dishes and drinks you sell.
            </div>
          ) : null}
          {shownMenu.map((row) => (
            <div key={row.id} className="rd-stock-row menu">
              <div className="what">
                <strong>{row.name}</strong>
                <small>
                  {row.category || 'Menu'} · {row.prep_station === 'bar' ? 'Bar' : 'Kitchen'} ·{' '}
                  {recipeMenu.has(row.id) ? 'has a recipe' : <Link href="/restaurant?tab=recipes">no recipe yet</Link>}
                </small>
              </div>
              <div className="onhand">
                <strong>{money(row.selling_price)}</strong>
                <small>price</small>
              </div>
              <span className={`rd-pill ${soldOut.includes(row.id) ? 'bad' : ''}`}>{soldOut.includes(row.id) ? 'Sold out today' : 'On the menu'}</span>
              <div className="acts">
                <button type="button" aria-label={`${soldOut.includes(row.id) ? 'Put back' : 'Mark sold out'} ${row.name}`} onClick={() => void toggleSoldOut(row)}>
                  {soldOut.includes(row.id) ? 'Put back' : 'Sold out'}
                </button>
                <button type="button" aria-label={`Edit ${row.name}`} onClick={() => setSheet({ kind: 'edit-dish', row })}>Edit</button>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {sheet ? <StockSheet sheet={sheet} units={units} onClose={() => setSheet(null)} onDone={done} /> : null}
    </div>
  );
}

function StockSheet({
  sheet,
  units,
  onClose,
  onDone,
}: {
  sheet: NonNullable<Sheet>;
  units: Row[];
  onClose: () => void;
  onDone: (message: string) => Promise<void>;
}) {
  const row = 'row' in sheet ? sheet.row : null;
  const [amount, setAmount] = useState('');
  const [notes, setNotes] = useState('');
  const [name, setName] = useState(String(row?.name || ''));
  const [unitId, setUnitId] = useState(String(row?.unit_id || ''));
  const [cost, setCost] = useState(row ? String(row.cost_price ?? '') : '');
  const [reorder, setReorder] = useState(row ? String(row.reorder_level ?? '') : '');
  const [opening, setOpening] = useState('');
  const [price, setPrice] = useState(row ? String(row.selling_price ?? '') : '');
  const [category, setCategory] = useState(String(row?.category || ''));
  const [station, setStation] = useState(String(row?.prep_station || 'kitchen'));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function run(fn: () => Promise<string>) {
    setBusy(true);
    setError('');
    try {
      await onDone(await fn());
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }

  const title =
    sheet.kind === 'receive' ? `Receive ${row?.name}` :
    sheet.kind === 'count' ? `Count ${row?.name}` :
    sheet.kind === 'edit' ? `Edit ${row?.name}` :
    sheet.kind === 'add-ingredient' ? 'New ingredient' :
    sheet.kind === 'add-dish' ? 'New menu item' : `Edit ${row?.name}`;

  async function submit() {
    if (sheet.kind === 'receive') {
      await run(async () => {
        const n = Number(amount);
        if (!(n > 0)) throw new Error('Enter how much came in.');
        await api('/inventory/stock-in', {
          method: 'POST',
          body: JSON.stringify({ product_id: row!.id, quantity: n, notes: notes.trim() || null }),
        });
        return `${qty(n)} ${row!.name} received`;
      });
    } else if (sheet.kind === 'count') {
      await run(async () => {
        if (amount.trim() === '') throw new Error('Enter what you counted.');
        const delta = Number(amount) - Number(row!.stock_qty || 0);
        if (Math.abs(delta) < 0.0001) return `${row!.name} count matches`;
        await api(`/inventory/adjust/${row!.id}`, {
          method: 'POST',
          body: JSON.stringify({ quantity: delta, reason: delta > 0 ? 'found' : 'lost', notes: notes.trim() || 'Stock count' }),
        });
        return `${row!.name} counted: ${delta > 0 ? '+' : ''}${qty(delta)}`;
      });
    } else if (sheet.kind === 'edit') {
      await run(async () => {
        await api(`/products/${row!.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            name: name.trim(),
            cost_price: Number(cost || 0),
            reorder_level: Number(reorder || 0),
            unit_id: unitId || null,
          }),
        });
        return `${name.trim()} saved`;
      });
    } else if (sheet.kind === 'add-ingredient') {
      await run(async () => {
        if (!name.trim()) throw new Error('Name the ingredient.');
        await api('/products', {
          method: 'POST',
          body: JSON.stringify({
            name: name.trim(),
            category: 'Ingredients',
            unit_id: unitId || null,
            cost_price: Number(cost || 0),
            selling_price: 0,
            stock_qty: Number(opening || 0),
            reorder_level: Number(reorder || 0),
          }),
        });
        return `${name.trim()} added`;
      });
    } else {
      await run(async () => {
        if (!name.trim()) throw new Error('Name the dish or drink.');
        const body = {
          name: name.trim(),
          category: category.trim() || 'Menu',
          selling_price: Number(price || 0),
          prep_station: station === 'bar' ? 'bar' : 'kitchen',
        };
        if (sheet.kind === 'add-dish') {
          await api('/products', { method: 'POST', body: JSON.stringify({ ...body, stock_qty: 0 }) });
          return `${name.trim()} is on the menu`;
        }
        await api(`/products/${row!.id}`, { method: 'PATCH', body: JSON.stringify(body) });
        return `${name.trim()} saved`;
      });
    }
  }

  return (
    <div className="rd-scrim" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <aside className="rd-drawer" onClick={(e) => e.stopPropagation()}>
        <div className="rd-drawer-head">
          <div>
            <h2>{title}</h2>
            {row && (sheet.kind === 'receive' || sheet.kind === 'count') ? (
              <p>
                {qty(row.stock_qty)} on hand now{row.unit_name ? ` (${row.unit_name})` : ''}
              </p>
            ) : null}
          </div>
          <button type="button" className="rd-link" onClick={onClose}>Close</button>
        </div>
        <div className="rd-form-grid">
          {sheet.kind === 'receive' || sheet.kind === 'count' ? (
            <>
              <label className="rd-span">
                <span>{sheet.kind === 'receive' ? 'How much came in' : 'What you counted'}</span>
                <input aria-label={sheet.kind === 'receive' ? 'Quantity received' : 'Quantity counted'} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))} autoFocus />
              </label>
              {sheet.kind === 'count' && amount.trim() !== '' ? (
                <p className="rd-hint-line rd-span">
                  Difference: {Number(amount) - Number(row!.stock_qty || 0) > 0 ? '+' : ''}
                  {qty(Number(amount) - Number(row!.stock_qty || 0))}
                </p>
              ) : null}
              <label className="rd-span">
                <span>Note (optional)</span>
                <input aria-label="Stock note" placeholder={sheet.kind === 'receive' ? 'Market run, supplier name…' : 'Monday count'} value={notes} onChange={(e) => setNotes(e.target.value)} />
              </label>
              {sheet.kind === 'receive' ? (
                <p className="rd-hint-line rd-span">From a supplier order? Use “Receive delivery” on the order under Purchasing instead.</p>
              ) : null}
            </>
          ) : null}
          {sheet.kind === 'edit' || sheet.kind === 'add-ingredient' ? (
            <>
              <label className="rd-span">
                <span>Name</span>
                <input aria-label="Ingredient name" placeholder="Rice" value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <label>
                <span>Unit</span>
                <select aria-label="Ingredient unit" value={unitId} onChange={(e) => setUnitId(e.target.value)}>
                  <option value="">No unit</option>
                  {units.map((u) => (
                    <option key={u.id} value={u.id}>{u.name}</option>
                  ))}
                </select>
              </label>
              <label>
                <span>Cost per unit</span>
                <input aria-label="Ingredient cost" inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value.replace(/[^0-9.]/g, ''))} />
              </label>
              <label>
                <span>Reorder at</span>
                <input aria-label="Reorder level" inputMode="decimal" placeholder="0 = no alert" value={reorder} onChange={(e) => setReorder(e.target.value.replace(/[^0-9.]/g, ''))} />
              </label>
              {sheet.kind === 'add-ingredient' ? (
                <label>
                  <span>On hand now</span>
                  <input aria-label="Opening stock" inputMode="decimal" value={opening} onChange={(e) => setOpening(e.target.value.replace(/[^0-9.]/g, ''))} />
                </label>
              ) : null}
            </>
          ) : null}
          {sheet.kind === 'add-dish' || sheet.kind === 'edit-dish' ? (
            <>
              <label className="rd-span">
                <span>Name</span>
                <input aria-label="Menu item name" placeholder="Jollof rice and chicken" value={name} onChange={(e) => setName(e.target.value)} />
              </label>
              <label>
                <span>Price</span>
                <input aria-label="Menu item price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value.replace(/[^0-9.]/g, ''))} />
              </label>
              <label>
                <span>Section</span>
                <input aria-label="Menu section" placeholder="Mains, Drinks…" value={category} onChange={(e) => setCategory(e.target.value)} />
              </label>
              <label>
                <span>Made at</span>
                <select aria-label="Made at" value={station} onChange={(e) => setStation(e.target.value)}>
                  <option value="kitchen">Kitchen</option>
                  <option value="bar">Bar</option>
                </select>
              </label>
              <p className="rd-hint-line rd-span">
                Then write its recipe under <Link href="/restaurant?tab=recipes">Recipes</Link> so selling it takes the ingredients off stock.
              </p>
            </>
          ) : null}
        </div>
        {error ? <div className="rd-error" role="alert">{error}</div> : null}
        <div className="rd-actions">
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="rd-primary" aria-label="Save" disabled={busy} onClick={() => void submit()}>
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </aside>
    </div>
  );
}
