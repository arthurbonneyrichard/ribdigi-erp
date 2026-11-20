'use client';

/**
 * FMCG quality: proof of delivery (signature pad, photo, location), goods inspections that can
 * hold a batch, supplier quality history and customer complaints. Rules live on the server.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { enqueue, looksOffline, type OfflineKind } from '../../../lib/fmcgOffline';
import FmcgOfflineBar from '../../../components/FmcgOfflineBar';
import { FmcgHead } from './FmcgSelling';
import './fmcg-selling.css';

type Row = Record<string, any>;

export const QUALITY_TABS = ['pod', 'quality', 'complaints'];
const MANAGERS = ['company_admin', 'fmcg_manager', 'super_admin', 'fmcg_quality'];
const CATEGORIES = [
  { id: 'quality', label: 'Quality' }, { id: 'damaged', label: 'Arrived damaged' }, { id: 'short', label: 'Short delivery' },
  { id: 'wrong', label: 'Wrong product' }, { id: 'expiry', label: 'Expiry date' }, { id: 'other', label: 'Other' },
];
const problem = (err: unknown) => (err as { message?: string } | null)?.message || 'Something went wrong. Try again.';

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(new Error('Could not read that photo'));
    r.readAsDataURL(file);
  });
}

/** A small finger or mouse signature pad. Reports a PNG data URL, or '' when empty. */
function SignaturePad({ onChange }: { onChange: (png: string) => void }) {
  const ref = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const inked = useRef(false);

  const point = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    return { x: ((e.clientX - box.left) / box.width) * e.currentTarget.width, y: ((e.clientY - box.top) / box.height) * e.currentTarget.height };
  };
  const down = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const ctx = e.currentTarget.getContext('2d');
    if (!ctx) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drawing.current = true;
    const p = point(e);
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.strokeStyle = '#10211B';
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
  };
  const move = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const ctx = e.currentTarget.getContext('2d');
    if (!ctx) return;
    const p = point(e);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    inked.current = true;
  };
  const up = (e: React.PointerEvent<HTMLCanvasElement>) => {
    drawing.current = false;
    if (inked.current) onChange(e.currentTarget.toDataURL('image/png'));
  };
  const clear = () => {
    const c = ref.current;
    c?.getContext('2d')?.clearRect(0, 0, c.width, c.height);
    inked.current = false;
    onChange('');
  };
  return (
    <div>
      <canvas ref={ref} width={480} height={160} aria-label="Signature pad"
        style={{ width: '100%', maxWidth: 480, border: '1px solid var(--fs-line)', borderRadius: 12, background: '#fff', touchAction: 'none' }}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerLeave={up} />
      <button type="button" onClick={clear} aria-label="Clear signature">Clear</button>
    </div>
  );
}

