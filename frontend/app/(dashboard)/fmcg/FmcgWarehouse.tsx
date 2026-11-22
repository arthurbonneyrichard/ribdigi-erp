'use client';

/**
 * FMCG warehouse layout: zones and bins, put-away, moves between bins, bin counts and a scan box
 * that works with a USB or Bluetooth barcode scanner (it types the bin code and presses Enter).
 * Bins only record where stock sits; they never change how much stock the company has.
 */

import React, { useCallback, useEffect, useState } from 'react';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const WAREHOUSE_TABS = ['warehouse'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin', 'fmcg_storekeeper'];
const ZONE_TYPES = [
  { id: 'ambient', label: 'Ambient' }, { id: 'cold', label: 'Cold' }, { id: 'bulk', label: 'Bulk' },
  { id: 'quarantine', label: 'Quarantine' }, { id: 'receiving', label: 'Receiving' },
  { id: 'dispatch', label: 'Dispatch' }, { id: 'returns', label: 'Returns' },
];
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

export default function FmcgWarehouse({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [warehouses, setWarehouses] = useState<Row[]>([]);
  const [wh, setWh] = useState('');
  const [tree, setTree] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [batches, setBatches] = useState<Row[]>([]);
  const [report, setReport] = useState<Row | null>(null);
  const [open, setOpen] = useState<Row | null>(null);
  const [scan, setScan] = useState('');
  const [zone, setZone] = useState({ code: '', name: '', zone_type: 'ambient' });
  const [bin, setBin] = useState({ zone_id: '', code: '', name: '', capacity: '' });
  const [put, setPut] = useState({ bin_id: '', product_id: '', batch_id: '', quantity: '' });
  const [suggest, setSuggest] = useState<Row[]>([]);
  const [mv, setMv] = useState({ to_bin_id: '', product_id: '', batch_id: '', quantity: '' });
  const [counts, setCounts] = useState<Record<string, string>>({});
  const [why, setWhy] = useState('');
  const manager = MANAGERS.includes(role);

  useEffect(() => {
    getMe().then((me: Row | null) => setRole(String(me?.data?.role || ''))).catch(() => setRole(''));
  }, []);

  const loadBase = useCallback(async () => {
    setError('');
    try {
      const [w, p, b] = await Promise.all([api('/warehouses'), api('/products'), api('/fmcg/batches?status=all')]);
      const list = Array.isArray(w?.data) ? w.data : [];
      setWarehouses(list);
      setWh((cur) => cur || list[0]?.id || '');
      setProducts(Array.isArray(p?.data) ? p.data : []);
      setBatches(b?.data?.batches || []);
    } catch (err) {
      setError(problem(err));
    }
  }, []);

  const loadTree = useCallback(async () => {
    if (!wh) return;
    try {
      const [t, r] = await Promise.all([api(`/fmcg/locations?warehouse_id=${wh}`), api('/fmcg/warehouse/report')]);
      setTree(t?.data || []);
      setReport(r?.data || null);
    } catch (err) {
      setError(problem(err));
    }
  }, [wh]);

  useEffect(() => {
    if (manager) loadBase();
  }, [manager, loadBase]);
  useEffect(() => {
    loadTree();
  }, [loadTree]);

  async function openBin(id: string) {
    try {
      const res = await api(`/fmcg/locations/${id}/contents`);
      setOpen(res?.data || null);
      setCounts({});
      setWhy('');
    } catch (err) {
      setError(problem(err));
    }
  }

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
      setNotice(done);
      await loadTree();
      if (open) await openBin(open.id);
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  const post = (path: string, body: unknown, method = 'POST') => api(path, { method, body: JSON.stringify(body) });
  const bins = tree.flatMap((z) => z.bins.map((b: Row) => ({ ...b, zone: z.code, zone_type: z.zone_type })));
  const batchesFor = (productId: string) => batches.filter((b) => b.product_id === productId);

  async function doScan() {
    if (!scan.trim()) return;
    try {
      const res = await api(`/fmcg/locations/scan?code=${encodeURIComponent(scan.trim())}`);
      setOpen(res?.data || null);
      setCounts({});
      setScan('');
    } catch (err) {
      setError(problem(err));
    }
  }

  async function getSuggestions() {
    if (!put.product_id || !(Number(put.quantity) > 0)) return;
    try {
      const q = `product_id=${put.product_id}&quantity=${Number(put.quantity)}${put.batch_id ? `&batch_id=${put.batch_id}` : ''}`;
      setSuggest((await api(`/fmcg/warehouse/suggest?${q}`))?.data || []);
    } catch (err) {
      setError(problem(err));
    }
  }

  if (role && !manager) {
    return (
      <div className="fmcg-sell">
        <FmcgHead tab={tab} />
        <div className="fs-banner">The warehouse layout is managed by a manager.</div>
      </div>
    );
  }

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      <section className="fs-box" aria-label="Warehouse and scan">
        <div className="fs-form">
          <label><span>Warehouse</span>
            <select value={wh} onChange={(e) => { setWh(e.target.value); setOpen(null); }} aria-label="Layout warehouse">
              {warehouses.length === 0 ? <option value="">No warehouses yet</option> : null}
              {warehouses.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          </label>
          <label><span>Scan a bin label</span>
            <input value={scan} onChange={(e) => setScan(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') doScan(); }} aria-label="Scan bin code" placeholder="Scan or type a bin code" />
          </label>
          <button type="button" onClick={doScan} disabled={!scan.trim()}>Find bin</button>
        </div>
        {warehouses.length === 0 ? <p className="fs-muted">Add a warehouse first in Stock levels, then lay it out here.</p> : null}
      </section>

      {wh ? (
        <section className="fs-box" aria-label="Add a zone or bin">
          <div className="fs-cardhead"><h2>Add a zone</h2></div>
          <div className="fs-form">
            <label><span>Code</span><input value={zone.code} onChange={(e) => setZone({ ...zone, code: e.target.value })} aria-label="Zone code" /></label>
            <label><span>Name</span><input value={zone.name} onChange={(e) => setZone({ ...zone, name: e.target.value })} aria-label="Zone name" /></label>
            <label><span>Type</span>
              <select value={zone.zone_type} onChange={(e) => setZone({ ...zone, zone_type: e.target.value })} aria-label="Zone type">
                {ZONE_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
              </select>
            </label>
            <button type="button" disabled={busy || zone.code.trim().length < 1 || zone.name.trim().length < 2}
              onClick={() => run(async () => { await post('/fmcg/locations', { warehouse_id: wh, kind: 'zone', code: zone.code.trim(), name: zone.name.trim(), zone_type: zone.zone_type }); setZone({ code: '', name: '', zone_type: 'ambient' }); }, 'Zone added.')}>Add zone</button>
          </div>
          <div className="fs-cardhead"><h2>Add a bin</h2></div>
          <div className="fs-form">
            <label><span>Zone</span>
              <select value={bin.zone_id} onChange={(e) => setBin({ ...bin, zone_id: e.target.value })} aria-label="Bin zone">
                <option value="">Pick a zone</option>{tree.filter((z) => z.is_active).map((z) => <option key={z.id} value={z.id}>{z.code} · {z.name}</option>)}
              </select>
            </label>
            <label><span>Code (on the label)</span><input value={bin.code} onChange={(e) => setBin({ ...bin, code: e.target.value })} aria-label="Bin code" /></label>
            <label><span>Name</span><input value={bin.name} onChange={(e) => setBin({ ...bin, name: e.target.value })} aria-label="Bin name" /></label>
            <label><span>Capacity (units, optional)</span><input type="number" min="0" value={bin.capacity} onChange={(e) => setBin({ ...bin, capacity: e.target.value })} aria-label="Bin capacity" /></label>
            <button type="button" disabled={busy || !bin.zone_id || bin.code.trim().length < 1 || bin.name.trim().length < 2}
              onClick={() => run(async () => { await post('/fmcg/locations', { warehouse_id: wh, kind: 'bin', parent_id: bin.zone_id, code: bin.code.trim(), name: bin.name.trim(), ...(Number(bin.capacity) > 0 ? { capacity: Number(bin.capacity) } : {}) }); setBin({ ...bin, code: '', name: '', capacity: '' }); }, 'Bin added.')}>Add bin</button>
          </div>
        </section>
      ) : null}

      <section className="fs-box fs-scroll" aria-label="Layout">
        <div className="fs-cardhead"><h2>Layout</h2></div>
        <table>
          <thead><tr><th>Zone</th><th>Bin</th><th>Used</th><th>Capacity</th><th>Full</th><th /></tr></thead>
          <tbody>
            {tree.map((z) => (
              <React.Fragment key={z.id}>
                <tr>
                  <td colSpan={5}><strong>{z.code}</strong> · {z.name} <span className="fs-flag">{z.zone_type}</span>{z.is_active ? '' : ' (off)'}</td>
                  <td><button type="button" disabled={busy} aria-label={`${z.is_active ? 'Turn off' : 'Turn on'} zone ${z.code}`} onClick={() => run(() => post(`/fmcg/locations/${z.id}`, { is_active: !z.is_active }, 'PATCH'), 'Saved.')}>{z.is_active ? 'Turn off' : 'Turn on'}</button></td>
                </tr>
                {z.bins.map((b: Row) => (
                  <tr key={b.id}>
                    <td /><td>{b.code}{b.is_active ? '' : ' (off)'}</td><td className="fs-num">{b.used}</td>
                    <td className="fs-num">{b.capacity ?? '-'}</td><td className="fs-num">{b.utilisation_pct != null ? `${b.utilisation_pct}%` : '-'}</td>
                    <td>
                      <button type="button" aria-label={`Open bin ${b.code}`} onClick={() => openBin(b.id)}>Open</button>{' '}
                      <button type="button" disabled={busy} aria-label={`${b.is_active ? 'Turn off' : 'Turn on'} bin ${b.code}`} onClick={() => run(() => post(`/fmcg/locations/${b.id}`, { is_active: !b.is_active }, 'PATCH'), 'Saved.')}>{b.is_active ? 'Turn off' : 'Turn on'}</button>
                    </td>
                  </tr>
                ))}
              </React.Fragment>
            ))}
            {tree.length === 0 ? <tr><td colSpan={6} className="fs-muted">No zones yet.</td></tr> : null}
          </tbody>
        </table>
      </section>

      {open ? (
        <section className="fs-box fs-scroll" aria-label="Bin contents">
          <div className="fs-cardhead"><h2>Bin {open.code} · {open.name}</h2></div>
          <table>
            <thead><tr><th>Product</th><th>Batch</th><th>Expires</th><th>In system</th><th>Counted</th></tr></thead>
            <tbody>
              {open.items.map((i: Row) => {
                const key = `${i.product_id}|${i.batch_id || ''}`;
                return (
                  <tr key={key}>
                    <td>{i.product_name}</td><td>{i.batch_number || '-'}</td><td>{i.expiry_date || '-'}</td><td className="fs-num">{i.quantity}</td>
                    <td><input type="number" min="0" value={counts[key] ?? ''} onChange={(e) => setCounts({ ...counts, [key]: e.target.value })} aria-label={`Counted ${i.product_name} ${i.batch_number || ''}`} /></td>
                  </tr>
                );
              })}
              {open.items.length === 0 ? <tr><td colSpan={5} className="fs-muted">Empty.</td></tr> : null}
            </tbody>
          </table>
          <div className="fs-form">
            <label><span>Reason, if the count differs</span><input value={why} onChange={(e) => setWhy(e.target.value)} aria-label="Count reason" /></label>
            <button type="button" className="fs-primary" disabled={busy || open.items.some((i: Row) => (counts[`${i.product_id}|${i.batch_id || ''}`] ?? '') === '')}
              onClick={() => run(async () => { await post(`/fmcg/locations/${open.id}/count`, { lines: open.items.map((i: Row) => ({ product_id: i.product_id, ...(i.batch_id ? { batch_id: i.batch_id } : {}), counted: Number(counts[`${i.product_id}|${i.batch_id || ''}`]) })), ...(why.trim().length >= 3 ? { note: why.trim() } : {}) }); setCounts({}); setWhy(''); }, 'Count saved.')}>Save count</button>
          </div>
          <p className="fs-muted">A count only changes where stock sits. If you find more than the system has, fix the stock level first.</p>
        </section>
      ) : null}

      <section className="fs-box" aria-label="Put away">
        <div className="fs-cardhead"><h2>Put away</h2></div>
        <div className="fs-form">
          <label><span>Product</span>
            <select value={put.product_id} onChange={(e) => setPut({ ...put, product_id: e.target.value, batch_id: '' })} aria-label="Put-away product">
              <option value="">Pick a product</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          </label>
          <label><span>Batch</span>
            <select value={put.batch_id} onChange={(e) => setPut({ ...put, batch_id: e.target.value })} aria-label="Put-away batch">
              <option value="">No batch</option>{batchesFor(put.product_id).map((b) => <option key={b.id} value={b.id}>{b.batch_number} ({b.quantity})</option>)}
            </select>
          </label>
          <label><span>Quantity</span><input type="number" min="0" value={put.quantity} onChange={(e) => setPut({ ...put, quantity: e.target.value })} aria-label="Put-away quantity" /></label>
          <button type="button" onClick={getSuggestions} disabled={!put.product_id || !(Number(put.quantity) > 0)}>Suggest a bin</button>
          <label><span>Into bin</span>
            <select value={put.bin_id} onChange={(e) => setPut({ ...put, bin_id: e.target.value })} aria-label="Put-away bin">
              <option value="">Pick a bin</option>{bins.filter((b) => b.is_active).map((b) => <option key={b.id} value={b.id}>{b.code} ({b.zone})</option>)}
            </select>
          </label>
          <button type="button" className="fs-primary" disabled={busy || !put.bin_id || !put.product_id || !(Number(put.quantity) > 0)}
            onClick={() => run(async () => { await post('/fmcg/warehouse/put-away', { bin_id: put.bin_id, product_id: put.product_id, quantity: Number(put.quantity), ...(put.batch_id ? { batch_id: put.batch_id } : {}) }); setPut({ ...put, quantity: '' }); setSuggest([]); }, 'Put away.')}>Put away</button>
        </div>
        {suggest.length ? <p>Try: {suggest.map((s) => <button key={s.bin_id} type="button" onClick={() => setPut({ ...put, bin_id: s.bin_id })}>{s.code}{s.already_holds_product ? ' (has it)' : ''}</button>)}</p> : null}
      </section>

      <section className="fs-box" aria-label="Move between bins">
        <div className="fs-cardhead"><h2>Move between bins</h2></div>
        <div className="fs-form">
          <label><span>From bin</span>
            <select value={open?.id || ''} onChange={(e) => { if (e.target.value) openBin(e.target.value); }} aria-label="Move from bin">
              <option value="">Open a bin above, or pick</option>{bins.map((b) => <option key={b.id} value={b.id}>{b.code}</option>)}
            </select>
          </label>
          <label><span>Item</span>
            <select value={`${mv.product_id}|${mv.batch_id}`} onChange={(e) => { const [p, b] = e.target.value.split('|'); setMv({ ...mv, product_id: p, batch_id: b }); }} aria-label="Move item">
              <option value="|">Pick an item</option>{(open?.items || []).map((i: Row) => <option key={`${i.product_id}|${i.batch_id || ''}`} value={`${i.product_id}|${i.batch_id || ''}`}>{i.product_name} {i.batch_number || ''} ({i.quantity})</option>)}
            </select>
          </label>
          <label><span>Quantity</span><input type="number" min="0" value={mv.quantity} onChange={(e) => setMv({ ...mv, quantity: e.target.value })} aria-label="Move quantity" /></label>
          <label><span>To bin</span>
            <select value={mv.to_bin_id} onChange={(e) => setMv({ ...mv, to_bin_id: e.target.value })} aria-label="Move to bin">
              <option value="">Pick a bin</option>{bins.filter((b) => b.is_active && b.id !== open?.id).map((b) => <option key={b.id} value={b.id}>{b.code}</option>)}
            </select>
          </label>
          <button type="button" className="fs-primary" disabled={busy || !open || !mv.product_id || !mv.to_bin_id || !(Number(mv.quantity) > 0)}
            onClick={() => run(async () => { await post('/fmcg/warehouse/move', { from_bin_id: open!.id, to_bin_id: mv.to_bin_id, product_id: mv.product_id, quantity: Number(mv.quantity), ...(mv.batch_id ? { batch_id: mv.batch_id } : {}) }); setMv({ ...mv, quantity: '' }); }, 'Moved.')}>Move</button>
        </div>
      </section>

      {report ? (
        <section className="fs-box fs-scroll" aria-label="Warehouse report">
          <div className="fs-cardhead"><h2>Warehouse report</h2></div>
          <table>
            <thead><tr><th>Warehouse</th><th>Bins</th><th>Empty</th><th>Units in bins</th><th>Capacity</th><th>Full</th></tr></thead>
            <tbody>
              {report.warehouses.map((w: Row) => (
                <tr key={w.warehouse_id}><td>{w.warehouse}</td><td className="fs-num">{w.bins}</td><td className="fs-num">{w.empty_bins}</td><td className="fs-num">{w.units_binned}</td><td className="fs-num">{w.capacity}</td><td className="fs-num">{w.utilisation_pct != null ? `${w.utilisation_pct}%` : '-'}</td></tr>
              ))}
              {report.warehouses.length === 0 ? <tr><td colSpan={6} className="fs-muted">No bins yet.</td></tr> : null}
            </tbody>
          </table>
          {report.waiting_for_put_away.length ? <p><strong>Waiting to be put away:</strong> {report.waiting_for_put_away.map((r: Row) => `${r.product} (${r.unplaced})`).join(', ')}</p> : null}
          {report.over_binned.length ? <p><span className="fs-flag">Check these</span> Bins hold more than the stock level: {report.over_binned.map((r: Row) => `${r.product} (+${r.over_by})`).join(', ')}. Count the bins to correct them.</p> : null}
        </section>
      ) : null}
    </div>
  );
}
