'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Store = {
  id: string;
  code: string;
  name: string;
  address?: string;
  is_active?: boolean;
  drawer_mode?: string;
  drawer_host?: string | null;
  drawer_port?: number;
  drawer_open_on_cash?: boolean;
};
type Product = { id: string; name: string; sku: string; stock_qty: number };
type Transfer = {
  id: string;
  transfer_number: string;
  from_store_id: string;
  to_store_id: string;
  status: string;
  awaiting_approval?: string | null;
  fully_approved?: boolean;
  can_ship?: boolean;
  items: { product_id: string; quantity: number }[];
};

export default function Page() {
  const [stores, setStores] = useState<Store[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [inventory, setInventory] = useState<any[]>([]);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [fromStore, setFromStore] = useState('');
  const [toStore, setToStore] = useState('');
  const [productId, setProductId] = useState('');
  const [qty, setQty] = useState('1');
  const [viewStore, setViewStore] = useState('');
  const [reorderProductId, setReorderProductId] = useState('');
  const [reorderLevel, setReorderLevel] = useState('5');
  const [reorderQty, setReorderQty] = useState('20');
  const [fefoStrict, setFefoStrict] = useState(false);
  const [drawerStoreId, setDrawerStoreId] = useState('');
  const [drawerMode, setDrawerMode] = useState('mock');
  const [drawerHost, setDrawerHost] = useState('');
  const [drawerPort, setDrawerPort] = useState('9100');
  const [drawerOnCash, setDrawerOnCash] = useState(true);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function refresh() {
    const [s, p, t, settings] = await Promise.all([
      api('/stores'),
      api('/products'),
      api('/stores/transfers'),
      api('/inventory/settings').catch(() => ({ data: { fefo_strict_warehouse: false } })),
    ]);
    setStores(s.data || []);
    setProducts(p.data || []);
    setTransfers(t.data || []);
    setFefoStrict(!!settings.data?.fefo_strict_warehouse);
    if (!fromStore && s.data?.length) setFromStore(s.data[0].id);
    if (!toStore && s.data?.length > 1) setToStore(s.data[1].id);
    if (!productId && p.data?.length) setProductId(p.data[0].id);
    if (!reorderProductId && p.data?.length) setReorderProductId(p.data[0].id);
    if (!drawerStoreId && s.data?.length) {
      setDrawerStoreId(s.data[0].id);
      setDrawerMode(s.data[0].drawer_mode || 'none');
      setDrawerHost(s.data[0].drawer_host || '');
      setDrawerPort(String(s.data[0].drawer_port || 9100));
      setDrawerOnCash(s.data[0].drawer_open_on_cash !== false);
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function createStore() {
    setError('');
    try {
      await api('/stores', {
        method: 'POST',
        body: JSON.stringify({ code, name, address: address || undefined }),
      });
      setCode('');
      setName('');
      setAddress('');
      setMessage('Store created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveDrawerSettings() {
    if (!drawerStoreId) return;
    setError('');
    setMessage('');
    try {
      await api(`/stores/${drawerStoreId}/drawer`, {
        method: 'PATCH',
        body: JSON.stringify({
          drawer_mode: drawerMode,
          drawer_host: drawerHost || null,
          drawer_port: Number(drawerPort) || 9100,
          drawer_open_on_cash: drawerOnCash,
        }),
      });
      setMessage('Cash drawer settings saved');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadInventory(storeId: string) {
    setViewStore(storeId);
    setError('');
    try {
      const r = await api(`/stores/${storeId}/inventory?include_zero=true`);
      setInventory(r.data || []);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveReorder() {
    if (!viewStore || !reorderProductId) return;
    setError('');
    setMessage('');
    try {
      await api(`/stores/${viewStore}/reorder-policy`, {
        method: 'PUT',
        body: JSON.stringify({
          product_id: reorderProductId,
          reorder_level: Number(reorderLevel) || 0,
          reorder_qty: Number(reorderQty) || 0,
        }),
      });
      setMessage('Reorder policy saved');
      await loadInventory(viewStore);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function toggleFefo() {
    setError('');
    try {
      const next = !fefoStrict;
      const r = await api('/inventory/settings', {
        method: 'PATCH',
        body: JSON.stringify({ fefo_strict_warehouse: next }),
      });
      setFefoStrict(!!r.data?.fefo_strict_warehouse);
      setMessage(
        next
          ? 'FEFO strict warehouse mode on (no unassigned-batch fallback)'
          : 'FEFO strict warehouse mode off',
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createTransfer() {
    setError('');
    try {
      const r = await api('/stores/transfers', {
        method: 'POST',
        body: JSON.stringify({
          from_store_id: fromStore,
          to_store_id: toStore,
          submit: true,
          items: [{ product_id: productId, quantity: Number(qty) }],
        }),
      });
      setMessage(`Transfer ${r.data.transfer_number} requested`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function act(id: string, action: string) {
    setError('');
    try {
      const r = await api(`/stores/transfers/${id}/${action}`, { method: 'POST' });
      setMessage(`${r.data.transfer_number} → ${r.data.status}`);
      await refresh();
      if (viewStore) await loadInventory(viewStore);
    } catch (err: any) {
      setError(err.message);
    }
  }

  const storeName = (id: string) => stores.find((s) => s.id === id)?.name || id;

  return (
    <Shell>
      <h1>Multi-Store</h1>
      <p className="muted">Stores, warehouse reorder policies, FEFO mode, and transfers</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div className="card" style={{ marginBottom: 16 }}>
        <label className="muted">
          <input type="checkbox" checked={fefoStrict} onChange={() => toggleFefo()} /> FEFO
          strict warehouse (stock-out only from batches tagged to that warehouse)
        </label>
      </div>

      <div className="grid">
        <div className="card">
          <h3>New store</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Code" />
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" />
            <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Address" />
            <button onClick={createStore}>Create store</button>
          </div>
        </div>
        <div className="card">
          <h3>New transfer</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <select value={fromStore} onChange={(e) => setFromStore(e.target.value)}>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  From: {s.name}
                </option>
              ))}
            </select>
            <select value={toStore} onChange={(e) => setToStore(e.target.value)}>
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  To: {s.name}
                </option>
              ))}
            </select>
            <select value={productId} onChange={(e) => setProductId(e.target.value)}>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.stock_qty})
                </option>
              ))}
            </select>
            <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Qty" />
            <button onClick={createTransfer}>Create & request</button>
          </div>
        </div>
        <div className="card">
          <h3>Cash drawer</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            <select
              value={drawerStoreId}
              onChange={(e) => {
                const id = e.target.value;
                setDrawerStoreId(id);
                const s = stores.find((x) => x.id === id);
                if (s) {
                  setDrawerMode(s.drawer_mode || 'none');
                  setDrawerHost(s.drawer_host || '');
                  setDrawerPort(String(s.drawer_port || 9100));
                  setDrawerOnCash(s.drawer_open_on_cash !== false);
                }
              }}
            >
              {stores.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.drawer_mode || 'none'})
                </option>
              ))}
            </select>
            <select value={drawerMode} onChange={(e) => setDrawerMode(e.target.value)}>
              <option value="none">none (disabled)</option>
              <option value="mock">mock (log pulse)</option>
              <option value="network">network (ESC/POS TCP)</option>
              <option value="browser_bridge">browser_bridge (return kick bytes)</option>
            </select>
            {drawerMode === 'network' && (
              <>
                <input
                  value={drawerHost}
                  onChange={(e) => setDrawerHost(e.target.value)}
                  placeholder="Printer/drawer host"
                />
                <input
                  value={drawerPort}
                  onChange={(e) => setDrawerPort(e.target.value)}
                  placeholder="Port (9100)"
                />
              </>
            )}
            <label>
              <input
                type="checkbox"
                checked={drawerOnCash}
                onChange={(e) => setDrawerOnCash(e.target.checked)}
              />{' '}
              Open on cash POS sales
            </label>
            <button onClick={saveDrawerSettings} disabled={!drawerStoreId}>
              Save drawer settings
            </button>
          </div>
        </div>
      </div>

      <h3 style={{ marginTop: 16 }}>Stores</h3>
      <table className="table">
        <thead>
          <tr>
            <th>Code</th>
            <th>Name</th>
            <th>Address</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {stores.map((s) => (
            <tr key={s.id}>
              <td>{s.code}</td>
              <td>{s.name}</td>
              <td>{s.address || '—'}</td>
              <td>
                <button onClick={() => loadInventory(s.id)}>Inventory / reorder</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {viewStore && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Inventory · {storeName(viewStore)}</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            <select value={reorderProductId} onChange={(e) => setReorderProductId(e.target.value)}>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <input
              value={reorderLevel}
              onChange={(e) => setReorderLevel(e.target.value)}
              placeholder="Reorder level"
              style={{ width: 110 }}
            />
            <input
              value={reorderQty}
              onChange={(e) => setReorderQty(e.target.value)}
              placeholder="Reorder qty"
              style={{ width: 110 }}
            />
            <button onClick={saveReorder}>Save policy</button>
          </div>
          {inventory.length === 0 && <p className="muted">No warehouse stock / policy rows yet</p>}
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Qty</th>
                <th>Reorder</th>
                <th>Suggest</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {inventory.map((i) => (
                <tr key={i.product_id}>
                  <td>
                    {i.name} ({i.sku})
                  </td>
                  <td>{i.quantity}</td>
                  <td>
                    {i.reorder_level} / {i.reorder_qty}
                  </td>
                  <td>{i.suggested_order_qty ?? '—'}</td>
                  <td>{i.below_reorder ? 'LOW' : 'ok'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3 style={{ marginTop: 16 }}>Transfers</h3>
      <p className="muted">
        Dual approval: source store manager → destination store manager, then ship / receive.
      </p>
      <table className="table">
        <thead>
          <tr>
            <th>Number</th>
            <th>From</th>
            <th>To</th>
            <th>Status</th>
            <th>Approval</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {transfers.map((t) => (
            <tr key={t.id}>
              <td>{t.transfer_number}</td>
              <td>{storeName(t.from_store_id)}</td>
              <td>{storeName(t.to_store_id)}</td>
              <td>{t.status}</td>
              <td>
                {t.status === 'requested'
                  ? t.fully_approved
                    ? 'Ready to ship'
                    : t.awaiting_approval === 'dest'
                      ? 'Awaiting dest'
                      : 'Awaiting source'
                  : '—'}
              </td>
              <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {t.status === 'draft' && (
                  <button type="button" onClick={() => act(t.id, 'submit')}>
                    Submit
                  </button>
                )}
                {t.status === 'requested' && !t.fully_approved && (
                  <>
                    <button type="button" onClick={() => act(t.id, 'approve')}>
                      Approve {t.awaiting_approval === 'dest' ? 'dest' : 'source'}
                    </button>
                    <button type="button" onClick={() => act(t.id, 'reject')}>
                      Reject
                    </button>
                  </>
                )}
                {t.can_ship && (
                  <button type="button" onClick={() => act(t.id, 'ship')}>
                    Ship
                  </button>
                )}
                {t.status === 'in_transit' && (
                  <button type="button" onClick={() => act(t.id, 'receive')}>
                    Receive
                  </button>
                )}
                {['draft', 'requested', 'in_transit'].includes(t.status) && (
                  <button type="button" onClick={() => act(t.id, 'cancel')}>
                    Cancel
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Shell>
  );
}
