'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Tab = 'products' | 'catalog' | 'variants' | 'batches' | 'expiry';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function Page() {
  const [tab, setTab] = useState<Tab>('products');
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [brands, setBrands] = useState<any[]>([]);
  const [units, setUnits] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [variants, setVariants] = useState<any[]>([]);
  const [batches, setBatches] = useState<any[]>([]);
  const [expiring, setExpiring] = useState<any[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const [productName, setProductName] = useState('');
  const [productSku, setProductSku] = useState('');
  const [productPrice, setProductPrice] = useState('0');
  const [productCategoryId, setProductCategoryId] = useState('');
  const [productBrandId, setProductBrandId] = useState('');
  const [productUnitId, setProductUnitId] = useState('');

  const [catCode, setCatCode] = useState('');
  const [catName, setCatName] = useState('');
  const [catParentId, setCatParentId] = useState('');
  const [brandCode, setBrandCode] = useState('');
  const [brandName, setBrandName] = useState('');
  const [unitCode, setUnitCode] = useState('');
  const [unitName, setUnitName] = useState('');

  const [variantName, setVariantName] = useState('');
  const [variantSku, setVariantSku] = useState('');
  const [variantSize, setVariantSize] = useState('');
  const [batchNumber, setBatchNumber] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [stockQty, setStockQty] = useState('10');

  async function refresh() {
    const [p, e, c, b, u] = await Promise.all([
      api('/products'),
      api('/inventory/batches/expiring?days=60'),
      api('/catalog/categories'),
      api('/catalog/brands'),
      api('/catalog/units'),
    ]);
    setProducts(p.data || []);
    setExpiring(e.data?.batches || []);
    setCategories(c.data || []);
    setBrands(b.data || []);
    setUnits(u.data || []);
    if (!selectedId && p.data?.length) setSelectedId(p.data[0].id);
  }

  async function refreshSelected(id: string) {
    if (!id) return;
    const [v, b] = await Promise.all([
      api(`/products/${id}/variants`),
      api(`/products/${id}/batches`),
    ]);
    setVariants(v.data || []);
    setBatches(b.data || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (selectedId) refreshSelected(selectedId).catch((err) => setError(err.message));
  }, [selectedId]);

  async function createProduct() {
    setError('');
    try {
      const r = await api('/products', {
        method: 'POST',
        body: JSON.stringify({
          name: productName,
          sku: productSku,
          selling_price: Number(productPrice) || 0,
          category_id: productCategoryId || null,
          brand_id: productBrandId || null,
          unit_id: productUnitId || null,
        }),
      });
      setMessage(`Product ${r.data.sku} created`);
      setProductName('');
      setProductSku('');
      setProductPrice('0');
      await refresh();
      setSelectedId(r.data.id);
      setTab('products');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function uploadImage(file: File) {
    if (!selectedId) return;
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${apiBase}/products/${selectedId}/image`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || body.message || 'Upload failed');
      setMessage('Product image uploaded');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function addVariant() {
    setError('');
    try {
      const r = await api(`/products/${selectedId}/variants`, {
        method: 'POST',
        body: JSON.stringify({
          name: variantName,
          sku: variantSku,
          size: variantSize || undefined,
        }),
      });
      setMessage(`Variant ${r.data.sku} created`);
      setVariantName('');
      setVariantSku('');
      setVariantSize('');
      await refreshSelected(selectedId);
      setTab('variants');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function stockInBatch() {
    setError('');
    try {
      const r = await api('/inventory/stock-in', {
        method: 'POST',
        body: JSON.stringify({
          product_id: selectedId,
          quantity: Number(stockQty),
          batch_number: batchNumber,
          expiry_date: expiryDate ? new Date(expiryDate).toISOString() : undefined,
        }),
      });
      setMessage(`Stock in — on-hand ${r.data.stock_qty}`);
      setBatchNumber('');
      await refresh();
      await refreshSelected(selectedId);
      setTab('batches');
    } catch (err: any) {
      setError(err.message);
    }
  }

  const selected = products.find((p) => p.id === selectedId);

  return (
    <Shell>
      <h1>Inventory</h1>
      <p className="muted">Products, catalog, variants, batches &amp; expiry</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(
          [
            ['products', 'Products'],
            ['catalog', 'Catalog'],
            ['variants', 'Variants'],
            ['batches', 'Batches'],
            ['expiry', 'Expiring'],
          ] as const
        ).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} disabled={tab === id}>
            {label}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16, maxWidth: 480 }}>
        <label className="muted">Selected product</label>
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} style={{ width: '100%' }}>
          <option value="">Select product</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.sku}) — {p.stock_qty}
            </option>
          ))}
        </select>
        {selected?.has_image && <p className="muted">Has image</p>}
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          disabled={!selectedId}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) uploadImage(file);
            e.target.value = '';
          }}
        />
      </div>

      {tab === 'products' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 480 }}>
            <h3>Add product</h3>
            <input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="Name" />
            <input value={productSku} onChange={(e) => setProductSku(e.target.value)} placeholder="SKU" />
            <input value={productPrice} onChange={(e) => setProductPrice(e.target.value)} placeholder="Selling price" />
            <select value={productCategoryId} onChange={(e) => setProductCategoryId(e.target.value)}>
              <option value="">Category</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <select value={productBrandId} onChange={(e) => setProductBrandId(e.target.value)}>
              <option value="">Brand</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <select value={productUnitId} onChange={(e) => setProductUnitId(e.target.value)}>
              <option value="">Unit</option>
              {units.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.code} — {u.name}
                </option>
              ))}
            </select>
            <button onClick={createProduct} disabled={!productName || !productSku}>
              Create product
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>SKU</th>
                <th>Category</th>
                <th>Stock</th>
                <th>Batches?</th>
                <th>Price</th>
                <th>Image</th>
              </tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id}>
                  <td>
                    <button
                      onClick={() => setSelectedId(p.id)}
                      style={{ background: 'none', border: 0, color: '#1d4ed8', cursor: 'pointer' }}
                    >
                      {p.name}
                    </button>
                  </td>
                  <td>{p.sku}</td>
                  <td>{p.category}</td>
                  <td>{p.stock_qty}</td>
                  <td>{p.tracks_batches ? 'yes' : 'no'}</td>
                  <td>{p.selling_price}</td>
                  <td>{p.has_image ? 'yes' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'catalog' && (
        <div style={{ display: 'grid', gap: 16, maxWidth: 520 }}>
          <div className="card" style={{ display: 'grid', gap: 8 }}>
            <h3>Category</h3>
            <input value={catCode} onChange={(e) => setCatCode(e.target.value)} placeholder="Code" />
            <input value={catName} onChange={(e) => setCatName(e.target.value)} placeholder="Name" />
            <select value={catParentId} onChange={(e) => setCatParentId(e.target.value)}>
              <option value="">Parent (optional)</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <button
              onClick={async () => {
                setError('');
                try {
                  await api('/catalog/categories', {
                    method: 'POST',
                    body: JSON.stringify({
                      code: catCode,
                      name: catName,
                      parent_id: catParentId || null,
                    }),
                  });
                  setCatCode('');
                  setCatName('');
                  setCatParentId('');
                  setMessage('Category created');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              disabled={!catCode || !catName}
            >
              Add category
            </button>
            <ul className="muted">
              {categories.map((c) => (
                <li key={c.id}>
                  {c.code} — {c.name}
                  {c.parent_id ? ' (child)' : ''}
                </li>
              ))}
            </ul>
          </div>
          <div className="card" style={{ display: 'grid', gap: 8 }}>
            <h3>Brand</h3>
            <input value={brandCode} onChange={(e) => setBrandCode(e.target.value)} placeholder="Code" />
            <input value={brandName} onChange={(e) => setBrandName(e.target.value)} placeholder="Name" />
            <button
              onClick={async () => {
                setError('');
                try {
                  await api('/catalog/brands', {
                    method: 'POST',
                    body: JSON.stringify({ code: brandCode, name: brandName }),
                  });
                  setBrandCode('');
                  setBrandName('');
                  setMessage('Brand created');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              disabled={!brandCode || !brandName}
            >
              Add brand
            </button>
            <ul className="muted">
              {brands.map((b) => (
                <li key={b.id}>
                  {b.code} — {b.name}
                </li>
              ))}
            </ul>
          </div>
          <div className="card" style={{ display: 'grid', gap: 8 }}>
            <h3>Unit of measure</h3>
            <input value={unitCode} onChange={(e) => setUnitCode(e.target.value)} placeholder="Code" />
            <input value={unitName} onChange={(e) => setUnitName(e.target.value)} placeholder="Name" />
            <button
              onClick={async () => {
                setError('');
                try {
                  await api('/catalog/units', {
                    method: 'POST',
                    body: JSON.stringify({ code: unitCode, name: unitName }),
                  });
                  setUnitCode('');
                  setUnitName('');
                  setMessage('Unit created');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              disabled={!unitCode || !unitName}
            >
              Add unit
            </button>
            <ul className="muted">
              {units.map((u) => (
                <li key={u.id}>
                  {u.code} — {u.name}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {tab === 'variants' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 480 }}>
            <h3>Add variant</h3>
            <input value={variantName} onChange={(e) => setVariantName(e.target.value)} placeholder="Name" />
            <input value={variantSku} onChange={(e) => setVariantSku(e.target.value)} placeholder="SKU" />
            <input value={variantSize} onChange={(e) => setVariantSize(e.target.value)} placeholder="Size (optional)" />
            <button onClick={addVariant} disabled={!selectedId || !variantName || !variantSku}>
              Create variant
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>SKU</th>
                <th>Size</th>
                <th>Stock</th>
                <th>Price</th>
              </tr>
            </thead>
            <tbody>
              {variants.map((v) => (
                <tr key={v.id}>
                  <td>{v.name}</td>
                  <td>{v.sku}</td>
                  <td>{v.size || '—'}</td>
                  <td>{v.stock_qty}</td>
                  <td>{v.selling_price}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'batches' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 480 }}>
            <h3>Stock in with batch</h3>
            <input value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} placeholder="Batch number" />
            <input type="date" value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} />
            <input value={stockQty} onChange={(e) => setStockQty(e.target.value)} placeholder="Quantity" />
            <button onClick={stockInBatch} disabled={!selectedId || !batchNumber}>
              Receive batch
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Batch</th>
                <th>Qty</th>
                <th>Expiry</th>
                <th>Variant</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id}>
                  <td>{b.batch_number}</td>
                  <td>{b.quantity}</td>
                  <td>{b.expiry_date ? String(b.expiry_date).slice(0, 10) : '—'}</td>
                  <td>{b.variant_id || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'expiry' && (
        <table className="table">
          <thead>
            <tr>
              <th>Batch</th>
              <th>Product</th>
              <th>Qty</th>
              <th>Expiry</th>
            </tr>
          </thead>
          <tbody>
            {expiring.map((b) => (
              <tr key={b.id}>
                <td>{b.batch_number}</td>
                <td>{b.product_id}</td>
                <td>{b.quantity}</td>
                <td>{b.expiry_date ? String(b.expiry_date).slice(0, 10) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Shell>
  );
}
