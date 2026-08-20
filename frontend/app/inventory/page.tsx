'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Tab =
  | 'products'
  | 'lookup'
  | 'import'
  | 'catalog'
  | 'variants'
  | 'batches'
  | 'opening'
  | 'expiry'
  | 'counts'
  | 'movements'
  | 'adjust'
  | 'stockout'
  | 'whstock'
  | 'transfers';

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

const STOCK_STATUS_YELLOW_FACTOR = 1.5;

function categoryLabel(c: { path?: string; name?: string; code?: string; depth?: number }) {
  if (c.path) return c.path;
  return c.name || c.code || '';
}

function categoryIndent(depth?: number) {
  const d = Math.max(0, Number(depth) || 0);
  return '\u00A0\u00A0'.repeat(d);
}

function stockStatusOf(p: { stock_qty?: number; reorder_level?: number; stock_status?: string }) {
  if (p.stock_status === 'red' || p.stock_status === 'yellow' || p.stock_status === 'green') {
    return p.stock_status;
  }
  const qty = Number(p.stock_qty ?? 0);
  const reorder = Number(p.reorder_level ?? 0);
  if (qty <= 0 || (reorder > 0 && qty <= reorder)) return 'red';
  if (reorder > 0 && qty <= reorder * STOCK_STATUS_YELLOW_FACTOR) return 'yellow';
  return 'green';
}

