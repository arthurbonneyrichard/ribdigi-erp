'use client';

import { useEffect, useState } from 'react';
import BarcodeCameraScanner from '../../components/BarcodeCameraScanner';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { useTabQuery } from '../../lib/tabQuery';

type Tab =
  | 'products'
  | 'catalog'
  | 'variants'
  | 'batches'
  | 'expiry'
  | 'counts'
  | 'transfers'
  | 'ops'
  | 'opening'
  | 'movements'
  | 'stock'
  | 'lowstock';
const INVENTORY_TABS: Tab[] = [
  'products',
  'catalog',
  'variants',
  'batches',
  'expiry',
  'counts',
  'transfers',
  'ops',
  'opening',
  'movements',
  'stock',
  'lowstock',
];

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export default function Page() {
  const [tab, setTab] = useTabQuery(INVENTORY_TABS, 'products');
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
  const [transfers, setTransfers] = useState<any[]>([]);
  const [activeCount, setActiveCount] = useState<any | null>(null);
  const [countWarehouseId, setCountWarehouseId] = useState('');
  const [countQtys, setCountQtys] = useState<Record<string, string>>({});
  const [countScan, setCountScan] = useState('');
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scannerTarget, setScannerTarget] = useState<'count' | 'ops'>('count');
  const [opsScan, setOpsScan] = useState('');
  const [opsReason, setOpsReason] = useState('other');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const [fromWarehouseId, setFromWarehouseId] = useState('');
  const [toWarehouseId, setToWarehouseId] = useState('');
  const [transferQty, setTransferQty] = useState('1');
  const [opsWarehouseId, setOpsWarehouseId] = useState('');
  const [opsQty, setOpsQty] = useState('1');
  const [opsNotes, setOpsNotes] = useState('');
  const [openingMode, setOpeningMode] = useState<'add' | 'set'>('add');
  const [openingQty, setOpeningQty] = useState('0');
  const [openingWarehouseId, setOpeningWarehouseId] = useState('');
  const [openingNotes, setOpeningNotes] = useState('');
  const [openingFiscal, setOpeningFiscal] = useState('');
  const [openingBatch, setOpeningBatch] = useState('');
  const [movements, setMovements] = useState<any[]>([]);
  // Stage 109 R1 — shareable movements from_date / to_date (extends Stage 101 movement_type)
  const [moveFrom, setMoveFrom] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('from_date')?.trim() || '';
  });
  const [moveTo, setMoveTo] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('to_date')?.trim() || '';
  });
  const [moveType, setMoveType] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('movement_type')?.trim() || '';
  });
  const [moveWarehouseId, setMoveWarehouseId] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('warehouse_id')?.trim() || '';
  });
  const [warehouseStock, setWarehouseStock] = useState<any | null>(null);
  const [lowStock, setLowStock] = useState<any[]>([]);
  const [suppliers, setSuppliers] = useState<any[]>([]);
  const [reorderSupplierId, setReorderSupplierId] = useState('');

  const [productName, setProductName] = useState('');
  const [productSku, setProductSku] = useState('');
  const [productPrice, setProductPrice] = useState('0');
  const [productOpeningStock, setProductOpeningStock] = useState('0');
  const [productCategoryId, setProductCategoryId] = useState('');
  const [productBrandId, setProductBrandId] = useState('');
  const [productUnitId, setProductUnitId] = useState('');
  const [productBarcode, setProductBarcode] = useState('');
  const [editMinimum, setEditMinimum] = useState('0');
  const [editReorder, setEditReorder] = useState('0');
  const [editPrice, setEditPrice] = useState('0');
  const [editBarcode, setEditBarcode] = useState('');

  function statusColor(status?: string) {
    if (status === 'red') return '#b91c1c';
    if (status === 'yellow') return '#a16207';
    return '#047857';
  }
  const [categoryTree, setCategoryTree] = useState<any[]>([]);
  const [importReport, setImportReport] = useState<any | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [stockImportReport, setStockImportReport] = useState<any | null>(null);
  const [stockImportFile, setStockImportFile] = useState<File | null>(null);
  const [labelCopies, setLabelCopies] = useState('1');
  const [variantBarcode, setVariantBarcode] = useState('');

  const [catCode, setCatCode] = useState('');
  const [catName, setCatName] = useState('');
  const [catParentId, setCatParentId] = useState('');
  const [catTaxRateId, setCatTaxRateId] = useState('');
  const [taxRates, setTaxRates] = useState<any[]>([]);
  const [brandCode, setBrandCode] = useState('');
  const [brandName, setBrandName] = useState('');
  const [unitCode, setUnitCode] = useState('');
  const [unitName, setUnitName] = useState('');
  const [unitBaseId, setUnitBaseId] = useState('');
  const [unitFactor, setUnitFactor] = useState('1');
  const [editWeight, setEditWeight] = useState('');
  const [editLength, setEditLength] = useState('');
  const [editWidth, setEditWidth] = useState('');
  const [editHeight, setEditHeight] = useState('');

  const [variantName, setVariantName] = useState('');
  const [variantSku, setVariantSku] = useState('');
  const [variantSize, setVariantSize] = useState('');
  const [batchNumber, setBatchNumber] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [stockQty, setStockQty] = useState('10');

  // Stage 107 S1 — shareable product list filters (q/category/brand client-side)
  // Stage 120 P1 — product_active → GET /products?is_active=
  const [listFilterQ, setListFilterQ] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('q')?.trim() || '';
  });
  const [listFilterCategoryId, setListFilterCategoryId] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('category_id')?.trim() || '';
  });
  const [listFilterBrandId, setListFilterBrandId] = useState(() => {
    if (typeof window === 'undefined') return '';
    return new URLSearchParams(window.location.search).get('brand_id')?.trim() || '';
  });
  const [productActiveFilter, setProductActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('product_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  // Stage 122 M1 — category_active / brand_active / unit_active → GET ?is_active=
  const [categoryActiveFilter, setCategoryActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('category_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  const [brandActiveFilter, setBrandActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('brand_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  const [unitActiveFilter, setUnitActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('unit_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });
  // Stage 124 V1 — variant_active → GET /products/{id}/variants?is_active=
  const [variantActiveFilter, setVariantActiveFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const v = (new URLSearchParams(window.location.search).get('variant_active') || '')
      .trim()
      .toLowerCase();
    return v === 'true' || v === 'false' ? v : '';
  });

  function writeProductListFilters(next: {
    q?: string;
    category_id?: string;
    brand_id?: string;
    product_active?: string;
  }) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('tab', 'products');
    const q = next.q !== undefined ? next.q : listFilterQ;
    const cat = next.category_id !== undefined ? next.category_id : listFilterCategoryId;
    const brand = next.brand_id !== undefined ? next.brand_id : listFilterBrandId;
    const active =
      next.product_active !== undefined ? next.product_active : productActiveFilter;
    if (q.trim()) url.searchParams.set('q', q.trim());
    else url.searchParams.delete('q');
    if (cat) url.searchParams.set('category_id', cat);
    else url.searchParams.delete('category_id');
    if (brand) url.searchParams.set('brand_id', brand);
    else url.searchParams.delete('brand_id');
    if (active === 'true' || active === 'false') url.searchParams.set('product_active', active);
    else url.searchParams.delete('product_active');
    window.history.replaceState({}, '', `${url.pathname}?${url.searchParams.toString()}`);
  }

  const filteredProducts = products.filter((p) => {
    const q = listFilterQ.trim().toLowerCase();
    if (q) {
      const hay = `${p.name || ''} ${p.sku || ''} ${p.barcode || ''}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (listFilterCategoryId && p.category_id !== listFilterCategoryId) return false;
    if (listFilterBrandId && p.brand_id !== listFilterBrandId) return false;
    if (productActiveFilter === 'true' && p.is_active === false) return false;
    if (productActiveFilter === 'false' && p.is_active !== false) return false;
    return true;
  });

  async function refresh(opts?: {
    productActive?: string;
    categoryActive?: string;
    brandActive?: string;
    unitActive?: string;
  }) {
    const productActive =
      opts?.productActive !== undefined ? opts.productActive : productActiveFilter;
    const categoryActive =
      opts?.categoryActive !== undefined ? opts.categoryActive : categoryActiveFilter;
    const brandActive = opts?.brandActive !== undefined ? opts.brandActive : brandActiveFilter;
    const unitActive = opts?.unitActive !== undefined ? opts.unitActive : unitActiveFilter;
    const productQs =
      productActive === 'true'
        ? '?is_active=true'
        : productActive === 'false'
          ? '?is_active=false'
          : '';
    const catQs =
      categoryActive === 'true'
        ? 'is_active=true'
        : categoryActive === 'false'
          ? 'is_active=false'
          : '';
    const brandQs =
      brandActive === 'true'
        ? '?is_active=true'
        : brandActive === 'false'
          ? '?is_active=false'
          : '';
    const unitQs =
      unitActive === 'true'
        ? '?is_active=true'
        : unitActive === 'false'
          ? '?is_active=false'
          : '';
    const catFlat = catQs ? `?${catQs}` : '';
    const catTree = catQs ? `?tree=true&${catQs}` : '?tree=true';
    const [p, e, c, tree, b, u, w, sc, tr, ls, sup, tax] = await Promise.all([
      api(`/products${productQs}`),
      api('/inventory/batches/expiring?days=60'),
      api(`/catalog/categories${catFlat}`),
      api(`/catalog/categories${catTree}`),
      api(`/catalog/brands${brandQs}`),
      api(`/catalog/units${unitQs}`),
      api('/warehouses'),
      api('/inventory/stock-counts'),
      api('/inventory/stock-transfers').catch(() => ({ data: [] })),
      api('/inventory/low-stock').catch(() => ({ data: [] })),
      api('/suppliers').catch(() => ({ data: [] })),
      api('/tax/rates').catch(() => ({ data: [] })),
    ]);
    setProducts(p.data || []);
    setExpiring(e.data?.batches || []);
    setCategories(c.data || []);
    setTaxRates(tax.data || []);
    setCategoryTree(tree.data || []);
    setBrands(b.data || []);
    setUnits(u.data || []);
    setWarehouses(w.data || []);
    setCounts(sc.data || []);
    setTransfers(tr.data || []);
    setLowStock(ls.data || []);
    setSuppliers(sup.data || []);
    if (!selectedId && p.data?.length) setSelectedId(p.data[0].id);
    if (!countWarehouseId && w.data?.length) setCountWarehouseId(w.data[0].id);
    if (!fromWarehouseId && w.data?.length) setFromWarehouseId(w.data[0].id);
    if (!toWarehouseId && w.data?.length > 1) setToWarehouseId(w.data[1].id);
    if (!opsWarehouseId && w.data?.length) setOpsWarehouseId(w.data[0].id);
    if (!reorderSupplierId && sup.data?.length) setReorderSupplierId(sup.data[0].id);
  }

  function writeCatalogMetaFilters(next: {
    category_active?: string;
    brand_active?: string;
    unit_active?: string;
  }) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('tab', 'catalog');
    const cat =
      next.category_active !== undefined ? next.category_active : categoryActiveFilter;
    const brand = next.brand_active !== undefined ? next.brand_active : brandActiveFilter;
    const unit = next.unit_active !== undefined ? next.unit_active : unitActiveFilter;
    if (cat === 'true' || cat === 'false') url.searchParams.set('category_active', cat);
    else url.searchParams.delete('category_active');
    if (brand === 'true' || brand === 'false') url.searchParams.set('brand_active', brand);
    else url.searchParams.delete('brand_active');
    if (unit === 'true' || unit === 'false') url.searchParams.set('unit_active', unit);
    else url.searchParams.delete('unit_active');
    window.history.replaceState({}, '', `${url.pathname}?${url.searchParams.toString()}${url.hash}`);
  }

  async function downloadCatalogCsv(path: string, filename: string) {
    setError('');
    setMessage('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}${path}`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) throw new Error(`${filename} export failed`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`${filename} exported`);
    } catch (err: any) {
      setError(err.message || 'Export failed');
    }
  }

  // Stage 109 R1 / Stage 111 I1 — shareable movements filters (type / dates / warehouse)
  function syncMovementFiltersUrl(next?: {
    movement_type?: string;
    from_date?: string;
    to_date?: string;
    warehouse_id?: string;
  }) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    url.searchParams.set('tab', 'movements');
    const mt = next?.movement_type !== undefined ? next.movement_type : moveType;
    const fd = next?.from_date !== undefined ? next.from_date : moveFrom;
    const td = next?.to_date !== undefined ? next.to_date : moveTo;
    const wh = next?.warehouse_id !== undefined ? next.warehouse_id : moveWarehouseId;
    if (mt) url.searchParams.set('movement_type', mt);
    else url.searchParams.delete('movement_type');
    if (fd) url.searchParams.set('from_date', fd);
    else url.searchParams.delete('from_date');
    if (td) url.searchParams.set('to_date', td);
    else url.searchParams.delete('to_date');
    if (wh) url.searchParams.set('warehouse_id', wh);
    else url.searchParams.delete('warehouse_id');
    window.history.replaceState({}, '', `${url.pathname}?${url.searchParams.toString()}`);
  }

  function syncMovementTypeUrl(nextType: string) {
    syncMovementFiltersUrl({ movement_type: nextType });
  }

  async function loadMovements() {
    const params = new URLSearchParams();
    if (selectedId) params.set('product_id', selectedId);
    if (moveWarehouseId) params.set('warehouse_id', moveWarehouseId);
    if (moveType) params.set('movement_type', moveType);
    if (moveFrom) params.set('from_date', moveFrom);
    if (moveTo) params.set('to_date', moveTo);
    const qs = params.toString();
    const r = await api(`/inventory/movements${qs ? `?${qs}` : ''}`);
    setMovements(r.data || []);
  }

  async function loadWarehouseStock(id: string) {
    if (!id) {
      setWarehouseStock(null);
      return;
    }
    const r = await api(`/products/${id}/warehouse-stock`);
    setWarehouseStock(r.data || null);
  }

  async function refreshSelected(id: string, opts?: { variantActive?: string }) {
    if (!id) return;
    const variantActive =
      opts?.variantActive !== undefined ? opts.variantActive : variantActiveFilter;
    const variantQs =
      variantActive === 'true'
        ? '?is_active=true'
        : variantActive === 'false'
          ? '?is_active=false'
          : '';
    const [v, b, g] = await Promise.all([
      api(`/products/${id}/variants${variantQs}`),
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

  // Stage 101 O1 — honor Shell #categories / #brands / #units on Catalog
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!hash) return;
    const catalogAnchors = ['categories', 'brands', 'units'];
    if (catalogAnchors.includes(hash) && tab !== 'catalog') {
      setTab('catalog');
      return;
    }
    if (tab !== 'catalog') return;
    const t = window.setTimeout(() => {
      const el = document.getElementById(hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
  }, [tab, setTab]);

  useEffect(() => {
    if (tab === 'movements') {
      loadMovements().catch((err) => setError(err.message));
    }
    if (tab === 'stock' && selectedId) {
      loadWarehouseStock(selectedId).catch((err) => setError(err.message));
    }
  }, [tab, selectedId]);

  async function createReorderPo(productId: string, quantity?: number) {
    if (!reorderSupplierId) {
      setError('Select a supplier for the reorder PO');
      return;
    }
    setError('');
    try {
      const body: Record<string, unknown> = {
        product_id: productId,
        supplier_id: reorderSupplierId,
        notes: 'Created from Inventory low-stock reorder',
      };
      if (quantity != null && quantity > 0) body.quantity = quantity;
      const r = await api('/inventory/low-stock/reorder-po', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setMessage(
        `Draft PO ${r.data?.po_number || r.data?.id} created with ${r.data?.items?.length || 0} line(s)`,
      );
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (selectedId) {
      refreshSelected(selectedId).catch((err) => setError(err.message));
      const p = products.find((x) => x.id === selectedId);
      if (p) {
        setEditMinimum(String(p.minimum_stock ?? 0));
        setEditReorder(String(p.reorder_level ?? 0));
        setEditPrice(String(p.selling_price ?? 0));
        setEditBarcode(p.barcode || '');
        setEditWeight(p.weight != null ? String(p.weight) : '');
        setEditLength(p.length != null ? String(p.length) : '');
        setEditWidth(p.width != null ? String(p.width) : '');
        setEditHeight(p.height != null ? String(p.height) : '');
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
          minimum_stock: Number(editMinimum) || 0,
          reorder_level: Number(editReorder) || 0,
          selling_price: Number(editPrice) || 0,
          barcode: editBarcode || null,
          weight: editWeight === '' ? null : Number(editWeight),
          length: editLength === '' ? null : Number(editLength),
          width: editWidth === '' ? null : Number(editWidth),
          height: editHeight === '' ? null : Number(editHeight),
        }),
      });
      setMessage('Product updated');
      await refresh();
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

  async function downloadCountVariance(countId: string, format: 'csv' | 'pdf') {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(
        `${apiBase}/inventory/stock-counts/${countId}/variance-report?format=${format}`,
        {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
          },
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const detail = body.detail;
        const msg =
          typeof detail === 'string'
            ? detail
            : detail?.message || body.message || 'Variance report failed';
        throw new Error(msg);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `stock-count-variance.${format}`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(`Variance ${format.toUpperCase()} downloaded`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function lookupProductByScan(code: string) {
    const value = code.trim();
    if (!value) return null;
    const params = new URLSearchParams({ q: value, barcode: value });
    const r = await api('/inventory/products/lookup?' + params.toString());
    const rows: any[] = r.data || [];
    return (
      rows.find((row) => row.barcode === value || row.sku === value) || (rows.length === 1 ? rows[0] : null)
    );
  }

  async function applyCountScan(code: string) {
    const value = code.trim();
    if (!value || !activeCount || activeCount.status !== 'draft') return;
    setError('');
    setCountScan(value);
    setScannerOpen(false);
    try {
      const exact = await lookupProductByScan(value);
      if (!exact) {
        setError(`No product for barcode ${value}`);
        return;
      }
      const productId = exact.product_id || exact.id;
      const item = (activeCount.items || []).find((i: any) => i.product_id === productId);
      if (!item) {
        setError(`${exact.name || exact.sku} is not on this count sheet`);
        return;
      }
      let next = '1';
      setCountQtys((prev) => {
        const current = Number(prev[productId] ?? item.counted_qty ?? item.expected_qty ?? 0);
        next = String(current + 1);
        return { ...prev, [productId]: next };
      });
      setMessage(`Counted ${exact.name || exact.sku}: ${next}`);
      setCountScan('');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function applyOpsScan(code: string) {
    const value = code.trim();
    if (!value) return;
    setError('');
    setOpsScan(value);
    setScannerOpen(false);
    try {
      const exact = await lookupProductByScan(value);
      if (!exact) {
        setError(`No product for barcode ${value}`);
        return;
      }
      const productId = exact.product_id || exact.id;
      setSelectedId(productId);
      setMessage(`Selected ${exact.name || exact.sku} for stock ops`);
      setOpsScan('');
      await refreshSelected(productId).catch(() => undefined);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function onCameraScan(code: string) {
    if (scannerTarget === 'ops') {
      applyOpsScan(code);
    } else {
      applyCountScan(code);
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
          selling_price: Number(productPrice) || 0,
          stock_qty: Number(productOpeningStock) || 0,
          barcode: productBarcode || null,
          category_id: productCategoryId || null,
          brand_id: productBrandId || null,
          unit_id: productUnitId || null,
        }),
      });
      setMessage(`Product ${r.data.sku} created`);
      setProductName('');
      setProductSku('');
      setProductPrice('0');
      setProductOpeningStock('0');
      setProductBarcode('');
      await refresh();
      setSelectedId(r.data.id);
      setTab('products');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createWarehouseTransfer() {
    if (!fromWarehouseId || !toWarehouseId || !selectedId) return;
    setError('');
    try {
      await api('/inventory/stock-transfers', {
        method: 'POST',
        body: JSON.stringify({
          from_warehouse_id: fromWarehouseId,
          to_warehouse_id: toWarehouseId,
          submit: true,
          items: [{ product_id: selectedId, quantity: Number(transferQty) || 1 }],
        }),
      });
      setMessage('Warehouse transfer created');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function transferAction(id: string, action: 'ship' | 'receive' | 'cancel') {
    setError('');
    try {
      await api(`/inventory/stock-transfers/${id}/${action}`, { method: 'POST' });
      setMessage(`Transfer ${action} completed`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function stockOp(kind: 'in' | 'out' | 'adjust') {
    if (!selectedId) return;
    setError('');
    try {
      const qty = Number(opsQty) || 0;
      if (kind === 'adjust') {
        await api(`/inventory/adjust/${selectedId}`, {
          method: 'POST',
          body: JSON.stringify({
            quantity: qty,
            reason: opsReason || 'other',
            notes: opsNotes || undefined,
            warehouse_id: opsWarehouseId || null,
          }),
        });
      } else if (kind === 'in') {
        await api('/inventory/stock-in', {
          method: 'POST',
          body: JSON.stringify({
            product_id: selectedId,
            quantity: Math.abs(qty),
            warehouse_id: opsWarehouseId || null,
            notes: opsNotes || undefined,
          }),
        });
      } else {
        await api('/inventory/stock-out', {
          method: 'POST',
          body: JSON.stringify({
            product_id: selectedId,
            quantity: Math.abs(qty),
            warehouse_id: opsWarehouseId || null,
            notes: opsNotes || undefined,
          }),
        });
      }
      setMessage(`Stock ${kind} recorded`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function submitOpeningStock() {
    if (!selectedId) return;
    setError('');
    try {
      const qty = Number(openingQty);
      if (Number.isNaN(qty) || qty < 0) {
        setError('Opening quantity must be zero or positive');
        return;
      }
      await api('/inventory/opening-stock', {
        method: 'POST',
        body: JSON.stringify({
          product_id: selectedId,
          quantity: qty,
          mode: openingMode,
          warehouse_id: openingWarehouseId || null,
          notes: openingNotes || undefined,
          fiscal_period: openingFiscal || undefined,
          batch_number: openingBatch || undefined,
        }),
      });
      setMessage(`Opening stock (${openingMode}) recorded`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
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

  async function reactivateVariant(variantId: string) {
    if (!selectedId) return;
    setError('');
    try {
      await api(`/products/${selectedId}/variants/${variantId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: true }),
      });
      setMessage('Variant reactivated');
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

  async function generateProductBarcode(fmt: string = 'code128') {
    if (!selectedId) return;
    setError('');
    try {
      const r = await api(`/products/${selectedId}/barcode/generate?format=${fmt}&force=false`, {
        method: 'POST',
      });
      setMessage(`Barcode ${r.data.barcode}`);
      setEditBarcode(r.data.barcode || '');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function printProductLabels(
    format: 'html' | 'pdf' | 'png' = 'html',
    codeType: 'barcode' | 'qr' = 'barcode',
  ) {
    if (!selectedId) return;
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const copies = Math.max(1, Math.min(50, Number(labelCopies) || 1));
      const res = await fetch(
        `${apiBase}/products/${selectedId}/labels?format=${format}&copies=${copies}&code_type=${codeType}`,
        {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
          },
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Label print failed');
      }
      const prefix = codeType === 'qr' ? 'qr' : 'barcode';
      if (format === 'html') {
        const html = await res.text();
        const win = window.open('', '_blank', 'noopener,noreferrer');
        if (!win) throw new Error('Pop-up blocked; allow pop-ups to print labels');
        win.document.write(html);
        win.document.close();
        win.focus();
      } else {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = format === 'pdf' ? `${prefix}_labels.pdf` : `${prefix}_labels.png`;
        a.click();
        URL.revokeObjectURL(url);
      }
      setMessage(
        `${codeType === 'qr' ? 'QR' : 'Barcode'} labels ready (${copies} cop${copies === 1 ? 'y' : 'ies'})`,
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function generateVariantBarcode(variantId: string) {
    if (!selectedId) return;
    setError('');
    try {
      const r = await api(
        `/products/${selectedId}/variants/${variantId}/barcode/generate?format=code128`,
        { method: 'POST' },
      );
      setMessage(`Variant barcode ${r.data.barcode}`);
      await refreshSelected(selectedId);
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
      if (!res.ok) throw new Error('Template download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'product_import_template.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function downloadProductsExport() {
    // Stage 118 E1 — catalog CSV export
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/products/export`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) throw new Error('Product export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'products_export.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('Products CSV exported');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function importProductsCsv(file: File, dryRun: boolean) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${apiBase}/products/import?dry_run=${dryRun}`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || body.message || 'Import failed');
      setImportReport(body.data);
      setMessage(body.message || (dryRun ? 'Dry-run complete' : 'Import complete'));
      if (!dryRun) await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function downloadStockImportTemplate() {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/inventory/stock/import/template`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) throw new Error('Stock template download failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'stock_import_template.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function importStockCsv(file: File, dryRun: boolean) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${apiBase}/inventory/stock/import?dry_run=${dryRun}`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || body.message || 'Stock import failed');
      setStockImportReport(body.data);
      setMessage(body.message || (dryRun ? 'Stock dry-run complete' : 'Stock import complete'));
      if (!dryRun) await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function renderCategoryNodes(nodes: any[], depth = 0): any {
    return nodes.map((node) => {
      const rate = taxRates.find((r) => r.id === node.tax_rate_id);
      return (
        <li key={node.id} style={{ marginLeft: depth * 16 }}>
          <span>
            {depth > 0 ? 'Sub Category: ' : ''}
            {node.code} — {node.name}
            {rate ? ` · tax ${rate.name} (${rate.rate}%)` : ''}
            {!node.is_active ? ' [inactive]' : ''}
          </span>
          {node.is_active && (
            <button
              type="button"
              style={{ marginLeft: 8 }}
              onClick={async () => {
                setError('');
                try {
                  await api(`/catalog/categories/${node.id}`, { method: 'DELETE' });
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
          {node.children?.length ? (
            <ul className="muted">{renderCategoryNodes(node.children, depth + 1)}</ul>
          ) : null}
        </li>
      );
    });
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
          barcode: variantBarcode || undefined,
        }),
      });
      setMessage(`Variant ${r.data.sku} created`);
      setVariantName('');
      setVariantSku('');
      setVariantSize('');
      setVariantBarcode('');
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
      <p className="muted">
        Products, catalog, stock ops, warehouse transfers, batches, expiry &amp; counts
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(
          [
            ['products', 'Products'],
            ['ops', 'Stock ops'],
            ['opening', 'Opening'],
            ['transfers', 'Transfers'],
            ['movements', 'Movements'],
            ['stock', 'Stock'],
            ['lowstock', 'Low stock'],
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
            <label className="muted">Minimum stock</label>
            <input value={editMinimum} onChange={(e) => setEditMinimum(e.target.value)} />
            <label className="muted">Reorder level</label>
            <input value={editReorder} onChange={(e) => setEditReorder(e.target.value)} />
            <label className="muted">Selling price</label>
            <input value={editPrice} onChange={(e) => setEditPrice(e.target.value)} />
            <label className="muted">Weight (kg)</label>
            <input value={editWeight} onChange={(e) => setEditWeight(e.target.value)} placeholder="Optional" />
            <label className="muted">Dimensions L×W×H (cm)</label>
            <div style={{ display: 'flex', gap: 8 }}>
              <input value={editLength} onChange={(e) => setEditLength(e.target.value)} placeholder="L" />
              <input value={editWidth} onChange={(e) => setEditWidth(e.target.value)} placeholder="W" />
              <input value={editHeight} onChange={(e) => setEditHeight(e.target.value)} placeholder="H" />
            </div>
            <label className="muted">Barcode</label>
            <input value={editBarcode} onChange={(e) => setEditBarcode(e.target.value)} placeholder="EAN/UPC/Code128" />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" onClick={saveProductEdits}>
                Save product
              </button>
              <button type="button" onClick={() => generateProductBarcode('code128')}>
                Generate Code128
              </button>
              <button type="button" onClick={() => generateProductBarcode('ean13')}>
                Generate EAN-13
              </button>
            </div>
            <label className="muted">Label copies</label>
            <input
              value={labelCopies}
              onChange={(e) => setLabelCopies(e.target.value)}
              placeholder="Copies"
              style={{ maxWidth: 120 }}
            />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" onClick={() => printProductLabels('html')} disabled={!editBarcode}>
                Print labels
              </button>
              <button type="button" onClick={() => printProductLabels('pdf')} disabled={!editBarcode}>
                Download PDF
              </button>
              <button type="button" onClick={() => printProductLabels('png')} disabled={!editBarcode}>
                Download PNG
              </button>
              <button
                type="button"
                onClick={() => printProductLabels('html', 'qr')}
                disabled={!editBarcode}
                title="Print QR labels encoding the product barcode"
              >
                Print QR labels
              </button>
              <button
                type="button"
                onClick={() => printProductLabels('pdf', 'qr')}
                disabled={!editBarcode}
              >
                QR PDF
              </button>
            </div>
          </div>
        )}
      </div>

      {tab === 'products' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 480 }}>
            <h3>Add product</h3>
            <input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="Name" />
            <input value={productSku} onChange={(e) => setProductSku(e.target.value)} placeholder="SKU" />
            <input value={productPrice} onChange={(e) => setProductPrice(e.target.value)} placeholder="Selling price" />
            <input
              value={productOpeningStock}
              onChange={(e) => setProductOpeningStock(e.target.value)}
              placeholder="Opening stock"
            />
            <input value={productBarcode} onChange={(e) => setProductBarcode(e.target.value)} placeholder="Barcode (optional)" />
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
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 520 }}>
            <h3>Import products (CSV)</h3>
            <p className="muted">Download the template, fill rows, dry-run validate, then import.</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" onClick={downloadImportTemplate}>
                Download template
              </button>
              <button type="button" onClick={downloadProductsExport}>
                Export products CSV
              </button>
            </div>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) {
                  setImportFile(file);
                  await importProductsCsv(file, true);
                }
                e.target.value = '';
              }}
            />
            {importReport && (
              <div className="muted">
                <p>
                  Rows {importReport.total_rows}: {importReport.valid_rows} valid, {importReport.error_rows} errors
                  {importReport.dry_run ? ' (dry-run)' : ''}
                </p>
                {importReport.errors?.length > 0 && (
                  <ul>
                    {importReport.errors.slice(0, 8).map((err: any) => (
                      <li key={`${err.row}-${err.sku}`}>
                        Row {err.row} {err.sku || ''}: {(err.errors || []).join('; ')}
                      </li>
                    ))}
                  </ul>
                )}
                {importReport.dry_run && importReport.valid_rows > 0 && importFile && (
                  <button type="button" onClick={() => importProductsCsv(importFile, false)}>
                    Import valid rows
                  </button>
                )}
              </div>
            )}
          </div>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 520 }}>
            <h3>Import stock (CSV)</h3>
            <p className="muted">
              Adjust or set quantities for existing products by SKU/barcode. Optional warehouse_code.
              Modes: adjust (signed delta) or set (absolute qty).
            </p>
            <button type="button" onClick={downloadStockImportTemplate}>
              Download stock template
            </button>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (file) {
                  setStockImportFile(file);
                  await importStockCsv(file, true);
                }
                e.target.value = '';
              }}
            />
            {stockImportReport && (
              <div className="muted">
                <p>
                  Rows {stockImportReport.total_rows}: {stockImportReport.valid_rows} valid,{' '}
                  {stockImportReport.error_rows} errors, {stockImportReport.skipped_rows || 0} skipped
                  {stockImportReport.dry_run ? ' (dry-run)' : ''}
                </p>
                {stockImportReport.errors?.length > 0 && (
                  <ul>
                    {stockImportReport.errors.slice(0, 8).map((err: any) => (
                      <li key={`${err.row}-${err.sku}`}>
                        Row {err.row} {err.sku || err.barcode || ''}: {(err.errors || []).join('; ')}
                      </li>
                    ))}
                  </ul>
                )}
                {stockImportReport.dry_run && stockImportReport.valid_rows > 0 && stockImportFile && (
                  <button type="button" onClick={() => importStockCsv(stockImportFile, false)}>
                    Apply stock changes
                  </button>
                )}
              </div>
            )}
          </div>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 520 }}>
            <h3>Filter products</h3>
            <p className="muted">
              Shareable URL filters (q / category_id / brand_id / product_active). Status uses{' '}
              <code>GET /products?is_active=</code> (Stage 120 P1).
            </p>
            <label className="muted" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              Status
              <select
                value={productActiveFilter}
                onChange={(e) => {
                  const next = e.target.value;
                  setProductActiveFilter(next);
                  writeProductListFilters({ product_active: next });
                  refresh({ productActive: next }).catch((err) => setError(err.message));
                }}
                aria-label="Filter products by active status"
              >
                <option value="">All products</option>
                <option value="true">Active only</option>
                <option value="false">Inactive only</option>
              </select>
            </label>
            <input
              value={listFilterQ}
              onChange={(e) => {
                const next = e.target.value;
                setListFilterQ(next);
                writeProductListFilters({ q: next });
              }}
              placeholder="Search name / SKU / barcode"
              aria-label="Product search filter"
            />
            <select
              value={listFilterCategoryId}
              onChange={(e) => {
                const next = e.target.value;
                setListFilterCategoryId(next);
                writeProductListFilters({ category_id: next });
              }}
              aria-label="Filter products by category"
            >
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <select
              value={listFilterBrandId}
              onChange={(e) => {
                const next = e.target.value;
                setListFilterBrandId(next);
                writeProductListFilters({ brand_id: next });
              }}
              aria-label="Filter products by brand"
            >
              <option value="">All brands</option>
              {brands.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>SKU</th>
                <th>Barcode</th>
                <th>Category</th>
                <th>Stock</th>
                <th>Status</th>
                <th>Batches?</th>
                <th>Price</th>
                <th>Image</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.map((p) => (
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
                  <td style={{ color: statusColor(p.stock_status), fontWeight: 600 }}>
                    {p.stock_status || 'green'}
                  </td>
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
          <p className="muted" style={{ margin: 0 }}>
            Catalog meta active filters use <code>category_active</code> / <code>brand_active</code>{' '}
            / <code>unit_active</code> → <code>GET ?is_active=</code> (Stage 122 M1).
          </p>
          <div className="card" style={{ display: 'grid', gap: 8 }} id="categories">
            <h3>Categories &amp; Sub Categories</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <label className="muted">
                Active status{' '}
                <select
                  value={categoryActiveFilter}
                  onChange={(e) => {
                    const v = e.target.value;
                    setCategoryActiveFilter(v);
                    writeCatalogMetaFilters({ category_active: v });
                    refresh({ categoryActive: v }).catch((err) => setError(err.message));
                  }}
                  aria-label="Category active filter"
                >
                  <option value="">All</option>
                  <option value="true">Active only</option>
                  <option value="false">Inactive only</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => {
                  // Stage 122 X1 — categories CSV export
                  const qs =
                    categoryActiveFilter === 'true'
                      ? '?is_active=true'
                      : categoryActiveFilter === 'false'
                        ? '?is_active=false'
                        : '';
                  downloadCatalogCsv(`/catalog/categories/export${qs}`, 'categories_export.csv');
                }}
              >
                Export categories CSV
              </button>
            </div>
            <p className="muted">
              Leave parent empty for a top-level Category. Choose a parent to create a Sub Category.
            </p>
            <input value={catCode} onChange={(e) => setCatCode(e.target.value)} placeholder="Code" />
            <input value={catName} onChange={(e) => setCatName(e.target.value)} placeholder="Name" />
            <select
              value={catParentId}
              onChange={(e) => setCatParentId(e.target.value)}
              aria-label="Parent category for Sub Category"
            >
              <option value="">Parent category (optional — Sub Category when set)</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <select
              value={catTaxRateId}
              onChange={(e) => setCatTaxRateId(e.target.value)}
              aria-label="Category tax rate"
            >
              <option value="">Tax rate (optional)</option>
              {taxRates
                .filter((r) => r.is_active !== false)
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.rate}%)
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
                      tax_rate_id: catTaxRateId || null,
                    }),
                  });
                  const wasSub = Boolean(catParentId);
                  setCatCode('');
                  setCatName('');
                  setCatParentId('');
                  setCatTaxRateId('');
                  setMessage(wasSub ? 'Sub Category created' : 'Category created');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              disabled={!catCode || !catName}
            >
              {catParentId ? 'Add Sub Category' : 'Add category'}
            </button>
            <ul className="muted">{renderCategoryNodes(categoryTree)}</ul>
          </div>
          <div className="card" style={{ display: 'grid', gap: 8 }} id="brands">
            <h3>Brand</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <label className="muted">
                Active status{' '}
                <select
                  value={brandActiveFilter}
                  onChange={(e) => {
                    const v = e.target.value;
                    setBrandActiveFilter(v);
                    writeCatalogMetaFilters({ brand_active: v });
                    refresh({ brandActive: v }).catch((err) => setError(err.message));
                  }}
                  aria-label="Brand active filter"
                >
                  <option value="">All</option>
                  <option value="true">Active only</option>
                  <option value="false">Inactive only</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => {
                  // Stage 122 X1 — brands CSV export
                  const qs =
                    brandActiveFilter === 'true'
                      ? '?is_active=true'
                      : brandActiveFilter === 'false'
                        ? '?is_active=false'
                        : '';
                  downloadCatalogCsv(`/catalog/brands/export${qs}`, 'brands_export.csv');
                }}
              >
                Export brands CSV
              </button>
            </div>
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
                    {b.has_logo ? ' [logo]' : ''}
                    {!b.is_active ? ' [inactive]' : ''}
                  </span>
                  {b.is_active && (
                    <>
                      <label style={{ cursor: 'pointer' }}>
                        <span style={{ textDecoration: 'underline' }}>Upload logo</span>
                        <input
                          type="file"
                          accept="image/*"
                          style={{ display: 'none' }}
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            e.target.value = '';
                            if (!file) return;
                            setError('');
                            try {
                              const token = localStorage.getItem('token');
                              const tenant = localStorage.getItem('tenant');
                              const form = new FormData();
                              form.append('file', file);
                              const res = await fetch(`${apiBase}/catalog/brands/${b.id}/logo`, {
                                method: 'POST',
                                headers: {
                                  ...(token ? { Authorization: `Bearer ${token}` } : {}),
                                  ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
                                },
                                body: form,
                              });
                              const body = await res.json().catch(() => ({}));
                              if (!res.ok) throw new Error(body.detail || body.message || 'Logo upload failed');
                              setMessage('Brand logo uploaded');
                              await refresh();
                            } catch (err: any) {
                              setError(err.message);
                            }
                          }}
                        />
                      </label>
                      {b.has_logo && (
                        <button
                          type="button"
                          onClick={async () => {
                            setError('');
                            try {
                              await api(`/catalog/brands/${b.id}/logo`, { method: 'DELETE' });
                              setMessage('Brand logo removed');
                              await refresh();
                            } catch (err: any) {
                              setError(err.message);
                            }
                          }}
                        >
                          Remove logo
                        </button>
                      )}
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
                    </>
                  )}
                </li>
              ))}
            </ul>
          </div>
          <div className="card" style={{ display: 'grid', gap: 8 }} id="units">
            <h3>Unit of measure</h3>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <label className="muted">
                Active status{' '}
                <select
                  value={unitActiveFilter}
                  onChange={(e) => {
                    const v = e.target.value;
                    setUnitActiveFilter(v);
                    writeCatalogMetaFilters({ unit_active: v });
                    refresh({ unitActive: v }).catch((err) => setError(err.message));
                  }}
                  aria-label="Unit active filter"
                >
                  <option value="">All</option>
                  <option value="true">Active only</option>
                  <option value="false">Inactive only</option>
                </select>
              </label>
              <button
                type="button"
                onClick={() => {
                  // Stage 122 X1 — units CSV export
                  const qs =
                    unitActiveFilter === 'true'
                      ? '?is_active=true'
                      : unitActiveFilter === 'false'
                        ? '?is_active=false'
                        : '';
                  downloadCatalogCsv(`/catalog/units/export${qs}`, 'units_export.csv');
                }}
              >
                Export units CSV
              </button>
            </div>
            <p className="muted">Optional base unit + factor (e.g. 1 BOX = 12 PCS).</p>
            <input value={unitCode} onChange={(e) => setUnitCode(e.target.value)} placeholder="Code" />
            <input value={unitName} onChange={(e) => setUnitName(e.target.value)} placeholder="Name" />
            <select value={unitBaseId} onChange={(e) => setUnitBaseId(e.target.value)}>
              <option value="">No base (this is a base unit)</option>
              {units
                .filter((u) => u.is_active && !u.base_unit_id)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.code} — {u.name}
                  </option>
                ))}
            </select>
            <input
              value={unitFactor}
              onChange={(e) => setUnitFactor(e.target.value)}
              placeholder="Conversion factor"
              disabled={!unitBaseId}
            />
            <button
              onClick={async () => {
                setError('');
                try {
                  await api('/catalog/units', {
                    method: 'POST',
                    body: JSON.stringify({
                      code: unitCode,
                      name: unitName,
                      base_unit_id: unitBaseId || null,
                      conversion_factor: Number(unitFactor) || 1,
                    }),
                  });
                  setUnitCode('');
                  setUnitName('');
                  setUnitBaseId('');
                  setUnitFactor('1');
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
              {units.map((u) => {
                const base = units.find((x) => x.id === u.base_unit_id);
                return (
                  <li key={u.id} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span>
                      {u.code} — {u.name}
                      {base ? ` (= ${u.conversion_factor} × ${base.code})` : ' [base]'}
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
                );
              })}
            </ul>
          </div>
        </div>
      )}

      {tab === 'variants' && (
        <>
          <p className="muted" style={{ marginBottom: 8 }}>
            Filter via <code>variant_active</code> → <code>GET /products/&#123;id&#125;/variants?is_active=</code>{' '}
            (Stage 124 V1).
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, alignItems: 'center' }}>
            <label className="muted">
              Active status{' '}
              <select
                value={variantActiveFilter}
                onChange={(e) => {
                  const v = e.target.value;
                  setVariantActiveFilter(v);
                  const url = new URL(window.location.href);
                  url.searchParams.set('tab', 'variants');
                  if (v === 'true' || v === 'false') url.searchParams.set('variant_active', v);
                  else url.searchParams.delete('variant_active');
                  window.history.replaceState(
                    {},
                    '',
                    `${url.pathname}?${url.searchParams.toString()}`
                  );
                  if (selectedId) {
                    refreshSelected(selectedId, { variantActive: v }).catch((err) =>
                      setError(err.message)
                    );
                  }
                }}
                aria-label="Variant active filter"
              >
                <option value="">All</option>
                <option value="true">Active only</option>
                <option value="false">Inactive only</option>
              </select>
            </label>
            <button
              type="button"
              onClick={async () => {
                // Stage 124 X1 — variants CSV export
                setError('');
                setMessage('');
                try {
                  const token = localStorage.getItem('token');
                  const tenant = localStorage.getItem('tenant');
                  const qs = new URLSearchParams();
                  if (selectedId) qs.set('product_id', selectedId);
                  if (variantActiveFilter === 'true' || variantActiveFilter === 'false') {
                    qs.set('is_active', variantActiveFilter);
                  }
                  const q = qs.toString();
                  const res = await fetch(`${apiBase}/products/variants/export${q ? `?${q}` : ''}`, {
                    headers: {
                      ...(token ? { Authorization: `Bearer ${token}` } : {}),
                      ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
                    },
                  });
                  if (!res.ok) throw new Error('Variants export failed');
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = 'variants_export.csv';
                  a.click();
                  URL.revokeObjectURL(url);
                  setMessage('Variants CSV exported');
                } catch (err: any) {
                  setError(err.message || 'Variants export failed');
                }
              }}
            >
              Export variants CSV
            </button>
          </div>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 480 }}>
            <h3>Add variant</h3>
            <input value={variantName} onChange={(e) => setVariantName(e.target.value)} placeholder="Name" />
            <input value={variantSku} onChange={(e) => setVariantSku(e.target.value)} placeholder="SKU" />
            <input value={variantSize} onChange={(e) => setVariantSize(e.target.value)} placeholder="Size (optional)" />
            <input value={variantBarcode} onChange={(e) => setVariantBarcode(e.target.value)} placeholder="Barcode (optional)" />
            <button onClick={addVariant} disabled={!selectedId || !variantName || !variantSku}>
              Create variant
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>SKU</th>
                <th>Barcode</th>
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
                  <td>
                    {v.barcode || '—'}{' '}
                    {!v.barcode && v.is_active && (
                      <button type="button" onClick={() => generateVariantBarcode(v.id)}>
                        Generate
                      </button>
                    )}
                  </td>
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
                    {v.is_active ? (
                      <button type="button" onClick={() => deactivateVariant(v.id)}>
                        Deactivate
                      </button>
                    ) : (
                      <button type="button" onClick={() => reactivateVariant(v.id)}>
                        Reactivate
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

      {tab === 'counts' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 520 }}>
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
                  <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button type="button" onClick={() => openCount(c.id)}>
                      Open
                    </button>
                    {c.status === 'completed' && (
                      <>
                        <button type="button" onClick={() => downloadCountVariance(c.id, 'csv')}>
                          CSV
                        </button>
                        <button type="button" onClick={() => downloadCountVariance(c.id, 'pdf')}>
                          PDF
                        </button>
                      </>
                    )}
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
              {activeCount.status === 'draft' && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <input
                    value={countScan}
                    onChange={(e) => setCountScan(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        applyCountScan(countScan);
                      }
                    }}
                    placeholder="Scan barcode to count +1 (USB/Bluetooth or camera)"
                    style={{ padding: 10, flex: '1 1 240px' }}
                  />
                  <button type="button" onClick={() => applyCountScan(countScan)} disabled={!countScan.trim()}>
                    Apply scan
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setScannerTarget('count');
                      setScannerOpen(true);
                    }}
                  >
                    Camera scan
                  </button>
                </div>
              )}
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
              {activeCount.status === 'completed' && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => downloadCountVariance(activeCount.id, 'csv')}>
                    Download variance CSV
                  </button>
                  <button type="button" onClick={() => downloadCountVariance(activeCount.id, 'pdf')}>
                    Download variance PDF
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {tab === 'ops' && (
        <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
          <h3>Stock in / out / adjust</h3>
          <p className="muted">
            Scan a barcode to select the product, or use the selector above. Optional warehouse for
            located stock. Adjustments require a BR-5.2 reason code.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              value={opsScan}
              onChange={(e) => setOpsScan(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  applyOpsScan(opsScan);
                }
              }}
              placeholder="Scan barcode to select product"
              style={{ padding: 10, flex: '1 1 240px' }}
            />
            <button type="button" onClick={() => applyOpsScan(opsScan)} disabled={!opsScan.trim()}>
              Apply scan
            </button>
            <button
              type="button"
              onClick={() => {
                setScannerTarget('ops');
                setScannerOpen(true);
              }}
            >
              Camera scan
            </button>
          </div>
          <select value={opsWarehouseId} onChange={(e) => setOpsWarehouseId(e.target.value)}>
            <option value="">No warehouse (consolidated only)</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.code} — {w.name}
              </option>
            ))}
          </select>
          <input value={opsQty} onChange={(e) => setOpsQty(e.target.value)} placeholder="Quantity" />
          <select value={opsReason} onChange={(e) => setOpsReason(e.target.value)}>
            <option value="damage">damage</option>
            <option value="theft">theft</option>
            <option value="expiry">expiry</option>
            <option value="found">found</option>
            <option value="lost">lost</option>
            <option value="other">other</option>
          </select>
          <input value={opsNotes} onChange={(e) => setOpsNotes(e.target.value)} placeholder="Notes (optional)" />
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={() => stockOp('in')} disabled={!selectedId}>
              Stock in
            </button>
            <button type="button" onClick={() => stockOp('out')} disabled={!selectedId}>
              Stock out
            </button>
            <button type="button" onClick={() => stockOp('adjust')} disabled={!selectedId}>
              Adjust (+/−)
            </button>
          </div>
        </div>
      )}

      {tab === 'opening' && (
        <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
          <h3>Opening stock</h3>
          <p className="muted">
            Initialize on-hand for go-live or fiscal year start. Uses movement type{' '}
            <code>opening_stock</code>. Set mode cannot reduce stock — use adjust or stock count.
            Bulk: stock CSV with <code>mode=opening</code>, or API multi-line{' '}
            <code>items</code>.
          </p>
          <select value={openingMode} onChange={(e) => setOpeningMode(e.target.value as 'add' | 'set')}>
            <option value="add">Add quantity</option>
            <option value="set">Set absolute quantity</option>
          </select>
          <select value={openingWarehouseId} onChange={(e) => setOpeningWarehouseId(e.target.value)}>
            <option value="">No warehouse (consolidated only)</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.code} — {w.name}
              </option>
            ))}
          </select>
          <input
            value={openingQty}
            onChange={(e) => setOpeningQty(e.target.value)}
            placeholder={openingMode === 'set' ? 'Target quantity' : 'Quantity to add'}
          />
          <input
            value={openingFiscal}
            onChange={(e) => setOpeningFiscal(e.target.value)}
            placeholder="Fiscal period (optional, e.g. FY2026)"
          />
          <input
            value={openingBatch}
            onChange={(e) => setOpeningBatch(e.target.value)}
            placeholder="Batch number (if product tracks batches)"
          />
          <input
            value={openingNotes}
            onChange={(e) => setOpeningNotes(e.target.value)}
            placeholder="Notes"
          />
          <button type="button" onClick={submitOpeningStock} disabled={!selectedId}>
            Record opening stock
          </button>
        </div>
      )}

      {tab === 'movements' && (
        <>
          <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 560, marginBottom: 16 }}>
            <h3>Movement history</h3>
            <p className="muted">Filter by selected product, warehouse, type, and date range.</p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                type="date"
                value={moveFrom}
                onChange={(e) => {
                  setMoveFrom(e.target.value);
                  syncMovementFiltersUrl({ from_date: e.target.value });
                }}
                aria-label="Movements from date"
              />
              <input
                type="date"
                value={moveTo}
                onChange={(e) => {
                  setMoveTo(e.target.value);
                  syncMovementFiltersUrl({ to_date: e.target.value });
                }}
                aria-label="Movements to date"
              />
              <select
                value={moveType}
                onChange={(e) => setMoveType(e.target.value)}
                aria-label="Movement type filter"
              >
                <option value="">All types</option>
                <option value="stock_in">stock_in</option>
                <option value="stock_out">stock_out</option>
                <option value="opening_stock">opening_stock</option>
                <option value="adjustment">adjustment</option>
                <option value="transfer_out">transfer_out</option>
                <option value="transfer_in">transfer_in</option>
              </select>
              <select
                value={moveWarehouseId}
                onChange={(e) => {
                  setMoveWarehouseId(e.target.value);
                  syncMovementFiltersUrl({ warehouse_id: e.target.value });
                }}
                aria-label="Movements warehouse filter"
              >
                <option value="">All warehouses</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.code} — {w.name}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => {
                  syncMovementFiltersUrl();
                  loadMovements().catch((err) => setError(err.message));
                }}
              >
                Apply filters
              </button>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Type</th>
                <th>Qty</th>
                <th>Before</th>
                <th>After</th>
                <th>Product</th>
                <th>Warehouse</th>
                <th>User</th>
                <th>Reason</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {movements.map((row) => (
                <tr key={row.id}>
                  <td>{row.created_at ? String(row.created_at).slice(0, 19) : '—'}</td>
                  <td>{row.movement_type}</td>
                  <td>{row.quantity}</td>
                  <td>{row.quantity_before ?? '—'}</td>
                  <td>{row.quantity_after ?? '—'}</td>
                  <td>
                    {row.product_sku ||
                      products.find((p) => p.id === row.product_id)?.sku ||
                      row.product_id}
                  </td>
                  <td>
                    {row.warehouse_code ||
                      warehouses.find((w) => w.id === row.warehouse_id)?.code ||
                      row.warehouse_id ||
                      '—'}
                  </td>
                  <td>{row.created_by_email || row.created_by_name || row.created_by || '—'}</td>
                  <td>{row.reason || '—'}</td>
                  <td>{row.notes || '—'}</td>
                </tr>
              ))}
              {!movements.length && (
                <tr>
                  <td colSpan={10} className="muted">
                    No movements match the current filters
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}

      {tab === 'stock' && (
        <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 640 }}>
          <h3>Warehouse stock</h3>
          <p className="muted">On-hand by warehouse for the selected product.</p>
          {!selectedId && <p className="muted">Select a product above.</p>}
          {warehouseStock && (
            <>
              <p>
                Consolidated qty: <strong>{warehouseStock.stock_qty}</strong> · Reorder level:{' '}
                {warehouseStock.reorder_level}
              </p>
              <table className="table">
                <thead>
                  <tr>
                    <th>Warehouse</th>
                    <th>Qty</th>
                    <th>Reorder level</th>
                    <th>Reorder qty</th>
                  </tr>
                </thead>
                <tbody>
                  {(warehouseStock.warehouses || []).map((row: any) => (
                    <tr key={row.warehouse_id}>
                      <td>
                        {row.code} — {row.name}
                      </td>
                      <td>{row.quantity}</td>
                      <td>{row.reorder_level}</td>
                      <td>{row.reorder_qty}</td>
                    </tr>
                  ))}
                  {!(warehouseStock.warehouses || []).length && (
                    <tr>
                      <td colSpan={4} className="muted">
                        No warehouse-located stock for this product
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {tab === 'lowstock' && (
        <>
          <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 480, marginBottom: 16 }}>
            <h3>Low stock reorder</h3>
            <p className="muted">Create a draft purchase order for a low-stock product.</p>
            <select value={reorderSupplierId} onChange={(e) => setReorderSupplierId(e.target.value)}>
              <option value="">Select supplier</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Scope</th>
                <th>On hand</th>
                <th>Minimum</th>
                <th>Reorder</th>
                <th>Status</th>
                <th>Suggested</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lowStock.map((row) => (
                <tr key={`${row.scope || 'product'}-${row.id}-${row.warehouse_id || ''}`}>
                  <td>{row.sku}</td>
                  <td>{row.name}</td>
                  <td>
                    {row.scope === 'warehouse' ? `WH ${row.warehouse_code || row.warehouse_id}` : 'Product'}
                  </td>
                  <td>{row.stock_qty}</td>
                  <td>{row.minimum_stock ?? 0}</td>
                  <td>{row.reorder_level}</td>
                  <td style={{ color: statusColor(row.stock_status), fontWeight: 600 }}>
                    {row.stock_status || 'yellow'}
                  </td>
                  <td>{row.suggested_order_qty}</td>
                  <td>
                    <button
                      type="button"
                      disabled={!reorderSupplierId}
                      onClick={() => createReorderPo(row.id, Number(row.suggested_order_qty))}
                    >
                      Create draft PO
                    </button>
                  </td>
                </tr>
              ))}
              {!lowStock.length && (
                <tr>
                  <td colSpan={9} className="muted">
                    No products at or below minimum / reorder level
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}

      {tab === 'transfers' && (
        <>
          <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 520, marginBottom: 16 }}>
            <h3>Inter-warehouse transfer</h3>
            <p className="muted">Moves located stock between warehouses without changing consolidated qty.</p>
            <select value={fromWarehouseId} onChange={(e) => setFromWarehouseId(e.target.value)}>
              <option value="">From warehouse</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
            <select value={toWarehouseId} onChange={(e) => setToWarehouseId(e.target.value)}>
              <option value="">To warehouse</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
            <input value={transferQty} onChange={(e) => setTransferQty(e.target.value)} placeholder="Qty" />
            <button
              type="button"
              onClick={createWarehouseTransfer}
              disabled={!selectedId || !fromWarehouseId || !toWarehouseId}
            >
              Create &amp; request transfer
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Status</th>
                <th>From → To</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {transfers.map((t) => {
                const fromName =
                  warehouses.find((w) => w.id === t.from_warehouse_id)?.code || t.from_warehouse_id;
                const toName =
                  warehouses.find((w) => w.id === t.to_warehouse_id)?.code || t.to_warehouse_id;
                return (
                  <tr key={t.id}>
                    <td>{t.transfer_number}</td>
                    <td>{t.status}</td>
                    <td>
                      {fromName} → {toName}
                    </td>
                    <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {(t.status === 'requested' || t.status === 'draft') && (
                        <button type="button" onClick={() => transferAction(t.id, 'ship')}>
                          Ship
                        </button>
                      )}
                      {t.status === 'in_transit' && (
                        <button type="button" onClick={() => transferAction(t.id, 'receive')}>
                          Receive
                        </button>
                      )}
                      {['draft', 'requested', 'in_transit'].includes(t.status) && (
                        <button type="button" onClick={() => transferAction(t.id, 'cancel')}>
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!transfers.length && (
                <tr>
                  <td colSpan={4} className="muted">
                    No warehouse transfers yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}

      <BarcodeCameraScanner
        open={scannerOpen}
        onClose={() => setScannerOpen(false)}
        onScan={onCameraScan}
        title={scannerTarget === 'ops' ? 'Stock ops barcode scan' : 'Stock count barcode scan'}
      />
    </Shell>
  );
}