export default function FmcgQuality({ tab }: { tab: string }) {
  const [role, setRole] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const manager = MANAGERS.includes(role);

  const [tenant, setTenant] = useState('');
  const [tick, setTick] = useState(0);
  const queued = useRef(false);

  /** Send now; if the network is down, keep it on this device to send later. Server refusals still show as errors. */
  async function sendOrQueue(kind: OfflineKind, path: string, body: Record<string, any>, label: string, extra: Record<string, any> = {}) {
    try {
      await api(path, { method: 'POST', body: JSON.stringify(body) });
    } catch (err) {
      if (!tenant || !looksOffline(err)) throw err;
      await enqueue(tenant, kind, { ...extra, ...body }, label);
      queued.current = true;
      setTick((t) => t + 1);
    }
  }

  const [missing, setMissing] = useState<Row[]>([]);
  const [podOrder, setPodOrder] = useState('');
  const [pod, setPod] = useState({ recipient_name: '', notes: '' });
  const [sig, setSig] = useState('');
  const [photo, setPhoto] = useState('');
  const [sigKey, setSigKey] = useState(0);

  const [inspections, setInspections] = useState<Row[]>([]);
  const [suppliers, setSuppliers] = useState<Row[]>([]);
  const [products, setProducts] = useState<Row[]>([]);
  const [batches, setBatches] = useState<Row[]>([]);
  const [form, setForm] = useState({ product_id: '', batch_id: '', packaging_ok: 'yes', label_ok: 'yes', expiry_ok: 'yes', temperature_c: '', hold: true, notes: '' });
  const [deciding, setDeciding] = useState<Row | null>(null);
  const [decision, setDecision] = useState({ result: 'pass', note: '', rejected_qty: '' });

  const [complaints, setComplaints] = useState<Row[]>([]);
  const [cform, setCform] = useState({ category: 'quality', description: '', product_id: '', batch_id: '' });
  const [resolving, setResolving] = useState<Row | null>(null);
  const [resolution, setResolution] = useState('');

  useEffect(() => {
    getMe().then((me: Row | null) => { setRole(String(me?.data?.role || '')); setTenant(String(me?.data?.tenant_id || '')); }).catch(() => setRole(''));
  }, []);

  const load = useCallback(async () => {
    setError('');
    try {
      if (tab === 'pod') setMissing((await api('/fmcg/pod/missing'))?.data || []);
      if (tab === 'quality' && manager) {
        const [i, s, p, b] = await Promise.all([
          api('/fmcg/quality/inspections'), api('/fmcg/quality/suppliers'), api('/products'), api('/fmcg/batches?status=all'),
        ]);
        setInspections(i?.data || []);
        setSuppliers(s?.data || []);
        setProducts(Array.isArray(p?.data) ? p.data : []);
        setBatches(b?.data?.batches || []);
      }
      if (tab === 'complaints') {
        setComplaints((await api('/fmcg/complaints'))?.data || []);
        const p = await api('/products').catch(() => null);
        setProducts(Array.isArray(p?.data) ? p.data : []);
        if (manager) setBatches((await api('/fmcg/batches?status=all'))?.data?.batches || []);
      }
    } catch (err) {
      setError(problem(err));
    }
  }, [tab, manager]);

  useEffect(() => {
    if (role) load();
  }, [role, load]);

  async function run(fn: () => Promise<unknown>, done: string) {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      queued.current = false;
      await fn();
      if (queued.current) {
        setNotice('Saved on this device. It will be sent when you are back online.');
      } else {
        setNotice(done);
        await load();
      }
    } catch (err) {
      setError(problem(err));
    } finally {
      setBusy(false);
    }
  }
  const post = (path: string, body: unknown) => api(path, { method: 'POST', body: JSON.stringify(body) });
  const yesNo = (v: string) => (v === 'yes' ? true : v === 'no' ? false : null);

  async function savePod() {
    await run(async () => {
      let fix: { latitude: number; longitude: number; accuracy_m: number } | null = null;
      if (typeof navigator !== 'undefined' && navigator.geolocation) {
        fix = await new Promise((resolve) =>
          navigator.geolocation.getCurrentPosition(
            (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy_m: Math.round(p.coords.accuracy) }),
            () => resolve(null),
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
          ),
        );
      }
      await sendOrQueue('pod', `/fmcg/orders/${podOrder}/pod`, {
        recipient_name: pod.recipient_name.trim(),
        ...(sig ? { signature: sig } : {}), ...(photo ? { photo } : {}),
        ...(pod.notes.trim().length >= 3 ? { notes: pod.notes.trim() } : {}), ...(fix || {}),
      }, `${missing.find((o) => o.order_id === podOrder)?.order_number || 'order'} signed by ${pod.recipient_name.trim()}`, { order_id: podOrder });
      setPodOrder('');
      setPod({ recipient_name: '', notes: '' });
      setSig('');
      setPhoto('');
      setSigKey((k) => k + 1);
    }, 'Proof of delivery saved.');
  }

  const batchOptions = batches.filter((b) => !form.product_id || b.product_id === form.product_id);
  const cBatchOptions = batches.filter((b) => !cform.product_id || b.product_id === cform.product_id);

  return (
    <div className="fmcg-sell">
      <FmcgHead tab={tab} />
      <FmcgOfflineBar tenant={tenant} tick={tick} onSynced={load} />
      {notice ? <div className="fs-banner" role="status">{notice}</div> : null}
      {error ? <div className="fs-banner bad" role="alert">{error}</div> : null}

      {tab === 'pod' ? (
        <>
          <section className="fs-box fs-scroll" aria-label="Delivered without proof">
            <div className="fs-cardhead"><h2>Delivered, no proof yet</h2></div>
            <table>
              <thead><tr><th>Order</th><th>Outlet</th><th>Delivered</th><th /></tr></thead>
              <tbody>
                {missing.map((o) => (
                  <tr key={o.order_id}>
                    <td>{o.order_number}</td><td>{o.outlet}</td><td>{(o.delivered_at || '').slice(0, 16).replace('T', ' ')}</td>
                    <td><button type="button" aria-label={`Take proof for ${o.order_number}`} onClick={() => setPodOrder(o.order_id)}>Take proof</button></td>
                  </tr>
                ))}
                {missing.length === 0 ? <tr><td colSpan={4} className="fs-muted">Every recent delivery has proof.</td></tr> : null}
              </tbody>
            </table>
          </section>
          {podOrder ? (
            <section className="fs-box" aria-label="Capture proof">
              <div className="fs-cardhead"><h2>Proof for {missing.find((o) => o.order_id === podOrder)?.order_number}</h2></div>
              <div className="fs-form">
                <label><span>Who received it</span><input value={pod.recipient_name} onChange={(e) => setPod({ ...pod, recipient_name: e.target.value })} aria-label="Recipient name" /></label>
                <label><span>Note (optional)</span><input value={pod.notes} onChange={(e) => setPod({ ...pod, notes: e.target.value })} aria-label="Delivery note" /></label>
              </div>
              <p>Signature</p>
              <SignaturePad key={sigKey} onChange={setSig} />
              <div className="fs-form">
                <label><span>Photo (optional)</span>
                  <input type="file" accept="image/png,image/jpeg" capture="environment" aria-label="Delivery photo"
                    onChange={async (e) => { const f = e.target.files?.[0]; if (!f) return setPhoto(''); try { setPhoto(await readFile(f)); } catch (err) { setError(problem(err)); } }} />
                </label>
                <button type="button" className="fs-primary" disabled={busy || pod.recipient_name.trim().length < 2 || (!sig && !photo)} onClick={savePod}>Save proof</button>
                <button type="button" disabled={busy} onClick={() => setPodOrder('')}>Cancel</button>
              </div>
              <p className="fs-muted">Uses your location when you allow it. A photo over 800 KB is refused: use a lower photo size.</p>
            </section>
          ) : null}
        </>
      ) : null}

      {tab === 'quality' && !manager && role ? <div className="fs-banner">Inspections are done by a manager.</div> : null}
      {tab === 'quality' && manager ? (
        <>
          <section className="fs-box" aria-label="New inspection">
            <div className="fs-cardhead"><h2>New inspection</h2></div>
            <div className="fs-form">
              <label><span>Product</span>
                <select value={form.product_id} onChange={(e) => setForm({ ...form, product_id: e.target.value, batch_id: '' })} aria-label="Inspection product">
                  <option value="">Pick a product</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              <label><span>Batch</span>
                <select value={form.batch_id} onChange={(e) => setForm({ ...form, batch_id: e.target.value })} aria-label="Inspection batch">
                  <option value="">No batch</option>{batchOptions.map((b) => <option key={b.id} value={b.id}>{b.batch_number} ({b.quantity})</option>)}
                </select>
              </label>
              {(['packaging_ok', 'label_ok', 'expiry_ok'] as const).map((k) => (
                <label key={k}><span>{k === 'packaging_ok' ? 'Packaging' : k === 'label_ok' ? 'Label' : 'Expiry date'}</span>
                  <select value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} aria-label={`Inspection ${k}`}>
                    <option value="yes">OK</option><option value="no">Not OK</option><option value="na">Not checked</option>
                  </select>
                </label>
              ))}
              <label><span>Temperature °C</span><input type="number" value={form.temperature_c} onChange={(e) => setForm({ ...form, temperature_c: e.target.value })} aria-label="Inspection temperature" /></label>
              <label><span>Notes</span><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} aria-label="Inspection notes" /></label>
              <label><span>Hold the batch until decided</span>
                <input type="checkbox" checked={form.hold} onChange={(e) => setForm({ ...form, hold: e.target.checked })} aria-label="Hold batch until decided" disabled={!form.batch_id} />
              </label>
              <button type="button" className="fs-primary" disabled={busy || !form.product_id}
                onClick={() => run(() => post('/fmcg/quality/inspections', {
                  product_id: form.product_id, ...(form.batch_id ? { batch_id: form.batch_id, hold_until_decided: form.hold } : {}),
                  packaging_ok: yesNo(form.packaging_ok), label_ok: yesNo(form.label_ok), expiry_ok: yesNo(form.expiry_ok),
                  ...(form.temperature_c !== '' ? { temperature_c: Number(form.temperature_c) } : {}),
                  ...(form.notes.trim().length >= 3 ? { notes: form.notes.trim() } : {}),
                }), 'Inspection opened.')}>Open inspection</button>
            </div>
          </section>

          {deciding ? (
            <section className="fs-box" aria-label="Decide inspection">
              <div className="fs-cardhead"><h2>Decide {deciding.inspection_number}</h2></div>
              <div className="fs-form">
                <label><span>Result</span>
                  <select value={decision.result} onChange={(e) => setDecision({ ...decision, result: e.target.value })} aria-label="Inspection result">
                    <option value="pass">Pass</option><option value="conditional">Pass with conditions</option><option value="fail">Fail</option>
                  </select>
                </label>
                {decision.result === 'fail' ? <label><span>Quantity rejected</span><input type="number" min="0" value={decision.rejected_qty} onChange={(e) => setDecision({ ...decision, rejected_qty: e.target.value })} aria-label="Rejected quantity" /></label> : null}
                <label><span>{decision.result === 'pass' ? 'Note (optional)' : 'Why'}</span><input value={decision.note} onChange={(e) => setDecision({ ...decision, note: e.target.value })} aria-label="Decision note" /></label>
                <button type="button" className="fs-primary" disabled={busy || (decision.result !== 'pass' && decision.note.trim().length < 3)}
                  onClick={() => run(async () => { await post(`/fmcg/quality/inspections/${deciding.id}/decide`, { result: decision.result, ...(decision.note.trim() ? { note: decision.note.trim() } : {}), ...(decision.result === 'fail' && Number(decision.rejected_qty) > 0 ? { rejected_qty: Number(decision.rejected_qty) } : {}) }); setDeciding(null); setDecision({ result: 'pass', note: '', rejected_qty: '' }); }, 'Decision saved.')}>Save decision</button>
                <button type="button" disabled={busy} onClick={() => setDeciding(null)}>Cancel</button>
              </div>
              <p className="fs-muted">A failed batch stays on hold. Write it off or return it from Batches and expiry.</p>
            </section>
          ) : null}

          <section className="fs-box fs-scroll" aria-label="Inspections">
            <table>
              <thead><tr><th>No.</th><th>Product</th><th>Batch</th><th>Status</th><th>Held</th><th /></tr></thead>
              <tbody>
                {inspections.map((i) => (
                  <tr key={i.id}>
                    <td>{i.inspection_number}</td><td>{i.product_name}</td><td>{i.batch_number || '-'}</td>
                    <td>{i.status === 'failed' ? <span className="fs-flag">Failed</span> : i.status}</td><td>{i.held ? 'Yes' : '-'}</td>
                    <td>{i.status === 'pending' ? <button type="button" aria-label={`Decide inspection ${i.inspection_number}`} onClick={() => setDeciding(i)}>Decide</button> : null}</td>
                  </tr>
                ))}
                {inspections.length === 0 ? <tr><td colSpan={6} className="fs-muted">No inspections yet.</td></tr> : null}
              </tbody>
            </table>
          </section>

          <section className="fs-box fs-scroll" aria-label="Supplier quality">
            <div className="fs-cardhead"><h2>Supplier quality</h2></div>
            <table>
              <thead><tr><th>Supplier</th><th>Inspected</th><th>Passed</th><th>Conditional</th><th>Failed</th><th>Fail rate</th></tr></thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.supplier_id}><td>{s.supplier}</td><td className="fs-num">{s.inspected}</td><td className="fs-num">{s.passed}</td><td className="fs-num">{s.conditional}</td><td className="fs-num">{s.failed}</td><td className="fs-num">{s.fail_rate_pct}%</td></tr>
                ))}
                {suppliers.length === 0 ? <tr><td colSpan={6} className="fs-muted">Pick a supplier when you inspect goods to build their history.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}

      {tab === 'complaints' ? (
        <>
          <section className="fs-box" aria-label="Log a complaint">
            <div className="fs-cardhead"><h2>Log a complaint</h2></div>
            <div className="fs-form">
              <label><span>Kind</span>
                <select value={cform.category} onChange={(e) => setCform({ ...cform, category: e.target.value })} aria-label="Complaint kind">
                  {CATEGORIES.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
              </label>
              <label><span>Product</span>
                <select value={cform.product_id} onChange={(e) => setCform({ ...cform, product_id: e.target.value, batch_id: '' })} aria-label="Complaint product">
                  <option value="">Not sure</option>{products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </label>
              {manager ? (
                <label><span>Batch</span>
                  <select value={cform.batch_id} onChange={(e) => setCform({ ...cform, batch_id: e.target.value })} aria-label="Complaint batch" disabled={!cform.product_id}>
                    <option value="">Unknown</option>{cBatchOptions.map((b) => <option key={b.id} value={b.id}>{b.batch_number}</option>)}
                  </select>
                </label>
              ) : null}
              <label><span>What happened</span><input value={cform.description} onChange={(e) => setCform({ ...cform, description: e.target.value })} aria-label="Complaint description" /></label>
              <button type="button" className="fs-primary" disabled={busy || cform.description.trim().length < 3}
                onClick={() => run(async () => { await sendOrQueue('complaint', '/fmcg/complaints', { category: cform.category, description: cform.description.trim(), ...(cform.product_id ? { product_id: cform.product_id } : {}), ...(cform.batch_id ? { batch_id: cform.batch_id } : {}) }, cform.description.trim().slice(0, 40)); setCform({ ...cform, description: '' }); }, 'Complaint logged.')}>Log complaint</button>
            </div>
          </section>

          {resolving ? (
            <section className="fs-box" aria-label="Close complaint">
              <div className="fs-cardhead"><h2>{resolving.complaint_number}</h2></div>
              <div className="fs-form">
                <label><span>What was done</span><input value={resolution} onChange={(e) => setResolution(e.target.value)} aria-label="Complaint resolution" /></label>
                <button type="button" className="fs-primary" disabled={busy || resolution.trim().length < 3}
                  onClick={() => run(async () => { await post(`/fmcg/complaints/${resolving.id}/status`, { status: 'resolved', resolution: resolution.trim() }); setResolving(null); setResolution(''); }, 'Complaint resolved.')}>Resolve</button>
                <button type="button" className="fs-danger" disabled={busy || resolution.trim().length < 3}
                  onClick={() => run(async () => { await post(`/fmcg/complaints/${resolving.id}/status`, { status: 'rejected', resolution: resolution.trim() }); setResolving(null); setResolution(''); }, 'Complaint rejected.')}>Reject</button>
                <button type="button" disabled={busy} onClick={() => setResolving(null)}>Cancel</button>
              </div>
            </section>
          ) : null}

          <section className="fs-box fs-scroll" aria-label="Complaints">
            <table>
              <thead><tr><th>No.</th><th>Outlet</th><th>Product</th><th>Batch</th><th>Kind</th><th>Status</th><th /></tr></thead>
              <tbody>
                {complaints.map((c) => (
                  <tr key={c.id}>
                    <td>{c.complaint_number}</td><td>{c.outlet || '-'}</td><td>{c.product_name || '-'}</td>
                    <td>{c.batch_number ? <>{c.batch_number}{c.complaints_on_this_batch > 1 ? <span className="fs-flag">{c.complaints_on_this_batch} complaints</span> : null}</> : '-'}</td>
                    <td>{c.category}</td><td>{c.status}</td>
                    <td>
                      {manager && c.status === 'open' ? <button type="button" aria-label={`Investigate ${c.complaint_number}`} disabled={busy} onClick={() => run(() => post(`/fmcg/complaints/${c.id}/status`, { status: 'investigating' }), 'Marked as being looked at.')}>Investigate</button> : null}{' '}
                      {manager && (c.status === 'open' || c.status === 'investigating') ? <button type="button" aria-label={`Close ${c.complaint_number}`} onClick={() => setResolving(c)}>Close</button> : null}
                    </td>
                  </tr>
                ))}
                {complaints.length === 0 ? <tr><td colSpan={7} className="fs-muted">No complaints.</td></tr> : null}
              </tbody>
            </table>
          </section>
        </>
      ) : null}
    </div>
  );
}
