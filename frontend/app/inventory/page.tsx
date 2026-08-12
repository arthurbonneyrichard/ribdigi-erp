'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Tab = 'products' | 'import' | 'catalog' | 'variants' | 'batches' | 'expiry' | 'counts';

type ImportReportRow = {
  line: number;
  sku: string;
  name: string;
  ok: boolean;
  errors: string[];
};

type ImportReport = {
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  can_commit: boolean;
  imported?: number;
  rows: ImportReportRow[];
  created?: any[];
};

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function Page() {
  const [tab, setTab] = useState<Tab>('products');
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [brands, setBrands] = useState<any[]>([]);
  const [units, setUnits] = useState<any[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [variants, setVariants] = useState<any[]>([]);
  const [gallery, setGallery] = useState<any[]>([]);
  const [batches, setBatches] = useState<any[]>([]);
  const [expiring, setExpiring] = useState<any[]>([]);
  const [counts, setCounts] = useState<any[]>([]);
  const [activeCount, setActiveCount] = useState<any | null>(null);
  const [countWarehouseId, setCountWarehouseId] = useState('');
  const [countQtys, setCountQtys] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const [productName, setProductName] = useState('');
  const [productSku, setProductSku] = useState('');
  const [productPrice, setProductPrice] = useState('0');
  const [productCategoryId, setProductCategoryId] = useState('');
  const [productBrandId, setProductBrandId] = useState('');
  const [productUnitId, setProductUnitId] = useState('');
  const [editReorder, setEditReorder] = useState('0');
  const [editPrice, setEditPrice] = useState('0');
  const [editBarcode, setEditBarcode] = useState('');
  const [productBarcode, setProductBarcode] = useState('');
  const [productSupplyClass, setProductSupplyClass] = useState('standard');
  const [editSupplyClass, setEditSupplyClass] = useState('standard');
  const [labelCopies, setLabelCopies] = useState('1');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importReport, setImportReport] = useState<ImportReport | null>(null);
  const [importBusy, setImportBusy] = useState(false);

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
    const [p, e, c, b, u, w, sc] = await Promise.all([
      api('/products'),
      api('/inventory/batches/expiring?days=60'),
      api('/catalog/categories'),
      api('/catalog/brands'),
      api('/catalog/units'),
      api('/warehouses'),
      api('/inventory/stock-counts'),
    ]);
    setProducts(p.data || []);
    setExpiring(e.data?.batches || []);
    setCategories(c.data || []);
    setBrands(b.data || []);
    setUnits(u.data || []);
    setWarehouses(w.data || []);
    setCounts(sc.data || []);
    if (!selectedId && p.data?.length) setSelectedId(p.data[0].id);
    if (!countWarehouseId && w.data?.length) setCountWarehouseId(w.data[0].id);
  }

  async function refreshSelected(id: string) {
    if (!id) return;
    const [v, b, g] = await Promise.all([
      api(`/products/${id}/variants`),
      api(`/products/${id}/batches`),
      api(`/products/${id}/images`),
    ]);
    setVariants(v.data || []);
    setBatches(b.data || []);
    setGallery(g.data || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (selectedId) {
      refreshSelected(selectedId).catch((err) => setError(err.message));
      const p = products.find((x) => x.id === selectedId);
      if (p) {
        setEditReorder(String(p.reorder_level ?? 0));
        setEditPrice(String(p.selling_price ?? 0));
        setEditBarcode(String(p.barcode || ''));
        setEditSupplyClass(String(p.tax_supply_class || (p.tax_exempt ? 'exempt' : 'standard')));
      }
    }
  }, [selectedId, products]);

  async function saveProductEdits() {
    if (!selectedId) return;
    setError('');
    try {
      await api(`/products/${selectedId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          reorder_level: Number(editReorder) || 0,
          selling_price: Number(editPrice) || 0,
          barcode: editBarcode.trim() || null,
          tax_supply_class: editSupplyClass,
        }),
      });
      setMessage('Product updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function generateBarcode() {
    if (!selectedId) return;
    setError('');
    try {
      const r = await api(`/products/${selectedId}/barcode/generate`, { method: 'POST', body: '{}' });
      setEditBarcode(r.data?.barcode || '');
      setMessage(`Barcode set to ${r.data?.barcode}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function printBarcodeLabel() {
    if (!selectedId) return;
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const copies = Math.max(1, Math.min(40, Number(labelCopies) || 1));
      const res = await fetch(
        `${apiBase}/products/${selectedId}/barcode/label?copies=${copies}`,
        {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
          },
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Label failed');
      }
      const html = await res.text();
      const blob = new Blob([html], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const w = window.open(url, '_blank', 'noopener,noreferrer,width=720,height=640');
      if (!w) {
        URL.revokeObjectURL(url);
        throw new Error('Pop-up blocked — allow pop-ups to print labels');
      }
      // Revoke after the new tab has a chance to load the blob.
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      setMessage('Barcode label opened — use Print labels');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function startStockCount() {
    setError('');
    try {
      const r = await api('/inventory/stock-counts', {
        method: 'POST',
        body: JSON.stringify({ warehouse_id: countWarehouseId }),
      });
      setActiveCount(r.data);
      const qtys: Record<string, string> = {};
      for (const item of r.data.items || []) {
        qtys[item.product_id] = String(item.expected_qty ?? 0);
      }
      setCountQtys(qtys);
      setMessage(`Count ${r.data.count_number} created`);
      setTab('counts');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function openCount(id: string) {
    setError('');
    try {
      const r = await api(`/inventory/stock-counts/${id}`);
      setActiveCount(r.data);
      const qtys: Record<string, string> = {};
      for (const item of r.data.items || []) {
        qtys[item.product_id] =
          item.counted_qty == null ? String(item.expected_qty ?? 0) : String(item.counted_qty);
      }
      setCountQtys(qtys);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveCountLines() {
    if (!activeCount) return;
    setError('');
    try {
      const items = (activeCount.items || []).map((item: any) => ({
        product_id: item.product_id,
        counted_qty: Number(countQtys[item.product_id] ?? item.expected_qty ?? 0),
      }));
      const r = await api(`/inventory/stock-counts/${activeCount.id}/items`, {
        method: 'PATCH',
        body: JSON.stringify({ items }),
      });
      setActiveCount(r.data);
      setMessage('Count lines saved');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function completeActiveCount() {
    if (!activeCount) return;
    setError('');
    try {
      await saveCountLines();
      const r = await api(`/inventory/stock-counts/${activeCount.id}/complete`, { method: 'POST' });
      setActiveCount(r.data);
      setMessage(`Count ${r.data.count_number} completed`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createProduct() {
    setError('');
    try {
      const r = await api('/products', {
        method: 'POST',
        body: JSON.stringify({
          name: productName,
          sku: productSku,
          barcode: productBarcode.trim() || null,
          selling_price: Number(productPrice) || 0,
          category_id: productCategoryId || null,
          brand_id: productBrandId || null,
          unit_id: productUnitId || null,
          tax_supply_class: productSupplyClass,
        }),
      });
      setMessage(`Product ${r.data.sku} created`);
      setProductName('');
      setProductSku('');
      setProductBarcode('');
      setProductPrice('0');
      setProductSupplyClass('standard');
      await refresh();
      setSelectedId(r.data.id);
      setTab('products');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function downloadImportTemplate() {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/products/import/template`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Template download failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'products-import-template.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('CSV template downloaded');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function runProductImport(dryRun: boolean) {
    if (!importFile) {
      setError('Choose a CSV file first');
      return;
    }
    setError('');
    setMessage('');
    setImportBusy(true);
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', importFile);
      const res = await fetch(
        `${apiBase}/products/import?dry_run=${dryRun ? 'true' : 'false'}`,
        {
          method: 'POST',
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
          },
          body: form,
        }
      );
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = body.detail;
        if (detail && typeof detail === 'object' && detail.report) {
          setImportReport(detail.report);
          throw new Error(detail.message || 'Import validation failed');
        }
        throw new Error(
          typeof detail === 'string'
            ? detail
            : detail?.message || body.message || 'Import failed'
        );
      }
      setImportReport(body.data as ImportReport);
      if (dryRun) {
        setMessage(
          body.data?.can_commit
            ? `Validation OK — ${body.data.valid_rows} row(s) ready to import`
            : `Validation found ${body.data?.error_rows || 0} error row(s)`
        );
      } else {
        setMessage(`Imported ${body.data?.imported || 0} product(s)`);
        setImportFile(null);
        await refresh();
        setTab('products');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setImportBusy(false);
    }
  }

  async function uploadImage(file: File, opts?: { asPrimary?: boolean }) {
    const asPrimary = Boolean(opts?.asPrimary);
    if (!selectedId) return;
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', file);
      const path = asPrimary
        ? `${apiBase}/products/${selectedId}/image`
        : `${apiBase}/products/${selectedId}/images`;
      const res = await fetch(path, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || body.message || 'Upload failed');
      setMessage(asPrimary ? 'Primary product image uploaded' : 'Gallery image added');
      await refresh();
      await refreshSelected(selectedId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setPrimaryImage(imageId: string) {
    if (!selectedId) return;
    setError('');
    try {
      await api(`/products/${selectedId}/images/${imageId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_primary: true }),
      });
      setMessage('Primary image updated');
      await refresh();
      await refreshSelected(selectedId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeGalleryImage(imageId: string) {
    if (!selectedId) return;
    setError('');
    try {
      await api(`/products/${selectedId}/images/${imageId}`, { method: 'DELETE' });
      setMessage('Image removed');
      await refresh();
      await refreshSelected(selectedId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deactivateVariant(variantId: string) {
    if (!selectedId) return;
    setError('');
    try {
      await api(`/products/${selectedId}/variants/${variantId}`, { method: 'DELETE' });
      setMessage('Variant deactivated');
      await refreshSelected(selectedId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveVariantPrice(variantId: string, price: string) {
    if (!selectedId) return;
    setError('');
    try {
      await api(`/products/${selectedId}/variants/${variantId}`, {
        method: 'PATCH',
        body: JSON.stringify({ selling_price: Number(price) || 0 }),
      });
      setMessage('Variant updated');
      await refreshSelected(selectedId);
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
      <p className="muted">Products, catalog, variants, batches, expiry &amp; stock counts</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(
          [
            ['products', 'Products'],
            ['import', 'Import'],
            ['catalog', 'Catalog'],
            ['variants', 'Variants'],
            ['batches', 'Batches'],
            ['expiry', 'Expiring'],
            ['counts', 'Stock counts'],
          ] as const
        ).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} disabled={tab === id}>
            {label}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <label className="muted">Selected product</label>
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} style={{ width: '100%' }}>
          <option value="">Select product</option>
          {products.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.sku}) — {p.stock_qty}
            </option>
          ))}
        </select>
        {selected?.has_image && <p className="muted">Has primary image</p>}
        <label className="muted">Add gallery image (max 5)</label>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          disabled={!selectedId || gallery.length >= 5}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) uploadImage(file, { asPrimary: gallery.length === 0 });
            e.target.value = '';
          }}
        />
        {gallery.length > 0 && (
          <ul className="muted" style={{ marginTop: 8 }}>
            {gallery.map((img) => (
              <li key={img.id} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span>
                  {img.original_filename || img.storage_key.split('/').pop()}
                  {img.is_primary ? ' (primary)' : ''}
                </span>
                {!img.is_primary && (
                  <button type="button" onClick={() => setPrimaryImage(img.id)}>
                    Set primary
                  </button>
                )}
                <button type="button" onClick={() => removeGalleryImage(img.id)}>
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}
        {selectedId && (
          <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
            <label className="muted">Barcode</label>
            <input
              value={editBarcode}
              onChange={(e) => setEditBarcode(e.target.value)}
              placeholder="Scan or type barcode"
            />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <button type="button" onClick={generateBarcode}>
                Generate barcode
              </button>
              <input
                value={labelCopies}
                onChange={(e) => setLabelCopies(e.target.value)}
                style={{ width: 64 }}
                title="Label copies"
                aria-label="Label copies"
              />
              <button type="button" onClick={printBarcodeLabel}>
                Print barcode label
              </button>
            </div>
            <label className="muted">Reorder level</label>
            <input value={editReorder} onChange={(e) => setEditReorder(e.target.value)} />
            <label className="muted">Selling price</label>
            <input value={editPrice} onChange={(e) => setEditPrice(e.target.value)} />
            <label className="muted">Tax supply class</label>
            <select value={editSupplyClass} onChange={(e) => setEditSupplyClass(e.target.value)}>
              <option value="standard">Standard-rated</option>
              <option value="zero_rated">Zero-rated</option>
              <option value="exempt">Exempt</option>
            </select>
            <button type="button" onClick={saveProductEdits}>
              Save product
            </button>
          </div>
        )}
      </div>

      {tab === 'import' && (
        <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 12 }}>
          <h3>Bulk import products</h3>
          <p className="muted" style={{ margin: 0 }}>
            Download the CSV template, fill product rows (category / brand / unit must already exist),
            validate, then import. Import is all-or-nothing — fix every error row first.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={downloadImportTemplate}>
              Download CSV template
            </button>
          </div>
          <label className="muted">CSV file</label>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => {
              setImportFile(e.target.files?.[0] || null);
              setImportReport(null);
            }}
          />
          {importFile && <p className="muted">Selected: {importFile.name}</p>}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => runProductImport(true)}
              disabled={!importFile || importBusy}
            >
              {importBusy ? 'Working…' : 'Validate'}
            </button>
            <button
              type="button"
              onClick={() => runProductImport(false)}
              disabled={!importFile || importBusy || !importReport?.can_commit}
            >
              Import valid rows
            </button>
          </div>
          {importReport && (
            <div>
              <p className="muted">
                {importReport.total_rows} rows · {importReport.valid_rows} valid ·{' '}
                {importReport.error_rows} errors
                {importReport.imported != null ? ` · imported ${importReport.imported}` : ''}
              </p>
              <table className="table">
                <thead>
                  <tr>
                    <th>Line</th>
                    <th>SKU</th>
                    <th>Name</th>
                    <th>Status</th>
                    <th>Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {importReport.rows.map((r) => (
                    <tr key={`${r.line}-${r.sku}`}>
                      <td>{r.line}</td>
                      <td>{r.sku || '—'}</td>
                      <td>{r.name || '—'}</td>
                      <td style={{ color: r.ok ? '#047857' : '#b91c1c' }}>{r.ok ? 'OK' : 'Error'}</td>
                      <td>{r.errors?.length ? r.errors.join('; ') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'products' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Add product</h3>
            <input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="Name" />
            <input value={productSku} onChange={(e) => setProductSku(e.target.value)} placeholder="SKU" />
            <input
              value={productBarcode}
              onChange={(e) => setProductBarcode(e.target.value)}
              placeholder="Barcode (optional)"
            />
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
            <select value={productSupplyClass} onChange={(e) => setProductSupplyClass(e.target.value)}>
              <option value="standard">Tax: standard-rated</option>
              <option value="zero_rated">Tax: zero-rated</option>
              <option value="exempt">Tax: exempt</option>
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
                <th>Barcode</th>
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
                  <td>{p.barcode || '—'}</td>
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
        <div style={{ display: 'grid', gap: 16 }}>
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
                <li key={c.id} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span>
                    {c.code} — {c.name}
                    {c.parent_id ? ' (child)' : ''}
                    {!c.is_active ? ' [inactive]' : ''}
                  </span>
                  {c.is_active && (
                    <button
                      type="button"
                      onClick={async () => {
                        setError('');
                        try {
                          await api(`/catalog/categories/${c.id}`, { method: 'DELETE' });
                          setMessage('Category deactivated');
                          await refresh();
                        } catch (err: any) {
                          setError(err.message);
                        }
                      }}
                    >
                      Deactivate
                    </button>
                  )}
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
                <li key={b.id} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span>
                    {b.code} — {b.name}
                    {!b.is_active ? ' [inactive]' : ''}
                  </span>
                  {b.is_active && (
                    <button
                      type="button"
                      onClick={async () => {
                        setError('');
                        try {
                          await api(`/catalog/brands/${b.id}`, { method: 'DELETE' });
                          setMessage('Brand deactivated');
                          await refresh();
                        } catch (err: any) {
                          setError(err.message);
                        }
                      }}
                    >
                      Deactivate
                    </button>
                  )}
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
                <li key={u.id} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span>
                    {u.code} — {u.name}
                    {!u.is_active ? ' [inactive]' : ''}
                  </span>
                  {u.is_active && (
                    <button
                      type="button"
                      onClick={async () => {
                        setError('');
                        try {
                          await api(`/catalog/units/${u.id}`, { method: 'DELETE' });
                          setMessage('Unit deactivated');
                          await refresh();
                        } catch (err: any) {
                          setError(err.message);
                        }
                      }}
                    >
                      Deactivate
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {tab === 'variants' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
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
                <th>Active</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {variants.map((v) => (
                <tr key={v.id}>
                  <td>{v.name}</td>
                  <td>{v.sku}</td>
                  <td>{v.size || '—'}</td>
                  <td>{v.stock_qty}</td>
                  <td>
                    <input
                      defaultValue={String(v.selling_price ?? 0)}
                      style={{ width: 80 }}
                      onBlur={(e) => {
                        if (String(v.selling_price) !== e.target.value) {
                          saveVariantPrice(v.id, e.target.value);
                        }
                      }}
                    />
                  </td>
                  <td>{v.is_active ? 'yes' : 'no'}</td>
                  <td>
                    {v.is_active && (
                      <button type="button" onClick={() => deactivateVariant(v.id)}>
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'batches' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
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

      {tab === 'counts' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Start stock count</h3>
            <select value={countWarehouseId} onChange={(e) => setCountWarehouseId(e.target.value)}>
              <option value="">Warehouse</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.code})
                </option>
              ))}
            </select>
            <button type="button" onClick={startStockCount} disabled={!countWarehouseId}>
              Create draft count
            </button>
          </div>

          <table className="table" style={{ marginBottom: 16 }}>
            <thead>
              <tr>
                <th>Number</th>
                <th>Status</th>
                <th>Items</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {counts.map((c) => (
                <tr key={c.id}>
                  <td>{c.count_number}</td>
                  <td>{c.status}</td>
                  <td>
                    {c.counted_item_count}/{c.item_count}
                  </td>
                  <td>
                    <button type="button" onClick={() => openCount(c.id)}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {activeCount && (
            <div className="card" style={{ display: 'grid', gap: 12 }}>
              <h3>
                {activeCount.count_number} — {activeCount.status}
              </h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Expected</th>
                    <th>Counted</th>
                    <th>Variance</th>
                  </tr>
                </thead>
                <tbody>
                  {(activeCount.items || []).map((item: any) => {
                    const counted = Number(countQtys[item.product_id] ?? item.expected_qty ?? 0);
                    const variance = counted - Number(item.expected_qty || 0);
                    return (
                      <tr key={item.id}>
                        <td>
                          {item.product_sku || item.product_id}
                          <div className="muted">{item.product_name}</div>
                        </td>
                        <td>{item.expected_qty}</td>
                        <td>
                          <input
                            value={countQtys[item.product_id] ?? ''}
                            disabled={activeCount.status !== 'draft'}
                            onChange={(e) =>
                              setCountQtys({ ...countQtys, [item.product_id]: e.target.value })
                            }
                            style={{ width: 90 }}
                          />
                        </td>
                        <td>{Number.isFinite(variance) ? variance : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {activeCount.status === 'draft' && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" onClick={saveCountLines}>
                    Save counts
                  </button>
                  <button type="button" onClick={completeActiveCount}>
                    Complete &amp; post variances
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </Shell>
  );
}