function StockStatusBadge({ product }: { product: any }) {
  const status = stockStatusOf(product);
  const colors: Record<string, { bg: string; fg: string; text: string }> = {
    red: { bg: '#fee2e2', fg: '#b91c1c', text: 'Low / out' },
    yellow: { bg: '#fef9c3', fg: '#a16207', text: 'Near reorder' },
    green: { bg: '#dcfce7', fg: '#15803d', text: 'OK' },
  };
  const c = colors[status] || colors.green;
  return (
    <span
      title={`Stock ${product.stock_qty ?? 0} · reorder ${product.reorder_level ?? 0}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        padding: '2px 8px',
        borderRadius: 999,
        background: c.bg,
        color: c.fg,
        fontSize: 12,
        fontWeight: 600,
        whiteSpace: 'nowrap',
      }}
    >
      <span
        aria-hidden
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: c.fg,
          display: 'inline-block',
        }}
      />
      {product.stock_qty ?? 0}
      <span style={{ fontWeight: 500, opacity: 0.85 }}>({c.text})</span>
    </span>
  );
}

export default function Page() {
  const [tab, setTab] = useState<Tab>('products');
  const [products, setProducts] = useState<any[]>([]);
  const [categories, setCategories] = useState<any[]>([]);
  const [brands, setBrands] = useState<any[]>([]);
  const [units, setUnits] = useState<any[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [productManageFilter, setProductManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [categoryManageFilter, setCategoryManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [brandManageFilter, setBrandManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [unitManageFilter, setUnitManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [variantManageFilter, setVariantManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [variants, setVariants] = useState<any[]>([]);
  const [gallery, setGallery] = useState<any[]>([]);
  const [batches, setBatches] = useState<any[]>([]);
  const [expiring, setExpiring] = useState<any[]>([]);
  const [counts, setCounts] = useState<any[]>([]);
  const [countManageFilter, setCountManageFilter] = useState<
    'all' | 'draft' | 'completed' | 'cancelled'
  >('all');
  const [transferManageFilter, setTransferManageFilter] = useState<
    'all' | 'draft' | 'requested' | 'in_transit' | 'received' | 'cancelled'
  >('all');
  const [activeCount, setActiveCount] = useState<any | null>(null);
  const [countWarehouseId, setCountWarehouseId] = useState('');
  const [countNotes, setCountNotes] = useState('');
  const [countQtys, setCountQtys] = useState<Record<string, string>>({});
  const [countLineNotes, setCountLineNotes] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const [productName, setProductName] = useState('');
  const [productSku, setProductSku] = useState('');
  const [productPrice, setProductPrice] = useState('0');
  const [productDescription, setProductDescription] = useState('');
  const [productWeight, setProductWeight] = useState('');
  const [productLength, setProductLength] = useState('');
  const [productWidth, setProductWidth] = useState('');
  const [productHeight, setProductHeight] = useState('');
  const [productCategoryId, setProductCategoryId] = useState('');
  const [productBrandId, setProductBrandId] = useState('');
  const [productUnitId, setProductUnitId] = useState('');
  const [editReorder, setEditReorder] = useState('0');
  const [editPrice, setEditPrice] = useState('0');
  const [editBarcode, setEditBarcode] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editWeight, setEditWeight] = useState('');
  const [editLength, setEditLength] = useState('');
  const [editWidth, setEditWidth] = useState('');
  const [editHeight, setEditHeight] = useState('');
  const [productBarcode, setProductBarcode] = useState('');
  const [productSupplyClass, setProductSupplyClass] = useState('standard');
  const [editSupplyClass, setEditSupplyClass] = useState('standard');
  const [labelCopies, setLabelCopies] = useState('1');
  const [barcodeSymbology, setBarcodeSymbology] = useState('code128');
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importReport, setImportReport] = useState<ImportReport | null>(null);
  const [importBusy, setImportBusy] = useState(false);
  const [lookupQuery, setLookupQuery] = useState('');
  const [lookupBarcode, setLookupBarcode] = useState('');
  const [lookupBusy, setLookupBusy] = useState(false);
  const [lookupHits, setLookupHits] = useState<any[]>([]);
  const [lookupMeta, setLookupMeta] = useState<{ q?: string; barcode?: string | null; count?: number } | null>(
    null
  );
  const [lookupStock, setLookupStock] = useState<any | null>(null);

  const [catCode, setCatCode] = useState('');
  const [catName, setCatName] = useState('');
  const [catParentId, setCatParentId] = useState('');
  const [catTaxRateId, setCatTaxRateId] = useState('');
  const [taxRates, setTaxRates] = useState<any[]>([]);
  const [brandCode, setBrandCode] = useState('');
  const [brandName, setBrandName] = useState('');
  const [brandDescription, setBrandDescription] = useState('');
  const [brandLogoPreview, setBrandLogoPreview] = useState<Record<string, string>>({});
  const [unitCode, setUnitCode] = useState('');
  const [unitName, setUnitName] = useState('');
  const [unitBaseId, setUnitBaseId] = useState('');
  const [unitRatio, setUnitRatio] = useState('1');
  const [stockUnitId, setStockUnitId] = useState('');

  const [variantName, setVariantName] = useState('');
  const [variantSku, setVariantSku] = useState('');
  const [variantSize, setVariantSize] = useState('');
  const [variantColor, setVariantColor] = useState('');
  const [variantFlavor, setVariantFlavor] = useState('');
  const [variantDosage, setVariantDosage] = useState('');
  const [variantBarcode, setVariantBarcode] = useState('');
  const [batchNumber, setBatchNumber] = useState('');
  const [mfgDate, setMfgDate] = useState('');
  const [expiryDate, setExpiryDate] = useState('');
  const [stockQty, setStockQty] = useState('10');
  const [stockWarehouseId, setStockWarehouseId] = useState('');
  const [stockVariantId, setStockVariantId] = useState('');
  const [stockNotes, setStockNotes] = useState('');
  const [openingQty, setOpeningQty] = useState('10');
  const [openingWarehouseId, setOpeningWarehouseId] = useState('');
  const [openingUnitId, setOpeningUnitId] = useState('');
  const [openingVariantId, setOpeningVariantId] = useState('');
  const [openingUnitCost, setOpeningUnitCost] = useState('');
  const [openingBatch, setOpeningBatch] = useState('');
  const [openingMfg, setOpeningMfg] = useState('');
  const [openingExpiry, setOpeningExpiry] = useState('');
  const [openingReference, setOpeningReference] = useState('');
  const [openingNotes, setOpeningNotes] = useState('');
  const [openingLineNotes, setOpeningLineNotes] = useState('');
  const [openingPostJournal, setOpeningPostJournal] = useState(true);
  const [openingHistory, setOpeningHistory] = useState<any[]>([]);
  const [movements, setMovements] = useState<any[]>([]);
  const [mvWarehouseId, setMvWarehouseId] = useState('');
  const [mvType, setMvType] = useState('');
  const [mvFrom, setMvFrom] = useState('');
  const [mvTo, setMvTo] = useState('');
  const [mvProductOnly, setMvProductOnly] = useState(false);
  const [mvMeta, setMvMeta] = useState<{ count?: number; warehouse_name?: string | null }>({});
  const [mvReason, setMvReason] = useState('');
  const [adjQty, setAdjQty] = useState('-1');
  const [adjReason, setAdjReason] = useState('');
  const [adjWarehouseId, setAdjWarehouseId] = useState('');
  const [adjNotes, setAdjNotes] = useState('');
  const [outQty, setOutQty] = useState('1');
  const [outRefType, setOutRefType] = useState('');
  const [outRefId, setOutRefId] = useState('');
  const [outWarehouseId, setOutWarehouseId] = useState('');
  const [outVariantId, setOutVariantId] = useState('');
  const [outUnitId, setOutUnitId] = useState('');
  const [outBatchId, setOutBatchId] = useState('');
  const [outNotes, setOutNotes] = useState('');
  const [whStockWarehouseId, setWhStockWarehouseId] = useState('');
  const [whStockIncludeZero, setWhStockIncludeZero] = useState(false);
  const [whStockRows, setWhStockRows] = useState<any[]>([]);
  const [whStockMeta, setWhStockMeta] = useState<{
    warehouse_name?: string;
    total_quantity?: number;
    count?: number;
  }>({});
  const [whReorderProductId, setWhReorderProductId] = useState('');
  const [whReorderLevel, setWhReorderLevel] = useState('0');
  const [whReorderQty, setWhReorderQty] = useState('0');
  const [transfers, setTransfers] = useState<any[]>([]);
  const [xferFromWh, setXferFromWh] = useState('');
  const [xferToWh, setXferToWh] = useState('');
  const [xferQty, setXferQty] = useState('1');
  const [xferNotes, setXferNotes] = useState('');
  const [xferRejectReason, setXferRejectReason] = useState('');
  const [countCancelReason, setCountCancelReason] = useState('');
  const [trPrefix, setTrPrefix] = useState('TR');
  const [trNext, setTrNext] = useState('1');
  const [trPreview, setTrPreview] = useState('');
  const [scPrefix, setScPrefix] = useState('SC');
  const [scNext, setScNext] = useState('1');
  const [scPreview, setScPreview] = useState('');
  const [osPrefix, setOsPrefix] = useState('OS');
  const [osNext, setOsNext] = useState('1');
  const [osPreview, setOsPreview] = useState('');

  async function refresh() {
    const [p, e, c, b, u, w, sc, os, rates, settings] = await Promise.all([
      api('/products'),
      api('/inventory/batches/expiring?days=60'),
      api('/catalog/categories'),
      api('/catalog/brands'),
      api('/catalog/units'),
      api('/warehouses'),
      api('/inventory/stock-counts'),
      api('/inventory/opening-stock').catch(() => ({ data: [] })),
      api('/tax/rates').catch(() => ({ data: [] })),
      api('/inventory/settings').catch(() => ({ data: null })),
    ]);
    setProducts(p.data || []);
    setExpiring(e.data?.batches || []);
    setCategories(c.data || []);
    setBrands(b.data || []);
    setUnits(u.data || []);
    setWarehouses(w.data || []);
    setCounts(sc.data || []);
    setOpeningHistory(os.data || []);
    setTaxRates(rates.data || []);
    const trNum = settings.data?.stock_transfer_numbering;
    if (trNum) {
      setTrPrefix(trNum.prefix || 'TR');
      setTrNext(String(trNum.next_number ?? 1));
      setTrPreview(trNum.preview || '');
    }
    const scNum = settings.data?.stock_count_numbering;
    if (scNum) {
      setScPrefix(scNum.prefix || 'SC');
      setScNext(String(scNum.next_number ?? 1));
      setScPreview(scNum.preview || '');
    }
    const osNum = settings.data?.opening_stock_numbering;
    if (osNum) {
      setOsPrefix(osNum.prefix || 'OS');
      setOsNext(String(osNum.next_number ?? 1));
      setOsPreview(osNum.preview || '');
    }
    if (!selectedId && p.data?.length) setSelectedId(p.data[0].id);
    if (!countWarehouseId && w.data?.length) setCountWarehouseId(w.data[0].id);
    if (!openingWarehouseId && w.data?.length) setOpeningWarehouseId(w.data[0].id);
    if (!stockWarehouseId && w.data?.length) setStockWarehouseId(w.data[0].id);
    if (!whStockWarehouseId && w.data?.length) setWhStockWarehouseId(w.data[0].id);
    const linked = (w.data || []).filter((x: any) => x.store_id);
    if (!xferFromWh && linked[0]) setXferFromWh(linked[0].id);
    if (!xferToWh && linked[1]) setXferToWh(linked[1].id);
    else if (!xferToWh && linked[0]) setXferToWh(linked[0].id);
  }

  async function saveInventoryNumbering() {
    setError('');
    setMessage('');
    try {
      const r = await api('/inventory/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          stock_transfer_numbering: {
            prefix: trPrefix.trim(),
            next_number: Math.max(1, Number(trNext) || 1),
          },
          stock_count_numbering: {
            prefix: scPrefix.trim(),
            next_number: Math.max(1, Number(scNext) || 1),
          },
          opening_stock_numbering: {
            prefix: osPrefix.trim(),
            next_number: Math.max(1, Number(osNext) || 1),
          },
        }),
      });
      const trNum = r.data?.stock_transfer_numbering;
      if (trNum) {
        setTrPrefix(trNum.prefix || 'TR');
        setTrNext(String(trNum.next_number ?? 1));
        setTrPreview(trNum.preview || '');
      }
      const scNum = r.data?.stock_count_numbering;
      if (scNum) {
        setScPrefix(scNum.prefix || 'SC');
        setScNext(String(scNum.next_number ?? 1));
        setScPreview(scNum.preview || '');
      }
      const osNum = r.data?.opening_stock_numbering;
      if (osNum) {
        setOsPrefix(osNum.prefix || 'OS');
        setOsNext(String(osNum.next_number ?? 1));
        setOsPreview(osNum.preview || '');
      }
      setMessage(
        `Numbering saved — TR ${trNum?.preview || ''} / SC ${scNum?.preview || ''} / OS ${osNum?.preview || ''}`.trim()
      );
    } catch (err: any) {
      setError(err.message);
    }
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
    setStockVariantId('');
    setOpeningVariantId('');
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function loadMovements(overrides: {
    warehouse_id?: string;
    movement_type?: string;
    reason?: string;
    from_date?: string;
    to_date?: string;
    product_id?: string | null;
  } = {}) {
    setError('');
    try {
      const params = new URLSearchParams();
      const warehouse = overrides.warehouse_id ?? mvWarehouseId;
      const type = overrides.movement_type ?? mvType;
      const reason = overrides.reason ?? mvReason;
      const from = overrides.from_date ?? mvFrom;
      const to = overrides.to_date ?? mvTo;
      const productOnly =
        overrides.product_id !== undefined
          ? Boolean(overrides.product_id)
          : mvProductOnly && selectedId;
      const productId =
        overrides.product_id !== undefined
          ? overrides.product_id
          : mvProductOnly
            ? selectedId
            : null;
      if (warehouse) params.set('warehouse_id', warehouse);
      if (type) params.set('movement_type', type);
      if (reason) params.set('reason', reason);
      if (from) params.set('from_date', from);
      if (to) params.set('to_date', to);
      if (productOnly && productId) params.set('product_id', productId);
      const q = params.toString();
      const r = await api(`/inventory/movements${q ? `?${q}` : ''}`);
      const data = r.data || {};
      setMovements(data.movements || []);
      setMvMeta({
        count: data.count,
        warehouse_name: data.warehouse_name,
      });
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (tab === 'movements') {
      loadMovements().catch((err) => setError(err.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function loadWarehouseStock(overrides: {
    warehouse_id?: string;
    include_zero?: boolean;
  } = {}) {
    setError('');
    const warehouse = overrides.warehouse_id ?? whStockWarehouseId;
    const includeZero = overrides.include_zero ?? whStockIncludeZero;
    if (!warehouse) {
      setWhStockRows([]);
      setWhStockMeta({});
      return;
    }
    try {
      const params = new URLSearchParams();
      params.set('warehouse_id', warehouse);
      if (includeZero) params.set('include_zero', 'true');
      const r = await api(`/inventory/warehouse-stock?${params.toString()}`);
      const data = r.data || {};
      setWhStockRows(data.items || []);
      setWhStockMeta({
        warehouse_name: data.warehouse_name,
        total_quantity: data.total_quantity,
        count: data.count,
      });
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (tab === 'whstock') {
      loadWarehouseStock().catch((err) => setError(err.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, whStockWarehouseId, whStockIncludeZero]);

  async function loadTransfers() {
    setError('');
    try {
      const r = await api('/inventory/stock-transfers');
      setTransfers(r.data || []);
    } catch (err: any) {
      setError(err.message);
    }
  }

  useEffect(() => {
    if (tab === 'transfers') {
      loadTransfers().catch((err) => setError(err.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function createWarehouseTransfer() {
    setError('');
    setMessage('');
    if (!xferFromWh || !xferToWh) {
      setError('Select source and destination warehouses');
      return;
    }
    if (xferFromWh === xferToWh) {
      setError('Source and destination warehouses must differ');
      return;
    }
    if (!selectedId) {
      setError('Select a product');
      return;
    }
    const qty = Number(xferQty);
    if (!Number.isFinite(qty) || qty <= 0) {
      setError('Quantity must be positive');
      return;
    }
    try {
      const r = await api('/inventory/stock-transfers', {
        method: 'POST',
        body: JSON.stringify({
          from_warehouse_id: xferFromWh,
          to_warehouse_id: xferToWh,
          submit: true,
          notes: xferNotes.trim() || null,
          items: [{ product_id: selectedId, quantity: qty }],
        }),
      });
      setMessage(
        `Transfer ${r.data.transfer_number} requested` +
          (r.data.approval_steps_required <= 1
            ? ' (single approval — same store)'
            : ' (dual approval)')
      );
      setXferNotes('');
      await loadTransfers();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function transferAct(id: string, action: string) {
    setError('');
    setMessage('');
    if (action === 'reject' || action === 'cancel') {
      const reason = xferRejectReason.trim();
      if (!reason) {
        setError(
          action === 'cancel'
            ? 'Enter a cancel reason before cancelling a stock transfer'
            : 'Enter a reject reason before rejecting a stock transfer'
        );
        return;
      }
    }
    try {
      const r = await api(`/inventory/stock-transfers/${id}/${action}`, {
        method: 'POST',
        body:
          action === 'reject' || action === 'cancel'
            ? JSON.stringify({ reason: xferRejectReason.trim() })
            : undefined,
      });
      if (action === 'reject' || action === 'cancel') {
        setXferRejectReason('');
      }
      setMessage(r.message || `Transfer ${action} ok`);
      await loadTransfers();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function warehouseLabel(id: string | null | undefined) {
    if (!id) return '—';
    const w = warehouses.find((x) => x.id === id);
    return w ? w.name || w.code || id.slice(0, 8) : id.slice(0, 8);
  }

  async function saveWarehouseReorder() {
    setError('');
    setMessage('');
    if (!whStockWarehouseId) {
      setError('Select a warehouse');
      return;
    }
    if (!whReorderProductId) {
      setError('Select a product for reorder policy');
      return;
    }
    try {
      const r = await api('/inventory/warehouse-stock/reorder', {
        method: 'PUT',
        body: JSON.stringify({
          warehouse_id: whStockWarehouseId,
          product_id: whReorderProductId,
          reorder_level: Number(whReorderLevel) || 0,
          reorder_qty: Number(whReorderQty) || 0,
        }),
      });
      setMessage(
        `Reorder saved for ${r.data.sku || r.data.name}: level ${r.data.reorder_level} / qty ${r.data.reorder_qty}`
      );
      await loadWarehouseStock();
    } catch (err: any) {
      setError(err.message);
    }
  }
  useEffect(() => {
    brands
      .filter((b) => b.has_logo)
      .forEach((b) => {
        if (!brandLogoPreview[b.id]) loadBrandLogoPreview(b.id);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brands]);

  useEffect(() => {
    if (selectedId) {
      refreshSelected(selectedId).catch((err) => setError(err.message));
      const p = products.find((x) => x.id === selectedId);
      if (p) {
        setEditReorder(String(p.reorder_level ?? 0));
        setEditPrice(String(p.selling_price ?? 0));
        setEditBarcode(String(p.barcode || ''));
        setEditDescription(String(p.description || ''));
        setEditWeight(p.weight != null ? String(p.weight) : '');
        setEditLength(p.length != null ? String(p.length) : '');
        setEditWidth(p.width != null ? String(p.width) : '');
        setEditHeight(p.height != null ? String(p.height) : '');
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
          description: editDescription.trim() || null,
          weight: editWeight === '' ? null : Number(editWeight),
          length: editLength === '' ? null : Number(editLength),
          width: editWidth === '' ? null : Number(editWidth),
          height: editHeight === '' ? null : Number(editHeight),
          tax_supply_class: editSupplyClass,
        }),
      });
      setMessage('Product updated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function setProductActive(is_active: boolean) {
    if (!selectedId) return;
    setError('');
    try {
      await api(`/products/${selectedId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      setMessage(is_active ? 'Product activated' : 'Product deactivated');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function generateBarcode() {
    if (!selectedId) return;
    setError('');
    try {
      const r = await api(
        `/products/${selectedId}/barcode/generate?force=true&symbology=${encodeURIComponent(barcodeSymbology)}`,
        { method: 'POST', body: '{}' }
      );
      setEditBarcode(r.data?.barcode || '');
      setMessage(`Barcode set to ${r.data?.barcode} (${r.data?.symbology || barcodeSymbology})`);
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
        `${apiBase}/products/${selectedId}/barcode/label?copies=${copies}&symbology=${encodeURIComponent(barcodeSymbology)}`,
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
        body: JSON.stringify({
          warehouse_id: countWarehouseId,
          notes: countNotes.trim() || null,
        }),
      });
      setActiveCount(r.data);
      const qtys: Record<string, string> = {};
      for (const item of r.data.items || []) {
        qtys[item.product_id] = String(item.expected_qty ?? 0);
      }
      setCountQtys(qtys);
      setCountNotes('');
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
      const notes: Record<string, string> = {};
      for (const item of r.data.items || []) {
        qtys[item.product_id] =
          item.counted_qty == null ? String(item.expected_qty ?? 0) : String(item.counted_qty);
        notes[item.product_id] = item.notes || '';
      }
      setCountQtys(qtys);
      setCountLineNotes(notes);
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
        notes: (countLineNotes[item.product_id] || '').trim() || null,
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

  async function cancelStockCount(id: string, countNumber?: string) {
    setError('');
    const reason = countCancelReason.trim();
    if (!reason) {
      setError('Enter a cancel reason before cancelling a stock count');
      return;
    }
    try {
      const r = await api(`/inventory/stock-counts/${id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setMessage(`Count ${r.data?.count_number || countNumber || id} cancelled`);
      setCountCancelReason('');
      if (activeCount?.id === id) {
        setActiveCount(r.data);
      }
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
          name: productName.trim(),
          sku: productSku.trim() || null,
          barcode: productBarcode.trim() || null,
          description: productDescription.trim() || null,
          selling_price: Number(productPrice) || 0,
          weight: productWeight === '' ? null : Number(productWeight),
          length: productLength === '' ? null : Number(productLength),
          width: productWidth === '' ? null : Number(productWidth),
          height: productHeight === '' ? null : Number(productHeight),
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
      setProductDescription('');
      setProductWeight('');
      setProductLength('');
      setProductWidth('');
      setProductHeight('');
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

  async function downloadProductsExport() {
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
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Product export failed');
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'products-export.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('Products CSV exported');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function runProductLookup(opts?: { selectId?: string }) {
    setError('');
    setMessage('');
    const q = lookupQuery.trim();
    const barcode = lookupBarcode.trim();
    if (!q && !barcode) {
      setError('Enter a barcode or search text');
      return;
    }
    setLookupBusy(true);
    try {
      const params = new URLSearchParams();
      if (barcode) params.set('barcode', barcode);
      else if (q) params.set('q', q);
      const r = await api(`/inventory/products/lookup?${params.toString()}`);
      const data = r.data || {};
      const items = data.items || [];
      setLookupHits(items);
      setLookupMeta({ q: data.q, barcode: data.barcode, count: data.count });
      setLookupStock(null);
      if (!items.length) {
        setMessage('No products matched');
        return;
      }
      const pickId = opts?.selectId || items[0].id;
      setSelectedId(pickId);
      const stock = await api(`/products/${pickId}/warehouse-stock`);
      setLookupStock(stock.data);
      setMessage(
        `Found ${data.count} product(s)` +
          (data.barcode ? ` for barcode ${data.barcode}` : q ? ` for “${q}”` : '')
      );
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLookupBusy(false);
    }
  }

  async function selectLookupHit(productId: string) {
    setSelectedId(productId);
    setError('');
    try {
      const stock = await api(`/products/${productId}/warehouse-stock`);
      setLookupStock(stock.data);
      setTab('lookup');
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

  async function loadBrandLogoPreview(brandId: string) {
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/catalog/brands/${brandId}/logo`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      setBrandLogoPreview((prev) => {
        if (prev[brandId]) URL.revokeObjectURL(prev[brandId]);
        return { ...prev, [brandId]: url };
      });
    } catch {
      /* ignore preview failures */
    }
  }

  async function uploadBrandLogo(brandId: string, file: File) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${apiBase}/catalog/brands/${brandId}/logo`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || body.message || 'Upload failed');
      setMessage('Brand logo uploaded');
      await refresh();
      await loadBrandLogoPreview(brandId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeBrandLogo(brandId: string) {
    setError('');
    try {
      await api(`/catalog/brands/${brandId}/logo`, { method: 'DELETE' });
      setBrandLogoPreview((prev) => {
        if (prev[brandId]) URL.revokeObjectURL(prev[brandId]);
        const next = { ...prev };
        delete next[brandId];
        return next;
      });
      setMessage('Brand logo removed');
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

  async function activateVariant(variantId: string) {
    if (!selectedId) return;
    setError('');
    try {
      await api(`/products/${selectedId}/variants/${variantId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: true }),
      });
      setMessage('Variant activated');
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

  async function generateVariantBarcode(variantId: string) {
    if (!selectedId) return;
    setError('');
    try {
      const r = await api(
        `/products/${selectedId}/variants/${variantId}/barcode/generate?force=true&symbology=${encodeURIComponent(barcodeSymbology)}`,
        { method: 'POST', body: '{}' }
      );
      setMessage(
        `Variant barcode set to ${r.data?.barcode} (${r.data?.symbology || barcodeSymbology})`
      );
      await refreshSelected(selectedId);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function printVariantBarcodeLabel(variantId: string) {
    if (!selectedId) return;
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const copies = Math.max(1, Math.min(40, Number(labelCopies) || 1));
      const res = await fetch(
        `${apiBase}/products/${selectedId}/variants/${variantId}/barcode/label?copies=${copies}&symbology=${encodeURIComponent(barcodeSymbology)}`,
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
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      setMessage('Variant barcode label opened — use Print labels');
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
          name: variantName.trim(),
          sku: variantSku.trim() || null,
          barcode: variantBarcode.trim() || null,
          size: variantSize.trim() || null,
          color: variantColor.trim() || null,
          flavor: variantFlavor.trim() || null,
          dosage: variantDosage.trim() || null,
        }),
      });
      setMessage(`Variant ${r.data.sku} created`);
      setVariantName('');
      setVariantSku('');
      setVariantBarcode('');
      setVariantSize('');
      setVariantColor('');
      setVariantFlavor('');
      setVariantDosage('');
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
          unit_id: stockUnitId || null,
          warehouse_id: stockWarehouseId || null,
          variant_id: stockVariantId || null,
          notes: stockNotes.trim() || null,
          batch_number: batchNumber,
          manufacturing_date: mfgDate.trim() || null,
          expiry_date: expiryDate.trim() || null,
        }),
      });
      const converted =
        r.data.quantity_base != null && r.data.quantity_entered != null
          ? ` (${r.data.quantity_entered} entered → ${r.data.quantity_base} stock)`
          : '';
      const loc =
        r.data.batch?.warehouse_id || stockWarehouseId
          ? ` · wh ${(r.data.batch?.warehouse_id || stockWarehouseId).slice(0, 8)}…`
          : '';
      const varLabel = r.data.variant?.sku ? ` · ${r.data.variant.sku}` : '';
      setMessage(`Stock in — on-hand ${r.data.stock_qty}${converted}${loc}${varLabel}`);
      setBatchNumber('');
      setMfgDate('');
      setExpiryDate('');
      setStockNotes('');
      await refresh();
      await refreshSelected(selectedId);
      setTab('batches');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function postOpeningStock() {
    setError('');
    setMessage('');
    if (!selectedId) {
      setError('Select a product');
      return;
    }
    try {
      const line: Record<string, unknown> = {
        product_id: selectedId,
        quantity: Number(openingQty),
        unit_id: openingUnitId || null,
        warehouse_id: openingWarehouseId || null,
        variant_id: openingVariantId || null,
        batch_number: openingBatch || null,
        manufacturing_date: openingMfg.trim() || null,
        expiry_date: openingExpiry.trim() || null,
        notes: openingLineNotes.trim() || null,
      };
      if (openingUnitCost !== '') line.unit_cost = Number(openingUnitCost);
      const r = await api('/inventory/opening-stock', {
        method: 'POST',
        body: JSON.stringify({
          reference: openingReference.trim() || null,
          notes: openingNotes.trim() || null,
          post_journal: openingPostJournal,
          lines: [line],
        }),
      });
      const je = r.data.journal_number ? ` · JE ${r.data.journal_number}` : '';
      setMessage(
        `Opening stock ${r.data.reference}: ${r.data.line_count} line(s), value ${r.data.inventory_value}${je}`,
      );
      setOpeningBatch('');
      setOpeningMfg('');
      setOpeningExpiry('');
      setOpeningNotes('');
      setOpeningLineNotes('');
      await refresh();
      await refreshSelected(selectedId);
      setTab('opening');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function postStockAdjust() {
    setError('');
    setMessage('');
    if (!selectedId) {
      setError('Select a product');
      return;
    }
    if (!adjReason.trim()) {
      setError('Select an adjustment reason');
      return;
    }
    const qty = Number(adjQty);
    if (!Number.isFinite(qty) || qty === 0) {
      setError('Quantity delta must be a non-zero number');
      return;
    }
    try {
      const reason = adjReason;
      const r = await api(`/inventory/adjust/${selectedId}`, {
        method: 'POST',
        body: JSON.stringify({
          quantity: qty,
          reason,
          notes: adjNotes.trim() || null,
          warehouse_id: adjWarehouseId || null,
        }),
      });
      setMessage(
        `Adjusted (${r.data.reason}) — on-hand ${r.data.stock_qty}` +
          (r.data.warehouse_id ? ` · warehouse ${String(r.data.warehouse_id).slice(0, 8)}…` : '')
      );
      setAdjNotes('');
      setAdjReason('');
      await refresh();
      setMvType('adjustment');
      setMvReason(reason);
      setTab('movements');
      await loadMovements({ movement_type: 'adjustment', reason });
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function postStockOut() {
    setError('');
    setMessage('');
    if (!selectedId) {
      setError('Select a product');
      return;
    }
    if (!outRefType.trim()) {
      setError('Select a stock-out reference type');
      return;
    }
    const qty = Number(outQty);
    if (!Number.isFinite(qty) || qty <= 0) {
      setError('Quantity must be a positive number');
      return;
    }
    try {
      const r = await api('/inventory/stock-out', {
        method: 'POST',
        body: JSON.stringify({
          product_id: selectedId,
          quantity: qty,
          reference_type: outRefType,
          reference_id: outRefId.trim() || null,
          notes: outNotes.trim() || null,
          warehouse_id: outWarehouseId || null,
          variant_id: outVariantId || null,
          unit_id: outUnitId || null,
          batch_id: outBatchId || null,
        }),
      });
      setMessage(
        `Stock out (${r.data.reference_type}) — on-hand ${r.data.stock_qty}` +
          (r.data.warehouse_id ? ` · warehouse ${String(r.data.warehouse_id).slice(0, 8)}…` : '')
      );
      setOutNotes('');
      setOutRefId('');
      setOutRefType('');
      await refresh();
      setMvType('stock_out');
      setMvReason('');
      setTab('movements');
      await loadMovements({ movement_type: 'stock_out' });
    } catch (err: any) {
      setError(err.message);
    }
  }

  const selected = products.find((p) => p.id === selectedId);
  const managedProducts = products.filter((p) => {
    if (productManageFilter === 'all') return true;
    const active = p.is_active !== false;
    return productManageFilter === 'inactive' ? !active : active;
  });
  const byStatus = <T extends { is_active?: boolean }>(
    rows: T[],
    filter: 'all' | 'active' | 'inactive',
  ) =>
    rows.filter((r) => {
      if (filter === 'all') return true;
      const active = r.is_active !== false;
      return filter === 'inactive' ? !active : active;
    });
  const managedCategories = byStatus(categories, categoryManageFilter);
  const managedBrands = byStatus(brands, brandManageFilter);
  const managedUnits = byStatus(units, unitManageFilter);
  const managedVariants = byStatus(variants, variantManageFilter);
  const managedCounts = counts.filter((c) => {
    if (countManageFilter === 'all') return true;
    return (c.status || 'draft') === countManageFilter;
  });
  const managedTransfers = transfers.filter((t) => {
    if (transferManageFilter === 'all') return true;
    return (t.status || 'draft') === transferManageFilter;
  });

  return (
    <Shell>
      <h1>Inventory</h1>
      <p className="muted">
        Products, catalog, variants, batches, stock out, warehouse stock, transfers, expiry, stock
        counts, movements &amp; adjustments
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(
          [
            ['products', 'Products'],
            ['lookup', 'Lookup'],
            ['import', 'Import'],
            ['catalog', 'Catalog'],
            ['variants', 'Variants'],
            ['batches', 'Batches'],
            ['opening', 'Opening stock'],
            ['stockout', 'Stock Out'],
            ['whstock', 'Warehouse stock'],
            ['transfers', 'Transfers'],
            ['expiry', 'Expiring'],
            ['counts', 'Stock counts'],
            ['movements', 'Movements'],
            ['adjust', 'Adjust'],
          ] as const
        ).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} disabled={tab === id}>
            {label}
          </button>
        ))}
      </div>

      <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
        <strong>Document numbering</strong>
        <p className="muted" style={{ margin: 0 }}>
          Transfers, stock counts, and opening stock use PREFIX-YYYY-NNNN (defaults TR / SC / OS).
          Blank opening-stock reference auto-allocates the next OS number.
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Transfer</span>
          <input
            value={trPrefix}
            onChange={(e) => setTrPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={trNext}
            onChange={(e) => setTrNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{trPreview || '—'}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Stock count</span>
          <input
            value={scPrefix}
            onChange={(e) => setScPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={scNext}
            onChange={(e) => setScNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{scPreview || '—'}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Opening stock</span>
          <input
            value={osPrefix}
            onChange={(e) => setOsPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={osNext}
            onChange={(e) => setOsNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{osPreview || '—'}</span>
          <button type="button" onClick={saveInventoryNumbering}>
            Save numbering
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <label className="muted">Selected product</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          <select
            value={productManageFilter}
            onChange={(e) => {
              const next = e.target.value as 'all' | 'active' | 'inactive';
              setProductManageFilter(next);
              if (selectedId) {
                const row = products.find((p) => p.id === selectedId);
                const active = row?.is_active !== false;
                if (next === 'active' && !active) setSelectedId('');
                if (next === 'inactive' && active) setSelectedId('');
              }
            }}
            title="Filter manage product list by status"
            aria-label="Product status filter"
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
        </div>
        <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} style={{ width: '100%' }}>
          <option value="">Select product</option>
          {managedProducts.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.sku}) — {p.stock_qty}
              {p.is_active === false ? ' [inactive]' : ''}
            </option>
          ))}
        </select>
        {selected?.is_active === false && (
          <p className="muted">Inactive — hidden from sales/purchasing/POS pickers; stock ops still allowed</p>
        )}
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
              aria-label="Edit product barcode"
              title="Optional barcode (4–48 chars: letters, numbers, - . _)"
            />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <select
                value={barcodeSymbology}
                onChange={(e) => setBarcodeSymbology(e.target.value)}
                title="Symbology"
                aria-label="Barcode symbology"
              >
                <option value="code128">Code 128</option>
                <option value="ean13">EAN-13</option>
                <option value="upca">UPC-A</option>
              </select>
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
            <label className="muted">Description</label>
            <textarea
              value={editDescription}
              onChange={(e) => setEditDescription(e.target.value)}
              placeholder="Product description"
              aria-label="Edit product description"
              title="Optional description (1–500 chars; letters/digits required)"
              rows={2}
            />
            <label className="muted">Weight (kg) / dimensions (cm)</label>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                value={editWeight}
                onChange={(e) => setEditWeight(e.target.value)}
                placeholder="Weight"
                style={{ width: 100 }}
              />
              <input
                value={editLength}
                onChange={(e) => setEditLength(e.target.value)}
                placeholder="Length"
                style={{ width: 80 }}
              />
              <input
                value={editWidth}
                onChange={(e) => setEditWidth(e.target.value)}
                placeholder="Width"
                style={{ width: 80 }}
              />
              <input
                value={editHeight}
                onChange={(e) => setEditHeight(e.target.value)}
                placeholder="Height"
                style={{ width: 80 }}
              />
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
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button type="button" onClick={saveProductEdits} aria-label="Save product">
                Save product
              </button>
              {selected?.is_active === false ? (
                <button type="button" className="btn-ok" onClick={() => setProductActive(true)}>
                  Activate
                </button>
              ) : (
                <button type="button" className="btn-danger" onClick={() => setProductActive(false)}>
                  Deactivate
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {tab === 'lookup' && (
        <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 12 }}>
          <h3>Product lookup</h3>
          <p className="muted" style={{ margin: 0 }}>
            Scan a barcode or search by name/SKU (GET /inventory/products/lookup). Selecting a hit
            loads per-warehouse stock (GET /products/:id/warehouse-stock) and sets the product for
            other Inventory actions.
          </p>
          <div className="erp-form-grid" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              value={lookupBarcode}
              onChange={(e) => setLookupBarcode(e.target.value)}
              placeholder="Barcode (exact)"
              style={{ minWidth: 180 }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  runProductLookup();
                }
              }}
            />
            <input
              value={lookupQuery}
              onChange={(e) => setLookupQuery(e.target.value)}
              placeholder="Name / SKU search"
              style={{ minWidth: 200 }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  runProductLookup();
                }
              }}
            />
            <button type="button" onClick={() => runProductLookup()} disabled={lookupBusy}>
              {lookupBusy ? 'Searching…' : 'Lookup'}
            </button>
          </div>
          {lookupMeta && (
            <p className="muted" style={{ margin: 0 }}>
              Matches: {lookupMeta.count ?? lookupHits.length}
              {lookupMeta.barcode ? ` · barcode ${lookupMeta.barcode}` : ''}
              {lookupMeta.q ? ` · q “${lookupMeta.q}”` : ''}
            </p>
          )}
          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Name</th>
                <th>Barcode</th>
                <th>Stock</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lookupHits.map((p) => (
                <tr key={p.id} style={{ background: p.id === selectedId ? '#eff6ff' : undefined }}>
                  <td>{p.sku}</td>
                  <td>{p.name}</td>
                  <td>{p.barcode || '—'}</td>
                  <td>
                    <StockStatusBadge product={p} />
                  </td>
                  <td>{p.is_active === false ? 'inactive' : 'active'}</td>
                  <td>
                    <button type="button" onClick={() => selectLookupHit(p.id)}>
                      Select
                    </button>
                  </td>
                </tr>
              ))}
              {!lookupHits.length && (
                <tr>
                  <td colSpan={6} className="muted">
                    No lookup results yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {lookupStock && (
            <div style={{ display: 'grid', gap: 8 }}>
              <strong>
                Warehouse stock — {lookupStock.sku} ({lookupStock.name}) · consolidated{' '}
                {lookupStock.consolidated_stock}
              </strong>
              <table className="table">
                <thead>
                  <tr>
                    <th>Warehouse</th>
                    <th>Qty</th>
                    <th>Reorder</th>
                    <th>Reorder qty</th>
                    <th>Below?</th>
                  </tr>
                </thead>
                <tbody>
                  {(lookupStock.items || []).map((row: any) => (
                    <tr key={row.warehouse_id}>
                      <td>
                        {row.warehouse_code} — {row.warehouse_name}
                      </td>
                      <td>{row.quantity}</td>
                      <td>{row.reorder_level}</td>
                      <td>{row.reorder_qty}</td>
                      <td>{row.below_reorder ? 'yes' : '—'}</td>
                    </tr>
                  ))}
                  {!(lookupStock.items || []).length && (
                    <tr>
                      <td colSpan={5} className="muted">
                        No warehouse rows for this product
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
              <p className="muted" style={{ margin: 0 }}>
                Located total {lookupStock.total_quantity ?? 0} · product selected for stock
                ops / barcode tools above
              </p>
            </div>
          )}
        </div>
      )}

      {tab === 'import' && (
        <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 12 }}>
          <h3>Bulk import products</h3>
          <p className="muted" style={{ margin: 0 }}>
            Download the CSV template, fill product rows (category / brand / unit must already exist),
            validate, then import. Import is all-or-nothing — fix every error row first. Export
            downloads the current catalog in the same column layout.
          </p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button type="button" onClick={downloadImportTemplate}>
              Download CSV template
            </button>
            <button type="button" onClick={downloadProductsExport}>
              Export products CSV
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
            <input
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="Name"
              aria-label="Product name"
              title="Product name (1–200 chars; letters/digits required)"
            />
            <input
              value={productSku}
              onChange={(e) => setProductSku(e.target.value)}
              placeholder="SKU (auto if blank)"
            />
            <input
              value={productBarcode}
              onChange={(e) => setProductBarcode(e.target.value)}
              placeholder="Barcode (optional)"
              aria-label="Product barcode"
              title="Optional barcode (4–48 chars: letters, numbers, - . _)"
            />
            <textarea
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="Description (optional)"
              aria-label="Product description"
              title="Optional description (1–500 chars; letters/digits required)"
              rows={2}
            />
            <input value={productPrice} onChange={(e) => setProductPrice(e.target.value)} placeholder="Selling price" />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                value={productWeight}
                onChange={(e) => setProductWeight(e.target.value)}
                placeholder="Weight kg"
                style={{ width: 100 }}
              />
              <input
                value={productLength}
                onChange={(e) => setProductLength(e.target.value)}
                placeholder="L cm"
                style={{ width: 80 }}
              />
              <input
                value={productWidth}
                onChange={(e) => setProductWidth(e.target.value)}
                placeholder="W cm"
                style={{ width: 80 }}
              />
              <input
                value={productHeight}
                onChange={(e) => setProductHeight(e.target.value)}
                placeholder="H cm"
                style={{ width: 80 }}
              />
            </div>
            <select value={productCategoryId} onChange={(e) => setProductCategoryId(e.target.value)}>
              <option value="">Category</option>
              {categories
                .filter((c) => c.is_active !== false)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {categoryIndent(c.depth)}
                    {categoryLabel(c)}
                  </option>
                ))}
            </select>
            <select value={productBrandId} onChange={(e) => setProductBrandId(e.target.value)}>
              <option value="">Brand</option>
              {brands
                .filter((b) => b.is_active !== false)
                .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <select value={productUnitId} onChange={(e) => setProductUnitId(e.target.value)}>
              <option value="">Unit</option>
              {units
                .filter((u) => u.is_active !== false)
                .map((u) => (
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
            <button
              onClick={createProduct}
              disabled={!productName.trim()}
              aria-label="Create product"
            >
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
                <th>Active</th>
                <th>Image</th>
              </tr>
            </thead>
            <tbody>
              {managedProducts.map((p) => (
                <tr key={p.id}>
                  <td>
                    <button
                      onClick={() => setSelectedId(p.id)}
                      style={{ background: 'none', border: 0, color: '#1d4ed8', cursor: 'pointer' }}
                    >
                      {p.name}
                      {p.is_active === false ? ' [inactive]' : ''}
                    </button>
                  </td>
                  <td>{p.sku}</td>
                  <td>{p.barcode || '—'}</td>
                  <td>{p.category}</td>
                  <td>
                    <StockStatusBadge product={p} />
                  </td>
                  <td>{p.tracks_batches ? 'yes' : 'no'}</td>
                  <td>{p.selling_price}</td>
                  <td>{p.is_active === false ? 'no' : 'yes'}</td>
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
            <h3>Category tree (BR-5.1)</h3>
            <p className="muted" style={{ margin: 0 }}>
              Hierarchical parent/child categories with codes. Optional category tax rate applies when
              a product has no product-level rate (nearest parent wins). Product rate still overrides.
            </p>
            <input value={catCode} onChange={(e) => setCatCode(e.target.value)} placeholder="Code" />
            <input
              value={catName}
              onChange={(e) => setCatName(e.target.value)}
              placeholder="Name"
              aria-label="Category name"
              title="Category name (1–120 chars; letters/digits required)"
            />
            <select value={catParentId} onChange={(e) => setCatParentId(e.target.value)}>
              <option value="">Parent (optional — root)</option>
              {categories
                .filter((c) => c.is_active !== false)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {categoryIndent(c.depth)}
                    {categoryLabel(c)}
                  </option>
                ))}
            </select>
            <select value={catTaxRateId} onChange={(e) => setCatTaxRateId(e.target.value)}>
              <option value="">Tax rate (optional — tenant default)</option>
              {taxRates
                .filter((r) => r.is_active !== false)
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.rate}%){r.is_default ? ' · default' : ''}
                  </option>
                ))}
            </select>
            <button
              onClick={async () => {
                setError('');
                try {
                  const r = await api('/catalog/categories', {
                    method: 'POST',
                    body: JSON.stringify({
                      code: catCode.trim(),
                      name: catName.trim(),
                      parent_id: catParentId || null,
                      tax_rate_id: catTaxRateId || null,
                    }),
                  });
                  setCatCode('');
                  setCatName('');
                  setCatParentId('');
                  setCatTaxRateId('');
                  setMessage(`Category created: ${r.data?.path || r.data?.name || catName}`);
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              disabled={!catCode.trim() || !catName.trim()}
              aria-label="Add category"
            >
              Add category
            </button>
            <select
              value={categoryManageFilter}
              onChange={(e) =>
                setCategoryManageFilter(e.target.value as 'all' | 'active' | 'inactive')
              }
              title="Filter manage category list by status"
              aria-label="Catalog category status filter"
            >
              <option value="all">All statuses</option>
              <option value="active">Active only</option>
              <option value="inactive">Inactive only</option>
            </select>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 8 }}>
              {managedCategories.map((c) => {
                const rate = taxRates.find((r) => r.id === c.tax_rate_id);
                const depth = Math.max(0, Number(c.depth) || 0);
                return (
                  <li
                    key={c.id}
                    style={{
                      display: 'flex',
                      gap: 8,
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      paddingLeft: depth * 16,
                      borderLeft: depth ? '2px solid #cbd5e1' : undefined,
                    }}
                  >
                    <span className="muted" style={{ minWidth: 220 }}>
                      <strong style={{ color: 'inherit' }}>
                        {c.code} — {c.name}
                      </strong>
                      {depth > 0 ? ` · ${c.path || ''}` : ''}
                      {!c.is_active ? ' [inactive]' : ''}
                      {rate
                        ? ` · tax ${rate.name} (${rate.rate}%)`
                        : c.tax_rate_id
                          ? ' · tax set'
                          : ' · tax inherit/default'}
                    </span>
                    {c.is_active === false ? (
                      <button
                        type="button"
                        className="btn-ok"
                        onClick={async () => {
                          setError('');
                          try {
                            await api(`/catalog/categories/${c.id}`, {
                              method: 'PATCH',
                              body: JSON.stringify({ is_active: true }),
                            });
                            setMessage(`Category ${c.code} activated`);
                            await refresh();
                          } catch (err: any) {
                            setError(err.message);
                          }
                        }}
                      >
                        Activate
                      </button>
                    ) : (
                      <>
                        <select
                          aria-label={`Parent for ${c.code}`}
                          value={c.parent_id || ''}
                          onChange={async (e) => {
                            setError('');
                            try {
                              const value = e.target.value || null;
                              await api(`/catalog/categories/${c.id}`, {
                                method: 'PATCH',
                                body: JSON.stringify({ parent_id: value }),
                              });
                              setMessage(
                                value
                                  ? `Reparented ${c.code}`
                                  : `${c.code} moved to root`,
                              );
                              await refresh();
                            } catch (err: any) {
                              setError(err.message);
                            }
                          }}
                        >
                          <option value="">Root (no parent)</option>
                          {categories
                            .filter((p) => p.id !== c.id && p.is_active !== false)
                            .map((p) => (
                              <option key={p.id} value={p.id}>
                                {categoryIndent(p.depth)}
                                {categoryLabel(p)}
                              </option>
                            ))}
                        </select>
                        <select
                          value={c.tax_rate_id || ''}
                          onChange={async (e) => {
                            setError('');
                            try {
                              const value = e.target.value || null;
                              await api(`/catalog/categories/${c.id}`, {
                                method: 'PATCH',
                                body: JSON.stringify({ tax_rate_id: value }),
                              });
                              setMessage(
                                value ? `Tax rate set on ${c.code}` : `Tax rate cleared on ${c.code}`,
                              );
                              await refresh();
                            } catch (err: any) {
                              setError(err.message);
                            }
                          }}
                        >
                          <option value="">Inherit / tenant default</option>
                          {taxRates
                            .filter((r) => r.is_active !== false)
                            .map((r) => (
                              <option key={r.id} value={r.id}>
                                {r.name} ({r.rate}%)
                              </option>
                            ))}
                        </select>
                        <button
                          type="button"
                          className="btn-danger"
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
                      </>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="erp-split">
          <div className="card" style={{ display: 'grid', gap: 8 }}>
            <h3>Brand</h3>
            <p className="muted" style={{ margin: 0 }}>
              Name, description, and logo (BR-5.1).
            </p>
            <input value={brandCode} onChange={(e) => setBrandCode(e.target.value)} placeholder="Code" />
            <input
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="Name"
              aria-label="Brand name"
              title="Brand name (1–120 chars; letters/digits required)"
            />
            <textarea
              value={brandDescription}
              onChange={(e) => setBrandDescription(e.target.value)}
              placeholder="Description (optional)"
              aria-label="Brand description"
              title="Optional description (1–500 chars; letters/digits required)"
              rows={2}
            />
            <button
              onClick={async () => {
                setError('');
                try {
                  await api('/catalog/brands', {
                    method: 'POST',
                    body: JSON.stringify({
                      code: brandCode.trim(),
                      name: brandName.trim(),
                      description: brandDescription.trim() || null,
                    }),
                  });
                  setBrandCode('');
                  setBrandName('');
                  setBrandDescription('');
                  setMessage('Brand created');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              disabled={!brandCode.trim() || !brandName.trim()}
              aria-label="Add brand"
            >
              Add brand
            </button>
            <select
              value={brandManageFilter}
              onChange={(e) => setBrandManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
              title="Filter manage brand list by status"
              aria-label="Catalog brand status filter"
            >
              <option value="all">All statuses</option>
              <option value="active">Active only</option>
              <option value="inactive">Inactive only</option>
            </select>
            <ul className="muted">
              {managedBrands.map((b) => (
                <li
                  key={b.id}
                  style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}
                >
                  {brandLogoPreview[b.id] && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={brandLogoPreview[b.id]}
                      alt={`${b.name} logo`}
                      width={32}
                      height={32}
                      style={{ objectFit: 'contain', border: '1px solid #e2e8f0' }}
                    />
                  )}
                  <span>
                    {b.code} — {b.name}
                    {b.description ? ` · ${b.description}` : ''}
                    {b.has_logo ? ' · logo' : ''}
                    {!b.is_active ? ' [inactive]' : ''}
                  </span>
                  {b.is_active === false ? (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={async () => {
                        setError('');
                        try {
                          await api(`/catalog/brands/${b.id}`, {
                            method: 'PATCH',
                            body: JSON.stringify({ is_active: true }),
                          });
                          setMessage(`Brand ${b.name} activated`);
                          await refresh();
                        } catch (err: any) {
                          setError(err.message);
                        }
                      }}
                    >
                      Activate
                    </button>
                  ) : (
                    <>
                      <label className="muted" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        Logo
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp,image/gif"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) uploadBrandLogo(b.id, file);
                            e.target.value = '';
                          }}
                        />
                      </label>
                      {b.has_logo && (
                        <button type="button" onClick={() => removeBrandLogo(b.id)}>
                          Remove logo
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn-danger"
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
          <div className="card" style={{ display: 'grid', gap: 8 }}>
            <h3>Unit of measure</h3>
            <p className="muted" style={{ margin: 0 }}>
              Optional base + ratio: 1 of this unit = ratio × base (e.g. BOX = 12 PCS). Stock stays in the
              product&apos;s stock unit.
            </p>
            <input value={unitCode} onChange={(e) => setUnitCode(e.target.value)} placeholder="Code" />
            <input
              value={unitName}
              onChange={(e) => setUnitName(e.target.value)}
              placeholder="Name"
              aria-label="Unit name"
              title="Unit name (1–80 chars; letters/digits required)"
            />
            <select value={unitBaseId} onChange={(e) => setUnitBaseId(e.target.value)}>
              <option value="">Base unit (root / none)</option>
              {units
                .filter((u) => u.is_active !== false && !u.base_unit_id)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.code} — {u.name}
                  </option>
                ))}
            </select>
            <input
              value={unitRatio}
              onChange={(e) => setUnitRatio(e.target.value)}
              placeholder="Conversion ratio"
              disabled={!unitBaseId}
            />
            <button
              onClick={async () => {
                setError('');
                try {
                  await api('/catalog/units', {
                    method: 'POST',
                    body: JSON.stringify({
                      code: unitCode.trim(),
                      name: unitName.trim(),
                      base_unit_id: unitBaseId || null,
                      conversion_ratio: unitBaseId ? Number(unitRatio) || 1 : 1,
                    }),
                  });
                  setUnitCode('');
                  setUnitName('');
                  setUnitBaseId('');
                  setUnitRatio('1');
                  setMessage('Unit created');
                  await refresh();
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              disabled={!unitCode.trim() || !unitName.trim()}
              aria-label="Add unit"
            >
              Add unit
            </button>
            <select
              value={unitManageFilter}
              onChange={(e) => setUnitManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
              title="Filter manage unit list by status"
              aria-label="Catalog unit status filter"
            >
              <option value="all">All statuses</option>
              <option value="active">Active only</option>
              <option value="inactive">Inactive only</option>
            </select>
            <ul className="muted">
              {managedUnits.map((u) => (
                <li key={u.id} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span>
                    {u.code} — {u.name}
                    {u.base_unit_code
                      ? ` (= ${u.conversion_ratio} ${u.base_unit_code})`
                      : ' [root]'}
                    {!u.is_active ? ' [inactive]' : ''}
                  </span>
                  {u.is_active === false ? (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={async () => {
                        setError('');
                        try {
                          await api(`/catalog/units/${u.id}`, {
                            method: 'PATCH',
                            body: JSON.stringify({ is_active: true }),
                          });
                          setMessage(`Unit ${u.code} activated`);
                          await refresh();
                        } catch (err: any) {
                          setError(err.message);
                        }
                      }}
                    >
                      Activate
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn-danger"
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
        </div>
      )}

      {tab === 'variants' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Add variant</h3>
            <p className="muted">
              Size, color, flavor, dosage (pharmacy) with unique SKUs and barcodes (BR-5.1). Use the
              product symbology picker above for Generate / Print on each row.
            </p>
            <input
              value={variantName}
              onChange={(e) => setVariantName(e.target.value)}
              placeholder="Name"
              aria-label="Variant name"
              title="Variant name (1–120 chars; letters/digits required)"
            />
            <input
              value={variantSku}
              onChange={(e) => setVariantSku(e.target.value)}
              placeholder="SKU (auto if blank)"
            />
            <input
              value={variantBarcode}
              onChange={(e) => setVariantBarcode(e.target.value)}
              placeholder="Barcode (optional)"
              aria-label="Variant barcode"
              title="Optional barcode (4–48 chars: letters, numbers, - . _)"
            />
            <input value={variantSize} onChange={(e) => setVariantSize(e.target.value)} placeholder="Size (optional)" />
            <input value={variantColor} onChange={(e) => setVariantColor(e.target.value)} placeholder="Color (optional)" />
            <input
              value={variantFlavor}
              onChange={(e) => setVariantFlavor(e.target.value)}
              placeholder="Flavor (optional)"
            />
            <input
              value={variantDosage}
              onChange={(e) => setVariantDosage(e.target.value)}
              placeholder="Dosage (optional)"
            />
            <button
              onClick={addVariant}
              disabled={!selectedId || !variantName.trim()}
              aria-label="Create variant"
            >
              Create variant
            </button>
          </div>
          <select
            value={variantManageFilter}
            onChange={(e) =>
              setVariantManageFilter(e.target.value as 'all' | 'active' | 'inactive')
            }
            title="Filter manage variant list by status"
            aria-label="Product variant status filter"
            style={{ marginBottom: 8 }}
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>SKU</th>
                <th>Barcode</th>
                <th>Size</th>
                <th>Color</th>
                <th>Flavor</th>
                <th>Dosage</th>
                <th>Stock</th>
                <th>Price</th>
                <th>Active</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {managedVariants.length === 0 && (
                <tr>
                  <td colSpan={11} className="muted">
                    No variants for this filter
                  </td>
                </tr>
              )}
              {managedVariants.map((v) => (
                <tr key={v.id}>
                  <td>
                    {v.name}
                    {v.is_active === false ? (
                      <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                        [inactive]
                      </span>
                    ) : null}
                  </td>
                  <td>{v.sku}</td>
                  <td>{v.barcode || '—'}</td>
                  <td>{v.size || '—'}</td>
                  <td>{v.color || '—'}</td>
                  <td>{v.flavor || '—'}</td>
                  <td>{v.dosage || '—'}</td>
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
                  <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <button type="button" onClick={() => generateVariantBarcode(v.id)}>
                      Generate
                    </button>
                    <button type="button" onClick={() => printVariantBarcodeLabel(v.id)}>
                      Label
                    </button>
                    {v.is_active === false ? (
                      <button type="button" className="btn-ok" onClick={() => activateVariant(v.id)}>
                        Activate
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn-danger"
                        onClick={() => deactivateVariant(v.id)}
                      >
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
            <p className="muted" style={{ margin: 0 }}>
              Batch number, manufacturing date, expiry, warehouse, and optional variant (BR-5.1 /
              BR-5.2).
            </p>
            <select
              value={stockWarehouseId}
              onChange={(e) => setStockWarehouseId(e.target.value)}
            >
              <option value="">Warehouse (optional)</option>
              {warehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name || w.code || w.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <select value={stockVariantId} onChange={(e) => setStockVariantId(e.target.value)}>
              <option value="">Variant (optional)</option>
              {variants
                .filter((v) => v.is_active !== false)
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.sku})
                  </option>
                ))}
            </select>
            <input value={batchNumber} onChange={(e) => setBatchNumber(e.target.value)} placeholder="Batch number" />
            <label className="muted">Manufacturing date</label>
            <input
              aria-label="Stock-in manufacturing date"
              type="text"
              placeholder="YYYY-MM-DD"
              title="Manufacturing date (optional YYYY-MM-DD)"
              value={mfgDate}
              onChange={(e) => setMfgDate(e.target.value)}
            />
            <label className="muted">Expiry date</label>
            <input
              aria-label="Stock-in expiry date"
              type="text"
              placeholder="YYYY-MM-DD"
              title="Expiry date (optional YYYY-MM-DD)"
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
            />
            <input value={stockQty} onChange={(e) => setStockQty(e.target.value)} placeholder="Quantity" />
            <select value={stockUnitId} onChange={(e) => setStockUnitId(e.target.value)}>
              <option value="">Unit (default = product stock unit)</option>
              {units
                .filter((u) => u.is_active !== false)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.code}
                    {u.base_unit_code ? ` (= ${u.conversion_ratio} ${u.base_unit_code})` : ''}
                  </option>
                ))}
            </select>
            <input
              value={stockNotes}
              onChange={(e) => setStockNotes(e.target.value)}
              placeholder="Notes (optional)"
              aria-label="Stock-in notes"
              title="Optional notes (1–500 chars; letters/digits required)"
            />
            <button
              type="button"
              className="btn-ok"
              onClick={stockInBatch}
              disabled={!selectedId || !batchNumber}
              aria-label="Receive batch"
            >
              Receive batch
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Batch</th>
                <th>Qty</th>
                <th>Mfg</th>
                <th>Expiry</th>
                <th>Warehouse</th>
                <th>Variant</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => {
                const wh = warehouses.find((w) => w.id === b.warehouse_id);
                const vr = variants.find((v) => v.id === b.variant_id);
                return (
                  <tr key={b.id}>
                    <td>{b.batch_number}</td>
                    <td>{b.quantity}</td>
                    <td>
                      {b.manufacturing_date ? String(b.manufacturing_date).slice(0, 10) : '—'}
                    </td>
                    <td>{b.expiry_date ? String(b.expiry_date).slice(0, 10) : '—'}</td>
                    <td>{wh ? wh.name || wh.code : b.warehouse_id ? String(b.warehouse_id).slice(0, 8) : '—'}</td>
                    <td>{vr ? `${vr.sku}` : b.variant_id ? String(b.variant_id).slice(0, 8) : '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </>
      )}

      {tab === 'opening' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Opening stock (BR-5.2)</h3>
            <p className="muted" style={{ margin: 0 }}>
              Initialize on-hand quantity for go-live or fiscal year. Optionally posts Dr Inventory /
              Cr Owner&apos;s Equity at cost.
            </p>
            <select
              value={openingWarehouseId}
              onChange={(e) => setOpeningWarehouseId(e.target.value)}
            >
              <option value="">Warehouse (optional)</option>
              {warehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name || w.code || w.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <select value={openingVariantId} onChange={(e) => setOpeningVariantId(e.target.value)}>
              <option value="">Variant (optional)</option>
              {variants
                .filter((v) => v.is_active !== false)
                .map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.name} ({v.sku})
                  </option>
                ))}
            </select>
            <input
              value={openingQty}
              onChange={(e) => setOpeningQty(e.target.value)}
              placeholder="Quantity"
            />
            <select value={openingUnitId} onChange={(e) => setOpeningUnitId(e.target.value)}>
              <option value="">Unit (product default)</option>
              {units
                .filter((u) => u.is_active !== false)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.code}
                  </option>
                ))}
            </select>
            <input
              value={openingUnitCost}
              onChange={(e) => setOpeningUnitCost(e.target.value)}
              placeholder={`Unit cost (default ${selected?.cost_price ?? 0})`}
            />
            <input
              value={openingBatch}
              onChange={(e) => setOpeningBatch(e.target.value)}
              placeholder="Batch number (if tracked)"
            />
            <label className="muted">Manufacturing date</label>
            <input
              aria-label="Opening stock manufacturing date"
              type="text"
              placeholder="YYYY-MM-DD"
              title="Manufacturing date (optional YYYY-MM-DD)"
              value={openingMfg}
              onChange={(e) => setOpeningMfg(e.target.value)}
            />
            <label className="muted">Expiry date</label>
            <input
              aria-label="Opening stock expiry date"
              type="text"
              placeholder="YYYY-MM-DD"
              title="Expiry date (optional YYYY-MM-DD)"
              value={openingExpiry}
              onChange={(e) => setOpeningExpiry(e.target.value)}
            />
            <input
              value={openingReference}
              onChange={(e) => setOpeningReference(e.target.value)}
              placeholder="Reference (blank = next OS-YYYY-NNNN)"
              aria-label="Opening stock reference"
              title="Optional reference (1–100 chars; blank = next OS-YYYY-NNNN)"
            />
            <input
              value={openingNotes}
              onChange={(e) => setOpeningNotes(e.target.value)}
              placeholder="Notes"
              aria-label="Opening stock notes"
              title="Optional notes (1–500 chars; letters/digits required)"
            />
            <input
              value={openingLineNotes}
              onChange={(e) => setOpeningLineNotes(e.target.value)}
              placeholder="Line notes (optional)"
              aria-label="Opening stock line notes"
              title="Optional per-line notes (1–500 chars; letters/digits required)"
            />
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={openingPostJournal}
                onChange={(e) => setOpeningPostJournal(e.target.checked)}
              />
              Post inventory / equity journal
            </label>
            <button
              type="button"
              className="btn-ok"
              onClick={postOpeningStock}
              disabled={!selectedId}
              aria-label="Post opening stock"
            >
              Post opening stock
            </button>
          </div>
          <h3>Recent opening movements</h3>
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Product</th>
                <th>Qty</th>
                <th>After</th>
                <th>Entry</th>
              </tr>
            </thead>
            <tbody>
              {openingHistory.map((m) => {
                const p = products.find((x) => x.id === m.product_id);
                return (
                  <tr key={m.id}>
                    <td>{m.created_at ? String(m.created_at).slice(0, 19) : '—'}</td>
                    <td>{p ? `${p.sku}` : m.product_id.slice(0, 8)}</td>
                    <td>{m.quantity}</td>
                    <td>{m.quantity_after}</td>
                    <td>{m.reference_id ? String(m.reference_id).slice(0, 8) : '—'}</td>
                  </tr>
                );
              })}
              {!openingHistory.length && (
                <tr>
                  <td colSpan={5} className="muted">
                    No opening stock posted yet
                  </td>
                </tr>
              )}
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
            <select
              value={countWarehouseId}
              onChange={(e) => setCountWarehouseId(e.target.value)}
              aria-label="Stock count warehouse"
            >
              <option value="">Warehouse</option>
              {warehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name} ({w.code})
                </option>
              ))}
            </select>
            <input
              value={countNotes}
              onChange={(e) => setCountNotes(e.target.value)}
              placeholder="Notes (optional)"
              aria-label="Stock count notes"
              title="Optional notes (1–500 chars; letters/digits required)"
            />
            <button
              type="button"
              className="btn-ok"
              onClick={startStockCount}
              disabled={!countWarehouseId}
              aria-label="Create draft count"
            >
              Create draft count
            </button>
          </div>

          <div className="card" style={{ marginBottom: 16 }}>
            <label>
              Cancel reason{' '}
              <input
                value={countCancelReason}
                onChange={(e) => setCountCancelReason(e.target.value)}
                placeholder="Required before Cancel"
                style={{ minWidth: 280 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Appended to count notes and audit (<code>POST .../stock-counts/.../cancel</code>{' '}
              {'{ reason }'}). Draft only; no variance postings.
            </p>
          </div>

          <select
            value={countManageFilter}
            onChange={(e) =>
              setCountManageFilter(
                e.target.value as 'all' | 'draft' | 'completed' | 'cancelled'
              )
            }
            title="Filter stock count list by status"
            aria-label="Stock count status filter"
            style={{ marginBottom: 12 }}
          >
            <option value="all">All statuses</option>
            <option value="draft">Draft only</option>
            <option value="completed">Completed only</option>
            <option value="cancelled">Cancelled only</option>
          </select>
          <table className="table" style={{ marginBottom: 16 }}>
            <thead>
              <tr>
                <th>Number</th>
                <th>Status</th>
                <th>Items</th>
                <th>Notes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {managedCounts.map((c) => (
                <tr key={c.id}>
                  <td>{c.count_number}</td>
                  <td>{c.status}</td>
                  <td>
                    {c.counted_item_count}/{c.item_count}
                  </td>
                  <td className="muted" style={{ maxWidth: 220, whiteSpace: 'pre-wrap' }}>
                    {c.notes || '—'}
                  </td>
                  <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    <button type="button" onClick={() => openCount(c.id)}>
                      Open
                    </button>
                    {(c.can_cancel || c.status === 'draft') && (
                      <button type="button" className="btn-danger" onClick={() => cancelStockCount(c.id, c.count_number)}>
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!managedCounts.length && (
                <tr>
                  <td colSpan={5} className="muted">
                    No stock counts for this filter
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {activeCount && (
            <div className="card" style={{ display: 'grid', gap: 12 }}>
              <h3>
                {activeCount.count_number} — {activeCount.status}
              </h3>
              {activeCount.notes && (
                <p className="muted" style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                  Notes: {activeCount.notes}
                </p>
              )}
              <table className="table">
                <thead>
                  <tr>
                    <th>SKU</th>
                    <th>Expected</th>
                    <th>Counted</th>
                    <th>Variance</th>
                    <th>Line notes</th>
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
                            aria-label={`Counted qty ${item.product_sku || item.product_id}`}
                          />
                        </td>
                        <td>{Number.isFinite(variance) ? variance : '—'}</td>
                        <td>
                          <input
                            value={countLineNotes[item.product_id] ?? ''}
                            disabled={activeCount.status !== 'draft'}
                            onChange={(e) =>
                              setCountLineNotes({
                                ...countLineNotes,
                                [item.product_id]: e.target.value,
                              })
                            }
                            placeholder="Line notes (optional)"
                            aria-label={`Stock count line notes ${item.product_sku || item.product_id}`}
                            title="Optional line notes (1–500 chars; letters/digits required)"
                            style={{ width: 180 }}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {activeCount.status === 'draft' && (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button type="button" onClick={saveCountLines} aria-label="Save count lines">
                    Save counts
                  </button>
                  <button type="button" onClick={completeActiveCount}>
                    Complete &amp; post variances
                  </button>
                  <button
                    type="button"
                    className="btn-danger"
                    onClick={() => cancelStockCount(activeCount.id, activeCount.count_number)}
                  >
                    Cancel count
                  </button>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {tab === 'movements' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Stock movement history</h3>
            <p className="muted">
              Immutable audit trail (BR-5.3). Records cannot be deleted. Filter by warehouse, type,
              date, or the selected product above.
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <select value={mvWarehouseId} onChange={(e) => setMvWarehouseId(e.target.value)}>
                <option value="">All warehouses</option>
                {warehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name || w.code || w.id.slice(0, 8)}
                  </option>
                ))}
              </select>
              <select
                aria-label="Movement type filter"
                value={mvType}
                onChange={(e) => setMvType(e.target.value)}
              >
                <option value="">All types</option>
                <option value="stock_in">stock_in</option>
                <option value="stock_out">stock_out</option>
                <option value="opening_stock">opening_stock</option>
                <option value="adjustment">adjustment</option>
                <option value="transfer_out">transfer_out</option>
                <option value="transfer_in">transfer_in</option>
                <option value="transfer_cancel">transfer_cancel</option>
              </select>
              <select
                aria-label="Movement reason filter"
                value={mvReason}
                onChange={(e) => setMvReason(e.target.value)}
              >
                <option value="">All reasons</option>
                <option value="damage">damage</option>
                <option value="theft">theft</option>
                <option value="expiry">expiry</option>
                <option value="found">found</option>
                <option value="lost">lost</option>
              </select>
              <label className="muted">From</label>
              <input
                type="date"
                value={mvFrom}
                onChange={(e) => setMvFrom(e.target.value)}
                title="From date (YYYY-MM-DD)"
                aria-label="Movement from date"
              />
              <label className="muted">To</label>
              <input
                type="date"
                value={mvTo}
                onChange={(e) => setMvTo(e.target.value)}
                title="To date (YYYY-MM-DD)"
                aria-label="Movement to date"
              />
              <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                <input
                  type="checkbox"
                  checked={mvProductOnly}
                  onChange={(e) => setMvProductOnly(e.target.checked)}
                />
                Selected product only
              </label>
              <button type="button" onClick={() => loadMovements()}>
                Refresh
              </button>
            </div>
            <p className="muted">
              {mvMeta.count ?? movements.length} movement
              {(mvMeta.count ?? movements.length) === 1 ? '' : 's'}
              {mvMeta.warehouse_name ? ` · ${mvMeta.warehouse_name}` : ''}
            </p>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Product</th>
                <th>Type</th>
                <th>Reason</th>
                <th>Qty</th>
                <th>Before → after</th>
                <th>User</th>
                <th>Ref</th>
              </tr>
            </thead>
            <tbody>
              {movements.map((mv) => (
                <tr key={mv.id}>
                  <td>{mv.created_at ? String(mv.created_at).slice(0, 19) : '—'}</td>
                  <td>
                    {mv.product_sku || mv.product_name
                      ? `${mv.product_sku || ''}${mv.product_name ? ` ${mv.product_name}` : ''}`.trim()
                      : mv.product_id
                        ? String(mv.product_id).slice(0, 8)
                        : '—'}
                  </td>
                  <td>{mv.movement_type}</td>
                  <td>{mv.reason || '—'}</td>
                  <td>{mv.quantity}</td>
                  <td>
                    {mv.quantity_before} → {mv.quantity_after}
                  </td>
                  <td>{mv.created_by_name || mv.created_by_email || '—'}</td>
                  <td>
                    {mv.reference_type || '—'}
                    {mv.reference_id ? ` ${String(mv.reference_id).slice(0, 8)}…` : ''}
                  </td>
                </tr>
              ))}
              {!movements.length && (
                <tr>
                  <td colSpan={8} className="muted">
                    No stock movements
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}

      {tab === 'adjust' && (
        <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
          <h3>Stock adjustment</h3>
          <p className="muted">
            Correct on-hand discrepancies with a coded reason (BR-5.2): damage, theft, expiry, found,
            or lost. Negative qty reduces stock; positive increases (e.g. found). Uses the product
            selected above.
          </p>
          <p className="muted">
            Selected:{' '}
            {selected ? `${selected.name} (${selected.sku}) — on-hand ${selected.stock_qty}` : 'none'}
          </p>
          <label className="muted">Quantity delta</label>
          <input
            value={adjQty}
            onChange={(e) => setAdjQty(e.target.value)}
            placeholder="-1"
          />
          <label className="muted">Reason</label>
          <select
            value={adjReason}
            onChange={(e) => setAdjReason(e.target.value)}
            aria-label="Adjustment reason"
          >
            <option value="">Select reason</option>
            <option value="damage">damage</option>
            <option value="theft">theft</option>
            <option value="expiry">expiry</option>
            <option value="found">found</option>
            <option value="lost">lost</option>
          </select>
          <label className="muted">Warehouse (optional)</label>
          <select value={adjWarehouseId} onChange={(e) => setAdjWarehouseId(e.target.value)}>
            <option value="">Company / product stock only</option>
            {warehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
              <option key={w.id} value={w.id}>
                {w.name || w.code || w.id.slice(0, 8)}
              </option>
            ))}
          </select>
          <label className="muted">Notes (optional)</label>
          <input
            value={adjNotes}
            onChange={(e) => setAdjNotes(e.target.value)}
            placeholder="Details"
            aria-label="Stock adjustment notes"
            title="Optional notes (1–500 chars; letters/digits required)"
          />
          <button
            type="button"
            className="btn-ok"
            onClick={postStockAdjust}
            disabled={!selectedId || !adjReason}
            aria-label="Post stock adjustment"
          >
            Post adjustment
          </button>
        </div>
      )}

      {tab === 'stockout' && (
        <div className="card" style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
          <h3>Stock Out</h3>
          <p className="muted">
            Issue outgoing stock with a reference type (BR-5.2): sale, transfer, adjustment, damage,
            internal, or other. Uses FEFO across batches when no batch is selected. Quantity must be
            positive.
          </p>
          <p className="muted">
            Selected:{' '}
            {selected ? `${selected.name} (${selected.sku}) — on-hand ${selected.stock_qty}` : 'none'}
          </p>
          <label className="muted">Quantity</label>
          <input
            value={outQty}
            onChange={(e) => setOutQty(e.target.value)}
            placeholder="1"
          />
          <label className="muted">Reference type</label>
          <select
            value={outRefType}
            onChange={(e) => setOutRefType(e.target.value)}
            aria-label="Stock-out reference type"
          >
            <option value="">Select reference type</option>
            <option value="sale">sale</option>
            <option value="transfer">transfer</option>
            <option value="adjustment">adjustment</option>
            <option value="damage">damage</option>
            <option value="internal">internal</option>
            <option value="other">other</option>
          </select>
          <label className="muted">Reference id (optional)</label>
          <input
            value={outRefId}
            onChange={(e) => setOutRefId(e.target.value)}
            placeholder="Invoice / transfer / ticket id"
          />
          <label className="muted">Warehouse (optional)</label>
          <select value={outWarehouseId} onChange={(e) => setOutWarehouseId(e.target.value)}>
            <option value="">Company / product stock only</option>
            {warehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
              <option key={w.id} value={w.id}>
                {w.name || w.code || w.id.slice(0, 8)}
              </option>
            ))}
          </select>
          <label className="muted">Variant (optional)</label>
          <select value={outVariantId} onChange={(e) => setOutVariantId(e.target.value)}>
            <option value="">None</option>
            {variants
              .filter((v) => v.is_active !== false)
              .map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} ({v.sku}) — {v.stock_qty}
                </option>
              ))}
          </select>
          <label className="muted">Unit (optional)</label>
          <select value={outUnitId} onChange={(e) => setOutUnitId(e.target.value)}>
            <option value="">Default = product stock unit</option>
            {units
              .filter((u) => u.is_active !== false)
              .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.code}
                  {u.base_unit_code ? ` (= ${u.conversion_ratio} ${u.base_unit_code})` : ''}
                </option>
              ))}
          </select>
          <label className="muted">Batch (optional — otherwise FEFO)</label>
          <select value={outBatchId} onChange={(e) => setOutBatchId(e.target.value)}>
            <option value="">FEFO across open batches</option>
            {batches
              .filter((b) => Number(b.quantity) > 0)
              .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.batch_number} — qty {b.quantity}
                  {b.expiry_date ? ` · exp ${String(b.expiry_date).slice(0, 10)}` : ''}
                </option>
              ))}
          </select>
          <label className="muted">Notes (optional)</label>
          <input
            value={outNotes}
            onChange={(e) => setOutNotes(e.target.value)}
            placeholder="Details"
            aria-label="Stock-out notes"
            title="Optional notes (1–500 chars; letters/digits required)"
          />
          <button
            type="button"
            className="btn-ok"
            onClick={postStockOut}
            disabled={!selectedId || !outRefType}
            aria-label="Post stock out"
          >
            Post stock out
          </button>
        </div>
      )}

      {tab === 'whstock' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8 }}>
            <h3>Warehouse stock (BR-5.4)</h3>
            <p className="muted" style={{ margin: 0 }}>
              On-hand quantities and reorder policy per warehouse (not consolidated company stock).
            </p>
            <label className="muted">Warehouse</label>
            <select
              value={whStockWarehouseId}
              onChange={(e) => setWhStockWarehouseId(e.target.value)}
            >
              <option value="">Select warehouse</option>
              {warehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name || w.code || w.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={whStockIncludeZero}
                onChange={(e) => setWhStockIncludeZero(e.target.checked)}
              />
              <span className="muted">Include zero-qty rows</span>
            </label>
            <button type="button" onClick={() => loadWarehouseStock()} disabled={!whStockWarehouseId}>
              Refresh
            </button>
            <p className="muted" style={{ margin: 0 }}>
              {whStockMeta.warehouse_name
                ? `${whStockMeta.warehouse_name} — ${whStockMeta.count ?? 0} products · total qty ${whStockMeta.total_quantity ?? 0}`
                : 'Pick a warehouse to load stock'}
            </p>
          </div>

          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 560 }}>
            <h3>Set warehouse reorder</h3>
            <p className="muted" style={{ margin: 0 }}>
              Saves warehouse_stocks.reorder_level / reorder_qty for the selected warehouse.
            </p>
            <select
              value={whReorderProductId}
              onChange={(e) => {
                const id = e.target.value;
                setWhReorderProductId(id);
                const row = whStockRows.find((r) => r.product_id === id);
                if (row) {
                  setWhReorderLevel(String(row.reorder_level ?? 0));
                  setWhReorderQty(String(row.reorder_qty ?? 0));
                }
              }}
            >
              <option value="">Product</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.sku})
                </option>
              ))}
            </select>
            <input
              value={whReorderLevel}
              onChange={(e) => setWhReorderLevel(e.target.value)}
              placeholder="Reorder level"
            />
            <input
              value={whReorderQty}
              onChange={(e) => setWhReorderQty(e.target.value)}
              placeholder="Reorder qty"
            />
            <button
              type="button"
              onClick={saveWarehouseReorder}
              disabled={!whStockWarehouseId || !whReorderProductId}
            >
              Save reorder policy
            </button>
          </div>

          <table className="table">
            <thead>
              <tr>
                <th>SKU</th>
                <th>Product</th>
                <th>Qty</th>
                <th>Reorder</th>
                <th>Suggest</th>
                <th>Company</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {whStockRows.map((r) => (
                <tr key={r.product_id}>
                  <td>{r.sku}</td>
                  <td>{r.name}</td>
                  <td>{r.quantity}</td>
                  <td>
                    {r.reorder_level} / {r.reorder_qty}
                  </td>
                  <td>{r.suggested_order_qty ?? '—'}</td>
                  <td>{r.consolidated_stock}</td>
                  <td style={{ color: r.below_reorder ? '#b91c1c' : undefined }}>
                    {r.below_reorder ? 'LOW' : 'ok'}
                  </td>
                </tr>
              ))}
              {whStockRows.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">
                    No warehouse stock rows
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}

      {tab === 'transfers' && (
        <>
          <div className="card" style={{ marginBottom: 16, display: 'grid', gap: 8, maxWidth: 560 }}>
            <h3>Warehouse transfer (BR-5.2 / BR-5.4)</h3>
            <p className="muted" style={{ margin: 0 }}>
              Move stock between warehouses with a transfer note and approval. Same-store warehouse
              pairs need one approval; different stores need dual manager approval. Warehouses must
              be linked to a store. Uses the product selected above.
            </p>
            <p className="muted">
              Selected:{' '}
              {selected ? `${selected.name} (${selected.sku}) — on-hand ${selected.stock_qty}` : 'none'}
            </p>
            <label className="muted">From warehouse</label>
            <select value={xferFromWh} onChange={(e) => setXferFromWh(e.target.value)}>
              <option value="">Select source</option>
              {warehouses
                .filter((w) => w.store_id)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name || w.code} ({w.code})
                  </option>
                ))}
            </select>
            <label className="muted">To warehouse</label>
            <select value={xferToWh} onChange={(e) => setXferToWh(e.target.value)}>
              <option value="">Select destination</option>
              {warehouses
                .filter((w) => w.store_id)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name || w.code} ({w.code})
                  </option>
                ))}
            </select>
            <label className="muted">Quantity</label>
            <input value={xferQty} onChange={(e) => setXferQty(e.target.value)} placeholder="1" />
            <label className="muted">Notes (optional)</label>
            <input
              value={xferNotes}
              onChange={(e) => setXferNotes(e.target.value)}
              placeholder="Transfer note"
              aria-label="Stock transfer notes"
              title="Optional notes (1–500 chars; letters/digits required)"
            />
            <button
              type="button"
              onClick={createWarehouseTransfer}
              disabled={!selectedId || !xferFromWh || !xferToWh}
              aria-label="Create stock transfer"
            >
              Create &amp; request
            </button>
          </div>

          <h3>Transfers</h3>
          <p className="muted">
            Approve → ship (deducts source) → receive (credits destination). Cancel restores in-transit
            stock.
          </p>
          <div className="card" style={{ marginBottom: 12 }}>
            <label>
              Reject / Cancel reason{' '}
              <input
                value={xferRejectReason}
                onChange={(e) => setXferRejectReason(e.target.value)}
                placeholder="Required before Reject or Cancel"
                title="Required reject/cancel reason (1–500 chars; letters/digits required)"
                aria-label="Stock transfer reject reason"
                style={{ minWidth: 280 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Used by Reject and Cancel (stored as <code>rejection_reason</code>; status → cancelled).
            </p>
          </div>
          <button type="button" onClick={() => loadTransfers()} style={{ marginBottom: 8 }}>
            Refresh
          </button>
          <select
            value={transferManageFilter}
            onChange={(e) =>
              setTransferManageFilter(
                e.target.value as
                  | 'all'
                  | 'draft'
                  | 'requested'
                  | 'in_transit'
                  | 'received'
                  | 'cancelled'
              )
            }
            title="Filter stock transfer list by status"
            aria-label="Stock transfer status filter"
            style={{ marginBottom: 12, marginLeft: 8 }}
          >
            <option value="all">All statuses</option>
            <option value="draft">Draft only</option>
            <option value="requested">Requested only</option>
            <option value="in_transit">In transit only</option>
            <option value="received">Received only</option>
            <option value="cancelled">Cancelled only</option>
          </select>
          <table className="table">
            <thead>
              <tr>
                <th>Number</th>
                <th>From WH</th>
                <th>To WH</th>
                <th>Status</th>
                <th>Approval</th>
                <th>Reject / Cancel reason</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {managedTransfers.map((t) => (
                <tr key={t.id}>
                  <td>{t.transfer_number}</td>
                  <td>{warehouseLabel(t.from_warehouse_id)}</td>
                  <td>{warehouseLabel(t.to_warehouse_id)}</td>
                  <td>{t.status}</td>
                  <td>
                    {t.status === 'requested'
                      ? t.fully_approved
                        ? 'Ready to ship'
                        : t.approval_steps_required <= 1
                          ? 'Awaiting approval'
                          : t.awaiting_approval === 'dest'
                            ? 'Awaiting dest'
                            : 'Awaiting source'
                      : '—'}
                  </td>
                  <td className="muted">{t.rejection_reason || '—'}</td>
                  <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {t.status === 'draft' && (
                      <button type="button" className="btn-ok" onClick={() => transferAct(t.id, 'submit')}>
                        Submit
                      </button>
                    )}
                    {t.status === 'requested' && !t.fully_approved && (
                      <>
                        <button type="button" className="btn-ok" onClick={() => transferAct(t.id, 'approve')}>
                          Approve
                          {t.approval_steps_required > 1
                            ? t.awaiting_approval === 'dest'
                              ? ' dest'
                              : ' source'
                            : ''}
                        </button>
                        <button
                          type="button"
                          className="btn-danger"
                          onClick={() => transferAct(t.id, 'reject')}
                          aria-label={`Reject stock transfer ${t.id}`}
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {t.can_ship && (
                      <button type="button" className="btn-ok" onClick={() => transferAct(t.id, 'ship')}>
                        Ship
                      </button>
                    )}
                    {t.status === 'in_transit' && (
                      <button type="button" className="btn-ok" onClick={() => transferAct(t.id, 'receive')}>
                        Receive
                      </button>
                    )}
                    {['draft', 'requested', 'in_transit'].includes(t.status) && (
                      <button type="button" className="btn-danger" onClick={() => transferAct(t.id, 'cancel')}>
                        Cancel
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {managedTransfers.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">
                    {transfers.length === 0
                      ? 'No transfers yet'
                      : 'No stock transfers for this filter'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}
    </Shell>
  );
}
