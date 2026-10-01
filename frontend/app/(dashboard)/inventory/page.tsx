'use client';

import dynamic from 'next/dynamic';
import { Fragment, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, apiOptional, isAbortError, getAccessToken, apiRoot, tenantHeaderValue } from '../../../lib/api';
import { getMe } from '../../../lib/meCache';
import { getPrefetched, peekPrefetch } from '../../../lib/prefetchCache';
import { pageLoadStarted } from '../../../lib/navTiming';
import PageSkeleton from '../../../components/PageSkeleton';
import { useStoreContext } from '../../../lib/storeContext';
import { isHotelIndustry, tenantIsMultiStore } from '../../../lib/tenantNav';
import { normalizeIndustry, usesStoreStockTransfers } from '../../../lib/industries';
import {
  formatTransferDate,
  matchesTransferSearch,
  sameWarehouseError,
  transferLineQtyError,
  transferOnDate,
  transferProductCount,
  transferQtyTotal,
} from '../../../lib/stockTransfers';
import { LIST_PAGE_SIZE, displayProductName, matchesProductList, paginate, sortByKey, sortProducts } from '../../../lib/listPages';

const FormModal = dynamic(() => import('../../../components/FormModal'), { ssr: false });

type Tab =
  | 'products'
  | 'labels'
  | 'lookup'
  | 'import'
  | 'categories'
  | 'brands'
  | 'units'
  | 'variants'
  | 'batches'
  | 'opening'
  | 'expiry'
  | 'counts'
  | 'movements'
  | 'adjust'
  | 'stockout'
  | 'lowstock'
  | 'whstock'
  | 'transfers';

const INVENTORY_TABS: Tab[] = [
  'products',
  'labels',
  'lookup',
  'import',
  'categories',
  'brands',
  'units',
  'variants',
  'batches',
  'opening',
  'expiry',
  'counts',
  'movements',
  'adjust',
  'stockout',
  'lowstock',
  'whstock',
  'transfers',
];

function isInventoryTab(value: string | null): value is Tab {
  return Boolean(value && (INVENTORY_TABS as string[]).includes(value));
}

const VIEW_TITLE: Record<Tab, string> = {
  products: 'Products',
  labels: 'Labels',
  lookup: 'Lookup',
  import: 'Import',
  categories: 'Categories',
  brands: 'Brands',
  units: 'Units',
  variants: 'Variants',
  batches: 'Batches',
  opening: 'Opening stock',
  expiry: 'Expiry',
  counts: 'Stock count',
  movements: 'Stock History',
  adjust: 'Stock Adjustment',
  stockout: 'Stock out',
  lowstock: 'Low Stock',
  whstock: 'Manage Stock',
  transfers: 'Stock transfer',
};

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

function categoryLabel(c: { path?: string; name?: string; code?: string; depth?: number }) {
  if (c.path) return c.path;
  return c.name || c.code || '';
}

function categoryIndent(depth?: number) {
  const d = Math.max(0, Number(depth) || 0);
  return '\u00A0\u00A0'.repeat(d);
}

function categoryParentName(categories: any[], parentId?: string | null) {
  if (!parentId) return 'Main category';
  const parent = categories.find((c) => c.id === parentId);
  return parent?.name || 'Main category';
}

function unitParentName(units: any[], baseId?: string | null) {
  if (!baseId) return 'Main unit';
  const parent = units.find((u) => u.id === baseId);
  return parent?.name || parent?.code || 'Main unit';
}

function unitDepthOf(units: any[], row: any) {
  let depth = 0;
  let pid = row.base_unit_id;
  const seen = new Set<string>();
  while (pid && !seen.has(pid) && depth < 8) {
    seen.add(pid);
    depth += 1;
    const parent = units.find((u) => u.id === pid);
    pid = parent?.base_unit_id;
  }
  return depth;
}

function uniqueById<T extends { id?: string }>(rows: T[]): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const row of rows) {
    if (!row?.id || seen.has(row.id)) continue;
    seen.add(row.id);
    out.push(row);
  }
  return out;
}

function lotNumberForExpiry(batch: string, expiry: string): string | null {
  const lot = batch.trim();
  if (lot) return lot;
  const day = expiry.trim().replace(/-/g, '');
  if (!day) return null;
  return `LOT-${day}`;
}

function activeCatalogVariants(rows: any[]): any[] {
  return uniqueById(rows).filter((v) => v.is_active !== false);
}

function variantOptionLabel(v: any, products: any[]) {
  const parent = products.find((p) => p.id === v.product_id);
  const parentBit = parent?.name ? ` — ${parent.name}` : '';
  return `${v.name || 'Variant'}${v.sku ? ` (${v.sku})` : ''}${parentBit}`;
}

function categoryDescendantIds(categories: any[], rootId: string) {
  const kids: Record<string, string[]> = {};
  for (const row of categories) {
    const pid = row.parent_id || '';
    (kids[pid] ||= []).push(row.id);
  }
  const out = new Set<string>();
  const stack = [...(kids[rootId] || [])];
  while (stack.length) {
    const id = stack.pop() as string;
    if (out.has(id)) continue;
    out.add(id);
    stack.push(...(kids[id] || []));
  }
  return out;
}

const STOCK_STATUS_YELLOW_FACTOR = 1.5;

function stockStatusOf(p: {
  stock_qty?: number;
  reorder_level?: number;
  minimum_stock?: number;
  stock_status?: string;
}): 'out' | 'red' | 'yellow' | 'green' {
  if (p.stock_status === 'out' || p.stock_status === 'red' || p.stock_status === 'yellow' || p.stock_status === 'green') {
    return p.stock_status;
  }
  const qty = Number(p.stock_qty ?? 0);
  const floor = Math.max(Number(p.minimum_stock ?? 0), Number(p.reorder_level ?? 0));
  if (qty <= 0) return 'out';
  if (floor > 0 && qty <= floor) return 'red';
  if (floor > 0 && qty <= floor * STOCK_STATUS_YELLOW_FACTOR) return 'yellow';
  return 'green';
}

function warehouseRowIsLow(r: {
  quantity?: number;
  reorder_level?: number;
  minimum_stock?: number;
  product_reorder_level?: number;
  product_minimum_stock?: number;
  low_stock_floor?: number;
  below_reorder?: boolean;
  is_low_stock?: boolean;
  is_out_of_stock?: boolean;
  stock_status?: string;
}): boolean {
  const qty = Number(r.quantity ?? 0);
  if (r.is_out_of_stock || qty <= 0) return false;
  if (r.stock_status === 'red' || r.below_reorder === true || r.is_low_stock === true) return true;
  const floor = Number(
    r.low_stock_floor ??
      Math.max(
        Number(r.minimum_stock ?? 0),
        Number(r.reorder_level ?? 0),
        Number(r.product_minimum_stock ?? 0),
        Number(r.product_reorder_level ?? 0),
      ),
  );
  return floor > 0 && qty <= floor;
}

function StockStatusBadge({ product }: { product: any }) {
  const status = stockStatusOf(product);
  const colors: Record<string, { bg: string; fg: string; text: string }> = {
    out: { bg: '#fee2e2', fg: '#991b1b', text: 'Out of stock' },
    red: { bg: '#ffedd5', fg: '#c2410c', text: 'Low stock' },
    yellow: { bg: '#fef9c3', fg: '#a16207', text: 'Near reorder' },
    green: { bg: '#eaf8d8', fg: '#006B2E', text: 'OK' },
  };
  const c = colors[status] || colors.green;
  return (
    <span
      title={`Stock ${product.stock_qty ?? 0} · floor ${Math.max(Number(product.minimum_stock ?? 0), Number(product.reorder_level ?? 0))}`}
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>('products');
  const [products, setProducts] = useState<any[]>([]);
  useEffect(() => {
    const next = searchParams.get('tab');
    if (isInventoryTab(next) && next !== tab) setTab(next);
  }, [searchParams, tab]);
  function selectTab(id: Tab) {
    setTab(id);
    router.replace(`/inventory?tab=${id}`, { scroll: false });
  }
  const [categories, setCategories] = useState<any[]>([]);
  const [brands, setBrands] = useState<any[]>([]);
  const [units, setUnits] = useState<any[]>([]);
  const { storeId } = useStoreContext();
  const [hotelOps, setHotelOps] = useState(false);
  const [pharmacyOps, setPharmacyOps] = useState(false);
  const [retailTransfers, setRetailTransfers] = useState(true);
  const [hideWarehouseUx, setHideWarehouseUx] = useState(false);
  useEffect(() => {
    getMe()
      .then((r) => {
        const industry = r.data?.industry;
        const multi = tenantIsMultiStore(r.data);
        setHotelOps(isHotelIndustry(industry));
        setPharmacyOps(normalizeIndustry(industry) === 'pharmacy');
        setRetailTransfers(usesStoreStockTransfers(industry) && multi);
        setHideWarehouseUx(!multi);
      })
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if ((hotelOps || !retailTransfers) && tab === 'transfers') {
      setTab('products');
      router.replace('/inventory?tab=products', { scroll: false });
    }
  }, [hotelOps, retailTransfers, tab, router]);
  const scopeStoreId = hotelOps ? '' : storeId;
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const storeWarehouses = useMemo(
    () =>
      !scopeStoreId
        ? warehouses
        : warehouses.filter((w: any) => !w.store_id || String(w.store_id) === String(scopeStoreId)),
    [warehouses, scopeStoreId],
  );
  const defaultWarehouseId = useMemo(() => {
    const row = storeWarehouses.find((w: any) => w && w.is_active !== false);
    return row?.id ? String(row.id) : '';
  }, [storeWarehouses]);
  useEffect(() => {
    const list = storeWarehouses.filter((w: any) => w && w.is_active !== false);
    if (!list.length) return;
    if (!hideWarehouseUx && !scopeStoreId) return;
    const ids = new Set(list.map((w: any) => String(w.id)));
    const pick = (cur: string) => (cur && ids.has(String(cur)) ? cur : String(list[0].id));
    setStockWarehouseId((cur: string) => pick(cur));
    setOutWarehouseId((cur: string) => pick(cur));
    setOpeningWarehouseId((cur: string) => pick(cur));
    setAdjWarehouseId((cur: string) => pick(cur));
    setCreateOpeningWh((cur: string) => pick(cur));
    setLotWh((cur: string) => pick(cur));
    setXferFromWh((cur: string) => pick(cur));
    setWhStockWarehouseId((cur: string) => pick(cur));
    setCountWarehouseId((cur: string) => pick(cur));
    setMvWarehouseId((cur: string) => (hideWarehouseUx ? '' : pick(cur)));
  }, [hideWarehouseUx, scopeStoreId, storeWarehouses]);
  const [selectedId, setSelectedId] = useState('');
  const [productManageFilter, setProductManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [categoryManageFilter, setCategoryManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [brandManageFilter, setBrandManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [unitManageFilter, setUnitManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [variantManageFilter, setVariantManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [variants, setVariants] = useState<any[]>([]);
  const [variantsReady, setVariantsReady] = useState(false);
  const [variantsError, setVariantsError] = useState('');
  const [variantParentFilter, setVariantParentFilter] = useState('');
  const [variantProductId, setVariantProductId] = useState('');
  const [productVariantId, setProductVariantId] = useState('');
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
  const [bootLoading, setBootLoading] = useState(true);
  const [formFlash, setFormFlash] = useState<{ ok?: string; err?: string }>({});
  const [saveBusy, setSaveBusy] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [productAddOpen, setProductAddOpen] = useState(false);
  const [productSearch, setProductSearch] = useState('');
  const [productCategoryFilter, setProductCategoryFilter] = useState('');
  const [productBrandFilter, setProductBrandFilter] = useState('');
  const [productStockFilter, setProductStockFilter] = useState<'all' | 'low' | 'oos' | 'ok'>('all');
  const [rxOnlyFilter, setRxOnlyFilter] = useState(false);
  const [productSort, setProductSort] = useState('name');
  const [productSortDir, setProductSortDir] = useState<1 | -1>(1);
  const [productPage, setProductPage] = useState(1);
  useEffect(() => {
    const stock = searchParams.get('stock');
    if (stock === 'oos' || stock === 'low' || stock === 'ok' || stock === 'all') {
      setProductStockFilter(stock === 'all' ? 'all' : stock);
    }
    setRxOnlyFilter(searchParams.get('rx') === '1');
  }, [searchParams]);
  const [productEditMode, setProductEditMode] = useState(false);
  const [createExpiryOpen, setCreateExpiryOpen] = useState(false);
  const [createOpenStockOpen, setCreateOpenStockOpen] = useState(false);
  const [createOpeningQty, setCreateOpeningQty] = useState('');
  const [createOpeningWh, setCreateOpeningWh] = useState('');
  const [createOpeningBatch, setCreateOpeningBatch] = useState('');
  const [createOpeningMfg, setCreateOpeningMfg] = useState('');
  const [createOpeningExpiry, setCreateOpeningExpiry] = useState('');
  const [createOpeningCost, setCreateOpeningCost] = useState('');
  const [lotQty, setLotQty] = useState('');
  const [lotWh, setLotWh] = useState('');
  const [lotExpiry, setLotExpiry] = useState('');
  const [lotBatch, setLotBatch] = useState('');
  const [expiryDrawerOpen, setExpiryDrawerOpen] = useState(false);
  const [expiryBusy, setExpiryBusy] = useState(false);
  const [expiryFailed, setExpiryFailed] = useState(false);

  const [productName, setProductName] = useState('');
  const [productSku, setProductSku] = useState('');
  const [productPrice, setProductPrice] = useState('0');
  const [productCost, setProductCost] = useState('0');
  const [productDescription, setProductDescription] = useState('');
  const [productDosage, setProductDosage] = useState('');
  const [productRxOnly, setProductRxOnly] = useState(false);
  const [productWeight, setProductWeight] = useState('');
  const [productLength, setProductLength] = useState('');
  const [productWidth, setProductWidth] = useState('');
  const [productHeight, setProductHeight] = useState('');
  const [productCategoryId, setProductCategoryId] = useState('');
  const [productTaxRateId, setProductTaxRateId] = useState('');
  const [productBrandId, setProductBrandId] = useState('');
  const [productUnitId, setProductUnitId] = useState('');
  const [editReorder, setEditReorder] = useState('0');
  const [editPrice, setEditPrice] = useState('0');
  const [editCost, setEditCost] = useState('0');
  const [editBarcode, setEditBarcode] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editDosage, setEditDosage] = useState('');
  const [editRxOnly, setEditRxOnly] = useState(false);
  const [editWeight, setEditWeight] = useState('');
  const [editLength, setEditLength] = useState('');
  const [editWidth, setEditWidth] = useState('');
  const [editHeight, setEditHeight] = useState('');
  const [productBarcode, setProductBarcode] = useState('');
  const [productSupplyClass, setProductSupplyClass] = useState('standard');
  const [editSupplyClass, setEditSupplyClass] = useState('standard');
  const [editCategoryId, setEditCategoryId] = useState('');
  const [editBrandId, setEditBrandId] = useState('');
  const [editUnitId, setEditUnitId] = useState('');
  const [editTaxRateId, setEditTaxRateId] = useState('');
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
  const [productMenuId, setProductMenuId] = useState('');
  const [labelPick, setLabelPick] = useState<Record<string, boolean>>({});

  const [catName, setCatName] = useState('');
  const [catParentId, setCatParentId] = useState('');
  const [catTaxRateId, setCatTaxRateId] = useState('');
  const [catSearch, setCatSearch] = useState('');
  const [catDrawerOpen, setCatDrawerOpen] = useState(false);
  const [catEditId, setCatEditId] = useState('');
  const [catTaxAdvanced, setCatTaxAdvanced] = useState(false);
  const [catMenuId, setCatMenuId] = useState('');
  const [catCollapsed, setCatCollapsed] = useState<Record<string, boolean>>({});
  const [brandSearch, setBrandSearch] = useState('');
  const [brandDrawerOpen, setBrandDrawerOpen] = useState(false);
  const [brandEditId, setBrandEditId] = useState('');
  const [brandAdvanced, setBrandAdvanced] = useState(false);
  const [brandMenuId, setBrandMenuId] = useState('');
  const [unitSearch, setUnitSearch] = useState('');
  const [unitDrawerOpen, setUnitDrawerOpen] = useState(false);
  const [unitEditId, setUnitEditId] = useState('');
  const [unitAdvanced, setUnitAdvanced] = useState(false);
  const [unitMenuId, setUnitMenuId] = useState('');
  const [unitCollapsed, setUnitCollapsed] = useState<Record<string, boolean>>({});
  const [variantSearch, setVariantSearch] = useState('');
  const [variantDrawerOpen, setVariantDrawerOpen] = useState(false);
  const [variantEditId, setVariantEditId] = useState('');
  const [variantAdvanced, setVariantAdvanced] = useState(false);
  const [variantMenuId, setVariantMenuId] = useState('');
  const [variantCost, setVariantCost] = useState('');
  const [variantPrice, setVariantPrice] = useState('');
  const [taxRates, setTaxRates] = useState<any[]>([]);
  const [brandName, setBrandName] = useState('');
  const [brandDescription, setBrandDescription] = useState('');
  const [brandLogoPreview, setBrandLogoPreview] = useState<Record<string, string>>({});
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
  const [stockRefType, setStockRefType] = useState('');
  const [stockRefId, setStockRefId] = useState('');
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
  const [whStockIncludeZero, setWhStockIncludeZero] = useState(true);
  const [adjustSearch, setAdjustSearch] = useState('');
  const [whStockRows, setWhStockRows] = useState<any[]>([]);
  const [whStockBusy, setWhStockBusy] = useState(false);
  const [whStockFailed, setWhStockFailed] = useState(false);
  const [whStockMeta, setWhStockMeta] = useState<{
    warehouse_name?: string;
    total_quantity?: number;
    count?: number;
  }>({});
  const [whReorderProductId, setWhReorderProductId] = useState('');
  const [whReorderLevel, setWhReorderLevel] = useState('0');
  const [whReorderQty, setWhReorderQty] = useState('0');
  const [transfers, setTransfers] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [xferFromWh, setXferFromWh] = useState('');
  const [xferToWh, setXferToWh] = useState('');
  const [xferFromFilter, setXferFromFilter] = useState('');
  const [xferToFilter, setXferToFilter] = useState('');
  const [xferLines, setXferLines] = useState<{ key: string; product_id: string; qty: string }[]>([
    { key: '1', product_id: '', qty: '1' },
  ]);
  const [xferNotes, setXferNotes] = useState('');
  const [xferRejectReason, setXferRejectReason] = useState('');
  const [xferConfirming, setXferConfirming] = useState(false);
  const [xferDetailId, setXferDetailId] = useState('');
  const [countCancelReason, setCountCancelReason] = useState('');
  const [invNumbering, setInvNumbering] = useState<{
    opening_stock_numbering?: { preview?: string };
    stock_transfer_numbering?: { preview?: string };
    stock_count_numbering?: { preview?: string };
  }>({});
  const [batchSearch, setBatchSearch] = useState('');
  const [batchDrawerOpen, setBatchDrawerOpen] = useState(false);
  const [openingSearch, setOpeningSearch] = useState('');
  const [openingDrawerOpen, setOpeningDrawerOpen] = useState(false);
  const [expirySearch, setExpirySearch] = useState('');
  const [countSearch, setCountSearch] = useState('');
  const [countDrawerOpen, setCountDrawerOpen] = useState(false);
  const [adjustDrawerOpen, setAdjustDrawerOpen] = useState(false);
  const [adjConfirming, setAdjConfirming] = useState(false);
  const [stockOutDrawerOpen, setStockOutDrawerOpen] = useState(false);
  const [whSearch, setWhSearch] = useState('');
  const [whLowOnly, setWhLowOnly] = useState(false);
  const [lowStockPayload, setLowStockPayload] = useState<any>(null);
  const [lowStockBusy, setLowStockBusy] = useState(false);
  const [lowStockSearch, setLowStockSearch] = useState('');
  const [receiveDrawerOpen, setReceiveDrawerOpen] = useState(false);
  const [reorderDrawerOpen, setReorderDrawerOpen] = useState(false);
  const [xferSearch, setXferSearch] = useState('');
  const [xferDateFrom, setXferDateFrom] = useState('');
  const [xferDateTo, setXferDateTo] = useState('');
  const [xferSort, setXferSort] = useState('date');
  const [xferSortDir, setXferSortDir] = useState<1 | -1>(-1);
  const [xferPage, setXferPage] = useState(1);
  const [xferBusy, setXferBusy] = useState(false);
  const [xferProductQuery, setXferProductQuery] = useState('');
  const [xferReference, setXferReference] = useState('');
  const [xferAvail, setXferAvail] = useState<Record<string, number>>({});
  const [xferDrawerOpen, setXferDrawerOpen] = useState(false);
  const [mvSearch, setMvSearch] = useState('');
  async function loadTabExtras(current: Tab, req: RequestInit = {}) {
    const jobs: Promise<void>[] = [];
    if (
      current === 'expiry' ||
      current === 'batches' ||
      current === 'opening'
    ) {
      jobs.push(
        (async () => {
          if (current === 'expiry') {
            setExpiryBusy(true);
            setExpiryFailed(false);
          }
          const e = await apiOptional('/inventory/batches/expiring?days=365', req);
          if ((e as { aborted?: boolean }).aborted) return;
          if (e.error) {
            if (current === 'expiry') setExpiryFailed(true);
            setError(e.error);
            if (current === 'expiry') setExpiring([]);
            return;
          }
          if (current === 'expiry') setExpiryFailed(false);
          setExpiring(e.data?.batches || []);
        })().finally(() => {
          if (current === 'expiry') setExpiryBusy(false);
        }),
      );
    }
    if (current === 'counts') {
      jobs.push(
        apiOptional('/inventory/stock-counts', req).then((sc) => {
          if ((sc as { aborted?: boolean }).aborted) return;
          setCounts(sc.data || []);
        }),
      );
    }
    if (current === 'opening') {
      jobs.push(
        apiOptional('/inventory/opening-stock', req).then((os) => {
          if ((os as { aborted?: boolean }).aborted) return;
          if (os.error) {
            setError(os.error);
            return;
          }
          setOpeningHistory(os.data || []);
        }),
      );
    }
    if (current === 'categories' || current === 'products') {
      jobs.push(
        apiOptional('/tax/rates', req).then((rates) => {
          if ((rates as { aborted?: boolean }).aborted) return;
          setTaxRates(rates.data || []);
        }),
      );
    }
    if (current === 'transfers' || current === 'whstock' || current === 'products') {
      jobs.push(
        apiOptional('/stores', req).then((st) => {
          if ((st as { aborted?: boolean }).aborted) return;
          setStores(st.data || []);
        }),
      );
    }
    if (current === 'products') {
      jobs.push(
        apiOptional('/inventory/settings', req).then((settings) => {
          if ((settings as { aborted?: boolean }).aborted) return;
          setInvNumbering(settings.data || {});
        }),
      );
    }
    if (jobs.length) await Promise.all(jobs);
  }

  async function refresh(opts?: { signal?: AbortSignal }) {
    const req: RequestInit = opts?.signal ? { signal: opts.signal } : {};
    const cachedFast = peekPrefetch('/products?limit=80') || peekPrefetch('/products');
    if (cachedFast?.data) {
      setProducts(cachedFast.data || []);
      setBootLoading(false);
    }
    const [pFast, c, b, u, w] = await Promise.all([
      getPrefetched('/products?limit=80'),
      getPrefetched('/catalog/categories'),
      getPrefetched('/catalog/brands'),
      getPrefetched('/catalog/units'),
      apiOptional('/warehouses', req),
    ]);
    if (opts?.signal?.aborted) return;
    const loadError = [c, b, u, w]
      .map((x: { error?: string | null }) => x.error)
      .filter(Boolean)
      .join(' ');
    if (loadError) setError(loadError);
    else setError('');
    setProducts(pFast.data || []);
    setCategories(c.data || []);
    setBrands(b.data || []);
    setUnits(u.data || []);
    setWarehouses(w.data || []);
    if (!countWarehouseId && w.data?.length) setCountWarehouseId(w.data[0].id);
    if (!openingWarehouseId && w.data?.length) setOpeningWarehouseId(w.data[0].id);
    if (!lotWh && w.data?.length) setLotWh(w.data[0].id);
    if (!stockWarehouseId && w.data?.length) setStockWarehouseId(w.data[0].id);
    if (!whStockWarehouseId && w.data?.length) setWhStockWarehouseId(w.data[0].id);
    const linked = hotelOps ? w.data || [] : (w.data || []).filter((x: any) => x.store_id);
    if (!xferFromWh && linked[0]) setXferFromWh(linked[0].id);
    if (!xferToWh && linked[1]) setXferToWh(linked[1].id);
    else if (!xferToWh && linked[0]) setXferToWh(linked[0].id);
    setBootLoading(false);

    const pFullP = apiOptional('/products', req);
    const vJob = loadAllVariants(req);
    const pFull = await pFullP;
    await vJob;
    if (opts?.signal?.aborted || (pFull as { aborted?: boolean }).aborted) return;
    if (pFull.error) setError(pFull.error);
    if (Array.isArray(pFull.data)) setProducts(pFull.data);

    await loadTabExtras(tab, req);
  }

  async function loadAllVariants(req: RequestInit = {}) {
    const v = await apiOptional('/products/variants', req);
    if ((v as { aborted?: boolean }).aborted) return;
    if (v.error) {
      setVariantsError(v.error);
      setError(v.error);
      setVariantsReady(true);
      return;
    }
    if (!Array.isArray(v.data)) {
      setVariantsError('Could not load variants');
      setError('Could not load variants');
      setVariantsReady(true);
      return;
    }
    setVariantsError('');
    setVariants(uniqueById(v.data));
    setVariantsReady(true);
  }

  async function refreshSelected(id: string) {
    if (!id) return;
    const [b, g] = await Promise.all([
      apiOptional(`/products/${id}/batches`),
      apiOptional(`/products/${id}/images`),
    ]);
    const selectedError = [b, g].map((x) => x.error).filter(Boolean).join(' ');
    if (selectedError) setError(selectedError);
    if (!b.error && Array.isArray(b.data)) setBatches(b.data);
    else if (b.error) setError(b.error);
    if (!g.error && Array.isArray(g.data)) setGallery(g.data);
    else if (g.error) setError(g.error);
    setStockVariantId('');
    setOpeningVariantId('');
  }

  useEffect(() => {
    const ac = new AbortController();
    const done = pageLoadStarted('products');
    refresh({ signal: ac.signal })
      .catch((err) => {
        if (!isAbortError(err)) setError(err.message);
      })
      .finally(() => {
        if (!ac.signal.aborted) setBootLoading(false);
        done();
      });
    return () => ac.abort();
  }, []);

  useEffect(() => {
    loadTabExtras(tab).catch((err) => {
      if (!isAbortError(err)) setError(err.message);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

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
      // trim so Movements (UuidIdValue Query product_id/warehouse_id) do not 422
      const warehouseTrim = warehouse ? String(warehouse).trim() : '';
      const productTrim = productId ? String(productId).trim() : '';
      if (warehouseTrim) params.set('warehouse_id', warehouseTrim);
      if (type) params.set('movement_type', type);
      if (reason) params.set('reason', reason);
      if (from) params.set('from_date', from);
      if (to) params.set('to_date', to);
      if (productOnly && productTrim) params.set('product_id', productTrim);
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
    setWhStockFailed(false);
    const warehouse = overrides.warehouse_id ?? whStockWarehouseId;
    const includeZero = overrides.include_zero ?? whStockIncludeZero;
    if (!warehouse) {
      setWhStockRows([]);
      setWhStockMeta({});
      return;
    }
    setWhStockBusy(true);
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
      setWhStockFailed(false);
    } catch (err: any) {
      setError(err.message);
      setWhStockRows([]);
      setWhStockMeta({});
      setWhStockFailed(true);
    } finally {
      setWhStockBusy(false);
    }
  }

  useEffect(() => {
    if (tab === 'whstock') {
      loadWarehouseStock().catch((err) => setError(err.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, whStockWarehouseId, whStockIncludeZero]);

  async function loadLowStock() {
    setLowStockBusy(true);
    setError('');
    try {
      const params = new URLSearchParams();
      if (scopeStoreId) params.set('store_id', scopeStoreId);
      const q = params.toString();
      const r = await api(`/inventory/low-stock${q ? `?${q}` : ''}`);
      setLowStockPayload(r.data || { products: [], warehouse_low_stock: [] });
    } catch (err: any) {
      setError(err.message);
      setLowStockPayload(null);
    } finally {
      setLowStockBusy(false);
    }
  }

  useEffect(() => {
    if (tab === 'lowstock') {
      loadLowStock().catch((err) => setError(err.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, scopeStoreId]);

  async function loadTransfers() {
    setError('');
    setXferBusy(true);
    try {
      const qs =
        transferManageFilter !== 'all'
          ? `?status=${encodeURIComponent(transferManageFilter)}`
          : '';
      const r = await api(`/inventory/stock-transfers${qs}`);
      setTransfers(r.data || []);
    } catch (err: any) {
      setError(err.message);
      setTransfers([]);
    } finally {
      setXferBusy(false);
    }
  }

  useEffect(() => {
    if (tab === 'transfers' && retailTransfers) {
      loadTransfers().catch((err) => setError(err.message));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, transferManageFilter, retailTransfers]);

  useEffect(() => {
    setProductPage(1);
  }, [productSearch, productCategoryFilter, productBrandFilter, productStockFilter, productManageFilter]);

  useEffect(() => {
    setXferPage(1);
  }, [xferSearch, xferFromFilter, xferToFilter, transferManageFilter, xferDateFrom, xferDateTo]);

  useEffect(() => {
    if (!xferDrawerOpen || !xferFromWh) {
      setXferAvail({});
      return;
    }
    let cancelled = false;
    api(`/inventory/warehouse-stock?warehouse_id=${encodeURIComponent(xferFromWh)}&include_zero=true`)
      .then((r) => {
        if (cancelled) return;
        const m: Record<string, number> = {};
        for (const row of r.data?.items || []) {
          if (row.product_id) m[row.product_id] = Number(row.quantity || 0);
        }
        setXferAvail(m);
      })
      .catch(() => {
        if (!cancelled) setXferAvail({});
      });
    return () => {
      cancelled = true;
    };
  }, [xferDrawerOpen, xferFromWh]);

  function parsedXferItems():
    | { ok: false; error: string }
    | { ok: true; items: { product_id: string; quantity: number }[] } {
    const items: { product_id: string; quantity: number }[] = [];
    for (const line of xferLines) {
      const product_id = line.product_id.trim();
      const quantity = Number(line.qty);
      if (!product_id) continue;
      const qtyErr = transferLineQtyError(quantity, xferAvail[product_id]);
      if (qtyErr) return { ok: false, error: qtyErr };
      items.push({ product_id, quantity });
    }
    if (!items.length) return { ok: false, error: 'Add at least one product line' };
    return { ok: true, items };
  }

  async function createWarehouseTransfer() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setFormFlash({});
    const locErr = sameWarehouseError(xferFromWh, xferToWh);
    if (locErr) {
      setFormFlash({ err: locErr });
      return;
    }
    const parsed = parsedXferItems();
    if (!parsed.ok) {
      setFormFlash({ err: parsed.error });
      return;
    }
    if (!xferConfirming) {
      setXferConfirming(true);
      return;
    }
    setSaveBusy(true);
    try {
      const r = await api('/inventory/stock-transfers', {
        method: 'POST',
        body: JSON.stringify({
          from_warehouse_id: xferFromWh.trim(),
          to_warehouse_id: xferToWh.trim(),
          submit: true,
          notes: [xferReference.trim() && `Ref ${xferReference.trim()}`, xferNotes.trim()]
            .filter(Boolean)
            .join(' — ') || null,
          items: parsed.items,
        }),
      });
      if (!r.data?.id && !r.data?.transfer_number) {
        setFormFlash({ err: 'Server did not confirm the transfer' });
        return;
      }
      setFormFlash({
        ok:
          `Transfer ${r.data.transfer_number} requested` +
          (r.data.approval_steps_required <= 1 ? ' — same store' : ' — needs both managers'),
      });
      setXferNotes('');
      setXferReference('');
      setXferConfirming(false);
      setXferDrawerOpen(false);
      setXferLines([{ key: String(Date.now()), product_id: '', qty: '1' }]);
      await loadTransfers();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not create transfer' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function transferAct(id: string, action: string) {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setFormFlash({});
    if (action === 'reject' || action === 'cancel') {
      const reason = xferRejectReason.trim();
      if (!reason) {
        setFormFlash({
        err:
          action === 'cancel'
            ? 'Enter a cancel reason before cancelling a stock transfer'
            : 'Enter a reject reason before rejecting a stock transfer',
      });
        return;
      }
      if (
        !window.confirm(
          action === 'cancel'
            ? 'Cancel this stock transfer? Stock will not move.'
            : 'Reject this stock transfer?',
        )
      ) {
        return;
      }
    }
    setSaveBusy(true);
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
      setFormFlash({ ok: r.message || `Transfer ${action} saved` });
      await loadTransfers();
    } catch (err: any) {
      setFormFlash({ err: err.message || `Could not ${action} transfer` });
    } finally {
      setSaveBusy(false);
    }
  }

  function storeLabel(id: string | null | undefined) {
    if (!id) return '';
    const s = stores.find((x) => x.id === id);
    return s ? s.name || s.code || id.slice(0, 8) : '';
  }

  function warehouseLabel(id: string | null | undefined) {
    if (!id) return '—';
    const w = warehouses.find((x) => x.id === id);
    if (!w) return id.slice(0, 8);
    const loc = w.name || w.code || id.slice(0, 8);
    const store = storeLabel(w.store_id);
    return store ? `${store} · ${loc}` : loc;
  }

  async function saveWarehouseReorder() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setFormFlash({});
    const reorderWh = whStockWarehouseId.trim() || (hideWarehouseUx ? defaultWarehouseId : '');
    if (!reorderWh) {
      setFormFlash({ err: hideWarehouseUx ? 'No warehouse is available for this store' : 'Select a location' });
      return;
    }
    if (!whReorderProductId) {
      setFormFlash({ err: 'Select a product' });
      return;
    }
    setSaveBusy(true);
    try {
      const r = await api('/inventory/warehouse-stock/reorder', {
        method: 'PUT',
        body: JSON.stringify({
          warehouse_id: reorderWh,
          product_id: whReorderProductId.trim(),
          reorder_level: Number(whReorderLevel) || 0,
          reorder_qty: Number(whReorderQty) || 0,
        }),
      });
      if (!r.data) {
        setFormFlash({ err: 'Server did not confirm the reorder level' });
        return;
      }
      setFormFlash({
        ok: `Reorder saved for ${r.data.sku || r.data.name}: ${r.data.reorder_level} / ${r.data.reorder_qty}`,
      });
      await loadWarehouseStock();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not save reorder' });
    } finally {
      setSaveBusy(false);
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
        setEditCost(String(p.cost_price ?? 0));
        setEditBarcode(String(p.barcode || ''));
        setEditDescription(String(p.description || ''));
        setEditDosage(String(p.dosage_instructions || ''));
        setEditRxOnly(Boolean(p.rx_only));
        setEditWeight(p.weight != null ? String(p.weight) : '');
        setEditLength(p.length != null ? String(p.length) : '');
        setEditWidth(p.width != null ? String(p.width) : '');
        setEditHeight(p.height != null ? String(p.height) : '');
        setEditSupplyClass(String(p.tax_supply_class || (p.tax_exempt ? 'exempt' : 'standard')));
        setEditCategoryId(String(p.category_id || ''));
        setEditBrandId(String(p.brand_id || ''));
        setEditUnitId(String(p.unit_id || ''));
        setEditTaxRateId(String(p.tax_rate_id || ''));
      }
    }
  }, [selectedId, products]);

  async function saveProductEdits() {
    if (!selectedId) return;
    setError('');
    setFormFlash({});
    setSaveBusy(true);
    try {
      await api(`/products/${selectedId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          reorder_level: Number(editReorder) || 0,
          selling_price: Number(editPrice) || 0,
          cost_price: Number(editCost) || 0,
          barcode: editBarcode.trim() || null,
          description: editDescription.trim() || null,
          dosage_instructions: pharmacyOps ? editDosage.trim() || null : undefined,
          rx_only: pharmacyOps ? editRxOnly : undefined,
          weight: editWeight === '' ? null : Number(editWeight),
          length: editLength === '' ? null : Number(editLength),
          width: editWidth === '' ? null : Number(editWidth),
          height: editHeight === '' ? null : Number(editHeight),
          tax_supply_class: editSupplyClass,
          category_id: editCategoryId.trim() || null,
          brand_id: editBrandId.trim() || null,
          unit_id: editUnitId.trim() || null,
          tax_rate_id: editTaxRateId.trim() || null,
        }),
      });
      setFormFlash({ ok: 'Product updated' });
      setProductEditMode(false);
      await refresh();
      return true;
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not update product' });
      return false;
    } finally {
      setSaveBusy(false);
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

  function inventoryAuthHeaders(): Record<string, string> {
    const token = getAccessToken();
    const tenant = tenantHeaderValue(typeof window !== 'undefined' ? localStorage.getItem('tenant') : null);
    return {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
    };
  }

  async function fetchInventoryText(path: string): Promise<string> {
    const res = await fetch(`${apiRoot()}${path}`, { headers: inventoryAuthHeaders() });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = (body as { detail?: string; message?: string }).detail || (body as { message?: string }).message;
      throw new Error(detail || 'Request failed');
    }
    return res.text();
  }

  async function fetchInventoryBlob(path: string): Promise<Blob> {
    const res = await fetch(`${apiRoot()}${path}`, { headers: inventoryAuthHeaders() });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = (body as { detail?: string; message?: string }).detail || (body as { message?: string }).message;
      throw new Error(detail || 'Request failed');
    }
    return res.blob();
  }

  function openHtmlPrint(html: string) {
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const w = window.open(url, '_blank', 'noopener,noreferrer,width=720,height=640');
    if (!w) {
      URL.revokeObjectURL(url);
      throw new Error('Pop-up blocked — allow pop-ups to print labels');
    }
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  async function generateBarcode(productId?: string, opts?: { force?: boolean }): Promise<boolean> {
    const id = productId || selectedId;
    if (!id) return false;
    setError('');
    try {
      const row = products.find((p) => p.id === id);
      let force = Boolean(opts?.force);
      if (!force && row?.barcode) {
        const ok = window.confirm(
          `This product already has barcode ${row.barcode}. Replace it with a new unique code?`
        );
        if (!ok) return false;
        force = true;
      }
      const qs = `${force ? 'force=true&' : ''}symbology=${encodeURIComponent(barcodeSymbology)}`;
      const r = await api(`/products/${id}/barcode/generate?${qs}`, { method: 'POST', body: '{}' });
      if (id === selectedId) setEditBarcode(r.data?.barcode || '');
      const already = String(r.message || '').toLowerCase().includes('already');
      setMessage(
        already
          ? `Barcode already set (${r.data?.barcode || row?.barcode || ''})`
          : `Barcode set to ${r.data?.barcode} (${r.data?.symbology || barcodeSymbology})`
      );
      await refresh();
      return true;
    } catch (err: any) {
      setError(err.message);
      return false;
    }
  }

  async function generateQr(productId?: string) {
    const id = productId || selectedId;
    if (!id) return;
    setError('');
    try {
      const row = products.find((p) => p.id === id);
      if (!row?.barcode) {
        const ok = await generateBarcode(id);
        if (!ok) return;
      }
      const blob = await fetchInventoryBlob(`/products/${id}/qr.png`);
      const sku = row?.sku || id;
      downloadBlob(blob, `qr-${sku}.png`);
      setMessage('QR downloaded — payload is barcode or SKU only');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function printBarcodeLabel(productId?: string) {
    const id = productId || selectedId;
    if (!id) return;
    await printBarcodeLabelsForIds([id]);
  }

  async function printBarcodeLabelsForIds(ids: string[]) {
    if (!ids.length) return;
    setError('');
    try {
      const copies = Math.max(1, Math.min(40, Number(labelCopies) || 1));
      const pages: string[] = [];
      for (const id of ids) {
        pages.push(
          await fetchInventoryText(
            `/products/${id}/barcode/label?copies=${copies}&symbology=${encodeURIComponent(barcodeSymbology)}`
          )
        );
      }
      if (pages.length === 1) {
        openHtmlPrint(pages[0]);
        setMessage('Barcode / QR label opened — use Print labels');
        return;
      }
      const labels: string[] = [];
      let styles = '';
      for (const html of pages) {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        if (!styles) styles = doc.querySelector('style')?.innerHTML || '';
        doc.querySelectorAll('.label').forEach((el) => labels.push(el.outerHTML));
      }
      openHtmlPrint(
        `<!doctype html><html><head><meta charset="utf-8"/><title>Barcode / QR labels</title><style>${styles}</style></head><body><div class="toolbar"><div><strong>Barcode / QR labels</strong></div><button onclick="window.print()">Print labels</button></div><div class="sheet">${labels.join('')}</div></body></html>`
      );
      setMessage(`Opened ${labels.length} barcode / QR labels — use Print labels`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  function selectedLabelIds(): string[] {
    return Object.entries(labelPick)
      .filter(([, on]) => on)
      .map(([id]) => id);
  }

  async function generateBarcodesForSelected() {
    const ids = selectedLabelIds();
    if (!ids.length) {
      setError('Select one or more products');
      return;
    }
    setError('');
    let generated = 0;
    let skipped = 0;
    for (const id of ids) {
      const row = products.find((p) => p.id === id);
      if (row?.barcode) {
        skipped += 1;
        continue;
      }
      try {
        const r = await api(
          `/products/${id}/barcode/generate?symbology=${encodeURIComponent(barcodeSymbology)}`,
          { method: 'POST', body: '{}' }
        );
        if (String(r.message || '').toLowerCase().includes('already')) skipped += 1;
        else generated += 1;
      } catch (err: any) {
        setError(err.message);
        return;
      }
    }
    setMessage(`Generated ${generated} barcode${generated === 1 ? '' : 's'}${skipped ? ` · ${skipped} already had a barcode (not overwritten)` : ''}`);
    await refresh();
  }

  async function generateQrForSelected() {
    const ids = selectedLabelIds();
    if (!ids.length) {
      setError('Select one or more products');
      return;
    }
    setError('');
    try {
      for (const id of ids) {
        const row = products.find((p) => p.id === id);
        if (!row?.barcode) {
          await api(
            `/products/${id}/barcode/generate?symbology=${encodeURIComponent(barcodeSymbology)}`,
            { method: 'POST', body: '{}' }
          );
        }
        const blob = await fetchInventoryBlob(`/products/${id}/qr.png`);
        downloadBlob(blob, `qr-${row?.sku || id}.png`);
      }
      setMessage(ids.length === 1 ? 'QR downloaded — payload is barcode or SKU only' : `Downloaded ${ids.length} QR codes`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function startStockCount() {
    if (saveBusy) return;
    setError('');
    setFormFlash({});
    const countWh = countWarehouseId.trim() || (hideWarehouseUx ? defaultWarehouseId : '');
    if (!countWh) {
      setFormFlash({ err: hideWarehouseUx ? 'No warehouse is available for this store' : 'Select a location' });
      return;
    }
    setSaveBusy(true);
    try {
      const r = await api('/inventory/stock-counts', {
        method: 'POST',
        body: JSON.stringify({
          warehouse_id: countWh,
          notes: countNotes.trim() || null,
        }),
      });
      if (!r.data?.id) {
        setFormFlash({ err: 'Server did not confirm the stock count' });
        return;
      }
      setActiveCount(r.data);
      const qtys: Record<string, string> = {};
      for (const item of r.data.items || []) {
        qtys[item.product_id] = String(item.expected_qty ?? 0);
      }
      setCountQtys(qtys);
      setCountNotes('');
      setFormFlash({ ok: `Count ${r.data.count_number} created` });
      setCountDrawerOpen(false);
      setTab('counts');
      await refresh();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not start stock count' });
    } finally {
      setSaveBusy(false);
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
    if (saveBusy) return;
    setError('');
    setFormFlash({});
    setSaveBusy(true);
    try {
      const items = (activeCount.items || []).map((item: any) => ({
        product_id: String(item.product_id).trim(),
        counted_qty: Number(countQtys[item.product_id] ?? item.expected_qty ?? 0),
        notes: (countLineNotes[item.product_id] || '').trim() || null,
      }));
      const r = await api(`/inventory/stock-counts/${activeCount.id}/items`, {
        method: 'PATCH',
        body: JSON.stringify({ items }),
      });
      setActiveCount(r.data);
      setFormFlash({ ok: 'Count lines saved' });
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not save count lines' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function completeActiveCount() {
    if (!activeCount) return;
    if (saveBusy) return;
    setError('');
    setFormFlash({});
    setSaveBusy(true);
    try {
      const items = (activeCount.items || []).map((item: any) => ({
        product_id: String(item.product_id).trim(),
        counted_qty: Number(countQtys[item.product_id] ?? item.expected_qty ?? 0),
        notes: (countLineNotes[item.product_id] || '').trim() || null,
      }));
      await api(`/inventory/stock-counts/${activeCount.id}/items`, {
        method: 'PATCH',
        body: JSON.stringify({ items }),
      });
      const r = await api(`/inventory/stock-counts/${activeCount.id}/complete`, { method: 'POST' });
      setActiveCount(r.data);
      setFormFlash({ ok: `Count ${r.data.count_number} completed` });
      await refresh();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not complete stock count' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function cancelStockCount(id: string, countNumber?: string) {
    if (saveBusy) return;
    setError('');
    setFormFlash({});
    const reason = countCancelReason.trim();
    if (!reason) {
      setFormFlash({ err: 'Enter a cancel reason before cancelling a stock count' });
      return;
    }
    setSaveBusy(true);
    try {
      const r = await api(`/inventory/stock-counts/${id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setFormFlash({ ok: `Count ${r.data?.count_number || countNumber || id} cancelled` });
      setCountCancelReason('');
      if (activeCount?.id === id) {
        setActiveCount(r.data);
      }
      await refresh();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not cancel stock count' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function createProduct() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setFormFlash({});
    const name = productName.trim();
    if (!name) {
      setFormFlash({ err: 'Enter a product name' });
      return;
    }
    const openingQty = Number(createOpeningQty);
    const wantsOpening = createOpeningQty.trim() !== '' && Number.isFinite(openingQty) && openingQty > 0;
    const wantsExpiry = Boolean(createOpeningExpiry.trim() || createOpeningBatch.trim() || createOpeningMfg.trim());
    if (wantsExpiry && !wantsOpening) {
      setFormFlash({ err: hideWarehouseUx
        ? 'Expiry is stored on a lot, not the product. Enter quantity with the expiry date.'
        : 'Expiry is stored on a warehouse lot, not the product. Enter quantity and location with the expiry date.' });
      setCreateOpenStockOpen(true);
      setCreateExpiryOpen(true);
      return;
    }
    const openingWh = createOpeningWh.trim() || (hideWarehouseUx ? defaultWarehouseId : '');
    if (wantsOpening && !openingWh) {
      setFormFlash({ err: hideWarehouseUx ? 'No warehouse is available for this store' : 'Select a warehouse for opening stock' });
      setCreateOpenStockOpen(true);
      return;
    }
    if (createOpeningExpiry && createOpeningMfg && createOpeningExpiry < createOpeningMfg) {
      setFormFlash({ err: 'Expiry date cannot be before manufacturing date' });
      setCreateExpiryOpen(true);
      return;
    }
    setSaveBusy(true);
    try {
      const lotNumber = wantsExpiry
        ? lotNumberForExpiry(createOpeningBatch, createOpeningExpiry || createOpeningMfg)
        : createOpeningBatch.trim() || null;
      const tracksBatches = Boolean(lotNumber);
      const r = await api('/products', {
        method: 'POST',
        body: JSON.stringify({
          name,
          sku: productSku.trim() || null,
          barcode: productBarcode.trim() || null,
          description: productDescription.trim() || null,
          dosage_instructions: pharmacyOps ? productDosage.trim() || null : undefined,
          rx_only: pharmacyOps ? productRxOnly : undefined,
          selling_price: Number(productPrice) || 0,
          cost_price: Number(productCost) || 0,
          weight: productWeight === '' ? null : Number(productWeight),
          length: productLength === '' ? null : Number(productLength),
          width: productWidth === '' ? null : Number(productWidth),
          height: productHeight === '' ? null : Number(productHeight),
          category_id: productCategoryId.trim() || null,
          tax_rate_id: productTaxRateId.trim() || null,
          brand_id: productBrandId.trim() || null,
          unit_id: productUnitId.trim() || null,
          tax_supply_class: productSupplyClass,
          tracks_batches: tracksBatches,
          stock_qty: 0,
        }),
      });
      const productId = r.data?.id;
      if (!productId) {
        setFormFlash({ err: 'Server did not confirm the product' });
        return;
      }
      if (wantsOpening) {
        const line: Record<string, unknown> = {
          product_id: productId,
          quantity: openingQty,
          warehouse_id: openingWh,
          batch_number: lotNumber,
          manufacturing_date: createOpeningMfg.trim() || null,
          expiry_date: createOpeningExpiry.trim() || null,
        };
        if (createOpeningCost !== '') line.unit_cost = Number(createOpeningCost);
        await api('/inventory/opening-stock', {
          method: 'POST',
          body: JSON.stringify({ post_journal: true, lines: [line] }),
        });
      }
      setProductName('');
      setProductSku('');
      setProductBarcode('');
      setProductDescription('');
      setProductDosage('');
      setProductRxOnly(false);
      setProductWeight('');
      setProductLength('');
      setProductWidth('');
      setProductHeight('');
      setProductPrice('0');
      setProductCost('0');
      setProductSupplyClass('standard');
      setProductTaxRateId('');
      setProductCategoryId('');
      setProductBrandId('');
      setProductUnitId('');
      setCreateOpeningQty('');
      setCreateOpeningBatch('');
      setCreateOpeningMfg('');
      setCreateOpeningExpiry('');
      setCreateOpeningCost('');
      setFormFlash({
        ok: wantsOpening
          ? createOpeningExpiry.trim()
            ? `Saved ${r.data.sku || name} with opening stock and expiry`
            : `Saved ${r.data.sku || name} with opening stock`
          : `Saved ${r.data.sku || name}. Set expiry below with quantity and warehouse, or use the Expiry tab.`,
      });
      setProductAddOpen(false);
      await refresh();
      setSelectedId(productId);
      setTab('products');
      setDrawerOpen(true);
      setProductEditMode(false);
      if (!lotWh && createOpeningWh) setLotWh(createOpeningWh);
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not save product' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function recordExpiryLot() {
    if (saveBusy) return;
    setError('');
    setFormFlash({});
    const productId = selectedId.trim();
    if (!productId) {
      setFormFlash({ err: 'Select a product' });
      return;
    }
    const qty = Number(lotQty);
    if (!Number.isFinite(qty) || qty <= 0) {
      setFormFlash({ err: 'Enter quantity for this warehouse lot' });
      return;
    }
    const warehouseId = (lotWh || createOpeningWh || stockWarehouseId || (hideWarehouseUx ? defaultWarehouseId : '')).trim();
    if (!warehouseId) {
      setFormFlash({ err: hideWarehouseUx ? 'No warehouse is available for this store' : 'Select a warehouse' });
      return;
    }
    const expiry = lotExpiry.trim();
    if (!expiry) {
      setFormFlash({ err: 'Enter an expiry date' });
      return;
    }
    const batch = lotNumberForExpiry(lotBatch, expiry);
    const product = products.find((p) => p.id === productId);
    const useOpening = Number(product?.stock_qty ?? 0) <= 0;
    setSaveBusy(true);
    try {
      if (useOpening) {
        const r = await api('/inventory/opening-stock', {
          method: 'POST',
          body: JSON.stringify({
            post_journal: true,
            lines: [
              {
                product_id: productId,
                quantity: qty,
                warehouse_id: warehouseId,
                batch_number: batch,
                expiry_date: expiry,
              },
            ],
          }),
        });
        if (!r.data?.id && !r.data?.reference) {
          setFormFlash({ err: 'Server did not confirm opening stock' });
          return;
        }
        setFormFlash({ ok: `Expiry saved on lot ${batch} · opening ${r.data.reference}` });
      } else {
        const r = await api('/inventory/stock-in', {
          method: 'POST',
          body: JSON.stringify({
            product_id: productId,
            quantity: qty,
            warehouse_id: warehouseId,
            batch_number: batch,
            expiry_date: expiry,
          }),
        });
        if (r.data?.stock_qty == null && !r.data?.batch) {
          setFormFlash({ err: 'Server did not confirm the lot' });
          return;
        }
        setFormFlash({ ok: `Expiry saved on lot ${batch} — on-hand ${r.data.stock_qty}` });
      }
      setLotQty('');
      setLotExpiry('');
      setLotBatch('');
      setExpiryDrawerOpen(false);
      await refresh();
      await refreshSelected(productId);
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not save expiry' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function downloadImportTemplate() {
    setError('');
    try {
      const token = getAccessToken();
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
      const token = getAccessToken();
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
      const token = getAccessToken();
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
      const token = getAccessToken();
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
      const token = getAccessToken();
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
      const token = getAccessToken();
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

  function variantApiProductId(variantId: string) {
    return (
      variants.find((v) => v.id === variantId)?.product_id ||
      variantProductId ||
      selectedId
    );
  }

  async function deactivateVariant(variantId: string) {
    const productId = variantApiProductId(variantId);
    if (!productId) return;
    setError('');
    setVariantMenuId('');
    if (
      !window.confirm(
        'Deactivate this variant? The product stays in the catalog. You can activate the variant again later.',
      )
    ) {
      return;
    }
    try {
      await api(`/products/${productId}/variants/${variantId}`, { method: 'DELETE' });
      setMessage('Variant deactivated');
      setVariants((prev) =>
        prev.map((v) => (v.id === variantId ? { ...v, is_active: false } : v)),
      );
      await loadAllVariants();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function activateVariant(variantId: string) {
    const productId = variantApiProductId(variantId);
    if (!productId) return;
    setError('');
    setVariantMenuId('');
    try {
      await api(`/products/${productId}/variants/${variantId}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: true }),
      });
      setMessage('Variant activated');
      setVariants((prev) =>
        prev.map((v) => (v.id === variantId ? { ...v, is_active: true } : v)),
      );
      await loadAllVariants();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveVariantPrice(variantId: string, price: string) {
    const productId = variantApiProductId(variantId);
    if (!productId) return;
    setError('');
    try {
      await api(`/products/${productId}/variants/${variantId}`, {
        method: 'PATCH',
        body: JSON.stringify({ selling_price: Number(price) || 0 }),
      });
      setMessage('Variant updated');
      await loadAllVariants();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveVariantCost(variantId: string, cost: string) {
    const productId = variantApiProductId(variantId);
    if (!productId) return;
    setError('');
    try {
      await api(`/products/${productId}/variants/${variantId}`, {
        method: 'PATCH',
        body: JSON.stringify({ cost_price: Number(cost) || 0 }),
      });
      setMessage('Variant cost updated');
      await loadAllVariants();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function generateVariantBarcode(variantId: string) {
    const productId = variantApiProductId(variantId);
    if (!productId) return;
    setError('');
    try {
      const row = variants.find((v) => v.id === variantId);
      let force = false;
      if (row?.barcode) {
        const ok = window.confirm(
          `This variant already has barcode ${row.barcode}. Replace it with a new unique code?`
        );
        if (!ok) return;
        force = true;
      }
      const qs = `${force ? 'force=true&' : ''}symbology=${encodeURIComponent(barcodeSymbology)}`;
      const r = await api(
        `/products/${productId}/variants/${variantId}/barcode/generate?${qs}`,
        { method: 'POST', body: '{}' }
      );
      const already = String(r.message || '').toLowerCase().includes('already');
      setMessage(
        already
          ? `Variant barcode already set (${r.data?.barcode || row?.barcode || ''})`
          : `Variant barcode set to ${r.data?.barcode} (${r.data?.symbology || barcodeSymbology})`
      );
      await loadAllVariants();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function generateVariantQr(variantId: string) {
    const productId = variantApiProductId(variantId);
    if (!productId) return;
    setError('');
    try {
      const row = variants.find((v) => v.id === variantId);
      if (!row?.barcode) {
        await api(
          `/products/${productId}/variants/${variantId}/barcode/generate?symbology=${encodeURIComponent(barcodeSymbology)}`,
          { method: 'POST', body: '{}' }
        );
        await loadAllVariants();
      }
      const blob = await fetchInventoryBlob(`/products/${productId}/variants/${variantId}/qr.png`);
      downloadBlob(blob, `qr-${row?.sku || variantId}.png`);
      setMessage('Variant QR downloaded — payload is barcode or SKU only');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function printVariantBarcodeLabel(variantId: string) {
    const productId = variantApiProductId(variantId);
    if (!productId) return;
    setError('');
    try {
      const copies = Math.max(1, Math.min(40, Number(labelCopies) || 1));
      const html = await fetchInventoryText(
        `/products/${productId}/variants/${variantId}/barcode/label?copies=${copies}&symbology=${encodeURIComponent(barcodeSymbology)}`
      );
      openHtmlPrint(html);
      setMessage('Variant barcode label opened — use Print labels');
    } catch (err: any) {
      setError(err.message);
    }
  }

  function openBrandCreate() {
    setBrandEditId('');
    setBrandName('');
    setBrandDescription('');
    setBrandAdvanced(false);
    setFormFlash({});
    setBrandDrawerOpen(true);
  }

  function openBrandEdit(row: any) {
    setBrandEditId(row.id);
    setBrandName(row.name || '');
    setBrandDescription(row.description || '');
    setBrandAdvanced(Boolean(row.description) || Boolean(row.has_logo));
    setFormFlash({});
    setBrandMenuId('');
    setBrandDrawerOpen(true);
  }

  async function saveBrand() {
    if (saveBusy) return;
    const name = brandName.trim();
    if (!name) {
      setFormFlash({ err: 'Enter a brand name' });
      return;
    }
    setSaveBusy(true);
    setFormFlash({});
    try {
      const body = {
        name,
        description: brandDescription.trim() || null,
      };
      if (brandEditId) {
        await api(`/catalog/brands/${brandEditId}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        setFormFlash({ ok: 'Brand updated' });
      } else {
        await api('/catalog/brands', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        setFormFlash({ ok: 'Brand created' });
      }
      await refresh();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not save brand' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function setBrandActive(row: any, isActive: boolean) {
    setError('');
    setBrandMenuId('');
    if (
      !isActive &&
      !window.confirm(
        'Deactivate this brand? Products stay in the catalog. You can activate the brand again later.',
      )
    ) {
      return;
    }
    try {
      if (isActive) {
        await api(`/catalog/brands/${row.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ is_active: true }),
        });
        setMessage(`Brand ${row.name} activated`);
      } else {
        await api(`/catalog/brands/${row.id}`, { method: 'DELETE' });
        setMessage('Brand deactivated');
      }
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function openUnitCreate() {
    setUnitEditId('');
    setUnitName('');
    setUnitBaseId('');
    setUnitRatio('1');
    setUnitAdvanced(false);
    setFormFlash({});
    setUnitDrawerOpen(true);
  }

  function openUnitEdit(row: any) {
    setUnitEditId(row.id);
    setUnitName(row.name || '');
    setUnitBaseId(row.base_unit_id || '');
    setUnitRatio(String(row.conversion_ratio ?? 1));
    setUnitAdvanced(Boolean(row.base_unit_id));
    setFormFlash({});
    setUnitMenuId('');
    setUnitDrawerOpen(true);
  }

  async function saveUnit() {
    if (saveBusy) return;
    const name = unitName.trim();
    if (!name) {
      setFormFlash({ err: 'Enter a unit name' });
      return;
    }
    setSaveBusy(true);
    setFormFlash({});
    try {
      const body: Record<string, unknown> = {
        name,
        base_unit_id: unitBaseId.trim() || null,
      };
      if (unitBaseId.trim()) {
        body.conversion_ratio = Number(unitRatio) || 1;
      } else if (unitEditId) {
        body.clear_base = true;
      }
      if (unitEditId) {
        await api(`/catalog/units/${unitEditId}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        setFormFlash({ ok: 'Unit updated' });
      } else {
        await api('/catalog/units', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        setFormFlash({ ok: 'Unit created' });
      }
      await refresh();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not save unit' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function setUnitActive(row: any, isActive: boolean) {
    setError('');
    setUnitMenuId('');
    if (
      !isActive &&
      !window.confirm(
        'Deactivate this unit? Products stay in the catalog. You can activate the unit again later.',
      )
    ) {
      return;
    }
    try {
      if (isActive) {
        await api(`/catalog/units/${row.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ is_active: true }),
        });
        setMessage(`Unit ${row.code} activated`);
      } else {
        await api(`/catalog/units/${row.id}`, { method: 'DELETE' });
        setMessage('Unit deactivated');
      }
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  function openVariantCreate() {
    setVariantEditId('');
    setVariantProductId(variantParentFilter || selectedId);
    setVariantName('');
    setVariantSku('');
    setVariantBarcode('');
    setVariantSize('');
    setVariantColor('');
    setVariantFlavor('');
    setVariantDosage('');
    setVariantCost('');
    setVariantPrice('');
    setVariantAdvanced(false);
    setFormFlash({});
    setVariantDrawerOpen(true);
  }

  function openVariantEdit(row: any) {
    setVariantEditId(row.id);
    setVariantProductId(row.product_id || selectedId);
    setVariantName(row.name || '');
    setVariantSku(row.sku || '');
    setVariantBarcode(row.barcode || '');
    setVariantSize(row.size || '');
    setVariantColor(row.color || '');
    setVariantFlavor(row.flavor || '');
    setVariantDosage(row.dosage || '');
    setVariantCost(String(row.cost_price ?? ''));
    setVariantPrice(String(row.selling_price ?? ''));
    setVariantAdvanced(Boolean(row.size || row.color || row.flavor || row.dosage || row.barcode));
    setFormFlash({});
    setVariantMenuId('');
    setVariantDrawerOpen(true);
  }

  async function addVariant() {
    if (saveBusy) return;
    setError('');
    setFormFlash({});
    const parentId = variantProductId || selectedId;
    if (!parentId) {
      setFormFlash({ err: 'Select a product first' });
      return;
    }
    const name = variantName.trim();
    if (!name) {
      setFormFlash({ err: 'Enter a variant name' });
      return;
    }
    setSaveBusy(true);
    try {
      const body: Record<string, unknown> = {
        name,
        sku: variantSku.trim() || null,
        barcode: variantBarcode.trim() || null,
        size: variantSize.trim() || null,
        color: variantColor.trim() || null,
        flavor: variantFlavor.trim() || null,
        dosage: variantDosage.trim() || null,
      };
      if (variantCost.trim()) body.cost_price = Number(variantCost) || 0;
      if (variantPrice.trim()) body.selling_price = Number(variantPrice) || 0;
      if (variantEditId) {
        const r = await api(`/products/${parentId}/variants/${variantEditId}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        if (r.data?.id) {
          setVariants((prev) => uniqueById([...prev.filter((x) => x.id !== r.data.id), r.data]));
        }
        setFormFlash({ ok: 'Variant updated' });
      } else {
        const r = await api(`/products/${parentId}/variants`, {
          method: 'POST',
          body: JSON.stringify(body),
        });
        if (!r.data?.id) {
          setFormFlash({ err: 'Server did not confirm the variant' });
          return;
        }
        setVariants((prev) => uniqueById([...prev.filter((x) => x.id !== r.data.id), r.data]));
        setFormFlash({ ok: `Variant ${r.data.sku || r.data.name} saved` });
      }
      await loadAllVariants();
      setTab('variants');
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not save variant' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function stockInBatch(opts?: { requireBatch?: boolean }) {
    if (saveBusy) return;
    setError('');
    setFormFlash({});
    if (!selectedId) {
      setFormFlash({ err: 'Select a product' });
      return;
    }
    const wh = (stockWarehouseId || whStockWarehouseId || (hideWarehouseUx ? defaultWarehouseId : '')).trim();
    if (!wh) {
      setFormFlash({ err: hideWarehouseUx ? 'No warehouse is available for this store' : 'Select a location' });
      return;
    }
    if (opts?.requireBatch && !batchNumber.trim()) {
      setFormFlash({ err: 'Enter a batch number' });
      return;
    }
    const qty = Number(stockQty);
    if (!Number.isFinite(qty) || qty <= 0) {
      setFormFlash({ err: 'Quantity must be a positive number' });
      return;
    }
    setSaveBusy(true);
    try {
      const r = await api('/inventory/stock-in', {
        method: 'POST',
        body: JSON.stringify({
          product_id: selectedId.trim(),
          quantity: qty,
          unit_id: stockUnitId.trim() || null,
          warehouse_id: wh,
          variant_id: stockVariantId.trim() || null,
          notes: stockNotes.trim() || null,
          batch_number: lotNumberForExpiry(batchNumber, expiryDate) || (opts?.requireBatch ? batchNumber.trim() : null),
          manufacturing_date: mfgDate.trim() || null,
          expiry_date: expiryDate.trim() || null,
          reference_type: stockRefType.trim() || null,
          reference_id: stockRefId.trim() || null,
        }),
      });
      if (r.data?.stock_qty == null && !r.data?.id) {
        setFormFlash({ err: 'Server did not confirm received stock' });
        return;
      }
      setFormFlash({ ok: `Stock received — on-hand ${r.data.stock_qty}` });
      setBatchNumber('');
      setMfgDate('');
      setExpiryDate('');
      setStockNotes('');
      await refresh();
      await refreshSelected(selectedId);
      if (whStockWarehouseId) await loadWarehouseStock();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not receive stock' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function postOpeningStock() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setFormFlash({});
    if (!selectedId) {
      setFormFlash({ err: 'Select a product' });
      return;
    }
    const qty = Number(openingQty);
    if (!Number.isFinite(qty) || qty <= 0) {
      setFormFlash({ err: 'Quantity must be a positive number' });
      return;
    }
    const openingWhId = openingWarehouseId.trim() || (hideWarehouseUx ? defaultWarehouseId : '');
    if ((openingExpiry.trim() || openingBatch.trim() || openingMfg.trim()) && !openingWhId) {
      setFormFlash({ err: hideWarehouseUx ? 'No warehouse is available for this store' : 'Select a warehouse to record expiry' });
      return;
    }
    if (openingExpiry && openingMfg && openingExpiry < openingMfg) {
      setFormFlash({ err: 'Expiry date cannot be before manufacturing date' });
      return;
    }
    setSaveBusy(true);
    try {
      const line: Record<string, unknown> = {
        product_id: selectedId.trim(),
        quantity: qty,
        unit_id: openingUnitId.trim() || null,
        warehouse_id: openingWhId || null,
        variant_id: openingVariantId.trim() || null,
        batch_number: lotNumberForExpiry(openingBatch, openingExpiry || openingMfg),
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
      if (!r.data?.reference && !r.data?.id) {
        setFormFlash({ err: 'Server did not confirm opening stock' });
        return;
      }
      const je = r.data.journal_number ? ` · journal ${r.data.journal_number}` : '';
      setFormFlash({
        ok: `Opening stock ${r.data.reference}: ${r.data.line_count} line(s), value ${r.data.inventory_value}${je}`,
      });
      setOpeningBatch('');
      setOpeningMfg('');
      setOpeningExpiry('');
      setOpeningNotes('');
      setOpeningLineNotes('');
      await refresh();
      await refreshSelected(selectedId);
      setTab('opening');
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not post opening stock' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function postStockAdjust() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setFormFlash({});
    if (!selectedId) {
      setFormFlash({ err: 'Select a product' });
      return;
    }
    if (!adjReason.trim()) {
      setFormFlash({ err: 'Select an adjustment reason' });
      return;
    }
    const qty = Number(adjQty);
    if (!Number.isFinite(qty) || qty === 0) {
      setFormFlash({ err: 'Enter a non-zero quantity change' });
      return;
    }
    if (!adjConfirming) {
      setAdjConfirming(true);
      return;
    }
    setSaveBusy(true);
    try {
      const reason = adjReason;
      const r = await api(`/inventory/adjust/${selectedId}`, {
        method: 'POST',
        body: JSON.stringify({
          quantity: qty,
          reason,
          notes: adjNotes.trim() || null,
          warehouse_id: adjWarehouseId.trim() || null,
        }),
      });
      if (r.data?.stock_qty == null) {
        setFormFlash({ err: 'Server did not confirm the adjustment' });
        return;
      }
      setAdjNotes('');
      setAdjReason('');
      setAdjConfirming(false);
      setFormFlash({ ok: `Adjustment saved — on-hand ${r.data.stock_qty}` });
      await refresh();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Adjustment failed' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function postStockOut() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setFormFlash({});
    if (!selectedId) {
      setFormFlash({ err: 'Select a product' });
      return;
    }
    if (!outRefType.trim()) {
      setFormFlash({ err: 'Select a stock-out reference type' });
      return;
    }
    const qty = Number(outQty);
    if (!Number.isFinite(qty) || qty <= 0) {
      setFormFlash({ err: 'Quantity must be a positive number' });
      return;
    }
    setSaveBusy(true);
    try {
      const r = await api('/inventory/stock-out', {
        method: 'POST',
        body: JSON.stringify({
          product_id: selectedId.trim(),
          quantity: qty,
          reference_type: outRefType,
          reference_id: outRefId.trim() || null,
          notes: outNotes.trim() || null,
          warehouse_id: outWarehouseId.trim() || null,
          variant_id: outVariantId.trim() || null,
          unit_id: outUnitId.trim() || null,
          batch_id: outBatchId.trim() || null,
        }),
      });
      if (r.data?.stock_qty == null) {
        setFormFlash({ err: 'Server did not confirm stock out' });
        return;
      }
      setFormFlash({ ok: `Stock out saved — on-hand ${r.data.stock_qty}` });
      setOutNotes('');
      setOutRefId('');
      setOutRefType('');
      await refresh();
      setMvType('stock_out');
      setMvReason('');
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not post stock out' });
    } finally {
      setSaveBusy(false);
    }
  }

  function openCategoryCreate() {
    setCatEditId('');
    setCatName('');
    setCatParentId('');
    setCatTaxRateId('');
    setCatTaxAdvanced(false);
    setFormFlash({});
    setCatDrawerOpen(true);
  }

  function openCategoryEdit(row: any) {
    setCatEditId(row.id);
    setCatName(row.name || '');
    setCatParentId(row.parent_id || '');
    setCatTaxRateId(row.tax_rate_id || '');
    setCatTaxAdvanced(Boolean(row.tax_rate_id));
    setFormFlash({});
    setCatMenuId('');
    setCatDrawerOpen(true);
  }

  async function saveCategory() {
    if (saveBusy) return;
    const name = catName.trim();
    if (!name) {
      setFormFlash({ err: 'Enter a category name' });
      return;
    }
    setSaveBusy(true);
    setFormFlash({});
    try {
      const body = {
        name,
        parent_id: catParentId.trim() || null,
        tax_rate_id: catTaxRateId.trim() || null,
      };
      if (catEditId) {
        await api(`/catalog/categories/${catEditId}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        setFormFlash({ ok: 'Category updated' });
      } else {
        await api('/catalog/categories', {
          method: 'POST',
          body: JSON.stringify(body),
        });
        setFormFlash({ ok: 'Category created' });
      }
      await refresh();
    } catch (err: any) {
      setFormFlash({ err: err.message || 'Could not save category' });
    } finally {
      setSaveBusy(false);
    }
  }

  async function setCategoryActive(row: any, isActive: boolean) {
    setError('');
    setCatMenuId('');
    if (
      !isActive &&
      !window.confirm(
        'Deactivate this category? Products stay in the catalog. You can activate the category again later.',
      )
    ) {
      return;
    }
    try {
      if (isActive) {
        await api(`/catalog/categories/${row.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ is_active: true }),
        });
        setMessage('Category activated');
      } else {
        await api(`/catalog/categories/${row.id}`, { method: 'DELETE' });
        setMessage('Category deactivated');
      }
      await refresh();
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
  const productListRows = sortProducts(
    managedProducts.filter((p) =>
      matchesProductList(
        p,
        {
          q: productSearch,
          categoryId: productCategoryFilter,
          brandId: productBrandFilter,
                stock: productStockFilter,
        },
        stockStatusOf(p),
      ) && (!rxOnlyFilter || Boolean(p.rx_only)),
    ),
    productSort,
    productSortDir,
  );
  const productPaged = paginate(productListRows, productPage, LIST_PAGE_SIZE);
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
  const categoryQuery = catSearch.trim().toLowerCase();
  const visibleCategories = managedCategories.filter((c) => {
    if (categoryQuery) {
      const parentName = categoryParentName(categories, c.parent_id).toLowerCase();
      const hay = `${c.name || ''} ${c.path || ''} ${parentName}`.toLowerCase();
      if (!hay.includes(categoryQuery)) return false;
    }
    if (categoryQuery) return true;
    let pid = c.parent_id;
    while (pid) {
      if (catCollapsed[pid]) return false;
      const parent = categories.find((x) => x.id === pid);
      pid = parent?.parent_id;
    }
    return true;
  });
  const managedBrands = byStatus(brands, brandManageFilter);
  const brandQuery = brandSearch.trim().toLowerCase();
  const visibleBrands = managedBrands.filter((b) => {
    if (!brandQuery) return true;
    const hay = `${b.name || ''} ${b.code || ''} ${b.description || ''}`.toLowerCase();
    return hay.includes(brandQuery);
  });
  const managedUnits = byStatus(units, unitManageFilter);
  const unitQuery = unitSearch.trim().toLowerCase();
  const visibleUnits = managedUnits
    .filter((u) => {
      if (unitQuery) {
        const parentName = unitParentName(units, u.base_unit_id).toLowerCase();
        const hay = `${u.name || ''} ${u.code || ''} ${parentName}`.toLowerCase();
        if (!hay.includes(unitQuery)) return false;
        return true;
      }
      let pid = u.base_unit_id;
      while (pid) {
        if (unitCollapsed[pid]) return false;
        const parent = units.find((x) => x.id === pid);
        pid = parent?.base_unit_id;
      }
      return true;
    })
    .slice()
    .sort((a, b) => {
      const da = unitDepthOf(units, a);
      const db = unitDepthOf(units, b);
      if (da !== db) return da - db;
      return String(a.name || '').localeCompare(String(b.name || ''));
    });
  const managedVariants = byStatus(uniqueById(variants), variantManageFilter);
  const variantQuery = variantSearch.trim().toLowerCase();
  const visibleVariants = managedVariants.filter((v) => {
    if (variantParentFilter && v.product_id !== variantParentFilter) return false;
    if (!variantQuery) return true;
    const parentName = products.find((p) => p.id === v.product_id)?.name || '';
    const hay = `${v.name || ''} ${v.sku || ''} ${parentName}`.toLowerCase();
    return hay.includes(variantQuery);
  });
  const selectorVariants = activeCatalogVariants(variants);
  const managedCounts = counts.filter((c) => {
    if (countManageFilter === 'all') return true;
    return (c.status || 'draft') === countManageFilter;
  });
  const managedTransfers = transfers.filter((t) => {
    if (xferFromFilter && t.from_warehouse_id !== xferFromFilter) return false;
    if (xferToFilter && t.to_warehouse_id !== xferToFilter) return false;
    if (transferManageFilter === 'all') return true;
    return (t.status || 'draft') === transferManageFilter;
  });
  const batchQuery = batchSearch.trim().toLowerCase();
  const visibleBatches = batches.filter((b) => {
    if (!batchQuery) return true;
    const prod = products.find((p) => p.id === b.product_id);
    const wh = warehouses.find((w) => w.id === b.warehouse_id);
    const hay = `${b.batch_number || ''} ${prod?.name || ''} ${prod?.sku || ''} ${wh?.name || ''} ${wh?.code || ''}`.toLowerCase();
    return hay.includes(batchQuery);
  });
  const openingQuery = openingSearch.trim().toLowerCase();
  const visibleOpening = openingHistory.filter((m) => {
    if (!openingQuery) return true;
    const p = products.find((x) => x.id === m.product_id);
    const hay = `${p?.sku || ''} ${p?.name || ''} ${m.reference_id || ''}`.toLowerCase();
    return hay.includes(openingQuery);
  });
  const expiryQuery = expirySearch.trim().toLowerCase();
  const storeWhIds = new Set(storeWarehouses.map((w: any) => String(w.id)));
  const visibleExpiring = expiring.filter((b) => {
    if (scopeStoreId && b.warehouse_id && !storeWhIds.has(String(b.warehouse_id))) return false;
    if (!expiryQuery) return true;
    const prod = products.find((p) => p.id === b.product_id);
    const wh = warehouses.find((w) => w.id === b.warehouse_id);
    const hay = `${b.batch_number || ''} ${prod?.name || ''} ${prod?.sku || ''} ${wh?.name || ''} ${wh?.code || ''}`.toLowerCase();
    return hay.includes(expiryQuery);
  });
  const countQuery = countSearch.trim().toLowerCase();
  const visibleCounts = managedCounts.filter((c) => {
    if (!countQuery) return true;
    const hay = `${c.count_number || ''} ${c.status || ''} ${c.notes || ''}`.toLowerCase();
    return hay.includes(countQuery);
  });
  const mvQuery = mvSearch.trim().toLowerCase();
  const visibleMovements = movements.filter((mv) => {
    if (!mvQuery) return true;
    const hay = `${mv.product_sku || ''} ${mv.product_name || ''} ${mv.movement_type || ''} ${mv.reason || ''} ${mv.created_by_name || ''}`.toLowerCase();
    return hay.includes(mvQuery);
  });
  const whQuery = whSearch.trim().toLowerCase();
  const visibleWhRows = whStockRows.filter((r) => {
    if (whLowOnly && !warehouseRowIsLow(r)) return false;
    if (!whQuery) return true;
    const hay = `${r.sku || ''} ${r.name || ''}`.toLowerCase();
    return hay.includes(whQuery);
  });
  const xferQuery = xferSearch.trim().toLowerCase();
  const visibleTransfers = sortByKey(
    managedTransfers.filter((t) => {
      if (!transferOnDate(t, xferDateFrom, xferDateTo)) return false;
      return matchesTransferSearch(t, xferQuery, {
        from: warehouseLabel(t.from_warehouse_id),
        to: warehouseLabel(t.to_warehouse_id),
      });
    }),
    (t) => {
      if (xferSort === 'from') return warehouseLabel(t.from_warehouse_id);
      if (xferSort === 'to') return warehouseLabel(t.to_warehouse_id);
      if (xferSort === 'qty') return transferQtyTotal(t);
      if (xferSort === 'status') return t.status || '';
      if (xferSort === 'ref') return t.transfer_number || '';
      return t.created_at || '';
    },
    xferSortDir,
  );
  const xferPaged = paginate(visibleTransfers, xferPage, LIST_PAGE_SIZE);
  const xferProductOptions = managedProducts.filter((p) => {
    const q = xferProductQuery.trim().toLowerCase();
    if (!q) return true;
    return `${p.name || ''} ${p.sku || ''} ${p.barcode || ''}`.toLowerCase().includes(q);
  });
  const xferParsed = parsedXferItems();
  const adjustEligible = products.filter((p) => p.is_active !== false);
  const adjQuery = adjustSearch.trim().toLowerCase();
  const adjustVisible = adjustEligible.filter((p) => {
    if (!adjQuery) return true;
    return `${p.name || ''} ${p.sku || ''} ${p.barcode || ''}`.toLowerCase().includes(adjQuery);
  });
  const adjustLowOutCount = adjustVisible.filter((p) => {
    const st = stockStatusOf(p);
    return st === 'red' || st === 'out';
  }).length;
  const batchFormDirty = Boolean(
    batchNumber.trim() ||
      mfgDate ||
      expiryDate ||
      stockNotes.trim() ||
      stockRefType.trim() ||
      stockRefId.trim() ||
      stockQty !== '10',
  );
  const openingFormDirty = Boolean(
    openingBatch.trim() ||
      openingMfg ||
      openingExpiry ||
      openingNotes.trim() ||
      openingLineNotes.trim() ||
      openingReference.trim() ||
      openingUnitCost.trim() ||
      openingQty !== '10',
  );
  const countFormDirty = Boolean(countNotes.trim());
  const adjustFormDirty = Boolean(adjQty.trim() || adjReason || adjNotes.trim() || adjConfirming);
  const stockOutFormDirty = Boolean(outQty.trim() || outRefType || outRefId.trim() || outNotes.trim());
  const receiveFormDirty = Boolean(stockQty !== '10' || batchNumber.trim() || expiryDate);
  const reorderFormDirty = Boolean(whReorderProductId || whReorderLevel.trim() || whReorderQty.trim());
  const productAddDirty = Boolean(
    productName.trim() ||
      productSku.trim() ||
      productBarcode.trim() ||
      productDescription.trim() ||
      productDosage.trim() ||
      productRxOnly ||
      (productPrice !== '' && productPrice !== '0') ||
      (productCost !== '' && productCost !== '0') ||
      productCategoryId ||
      productBrandId ||
      productUnitId ||
      createOpeningQty.trim() ||
      createOpeningExpiry ||
      createOpeningBatch.trim(),
  );
  const lsQuery = lowStockSearch.trim().toLowerCase();
  const lowStockSource = scopeStoreId
    ? (lowStockPayload?.warehouse_low_stock || []).map((w: any) => ({
        key: `w-${w.product_id}-${w.warehouse_id || ''}`,
        id: w.product_id,
        name: w.name,
        sku: w.sku,
        category: w.category || '—',
        qty: w.quantity,
        floor: w.low_stock_floor ?? Math.max(Number(w.minimum_stock || 0), Number(w.reorder_level || 0)),
        status: w.stock_status_label || 'low',
      }))
    : (lowStockPayload?.products || []).map((p: any) => ({
        key: `p-${p.id}`,
        id: p.id,
        name: p.name,
        sku: p.sku,
        category: p.category || '—',
        qty: p.stock_qty,
        floor: p.low_stock_floor ?? Math.max(Number(p.minimum_stock || 0), Number(p.reorder_level || 0)),
        status: p.stock_status_label || 'low',
      }));
  const lowStockRows = lowStockSource.filter((row: any) => {
    if (!lsQuery) return true;
    return `${row.name} ${row.sku} ${row.category}`.toLowerCase().includes(lsQuery);
  });

  return (
    <>
      <h1>{VIEW_TITLE[tab]}</h1>
      <p className="muted">
        {hotelOps
          ? 'Linen, toiletries, F&B, and cleaning supplies use the same inventory ledger as the rest of the hotel.'
          : 'Products, catalog, batches, stock, transfers, expiry, counts, history, and adjustments'}
      </p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: 'var(--brand, #4AB012)' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(
          [
            ['products', 'Products'],
            ['labels', 'Labels'],
            ['lookup', 'Lookup'],
            ['import', 'Import'],
            ['categories', 'Categories'],
            ['brands', 'Brands'],
            ['units', 'Units'],
            ['variants', 'Variants'],
            ['batches', 'Batches'],
            ['opening', 'Opening stock'],
            ['stockout', 'Stock out'],
            ['lowstock', 'Low stock'],
            ['whstock', 'Manage stock'],
            ['transfers', 'Stock transfer'],
            ['expiry', 'Expiry'],
            ['counts', 'Stock count'],
            ['movements', 'Stock history'],
            ['adjust', 'Adjust stock'],
          ] as const
        )
          .filter(([id]) => id !== 'transfers' || retailTransfers)
          .map(([id, label]) => (
          <button
            key={id}
            onClick={() => selectTab(id)}
            disabled={tab === id}
            aria-label={`Show inventory ${id} tab`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab !== 'products' &&
        tab !== 'labels' &&
        tab !== 'categories' &&
        tab !== 'brands' &&
        tab !== 'units' &&
        tab !== 'variants' &&
        tab !== 'lookup' &&
        tab !== 'import' &&
        tab !== 'expiry' &&
        tab !== 'batches' &&
        tab !== 'opening' &&
        tab !== 'counts' &&
        tab !== 'movements' &&
        tab !== 'adjust' &&
        tab !== 'stockout' &&
        tab !== 'lowstock' &&
        tab !== 'whstock' &&
        tab !== 'transfers' && (
      <div className="card" style={{ marginBottom: 16 }}>
        <label className="muted">
          {tab === 'whstock' ? 'Warehouse / product context' : 'Product for this action'}
        </label>
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
        <select
          value={selectedId}
          onChange={(e) => setSelectedId(e.target.value)}
          style={{ width: '100%' }}
          aria-label="Selected product"
        >
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
      </div>
        )}

      {tab === 'lookup' && (
        <div className="erp-split">
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
              aria-label="Product lookup barcode"
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
              aria-label="Product lookup search"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  runProductLookup();
                }
              }}
            />
            <button
              type="button"
              onClick={() => runProductLookup()}
              disabled={lookupBusy}
              aria-label="Run product lookup"
            >
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
                <th>Product</th>
                <th>SKU</th>
                <th>Barcode</th>
                <th>Stock</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {lookupHits.map((p) => (
                <tr key={p.id} style={{ background: p.id === selectedId ? '#eaf8d8' : undefined }}>
                  <td>{p.name}</td>
                  <td>{p.sku}</td>
                  <td>{p.barcode || '—'}</td>
                  <td>
                    <StockStatusBadge product={p} />
                  </td>
                  <td>{p.is_active === false ? 'inactive' : 'active'}</td>
                  <td>
                    <button type="button" onClick={() => selectLookupHit(p.id)} aria-label={`Select lookup product ${p.id}`}>
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
            <button type="button" onClick={downloadImportTemplate} aria-label="Download product CSV template">
              Download CSV template
            </button>
            <button type="button" onClick={downloadProductsExport} aria-label="Export products CSV">
              Export products CSV
            </button>
          </div>
          <label className="muted">CSV file</label>
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="Product CSV import file"
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
              aria-label="Validate product CSV import"
            >
              {importBusy ? 'Working…' : 'Validate'}
            </button>
            <button
              type="button"
              onClick={() => runProductImport(false)}
              disabled={!importFile || importBusy || !importReport?.can_commit}
              aria-label="Import valid product CSV rows"
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
                    <th>Product</th>
                    <th>SKU</th>
                    <th>Status</th>
                    <th>Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {importReport.rows.map((r) => (
                    <tr key={`${r.line}-${r.sku}`}>
                      <td>{r.line}</td>
                      <td>{r.name || '—'}</td>
                      <td>{r.sku || '—'}</td>
                      <td style={{ color: r.ok ? 'var(--brand, #4AB012)' : '#b91c1c' }}>{r.ok ? 'OK' : 'Error'}</td>
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
          {bootLoading && products.length === 0 ? <PageSkeleton label="Loading products…" cards={3} /> : null}
          <div className="card cat-panel">
            <div className="list-page-head">
              <div>
                <h2 style={{ margin: 0 }}>Product List</h2>
                <p className="muted" style={{ margin: '4px 0 0' }}>
                  Search, filter, and add products for this company.
                </p>
              </div>
              <div className="list-head-actions">
                <button
                  type="button"
                  className="list-btn-primary"
                  onClick={() => {
                    setFormFlash({});
                    setProductAddOpen(true);
                  }}
                  aria-label="Add Product"
                >
                  Add Product
                </button>
                <button type="button" onClick={() => selectTab('import')} aria-label="Import Product">
                  Import Product
                </button>
              </div>
            </div>
            {formFlash.ok && !productAddOpen ? (
              <p className="list-toast ok" role="status">
                {formFlash.ok}
              </p>
            ) : null}
            {formFlash.err && !productAddOpen ? (
              <p className="list-toast err" role="alert">
                {formFlash.err}
              </p>
            ) : null}
            {pharmacyOps && rxOnlyFilter ? (
              <p className="muted" role="status">
                Showing Rx-only products.{' '}
                <button
                  type="button"
                  onClick={() => {
                    setRxOnlyFilter(false);
                    router.replace('/inventory?tab=products', { scroll: false });
                  }}
                >
                  Show all products
                </button>
              </p>
            ) : null}
            <div className="list-toolbar">
              <input
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                placeholder="Search name, SKU, barcode"
                aria-label="Search products"
              />
              <select
                value={productCategoryFilter}
                onChange={(e) => setProductCategoryFilter(e.target.value)}
                aria-label="Filter by category"
              >
                <option value="">All categories</option>
                {categories
                  .filter((c) => c.is_active !== false)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {categoryLabel(c)}
                    </option>
                  ))}
              </select>
              <select
                value={productBrandFilter}
                onChange={(e) => setProductBrandFilter(e.target.value)}
                aria-label="Filter by brand"
              >
                <option value="">All brands</option>
                {brands
                  .filter((b) => b.is_active !== false)
                  .map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
              </select>
              <select
                value={productStockFilter}
                onChange={(e) => setProductStockFilter(e.target.value as 'all' | 'low' | 'oos' | 'ok')}
                aria-label="Filter by stock status"
              >
                <option value="all">All stock</option>
                <option value="low">Low stock</option>
                <option value="oos">Out of stock</option>
                <option value="ok">In stock</option>
              </select>
              <select
                value={productManageFilter}
                onChange={(e) => setProductManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
                aria-label="Product status filter"
              >
                <option value="all">All statuses</option>
                <option value="active">Active only</option>
                <option value="inactive">Inactive only</option>
              </select>
            </div>
            {productPaged.total === 0 ? (
              <div className="list-empty">
                <p style={{ margin: 0 }}>
                  {managedProducts.length === 0 ? 'No products yet.' : 'No products match these filters.'}
                </p>
                <p className="muted" style={{ margin: '8px 0 0' }}>
                  Add a product to sell it at POS and keep stock.
                </p>
                <button
                  type="button"
                  className="list-btn-primary"
                  style={{ marginTop: 12 }}
                  onClick={() => {
                    setFormFlash({});
                    setProductAddOpen(true);
                  }}
                >
                  Add Product
                </button>
              </div>
            ) : (
              <div className="list-table-wrap">
                <table className="table cat-table">
                  <thead>
                    <tr>
                      <th aria-sort={productSort === 'name' ? (productSortDir === 1 ? 'ascending' : 'descending') : 'none'}>
                        <button
                          type="button"
                          className="list-sort"
                          onClick={() => {
                            setProductSort('name');
                            setProductSortDir((d) => (productSort === 'name' ? ((d === 1 ? -1 : 1) as 1 | -1) : 1));
                          }}
                        >
                          Product{productSort === 'name' ? (productSortDir === 1 ? ' ↑' : ' ↓') : ''}
                        </button>
                      </th>
                      <th aria-sort={productSort === 'sku' ? (productSortDir === 1 ? 'ascending' : 'descending') : 'none'}>
                        <button
                          type="button"
                          className="list-sort"
                          onClick={() => {
                            setProductSort('sku');
                            setProductSortDir((d) => (productSort === 'sku' ? ((d === 1 ? -1 : 1) as 1 | -1) : 1));
                          }}
                        >
                          SKU{productSort === 'sku' ? (productSortDir === 1 ? ' ↑' : ' ↓') : ''}
                        </button>
                      </th>
                      <th aria-sort={productSort === 'category' ? (productSortDir === 1 ? 'ascending' : 'descending') : 'none'}>
                        <button
                          type="button"
                          className="list-sort"
                          onClick={() => {
                            setProductSort('category');
                            setProductSortDir((d) => (productSort === 'category' ? ((d === 1 ? -1 : 1) as 1 | -1) : 1));
                          }}
                        >
                          Category{productSort === 'category' ? (productSortDir === 1 ? ' ↑' : ' ↓') : ''}
                        </button>
                      </th>
                      <th aria-sort={productSort === 'brand' ? (productSortDir === 1 ? 'ascending' : 'descending') : 'none'}>
                        <button
                          type="button"
                          className="list-sort"
                          onClick={() => {
                            setProductSort('brand');
                            setProductSortDir((d) => (productSort === 'brand' ? ((d === 1 ? -1 : 1) as 1 | -1) : 1));
                          }}
                        >
                          Brand{productSort === 'brand' ? (productSortDir === 1 ? ' ↑' : ' ↓') : ''}
                        </button>
                      </th>
                      <th aria-sort={productSort === 'price' ? (productSortDir === 1 ? 'ascending' : 'descending') : 'none'}>
                        <button
                          type="button"
                          className="list-sort"
                          onClick={() => {
                            setProductSort('price');
                            setProductSortDir((d) => (productSort === 'price' ? ((d === 1 ? -1 : 1) as 1 | -1) : 1));
                          }}
                        >
                          Selling Price{productSort === 'price' ? (productSortDir === 1 ? ' ↑' : ' ↓') : ''}
                        </button>
                      </th>
                      <th aria-sort={productSort === 'qty' ? (productSortDir === 1 ? 'ascending' : 'descending') : 'none'}>
                        <button
                          type="button"
                          className="list-sort"
                          onClick={() => {
                            setProductSort('qty');
                            setProductSortDir((d) => (productSort === 'qty' ? ((d === 1 ? -1 : 1) as 1 | -1) : 1));
                          }}
                        >
                          Qty{productSort === 'qty' ? (productSortDir === 1 ? ' ↑' : ' ↓') : ''}
                        </button>
                      </th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {productPaged.rows.map((p) => {
                      const st = stockStatusOf(p);
                      const img = p.image_url || p.thumbnail_url || p.photo_url;
                      return (
                        <tr key={p.id}>
                          <td data-label="Product">
                            <div className="list-prod">
                              {img ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={img} alt="" />
                              ) : (
                                <span className="list-prod-ph" aria-hidden>
                                  {String(p.name || '?').slice(0, 1).toUpperCase()}
                                </span>
                              )}
                              <span className="list-prod-name">
                                {displayProductName(p.name)}
                                {p.is_active === false ? ' [inactive]' : ''}
                                {pharmacyOps && p.rx_only ? ' [Rx]' : ''}
                              </span>
                            </div>
                          </td>
                          <td data-label="SKU" className="list-secondary">{p.sku || '—'}</td>
                          <td data-label="Category" className="list-secondary">{p.category || '—'}</td>
                          <td data-label="Brand" className="list-secondary">{p.brand || '—'}</td>
                          <td data-label="Selling Price">{p.selling_price ?? 0}</td>
                          <td data-label="Qty" className={st === 'out' || st === 'red' ? 'list-qty-low' : undefined}>
                            <StockStatusBadge product={p} />
                          </td>
                          <td className="cat-actions">
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedId(p.id);
                                setDrawerOpen(true);
                                setProductEditMode(false);
                                setFormFlash({});
                              }}
                              aria-label={`Open product ${p.name}`}
                            >
                              View
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setSelectedId(p.id);
                                setDrawerOpen(true);
                                setProductEditMode(true);
                                setFormFlash({});
                              }}
                              aria-label={`Edit product ${p.name}`}
                            >
                              Edit
                            </button>
                            <div className="cat-menu">
                              <button
                                type="button"
                                aria-label={`More actions for ${p.name}`}
                                onClick={() => setProductMenuId(productMenuId === p.id ? '' : p.id)}
                              >
                                ···
                              </button>
                              {productMenuId === p.id ? (
                                <div className="cat-menu-pop">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSelectedId(p.id);
                                      generateBarcode(p.id);
                                      setProductMenuId('');
                                    }}
                                    aria-label={`Generate barcode for ${p.name}`}
                                  >
                                    Generate barcode
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSelectedId(p.id);
                                      generateQr(p.id);
                                      setProductMenuId('');
                                    }}
                                    aria-label={`Generate QR for ${p.name}`}
                                  >
                                    Generate QR
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setSelectedId(p.id);
                                      printBarcodeLabel(p.id);
                                      setProductMenuId('');
                                    }}
                                    aria-label={`Print barcode label for ${p.name}`}
                                  >
                                    Print label
                                  </button>
                                </div>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            {productPaged.total > 0 ? (
              <div className="list-pager">
                <span className="muted">
                  {productPaged.total} entries · page {productPaged.page} of {productPaged.pages}
                </span>
                <div className="list-pager-nav">
                  <button
                    type="button"
                    disabled={productPaged.page <= 1}
                    onClick={() => setProductPage(productPaged.page - 1)}
                    aria-label="Previous product page"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    disabled={productPaged.page >= productPaged.pages}
                    onClick={() => setProductPage(productPaged.page + 1)}
                    aria-label="Next product page"
                  >
                    Next
                  </button>
                </div>
              </div>
            ) : null}
          </div>
          {productAddOpen ? (
            <FormModal
              title="Add product"
              busy={saveBusy}
              dirty={productAddDirty}
              headerClose={false}
              closeLabel="Cancel"
              closeAriaLabel="Cancel add product"
              onClose={() => {
                setProductAddOpen(false);
                setFormFlash({});
              }}
              footer={
                <>
                  <button
                    type="button"
                    className="list-btn-primary"
                    onClick={createProduct}
                    disabled={!productName.trim() || saveBusy}
                    aria-label="Create product"
                  >
                    {saveBusy ? 'Saving…' : 'Save'}
                  </button>
                  {formFlash.ok ? <p className="form-flash ok" role="status">{formFlash.ok}</p> : null}
                  {formFlash.err ? <p className="form-flash err" role="alert">{formFlash.err}</p> : null}
                </>
              }
            >
            <div className="erp-form-grid">
            <h3 className="muted span-2" style={{ margin: 0, fontWeight: 600 }}>New catalog item</h3>
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
              aria-label="Product SKU"
              title="Optional SKU (1–100 chars: letters, digits, . _ -; blank → auto)"
            />
            <input
              value={productBarcode}
              onChange={(e) => setProductBarcode(e.target.value)}
              placeholder="Barcode (optional)"
              aria-label="Product barcode"
              title="Optional barcode (4–48 chars: letters, numbers, - . _)"
            />
            <p className="muted span-2" style={{ margin: 0 }}>
              Leave blank to generate after save (Actions, product form, or Labels). Existing unique barcodes are not overwritten.
            </p>
            <textarea
              value={productDescription}
              onChange={(e) => setProductDescription(e.target.value)}
              placeholder="Description (optional)"
              aria-label="Product description"
              title="Optional description (1–500 chars; letters/digits required)"
              rows={2}
            />
            {pharmacyOps ? (
              <>
                <textarea
                  value={productDosage}
                  onChange={(e) => setProductDosage(e.target.value)}
                  placeholder="Dosage instructions (optional)"
                  aria-label="Product dosage instructions"
                  title="Optional dosage instructions (1–500 chars)"
                  rows={2}
                />
                <label className="muted span-2">
                  <input
                    type="checkbox"
                    checked={productRxOnly}
                    onChange={(e) => setProductRxOnly(e.target.checked)}
                    aria-label="Rx-only product"
                  />{' '}
                  Rx-only (prescription required)
                </label>
              </>
            ) : null}
          <div className="product-price-field">
                      <label className="product-price-label" htmlFor="add-product-actual-price">Actual price</label>
                      <input
                        id="add-product-actual-price"
                        type="number"
                        min="0"
                        step="0.01"
                        inputMode="decimal"
                        placeholder="0.00"
                        value={productCost}
                        onChange={e => setProductCost(e.target.value)}
                        aria-label="Product cost price"
                      />
                    </div>
          <div className="product-price-field product-price-field--selling">
                      <label className="product-price-label" htmlFor="add-product-selling-price">Selling price</label>
                      <input
                        id="add-product-selling-price"
                        type="number"
                        min="0"
                        step="0.01"
                        inputMode="decimal"
                        placeholder="0.00"
                        value={productPrice}
                        onChange={e => setProductPrice(e.target.value)}
                        aria-label="Product selling price"
                      />
                    </div>
            <div className="span-2" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input
                value={productWeight}
                onChange={(e) => setProductWeight(e.target.value)}
                placeholder="Weight kg"
                aria-label="Product weight"
                style={{ width: 100 }}
              />
              <input
                value={productLength}
                onChange={(e) => setProductLength(e.target.value)}
                placeholder="L cm"
                aria-label="Product length"
                style={{ width: 80 }}
              />
              <input
                value={productWidth}
                onChange={(e) => setProductWidth(e.target.value)}
                placeholder="W cm"
                aria-label="Product width"
                style={{ width: 80 }}
              />
              <input
                value={productHeight}
                onChange={(e) => setProductHeight(e.target.value)}
                placeholder="H cm"
                aria-label="Product height"
                style={{ width: 80 }}
              />
            </div>
            <select
              value={productCategoryId}
              onChange={(e) => setProductCategoryId(e.target.value)}
              aria-label="Product category"
              title="Product category (catalog picker; API category label 1–100)"
            >
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
            <select
              value={productBrandId}
              onChange={(e) => setProductBrandId(e.target.value)}
              aria-label="Product brand"
              title="Product brand (optional catalog picker)"
            >
              <option value="">Brand</option>
              {brands
                .filter((b) => b.is_active !== false)
                .map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
            <select
              value={productUnitId}
              onChange={(e) => setProductUnitId(e.target.value)}
              aria-label="Product unit"
              title="Product unit (optional catalog picker)"
            >
              <option value="">Unit</option>
              {units
                .filter((u) => u.is_active !== false)
                .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.code} — {u.name}
                </option>
              ))}
            </select>
            <select
              value={productVariantId}
              onChange={(e) => setProductVariantId(e.target.value)}
              aria-label="Product variant"
              title="Existing active variants for this company"
            >
              <option value="">Variant (optional)</option>
              {selectorVariants.map((v) => (
                <option key={v.id} value={v.id}>
                  {variantOptionLabel(v, products)}
                </option>
              ))}
            </select>
            <select
              value={productSupplyClass}
              onChange={(e) => setProductSupplyClass(e.target.value)}
              aria-label="Product supply class"
            >
              <option value="standard">Tax: standard-rated</option>
              <option value="zero_rated">Tax: zero-rated</option>
              <option value="exempt">Tax: exempt</option>
            </select>
            <select
              value={productTaxRateId}
              onChange={(e) => setProductTaxRateId(e.target.value)}
              aria-label="Product tax rate"
              title="Product tax rate (optional — category/tenant default when blank)"
            >
              <option value="">Tax rate (optional — category/tenant default)</option>
              {taxRates
                .filter((r) => r.is_active !== false)
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.rate}%){r.is_default ? ' · default' : ''}
                  </option>
                ))}
            </select>
            <p className="muted span-2">
              {hideWarehouseUx
                ? 'Expiry is stored on a lot, not the product header. Enter quantity and expiry together — or save the product and set them from the product panel / Expiry tab.'
                : 'Expiry is stored on a warehouse lot, not the product header. Enter quantity, location, and expiry together — or save the product and set them from the product panel / Expiry tab.'}
            </p>
            <div className="field">
            <label className="muted">Expiry date</label>
            <input
              type="date"
              value={createOpeningExpiry}
              onChange={(e) => setCreateOpeningExpiry(e.target.value)}
              aria-label="Create product expiry date"
            />
            </div>
            <input
              value={createOpeningBatch}
              onChange={(e) => setCreateOpeningBatch(e.target.value)}
              placeholder="Batch number (optional — assigned if expiry is set)"
              aria-label="Create product batch number"
            />
            <div className="field">
            <label className="muted">Manufacturing date (optional)</label>
            <input
              type="date"
              value={createOpeningMfg}
              onChange={(e) => setCreateOpeningMfg(e.target.value)}
              aria-label="Create product manufacturing date"
            />
            </div>
            <div className="field">
            <label className="muted">Quantity</label>
            <input
              value={createOpeningQty}
              onChange={(e) => setCreateOpeningQty(e.target.value)}
              placeholder="Quantity"
              aria-label="Create product opening quantity"
            />
            </div>
            {!hideWarehouseUx ? (
            <select
              value={createOpeningWh}
              onChange={(e) => setCreateOpeningWh(e.target.value)}
              aria-label="Create product opening warehouse"
            >
              <option value="">Warehouse (required with quantity or expiry)</option>
              {storeWarehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name || w.code}
                  </option>
                ))}
            </select>
            ) : null}
            <input
              value={createOpeningCost}
              onChange={(e) => setCreateOpeningCost(e.target.value)}
              placeholder="Unit cost (optional)"
              aria-label="Create product opening unit cost"
            />
            </div>
            </FormModal>
          ) : null}
          {drawerOpen && selected && tab === 'products' && (
            <>
              <div className="inv-drawer-back" onClick={() => setDrawerOpen(false)} aria-hidden />
              <aside className="inv-drawer drawer product-detail" aria-label="Product details">
                <div className="inv-drawer-head">
                  <h3>{selected.name}</h3>
                  <button type="button" onClick={() => setDrawerOpen(false)} aria-label="Close product details">
                    Close
                  </button>
                </div>
                <div className="inv-drawer-body">
                <div className="drawer-meta product-detail-meta">
                <p className="muted">SKU {selected.sku}</p>
                <p className="muted">Barcode {selected.barcode || '—'}</p>
                <p className="muted">Category {selected.category || '—'}</p>
                <p className="muted">On-hand {selected.stock_qty ?? 0}</p>
                {pharmacyOps ? (
                  <>
                    <p className="muted">Rx-only {selected.rx_only ? 'Yes' : 'No'}</p>
                    <p className="muted">Dosage {selected.dosage_instructions || '—'}</p>
                  </>
                ) : null}
                </div>
                <h4>Warehouse lots / expiry</h4>
                <p className="muted">
                  Expiry is not a product field. Record quantity at a location with an expiry date.
                </p>
                {batches.length === 0 ? (
                  <p className="muted">No lots yet for this product.</p>
                ) : (
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {batches.map((b) => {
                      const wh = warehouses.find((w) => w.id === b.warehouse_id);
                      return (
                        <li key={b.id}>
                          {b.batch_number} · qty {b.quantity}
                          {b.expiry_date ? ` · expires ${String(b.expiry_date).slice(0, 10)}` : ' · no expiry'}
                          {wh ? ` · ${wh.name || wh.code}` : ''}
                        </li>
                      );
                    })}
                  </ul>
                )}
                <div className="erp-form-grid form-grid">
                {!hideWarehouseUx ? (
                <div className="field">
                <label className="muted">Location</label>
                <select
                  value={lotWh}
                  onChange={(e) => setLotWh(e.target.value)}
                  aria-label="Product lot warehouse"
                >
                  <option value="">Select warehouse</option>
                  {storeWarehouses
                    .filter((w) => w.is_active !== false)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name || w.code}
                      </option>
                    ))}
                </select>
                </div>
                ) : null}
                <div className="field">
                <label className="muted">Quantity</label>
                <input
                  value={lotQty}
                  onChange={(e) => setLotQty(e.target.value)}
                  placeholder="Quantity"
                  aria-label="Product lot quantity"
                />
                </div>
                <div className="field">
                <label className="muted">Expiry date</label>
                <input
                  type="date"
                  value={lotExpiry}
                  onChange={(e) => setLotExpiry(e.target.value)}
                  aria-label="Product lot expiry date"
                />
                </div>
                <input
                  value={lotBatch}
                  onChange={(e) => setLotBatch(e.target.value)}
                  placeholder="Batch number (optional)"
                  aria-label="Product lot batch number"
                />
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <select
                    value={barcodeSymbology}
                    onChange={(e) => setBarcodeSymbology(e.target.value)}
                    aria-label="Barcode symbology"
                    title="Barcode symbology"
                  >
                    <option value="code128">Code 128</option>
                    <option value="ean13">EAN-13</option>
                    <option value="upca">UPC-A</option>
                  </select>
                  <button type="button" onClick={() => generateBarcode(selected.id)} aria-label="Generate product barcode">
                    Generate barcode
                  </button>
                  <button type="button" onClick={() => generateQr(selected.id)} aria-label="Generate QR">
                    Generate QR
                  </button>
                  <button type="button" onClick={() => printBarcodeLabel(selected.id)} aria-label="Print product barcode label">
                    Print label
                  </button>
                </div>
                {productEditMode ? (
                  <div className="erp-form-grid form-grid">
                    <div className="field span-2">
                    <label className="muted">Barcode</label>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <input value={editBarcode} onChange={(e) => setEditBarcode(e.target.value)} aria-label="Edit product barcode" />
                      <button type="button" onClick={() => generateBarcode(selected.id)} aria-label="Generate barcode on product form">
                        Generate barcode
                      </button>
                      <button type="button" onClick={() => generateQr(selected.id)} aria-label="Generate QR on product form">
                        Generate QR
                      </button>
                    </div>
                    </div>
                    <div className="field span-2">
                    <label className="muted">Description</label>
                    <textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} rows={2} aria-label="Edit product description" />
                    </div>
                    {pharmacyOps ? (
                      <>
                        <div className="field span-2">
                        <label className="muted">Dosage instructions</label>
                        <textarea
                          value={editDosage}
                          onChange={(e) => setEditDosage(e.target.value)}
                          rows={2}
                          aria-label="Edit product dosage instructions"
                        />
                        </div>
                        <label className="muted span-2">
                          <input
                            type="checkbox"
                            checked={editRxOnly}
                            onChange={(e) => setEditRxOnly(e.target.checked)}
                            aria-label="Edit Rx-only product"
                          />{' '}
                          Rx-only (prescription required)
                        </label>
                      </>
                    ) : null}
                    <div className="field">
                    <label className="muted">Reorder</label>
                    <input value={editReorder} onChange={(e) => setEditReorder(e.target.value)} aria-label="Edit product reorder level" />
                    </div>
                    <div className="field">
                    <label className="muted">Actual price</label>
                    <input value={editCost} onChange={(e) => setEditCost(e.target.value)} aria-label="Edit product cost price" />
                    </div>
                    <div className="field">
                    <label className="muted">Selling price</label>
                    <input value={editPrice} onChange={(e) => setEditPrice(e.target.value)} aria-label="Edit product selling price" />
                    </div>
                    <div className="field">
                    <label className="muted">Variant</label>
                    <select
                      value={productVariantId}
                      onChange={(e) => setProductVariantId(e.target.value)}
                      aria-label="Product variant"
                      title="Existing active variants for this company"
                    >
                      <option value="">Variant (optional)</option>
                      {selectorVariants.map((v) => (
                        <option key={v.id} value={v.id}>
                          {variantOptionLabel(v, products)}
                        </option>
                      ))}
                    </select>
                    </div>
                  </div>
                ) : null}
                </div>
                <div className="inv-drawer-foot">
                  {!productEditMode ? (
                    <button type="button" onClick={() => setProductEditMode(true)} aria-label="Edit product">
                      Edit
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => saveProductEdits()}
                      disabled={saveBusy}
                      aria-label="Save product"
                    >
                      {saveBusy ? 'Saving…' : 'Save'}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={recordExpiryLot}
                    disabled={saveBusy}
                    aria-label="Save product expiry lot"
                  >
                    {saveBusy ? 'Saving…' : 'Save expiry lot'}
                  </button>
                  {formFlash.ok ? <p className="form-flash ok" role="status">{formFlash.ok}</p> : null}
                  {formFlash.err ? <p className="form-flash err" role="alert">{formFlash.err}</p> : null}
                </div>
              </aside>
            </>
          )}
        </>
      )}

      {tab === 'labels' && (
        <div className="card cat-panel">
          <div className="list-page-head">
            <div>
              <h2 style={{ margin: 0 }}>Barcode / QR labels</h2>
              <p className="muted" style={{ margin: '4px 0 0' }}>
                Generate a unique barcode or QR for selected products (name + SKU/barcode only), then print via the existing label sheet.
              </p>
            </div>
          </div>
          <div className="list-toolbar">
            <input
              value={productSearch}
              onChange={(e) => setProductSearch(e.target.value)}
              placeholder="Search name, SKU, barcode"
              aria-label="Search products for labels"
            />
            <select
              value={barcodeSymbology}
              onChange={(e) => setBarcodeSymbology(e.target.value)}
              aria-label="Barcode symbology"
              title="Barcode symbology for generate / print"
            >
              <option value="code128">Code 128</option>
              <option value="ean13">EAN-13</option>
              <option value="upca">UPC-A</option>
            </select>
            <input
              value={labelCopies}
              onChange={(e) => setLabelCopies(e.target.value)}
              placeholder="Copies"
              aria-label="Label copies"
              title="Copies (1–40)"
              style={{ width: 88 }}
            />
            <button type="button" onClick={generateBarcodesForSelected} aria-label="Generate barcode for selected products">
              Generate barcode
            </button>
            <button type="button" onClick={generateQrForSelected} aria-label="Generate QR for selected products">
              Generate QR
            </button>
            <button
              type="button"
              onClick={() => printBarcodeLabelsForIds(selectedLabelIds())}
              aria-label="Print product barcode label"
            >
              Print labels
            </button>
          </div>
          <div className="list-table-wrap">
            <table className="table cat-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      aria-label="Select all products for labels"
                      checked={managedProducts.length > 0 && managedProducts.every((p) => labelPick[p.id])}
                      onChange={(e) => {
                        const on = e.target.checked;
                        const next: Record<string, boolean> = { ...labelPick };
                        managedProducts.forEach((p) => {
                          next[p.id] = on;
                        });
                        setLabelPick(next);
                      }}
                    />
                  </th>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Barcode</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {managedProducts.filter((p) => {
                  const q = productSearch.trim().toLowerCase();
                  if (!q) return true;
                  return `${p.name || ''} ${p.sku || ''} ${p.barcode || ''}`.toLowerCase().includes(q);
                }).map((p) => (
                  <tr key={p.id}>
                    <td>
                      <input
                        type="checkbox"
                        checked={Boolean(labelPick[p.id])}
                        onChange={(e) => setLabelPick((prev) => ({ ...prev, [p.id]: e.target.checked }))}
                        aria-label={`Select ${p.name} for labels`}
                      />
                    </td>
                    <td data-label="Product">{displayProductName(p.name)}</td>
                    <td data-label="SKU" className="list-secondary">{p.sku || '—'}</td>
                    <td data-label="Barcode" className="list-secondary">{p.barcode || '—'}</td>
                    <td className="cat-actions">
                      <button type="button" onClick={() => generateBarcode(p.id)} aria-label={`Generate barcode for ${p.name}`}>
                        Generate barcode
                      </button>
                      <button type="button" onClick={() => generateQr(p.id)} aria-label={`Generate QR for ${p.name}`}>
                        Generate QR
                      </button>
                      <button type="button" onClick={() => printBarcodeLabel(p.id)} aria-label={`Print barcode label for ${p.name}`}>
                        Print label
                      </button>
                    </td>
                  </tr>
                ))}
                {managedProducts.filter((p) => {
                  const q = productSearch.trim().toLowerCase();
                  if (!q) return true;
                  return `${p.name || ''} ${p.sku || ''} ${p.barcode || ''}`.toLowerCase().includes(q);
                }).length === 0 ? (
                  <tr>
                    <td colSpan={5} className="muted">No products match.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'categories' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Categories</h2>
            <button type="button" onClick={openCategoryCreate} aria-label="Add category">
              Add category
            </button>
          </div>
          <div className="cat-toolbar">
            <input
              value={catSearch}
              onChange={(e) => setCatSearch(e.target.value)}
              placeholder="Search categories"
              aria-label="Search categories"
            />
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
          </div>
          {visibleCategories.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No categories yet.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Add a main category, then nest others under it.
              </p>
              <button type="button" style={{ marginTop: 12 }} onClick={openCategoryCreate}>
                Add category
              </button>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Parent</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visibleCategories.map((c) => {
                    const depth = Math.max(0, Number(c.depth) || 0);
                    const hasKids = categories.some((x) => x.parent_id === c.id);
                    const collapsed = Boolean(catCollapsed[c.id]);
                    return (
                      <tr key={c.id}>
                        <td data-label="Name">
                          <div
                            className="cat-name-cell"
                            style={{ paddingLeft: Math.min(depth, 6) * 14 }}
                          >
                            {hasKids ? (
                              <button
                                type="button"
                                className="cat-twist"
                                aria-label={collapsed ? `Expand ${c.name}` : `Collapse ${c.name}`}
                                onClick={() =>
                                  setCatCollapsed((prev) => ({ ...prev, [c.id]: !collapsed }))
                                }
                              >
                                {collapsed ? '+' : '−'}
                              </button>
                            ) : (
                              <span className="cat-twist-spacer" />
                            )}
                            <strong>{c.name}</strong>
                          </div>
                        </td>
                        <td data-label="Parent">{categoryParentName(categories, c.parent_id)}</td>
                        <td data-label="Status">{c.is_active === false ? 'Inactive' : 'Active'}</td>
                        <td className="cat-actions">
                          <button type="button" onClick={() => openCategoryEdit(c)} aria-label={`Edit ${c.name}`}>
                            Edit
                          </button>
                          <div className="cat-menu">
                            <button
                              type="button"
                              aria-label={`More actions for ${c.name}`}
                              onClick={() => setCatMenuId(catMenuId === c.id ? '' : c.id)}
                            >
                              ⋯
                            </button>
                            {catMenuId === c.id ? (
                              <div className="cat-menu-pop">
                                {c.is_active === false ? (
                                  <button type="button" className="btn-ok" onClick={() => setCategoryActive(c, true)}>
                                    Activate
                                  </button>
                                ) : (
                                  <button type="button" className="btn-danger" onClick={() => setCategoryActive(c, false)}>
                                    Deactivate
                                  </button>
                                )}
                              </div>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {catDrawerOpen ? (
            <FormModal
              title={catEditId ? 'Edit category' : 'Add category'}
              busy={saveBusy}
              dirty={Boolean(catName.trim())}
              onClose={() => setCatDrawerOpen(false)}
            >
                <label className="muted" htmlFor="cat-name-field">
                  Name
                </label>
                <input
                  id="cat-name-field"
                  value={catName}
                  onChange={(e) => setCatName(e.target.value)}
                  placeholder="Name"
                  aria-label="Category name"
                  title="Category name (1–120 chars; letters/digits required)"
                />
                <label className="muted" htmlFor="cat-parent-field">
                  Parent
                </label>
                {catEditId ? (
                  <select
                    id="cat-parent-field"
                    value={catParentId}
                    onChange={(e) => setCatParentId(e.target.value)}
                    aria-label="Edit category parent"
                    title="Main category when blank"
                  >
                    <option value="">Main category</option>
                    {categories
                      .filter((c) => c.is_active !== false)
                      .filter((c) => c.id !== catEditId && !categoryDescendantIds(categories, catEditId).has(c.id))
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {categoryIndent(c.depth)}
                          {c.name}
                        </option>
                      ))}
                  </select>
                ) : (
                  <select
                    id="cat-parent-field"
                    value={catParentId}
                    onChange={(e) => setCatParentId(e.target.value)}
                    aria-label="Category parent"
                    title="Main category when blank"
                  >
                    <option value="">Main category</option>
                    {categories
                      .filter((c) => c.is_active !== false)
                      .map((c) => (
                        <option key={c.id} value={c.id}>
                          {categoryIndent(c.depth)}
                          {c.name}
                        </option>
                      ))}
                  </select>
                )}
                <p className="muted" style={{ margin: 0 }}>
                  Uses your company default tax unless you set a different rate.
                </p>
                <button
                  type="button"
                  className="cat-advanced"
                  onClick={() => setCatTaxAdvanced((v) => !v)}
                  aria-expanded={catTaxAdvanced}
                >
                  {catTaxAdvanced ? 'Hide tax rate' : 'Advanced: tax rate'}
                </button>
                {catTaxAdvanced ? (
                  catEditId ? (
                  <select
                    value={catTaxRateId}
                    onChange={(e) => setCatTaxRateId(e.target.value)}
                    aria-label="Edit category tax rate"
                    title="Optional tax rate for this category"
                  >
                    <option value="">Company default</option>
                    {taxRates
                      .filter((r) => r.is_active !== false)
                      .map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} ({r.rate}%){r.is_default ? ' · default' : ''}
                        </option>
                      ))}
                  </select>
                  ) : (
                  <select
                    value={catTaxRateId}
                    onChange={(e) => setCatTaxRateId(e.target.value)}
                    aria-label="Category tax rate"
                    title="Optional tax rate for this category"
                  >
                    <option value="">Company default</option>
                    {taxRates
                      .filter((r) => r.is_active !== false)
                      .map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} ({r.rate}%){r.is_default ? ' · default' : ''}
                        </option>
                      ))}
                  </select>
                  )
                ) : null}
                <div className="cat-save-row">
                  <button
                    type="button"
                    onClick={saveCategory}
                    disabled={!catName.trim() || saveBusy}
                    aria-label={catEditId ? 'Save category' : 'Add category'}
                  >
                    {saveBusy ? 'Saving…' : catEditId ? 'Save' : 'Add category'}
                  </button>
                  {formFlash.ok ? <p className="form-flash ok">{formFlash.ok}</p> : null}
                  {formFlash.err ? <p className="form-flash err">{formFlash.err}</p> : null}
                </div>
            </FormModal>
          ) : null}
        </div>
      )}

      {tab === 'brands' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Brands</h2>
            <button type="button" onClick={openBrandCreate} aria-label="Add brand">
              Add brand
            </button>
          </div>
          <div className="cat-toolbar">
            <input
              value={brandSearch}
              onChange={(e) => setBrandSearch(e.target.value)}
              placeholder="Search brands"
              aria-label="Search brands"
            />
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
          </div>
          {visibleBrands.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No brands yet.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Add a brand, then assign it on products.
              </p>
              <button type="button" style={{ marginTop: 12 }} onClick={openBrandCreate}>
                Add brand
              </button>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visibleBrands.map((b) => (
                    <tr key={b.id}>
                      <td data-label="Name">
                        <div className="cat-name-cell">
                          {brandLogoPreview[b.id] ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={brandLogoPreview[b.id]}
                              alt=""
                              width={24}
                              height={24}
                              style={{ objectFit: 'contain' }}
                            />
                          ) : null}
                          <strong>{b.name}</strong>
                        </div>
                      </td>
                      <td data-label="Status">{b.is_active === false ? 'Inactive' : 'Active'}</td>
                      <td className="cat-actions">
                        <button type="button" onClick={() => openBrandEdit(b)} aria-label={`Edit ${b.name}`}>
                          Edit
                        </button>
                        <div className="cat-menu">
                          <button
                            type="button"
                            aria-label={`More actions for ${b.name}`}
                            onClick={() => setBrandMenuId(brandMenuId === b.id ? '' : b.id)}
                          >
                            ···
                          </button>
                          {brandMenuId === b.id ? (
                            <div className="cat-menu-pop">
                              {b.is_active === false ? (
                                <button type="button" className="btn-ok" onClick={() => setBrandActive(b, true)}>
                                  Activate
                                </button>
                              ) : (
                                <button type="button" className="btn-danger" onClick={() => setBrandActive(b, false)}>
                                  Deactivate
                                </button>
                              )}
                            </div>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {brandDrawerOpen ? (
            <FormModal
              title={brandEditId ? 'Edit brand' : 'Add brand'}
              busy={saveBusy}
              dirty={Boolean(brandName.trim() || brandDescription.trim())}
              onClose={() => setBrandDrawerOpen(false)}
            >
                <label className="muted" htmlFor="brand-name-field">
                  Name
                </label>
                <input
                  id="brand-name-field"
                  value={brandName}
                  onChange={(e) => setBrandName(e.target.value)}
                  placeholder="Name"
                  aria-label="Brand name"
                  title="Brand name (1–120 chars; letters/digits required)"
                />
                <button
                  type="button"
                  className="cat-advanced"
                  onClick={() => setBrandAdvanced((v) => !v)}
                  aria-expanded={brandAdvanced}
                >
                  {brandAdvanced ? 'Hide details' : 'Advanced: description and logo'}
                </button>
                {brandAdvanced ? (
                  <>
                    <label className="muted" htmlFor="brand-desc-field">
                      Description
                    </label>
                    <textarea
                      id="brand-desc-field"
                      value={brandDescription}
                      onChange={(e) => setBrandDescription(e.target.value)}
                      placeholder="Description (optional)"
                      aria-label="Brand description"
                      title="Optional description (1–500 chars; letters/digits required)"
                      rows={2}
                    />
                    {brandEditId ? (
                      <label className="muted" style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                        Logo
                        <input
                          type="file"
                          accept="image/png,image/jpeg,image/webp,image/gif"
                          aria-label={`Brand logo file ${brandEditId}`}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) uploadBrandLogo(brandEditId, file);
                            e.target.value = '';
                          }}
                        />
                      </label>
                    ) : null}
                    {brandEditId && brands.find((x) => x.id === brandEditId)?.has_logo ? (
                      <button type="button" onClick={() => removeBrandLogo(brandEditId)} aria-label={`Remove brand logo ${brandEditId}`}>
                        Remove logo
                      </button>
                    ) : null}
                  </>
                ) : null}
                <div className="cat-save-row">
                  <button
                    type="button"
                    onClick={saveBrand}
                    disabled={!brandName.trim() || saveBusy}
                    aria-label={brandEditId ? 'Save brand' : 'Add brand'}
                  >
                    {saveBusy ? 'Saving…' : brandEditId ? 'Save' : 'Add brand'}
                  </button>
                  {formFlash.ok ? <p className="form-flash ok">{formFlash.ok}</p> : null}
                  {formFlash.err ? <p className="form-flash err">{formFlash.err}</p> : null}
                </div>
            </FormModal>
          ) : null}
          {/* inv-drawer: brand create/edit uses FormModal */}
        </div>
      )}

      {tab === 'units' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Units</h2>
            <button type="button" onClick={openUnitCreate} aria-label="Add unit">
              Add unit
            </button>
          </div>
          <div className="cat-toolbar">
            <input
              value={unitSearch}
              onChange={(e) => setUnitSearch(e.target.value)}
              placeholder="Search units"
              aria-label="Search units"
            />
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
          </div>
          {visibleUnits.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No units yet.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Add a main unit, then nest conversions under it.
              </p>
              <button type="button" style={{ marginTop: 12 }} onClick={openUnitCreate}>
                Add unit
              </button>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Parent</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visibleUnits.map((u) => {
                    const depth = unitDepthOf(units, u);
                    const hasKids = units.some((x) => x.base_unit_id === u.id);
                    const collapsed = Boolean(unitCollapsed[u.id]);
                    return (
                      <tr key={u.id}>
                        <td data-label="Name">
                          <div
                            className="cat-name-cell"
                            style={{ paddingLeft: Math.min(depth, 6) * 14 }}
                          >
                            {hasKids ? (
                              <button
                                type="button"
                                className="cat-twist"
                                aria-label={collapsed ? `Expand ${u.name}` : `Collapse ${u.name}`}
                                onClick={() =>
                                  setUnitCollapsed((prev) => ({ ...prev, [u.id]: !collapsed }))
                                }
                              >
                                {collapsed ? '+' : '–'}
                              </button>
                            ) : (
                              <span className="cat-twist-spacer" />
                            )}
                            <strong>{u.name}</strong>
                          </div>
                        </td>
                        <td data-label="Parent">{unitParentName(units, u.base_unit_id)}</td>
                        <td data-label="Status">{u.is_active === false ? 'Inactive' : 'Active'}</td>
                        <td className="cat-actions">
                          <button type="button" onClick={() => openUnitEdit(u)} aria-label={`Edit ${u.name}`}>
                            Edit
                          </button>
                          <div className="cat-menu">
                            <button
                              type="button"
                              aria-label={`More actions for ${u.name}`}
                              onClick={() => setUnitMenuId(unitMenuId === u.id ? '' : u.id)}
                            >
                              ···
                            </button>
                            {unitMenuId === u.id ? (
                              <div className="cat-menu-pop">
                                {u.is_active === false ? (
                                  <button type="button" className="btn-ok" onClick={() => setUnitActive(u, true)}>
                                    Activate
                                  </button>
                                ) : (
                                  <button type="button" className="btn-danger" onClick={() => setUnitActive(u, false)}>
                                    Deactivate
                                  </button>
                                )}
                              </div>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {unitDrawerOpen ? (
            <FormModal
              title={unitEditId ? 'Edit unit' : 'Add unit'}
              busy={saveBusy}
              dirty={Boolean(unitName.trim())}
              onClose={() => setUnitDrawerOpen(false)}
            >
                <label className="muted" htmlFor="unit-name-field">
                  Name
                </label>
                <input
                  id="unit-name-field"
                  value={unitName}
                  onChange={(e) => setUnitName(e.target.value)}
                  placeholder="Name"
                  aria-label="Unit name"
                  title="Unit name (1–80 chars; letters/digits required)"
                />
                <label className="muted" htmlFor="unit-parent-field">
                  Parent
                </label>
                <select
                  id="unit-parent-field"
                  value={unitBaseId}
                  onChange={(e) => setUnitBaseId(e.target.value)}
                  aria-label="Unit base unit"
                  title="Main unit when blank"
                >
                  <option value="">Main unit</option>
                  {units
                    .filter((u) => u.is_active !== false && !u.base_unit_id)
                    .filter((u) => u.id !== unitEditId)
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.name}
                      </option>
                    ))}
                </select>
                <button
                  type="button"
                  className="cat-advanced"
                  onClick={() => setUnitAdvanced((v) => !v)}
                  aria-expanded={unitAdvanced}
                >
                  {unitAdvanced ? 'Hide conversion' : 'Advanced: conversion ratio'}
                </button>
                {unitAdvanced ? (
                  <input
                    value={unitRatio}
                    onChange={(e) => setUnitRatio(e.target.value)}
                    placeholder="Conversion ratio"
                    aria-label="Unit conversion ratio"
                    disabled={!unitBaseId}
                  />
                ) : null}
                <div className="cat-save-row">
                  <button
                    type="button"
                    onClick={saveUnit}
                    disabled={!unitName.trim() || saveBusy}
                    aria-label={unitEditId ? 'Save unit' : 'Add unit'}
                  >
                    {saveBusy ? 'Saving…' : unitEditId ? 'Save' : 'Add unit'}
                  </button>
                  {formFlash.ok ? <p className="form-flash ok">{formFlash.ok}</p> : null}
                  {formFlash.err ? <p className="form-flash err">{formFlash.err}</p> : null}
                </div>
            </FormModal>
          ) : null}
          {/* inv-drawer: unit create/edit uses FormModal */}
        </div>
      )}

      {tab === 'variants' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Variants</h2>
            <button type="button" onClick={openVariantCreate} aria-label="Add variant">
              Add variant
            </button>
          </div>
          <div className="cat-toolbar">
            <select
              value={variantParentFilter}
              onChange={(e) => setVariantParentFilter(e.target.value)}
              aria-label="Parent product for variant"
            >
              <option value="">All products</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <input
              value={variantSearch}
              onChange={(e) => setVariantSearch(e.target.value)}
              placeholder="Search variants"
              aria-label="Search variants"
            />
            <select
              value={variantManageFilter}
              onChange={(e) =>
                setVariantManageFilter(e.target.value as 'all' | 'active' | 'inactive')
              }
              title="Filter manage variant list by status"
              aria-label="Product variant status filter"
            >
              <option value="all">All statuses</option>
              <option value="active">Active only</option>
              <option value="inactive">Inactive only</option>
            </select>
          </div>
          {!variantsReady ? (
            <p className="muted">Loading variants…</p>
          ) : variantsError ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }} role="alert">
                Could not load variants. {variantsError}
              </p>
              <button type="button" style={{ marginTop: 12 }} onClick={() => loadAllVariants()}>
                Retry
              </button>
            </div>
          ) : visibleVariants.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No variants yet.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Choose the parent product, then add size, color, or other options.
              </p>
              <button type="button" style={{ marginTop: 12 }} onClick={openVariantCreate} disabled={!products.length}>
                Add variant
              </button>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Parent</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visibleVariants.map((v) => (
                    <tr key={v.id}>
                      <td data-label="Name">
                        <div className="cat-name-cell">
                          <strong>{v.name}</strong>
                        </div>
                      </td>
                      <td data-label="Parent">
                        {products.find((p) => p.id === v.product_id)?.name || '—'}
                      </td>
                      <td data-label="Status">{v.is_active === false ? 'Inactive' : 'Active'}</td>
                      <td className="cat-actions">
                        <button type="button" onClick={() => openVariantEdit(v)} aria-label={`Edit ${v.name}`}>
                          Edit
                        </button>
                        <div className="cat-menu">
                          <button
                            type="button"
                            aria-label={`More actions for ${v.name}`}
                            onClick={() => setVariantMenuId(variantMenuId === v.id ? '' : v.id)}
                          >
                            ···
                          </button>
                          {variantMenuId === v.id ? (
                            <div className="cat-menu-pop">
                              {v.is_active === false ? (
                                <button type="button" className="btn-ok" onClick={() => activateVariant(v.id)}>
                                  Activate
                                </button>
                              ) : (
                                <button type="button" className="btn-danger" onClick={() => deactivateVariant(v.id)}>
                                  Deactivate
                                </button>
                              )}
                              <button type="button" onClick={() => generateVariantBarcode(v.id)} aria-label={`Generate variant barcode ${v.id}`}>
                                Generate barcode
                              </button>
                              <button type="button" onClick={() => generateVariantQr(v.id)} aria-label={`Generate variant QR ${v.id}`}>
                                Generate QR
                              </button>
                              <button type="button" onClick={() => printVariantBarcodeLabel(v.id)} aria-label={`Print variant barcode label ${v.id}`}>
                                Label
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {variantDrawerOpen ? (
            <FormModal
              title={variantEditId ? 'Edit variant' : 'Add variant'}
              busy={saveBusy}
              dirty={Boolean(variantName.trim() || variantSku.trim())}
              onClose={() => setVariantDrawerOpen(false)}
            >
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    addVariant();
                  }}
                  style={{ display: 'grid', gap: 8 }}
                >
                <label className="muted" htmlFor="variant-name-field">
                  Name
                </label>
                <input
                  id="variant-name-field"
                  value={variantName}
                  onChange={(e) => setVariantName(e.target.value)}
                  placeholder="Name"
                  aria-label="Variant name"
                  title="Variant name (1–120 chars; letters/digits required)"
                />
                <label className="muted" htmlFor="variant-parent-product">
                  Parent product
                </label>
                <select
                  id="variant-parent-product"
                  value={variantProductId}
                  onChange={(e) => setVariantProductId(e.target.value)}
                  aria-label="Parent product for variant"
                  disabled={Boolean(variantEditId)}
                >
                  <option value="">Select a product</option>
                  {products.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="cat-advanced"
                  onClick={() => setVariantAdvanced((v) => !v)}
                  aria-expanded={variantAdvanced}
                >
                  {variantAdvanced ? 'Hide options' : 'Advanced: SKU, barcode, and attributes'}
                </button>
                {variantAdvanced ? (
                  <>
                    <input
                      value={variantSku}
                      onChange={(e) => setVariantSku(e.target.value)}
                      placeholder="SKU (auto if blank)"
                      aria-label="Variant SKU"
                      title="Optional SKU (1–100 chars: letters, digits, . _ -; blank → auto)"
                    />
                    <input
                      value={variantBarcode}
                      onChange={(e) => setVariantBarcode(e.target.value)}
                      placeholder="Barcode (optional)"
                      aria-label="Variant barcode"
                      title="Optional barcode (4–48 chars: letters, numbers, - . _)"
                    />
                    <input
                      value={variantSize}
                      onChange={(e) => setVariantSize(e.target.value)}
                      placeholder="Size (optional)"
                      aria-label="Variant size"
                      title="Optional size (1–80 chars; letters/digits required)"
                    />
                    <input
                      value={variantColor}
                      onChange={(e) => setVariantColor(e.target.value)}
                      placeholder="Color (optional)"
                      aria-label="Variant color"
                      title="Optional color (1–80 chars; letters/digits required)"
                    />
                    <input
                      value={variantFlavor}
                      onChange={(e) => setVariantFlavor(e.target.value)}
                      placeholder="Flavor (optional)"
                      aria-label="Variant flavor"
                      title="Optional flavor (1–80 chars; letters/digits required)"
                    />
                    <input
                      value={variantDosage}
                      onChange={(e) => setVariantDosage(e.target.value)}
                      placeholder="Dosage (optional)"
                      aria-label="Variant dosage"
                      title="Optional dosage (1–80 chars; letters/digits required)"
                    />
                    <input
                      value={variantCost}
                      onChange={(e) => setVariantCost(e.target.value)}
                      placeholder="Cost (optional)"
                      aria-label="Variant cost price"
                    />
                    <input
                      value={variantPrice}
                      onChange={(e) => setVariantPrice(e.target.value)}
                      placeholder="Price (optional)"
                      aria-label="Variant selling price"
                    />
                  </>
                ) : null}
                <div className="cat-save-row">
                  <button
                    type="submit"
                    disabled={!variantName.trim() || saveBusy}
                    aria-label={variantEditId ? 'Save variant' : 'Create variant'}
                  >
                    {saveBusy ? 'Saving…' : variantEditId ? 'Save' : 'Create variant'}
                  </button>
                  {formFlash.ok ? <p className="form-flash ok" role="status">{formFlash.ok}</p> : null}
                  {formFlash.err ? <p className="form-flash err" role="alert">{formFlash.err}</p> : null}
                </div>
                </form>
            </FormModal>
          ) : null}
          {/* inv-drawer: variant create/edit uses FormModal */}
        </div>
      )}

      {tab === 'batches' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Batches</h2>
            <button
              type="button"
              onClick={() => {
                setFormFlash({});
                setBatchDrawerOpen(true);
              }}
              aria-label="Receive batch"
            >
              Receive batch
            </button>
          </div>
          <div className="cat-toolbar">
            <input
              value={batchSearch}
              onChange={(e) => setBatchSearch(e.target.value)}
              placeholder="Search batches"
              aria-label="Search batches"
            />
          </div>
          {visibleBatches.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No batches yet.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Receive stock with a batch number, location, and optional expiry.
              </p>
              <button
                type="button"
                style={{ marginTop: 12 }}
                onClick={() => {
                  setFormFlash({});
                  setBatchDrawerOpen(true);
                }}
              >
                Receive batch
              </button>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Batch</th>
                    <th>Qty</th>
                    <th>Expiry</th>
                    <th>Location</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleBatches.map((b) => {
                    const wh = warehouses.find((w) => w.id === b.warehouse_id);
                    const vr = variants.find((v) => v.id === b.variant_id);
                    return (
                      <tr key={b.id}>
                        <td data-label="Batch">
                          <div className="cat-name-cell">
                            <strong>{b.batch_number}</strong>
                          </div>
                          <div className="muted inv-child">
                            {b.manufacturing_date ? `Made ${String(b.manufacturing_date).slice(0, 10)}` : 'No make date'}
                            {vr ? ` · ${vr.sku}` : ''}
                          </div>
                        </td>
                        <td data-label="Qty">{b.quantity}</td>
                        <td data-label="Expiry">{b.expiry_date ? String(b.expiry_date).slice(0, 10) : '—'}</td>
                        <td data-label="Location">{wh ? wh.name || wh.code : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {batchDrawerOpen ? (
            <FormModal
              title="Receive batch"
              busy={saveBusy}
              dirty={batchFormDirty}
              onClose={() => setBatchDrawerOpen(false)}
            >
                <label className="muted" htmlFor="batch-product">
                  Product
                </label>
                <select
                  id="batch-product"
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  aria-label="Batch product"
                >
                  <option value="">Select product</option>
                  {managedProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku}) — {p.stock_qty}
                    </option>
                  ))}
                </select>
                {!hideWarehouseUx ? (
                <>
                <label className="muted" htmlFor="batch-wh">
                  Location
                </label>
                <select
                  id="batch-wh"
                  value={stockWarehouseId}
                  onChange={(e) => setStockWarehouseId(e.target.value)}
                  aria-label="Stock-in warehouse"
                >
                  <option value="">Select location</option>
                  {storeWarehouses
                    .filter((w) => w.is_active !== false)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name || w.code || w.id.slice(0, 8)}
                      </option>
                    ))}
                </select>
                </>
                ) : null}
                <input
                  value={batchNumber}
                  onChange={(e) => setBatchNumber(e.target.value)}
                  placeholder="Batch number"
                  aria-label="Stock-in batch number"
                />
                <label className="muted">Manufacturing date</label>
                <input
                  aria-label="Stock-in manufacturing date"
                  type="date"
                  value={mfgDate}
                  onChange={(e) => setMfgDate(e.target.value)}
                />
                <label className="muted">Expiry date</label>
                <input
                  aria-label="Stock-in expiry date"
                  type="date"
                  value={expiryDate}
                  onChange={(e) => setExpiryDate(e.target.value)}
                />
                <input
                  value={stockQty}
                  onChange={(e) => setStockQty(e.target.value)}
                  placeholder="Quantity"
                  aria-label="Stock-in quantity"
                />
                <select value={stockUnitId} onChange={(e) => setStockUnitId(e.target.value)} aria-label="Stock-in unit">
                  <option value="">Unit (product default)</option>
                  {units
                    .filter((u) => u.is_active !== false)
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.code}
                      </option>
                    ))}
                </select>
                <select
                  value={stockVariantId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setStockVariantId(id);
                    const row = variants.find((v) => v.id === id);
                    if (row?.product_id) setSelectedId(row.product_id);
                  }}
                  aria-label="Stock-in variant"
                >
                  <option value="">Variant (optional)</option>
                  {selectorVariants.map((v) => (
                    <option key={v.id} value={v.id}>
                      {variantOptionLabel(v, products)}
                    </option>
                  ))}
                </select>
                <input
                  value={stockNotes}
                  onChange={(e) => setStockNotes(e.target.value)}
                  placeholder="Notes (optional)"
                  aria-label="Stock-in notes"
                />
                <input
                  value={stockRefType}
                  onChange={(e) => setStockRefType(e.target.value)}
                  placeholder="Reference type (optional)"
                  aria-label="Stock-in reference type"
                />
                <input
                  value={stockRefId}
                  onChange={(e) => setStockRefId(e.target.value)}
                  placeholder="Reference id (optional)"
                  aria-label="Stock-in reference id"
                />
                <div className="cat-save-row">
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={() => stockInBatch({ requireBatch: true })}
                    disabled={!selectedId || !batchNumber.trim() || saveBusy}
                    aria-label="Receive batch"
                  >
                    {saveBusy ? 'Saving…' : 'Receive batch'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </div>
            </FormModal>
          ) : null}
        </div>
      )}

      {tab === 'opening' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Opening stock</h2>
            <button
              type="button"
              onClick={() => {
                setFormFlash({});
                setOpeningDrawerOpen(true);
              }}
              aria-label="Post opening stock"
            >
              Post opening stock
            </button>
          </div>
          <div className="cat-toolbar">
            <input
              value={openingSearch}
              onChange={(e) => setOpeningSearch(e.target.value)}
              placeholder="Search opening stock"
              aria-label="Search opening stock"
            />
          </div>
          {visibleOpening.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No opening stock posted yet.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Set starting on-hand quantity for go-live. The document number is assigned when you save.
              </p>
              <button
                type="button"
                style={{ marginTop: 12 }}
                onClick={() => {
                  setFormFlash({});
                  setOpeningDrawerOpen(true);
                }}
              >
                Post opening stock
              </button>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>SKU</th>
                    <th>When</th>
                    <th>Qty</th>
                    <th>After</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleOpening.map((m) => {
                    const p = products.find((x) => x.id === m.product_id);
                    return (
                      <tr key={m.id}>
                        <td data-label="Product">
                          <strong className="list-prod-name">{displayProductName(p?.name)}</strong>
                        </td>
                        <td data-label="SKU" className="list-secondary">
                          {p?.sku || '—'}
                        </td>
                        <td data-label="When">{m.created_at ? String(m.created_at).slice(0, 19) : '—'}</td>
                        <td data-label="Qty">{m.quantity}</td>
                        <td data-label="After">{m.quantity_after}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {openingDrawerOpen ? (
            <FormModal
              title="Post opening stock"
              busy={saveBusy}
              dirty={openingFormDirty}
              headerClose={false}
              closeLabel="Cancel"
              closeAriaLabel="Cancel opening stock"
              onClose={() => setOpeningDrawerOpen(false)}
              footer={
                <>
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={postOpeningStock}
                    disabled={!selectedId || saveBusy}
                    aria-label="Post opening stock"
                  >
                    {saveBusy ? 'Saving…' : 'Post opening stock'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </>
              }
            >
                <div className="erp-form-grid form-grid">
                <p className="muted inv-child span-2" style={{ margin: 0 }}>
                  Number {invNumbering.opening_stock_numbering?.preview || 'assigned when you save'}
                </p>
                <input
                  className="span-2"
                  readOnly
                  value={invNumbering.opening_stock_numbering?.preview || ''}
                  placeholder="Assigned when you save"
                  aria-label="Opening stock reference"
                />
                <div className="field">
                <label className="muted" htmlFor="opening-product">
                  Product
                </label>
                <select
                  id="opening-product"
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  aria-label="Opening stock product"
                >
                  <option value="">Select product</option>
                  {managedProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </select>
                </div>
                {!hideWarehouseUx ? (
                <select
                  value={openingWarehouseId}
                  onChange={(e) => setOpeningWarehouseId(e.target.value)}
                  aria-label="Opening stock warehouse"
                >
                  <option value="">Location (required with expiry)</option>
                  {storeWarehouses
                    .filter((w) => w.is_active !== false)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name || w.code || w.id.slice(0, 8)}
                      </option>
                    ))}
                </select>
                ) : null}
                <input
                  value={openingQty}
                  onChange={(e) => setOpeningQty(e.target.value)}
                  placeholder="Quantity"
                  aria-label="Opening stock quantity"
                />
                <select value={openingUnitId} onChange={(e) => setOpeningUnitId(e.target.value)} aria-label="Opening stock unit">
                  <option value="">Unit (product default)</option>
                  {units
                    .filter((u) => u.is_active !== false)
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.code}
                      </option>
                    ))}
                </select>
                <select
                  value={openingVariantId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setOpeningVariantId(id);
                    const row = variants.find((v) => v.id === id);
                    if (row?.product_id) setSelectedId(row.product_id);
                  }}
                  aria-label="Opening stock variant"
                >
                  <option value="">Variant (optional)</option>
                  {selectorVariants.map((v) => (
                    <option key={v.id} value={v.id}>
                      {variantOptionLabel(v, products)}
                    </option>
                  ))}
                </select>
                <input
                  value={openingUnitCost}
                  onChange={(e) => setOpeningUnitCost(e.target.value)}
                  placeholder={`Unit cost (default ${selected?.cost_price ?? 0})`}
                  aria-label="Opening stock unit cost"
                />
                <input
                  value={openingBatch}
                  onChange={(e) => setOpeningBatch(e.target.value)}
                  placeholder="Batch number (if tracked)"
                  aria-label="Opening stock batch number"
                />
                <div className="field">
                <label className="muted">Manufacturing date</label>
                <input
                  aria-label="Opening stock manufacturing date"
                  type="date"
                  value={openingMfg}
                  onChange={(e) => setOpeningMfg(e.target.value)}
                />
                </div>
                <div className="field">
                <label className="muted">Expiry date</label>
                <input
                  aria-label="Opening stock expiry date"
                  type="date"
                  value={openingExpiry}
                  onChange={(e) => setOpeningExpiry(e.target.value)}
                />
                </div>
                <input
                  value={openingNotes}
                  onChange={(e) => setOpeningNotes(e.target.value)}
                  placeholder="Notes"
                  aria-label="Opening stock notes"
                />
                <input
                  value={openingLineNotes}
                  onChange={(e) => setOpeningLineNotes(e.target.value)}
                  placeholder="Line notes (optional)"
                  aria-label="Opening stock line notes"
                />
                <label className="span-2" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input
                    type="checkbox"
                    aria-label="Opening stock post journal"
                    checked={openingPostJournal}
                    onChange={(e) => setOpeningPostJournal(e.target.checked)}
                  />
                  Post inventory journal
                </label>
                </div>
            </FormModal>
          ) : null}
        </div>
      )}

      {tab === 'expiry' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Expiry</h2>
            <button
              type="button"
              onClick={() => {
                setFormFlash({});
                setExpiryFailed(false);
                setExpiryDrawerOpen(true);
              }}
              aria-label="Set expiry"
            >
              Set expiry
            </button>
          </div>
          <div className="cat-toolbar">
            <input
              value={expirySearch}
              onChange={(e) => setExpirySearch(e.target.value)}
              placeholder="Search expiry"
              aria-label="Search expiry"
            />
          </div>
          {expiryBusy ? <p className="muted" role="status">Loading expiry lots…</p> : null}
          {expiryFailed ? (
            <div className="cat-empty">
              <p style={{ margin: 0, color: '#b91c1c' }} role="alert">Could not load expiry lots.</p>
              <button
                type="button"
                style={{ marginTop: 12 }}
                onClick={() => loadTabExtras('expiry').catch((err) => setError(err.message))}
                aria-label="Retry expiry lots"
              >
                Retry
              </button>
            </div>
          ) : visibleExpiring.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No batches expiring in the next year.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                After you add a product, set expiry here with quantity and warehouse. Expiry is stored on the lot, not the product header.
              </p>
              <button
                type="button"
                style={{ marginTop: 12 }}
                onClick={() => {
                  setFormFlash({});
                  setExpiryDrawerOpen(true);
                }}
                aria-label="Set expiry"
              >
                Set expiry
              </button>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Batch</th>
                    <th>Product</th>
                    <th>Qty</th>
                    <th>Expiry</th>
                    <th>Location</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleExpiring.map((b) => {
                    const prod = products.find((p) => p.id === b.product_id);
                    const wh = warehouses.find((w) => w.id === b.warehouse_id);
                    return (
                      <tr key={b.id}>
                        <td data-label="Batch">
                          <strong>{b.batch_number}</strong>
                        </td>
                        <td data-label="Product">{prod?.name || 'Unknown product'}</td>
                        <td data-label="Qty">{b.quantity}</td>
                        <td data-label="Expiry">{b.expiry_date ? String(b.expiry_date).slice(0, 10) : '—'}</td>
                        <td data-label="Location">{wh ? wh.name || wh.code : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
          {expiryDrawerOpen ? (
            <FormModal
              title="Set expiry"
              busy={saveBusy}
              dirty={Boolean(lotQty.trim() || lotExpiry || lotBatch.trim())}
              headerClose={false}
              closeLabel="Cancel"
              closeAriaLabel="Cancel set expiry"
              onClose={() => setExpiryDrawerOpen(false)}
              footer={
                <>
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={recordExpiryLot}
                    disabled={!selectedId || saveBusy}
                    aria-label="Save expiry lot"
                  >
                    {saveBusy ? 'Saving…' : 'Save expiry'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </>
              }
            >
              <div className="erp-form-grid form-grid">
              <p className="muted span-2" style={{ margin: 0 }}>
                Records quantity at the selected warehouse with an expiry date. Uses opening stock when on-hand is zero, otherwise receive stock.
              </p>
              <div className="field">
              <label className="muted" htmlFor="expiry-product">
                Product
              </label>
              <select
                id="expiry-product"
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                aria-label="Expiry product"
              >
                <option value="">Select product</option>
                {managedProducts.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.sku})
                  </option>
                ))}
              </select>
              </div>
              {!hideWarehouseUx ? (
              <div className="field">
              <label className="muted" htmlFor="expiry-wh">
                Location
              </label>
              <select
                id="expiry-wh"
                value={lotWh}
                onChange={(e) => setLotWh(e.target.value)}
                aria-label="Expiry warehouse"
              >
                <option value="">Select warehouse</option>
                {storeWarehouses
                  .filter((w) => w.is_active !== false)
                  .map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name || w.code}
                    </option>
                  ))}
              </select>
              </div>
              ) : null}
              <input
                value={lotQty}
                onChange={(e) => setLotQty(e.target.value)}
                placeholder="Quantity"
                aria-label="Expiry quantity"
              />
              <div className="field">
              <label className="muted">Expiry date</label>
              <input
                type="date"
                value={lotExpiry}
                onChange={(e) => setLotExpiry(e.target.value)}
                aria-label="Expiry date"
              />
              </div>
              <input
                value={lotBatch}
                onChange={(e) => setLotBatch(e.target.value)}
                placeholder="Batch number (optional)"
                aria-label="Expiry batch number"
              />
              </div>
            </FormModal>
          ) : null}
        </div>
      )}

      {tab === 'counts' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Stock count</h2>
            <button
              type="button"
              onClick={() => {
                setFormFlash({});
                setCountDrawerOpen(true);
              }}
              aria-label="Start stock count"
            >
              Start count
            </button>
          </div>
          <div className="cat-toolbar">
            <input
              value={countSearch}
              onChange={(e) => setCountSearch(e.target.value)}
              placeholder="Search counts"
              aria-label="Search stock counts"
            />
            <select
              value={countManageFilter}
              onChange={(e) =>
                setCountManageFilter(e.target.value as 'all' | 'draft' | 'completed' | 'cancelled')
              }
              aria-label="Stock count status filter"
            >
              <option value="all">All statuses</option>
              <option value="draft">Draft only</option>
              <option value="completed">Completed only</option>
              <option value="cancelled">Cancelled only</option>
            </select>
          </div>
          {visibleCounts.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No stock counts yet.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Count on-hand quantity at a location, then post differences. This is not an adjustment
                or a transfer.
              </p>
              <button
                type="button"
                style={{ marginTop: 12 }}
                onClick={() => {
                  setFormFlash({});
                  setCountDrawerOpen(true);
                }}
              >
                Start count
              </button>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Number</th>
                    <th>Status</th>
                    <th>Items</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visibleCounts.map((c) => (
                    <tr key={c.id}>
                      <td data-label="Number">
                        <strong>{c.count_number}</strong>
                        <div className="muted inv-child">{c.notes || ''}</div>
                      </td>
                      <td data-label="Status">{c.status}</td>
                      <td data-label="Items">
                        {c.counted_item_count}/{c.item_count}
                      </td>
                      <td className="cat-actions">
                        <button type="button" onClick={() => openCount(c.id)} aria-label={`Open stock count ${c.id}`}>
                          Open
                        </button>
                        {(c.can_cancel || c.status === 'draft') && (
                          <button
                            type="button"
                            className="btn-danger"
                            onClick={() => cancelStockCount(c.id, c.count_number)}
                            aria-label={`Cancel stock count ${c.id}`}
                          >
                            Cancel
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {countDrawerOpen ? (
            <FormModal
              title="Start stock count"
              busy={saveBusy}
              dirty={countFormDirty}
              onClose={() => setCountDrawerOpen(false)}
            >
                <p className="muted inv-child" style={{ margin: 0 }}>
                  Number {invNumbering.stock_count_numbering?.preview || 'assigned when you save'}
                </p>
                {!hideWarehouseUx ? (
                <select
                  value={countWarehouseId}
                  onChange={(e) => setCountWarehouseId(e.target.value)}
                  aria-label="Stock count warehouse"
                >
                  <option value="">Location</option>
                  {storeWarehouses
                    .filter((w) => w.is_active !== false)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name} ({w.code})
                      </option>
                    ))}
                </select>
                ) : null}
                <input
                  value={countNotes}
                  onChange={(e) => setCountNotes(e.target.value)}
                  placeholder="Notes (optional)"
                  aria-label="Stock count notes"
                />
                <div className="cat-save-row">
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={startStockCount}
                    disabled={!countWarehouseId || saveBusy}
                    aria-label="Create draft count"
                  >
                    {saveBusy ? 'Saving…' : 'Create draft count'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </div>
            </FormModal>
          ) : null}
          {activeCount ? (
            <>
              <div className="inv-drawer-back" onClick={() => !saveBusy && setActiveCount(null)} aria-hidden />
              <aside className="inv-drawer drawer" aria-label="Stock count details" style={{ width: 'min(560px,100vw)' }}>
                <div className="inv-drawer-head">
                  <h3>
                    {activeCount.count_number} — {activeCount.status}
                  </h3>
                  <button type="button" onClick={() => setActiveCount(null)} disabled={saveBusy}>
                    Close
                  </button>
                </div>
                <div className="inv-drawer-body">
                {activeCount.notes ? <p className="muted inv-child">{activeCount.notes}</p> : null}
                <div className="cat-table-wrap">
                  <table className="table cat-table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>SKU</th>
                        <th>Expected</th>
                        <th>Counted</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(activeCount.items || []).map((item: any) => (
                        <tr key={item.id}>
                          <td data-label="Product">
                            <strong className="list-prod-name">
                              {displayProductName(item.product_name)}
                            </strong>
                          </td>
                          <td data-label="SKU" className="list-secondary">
                            {item.product_sku || '—'}
                          </td>
                          <td data-label="Expected">{item.expected_qty}</td>
                          <td data-label="Counted">
                            <input
                              value={countQtys[item.product_id] ?? ''}
                              disabled={activeCount.status !== 'draft'}
                              onChange={(e) => setCountQtys({ ...countQtys, [item.product_id]: e.target.value })}
                              aria-label={`Counted qty ${item.product_sku || item.product_id}`}
                            />
                            <input
                              value={countLineNotes[item.product_id] ?? ''}
                              disabled={activeCount.status !== 'draft'}
                              onChange={(e) =>
                                setCountLineNotes({
                                  ...countLineNotes,
                                  [item.product_id]: e.target.value,
                                })
                              }
                              placeholder="Stock count line notes"
                              aria-label={`Stock count line notes ${item.product_sku || item.product_id}`}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {activeCount.status === 'draft' ? (
                    <input
                      value={countCancelReason}
                      onChange={(e) => setCountCancelReason(e.target.value)}
                      placeholder="Required before Cancel"
                      aria-label="Stock count cancel reason"
                    />
                ) : null}
                </div>
                {activeCount.status === 'draft' ? (
                    <div className="inv-drawer-foot">
                      <button type="button" onClick={saveCountLines} disabled={saveBusy} aria-label="Save count lines">
                        {saveBusy ? 'Saving…' : 'Save counts'}
                      </button>
                      <button
                        type="button"
                        onClick={completeActiveCount}
                        disabled={saveBusy}
                        aria-label="Complete stock count and post variances"
                      >
                        Complete count
                      </button>
                      <button
                        type="button"
                        className="btn-danger"
                        onClick={() => cancelStockCount(activeCount.id, activeCount.count_number)}
                        disabled={saveBusy}
                        aria-label={`Cancel stock count ${activeCount.id}`}
                      >
                        Cancel count
                      </button>
                      {formFlash.ok ? (
                        <p className="form-flash ok" role="status">
                          {formFlash.ok}
                        </p>
                      ) : null}
                      {formFlash.err ? (
                        <p className="form-flash err" role="alert">
                          {formFlash.err}
                        </p>
                      ) : null}
                    </div>
                ) : null}
              </aside>
            </>
          ) : null}
        </div>
      )}

      {tab === 'movements' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Stock history</h2>
            <button type="button" onClick={() => loadMovements()} aria-label="Refresh inventory movements">
              Refresh
            </button>
          </div>
          <div className="cat-toolbar">
            <input
              value={mvSearch}
              onChange={(e) => setMvSearch(e.target.value)}
              placeholder="Search history"
              aria-label="Search stock history"
            />
            {!hideWarehouseUx ? (
            <select
              value={mvWarehouseId}
              onChange={(e) => setMvWarehouseId(e.target.value)}
              aria-label="Movement warehouse filter"
            >
              <option value="">All locations</option>
              {storeWarehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name || w.code || w.id.slice(0, 8)}
                  </option>
                ))}
            </select>
            ) : null}
            <select aria-label="Movement type filter" value={mvType} onChange={(e) => setMvType(e.target.value)}>
              <option value="">All types</option>
              <option value="stock_in">Received</option>
              <option value="stock_out">Issued</option>
              <option value="opening_stock">Opening</option>
              <option value="adjustment">Adjustment</option>
              <option value="transfer_out">Transfer out</option>
              <option value="transfer_in">Transfer in</option>
              <option value="transfer_cancel">Transfer cancel</option>
            </select>
            <select aria-label="Movement reason filter" value={mvReason} onChange={(e) => setMvReason(e.target.value)}>
              <option value="">All reasons</option>
              <option value="damage">Damaged</option>
              <option value="theft">Theft</option>
              <option value="expiry">Expired</option>
              <option value="found">Found</option>
              <option value="lost">Lost</option>
            </select>
            <input type="date" value={mvFrom} onChange={(e) => setMvFrom(e.target.value)} aria-label="Movement from date" />
            <input type="date" value={mvTo} onChange={(e) => setMvTo(e.target.value)} aria-label="Movement to date" />
            <label style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={mvProductOnly}
                onChange={(e) => setMvProductOnly(e.target.checked)}
                aria-label="Movement selected product only"
              />
              Selected product only
            </label>
            {mvProductOnly ? (
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                aria-label="Selected product"
              >
                <option value="">Select product</option>
                {managedProducts.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.sku})
                  </option>
                ))}
              </select>
            ) : null}
          </div>
          <p className="muted inv-child" style={{ margin: 0 }}>
            {mvMeta.count ?? movements.length} record{(mvMeta.count ?? movements.length) === 1 ? '' : 's'}
            {mvMeta.warehouse_name ? ` · ${mvMeta.warehouse_name}` : ''}
          </p>
          {visibleMovements.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>No stock history yet.</p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Receives, issues, counts, transfers, and adjustments appear here. Records are kept for
                audit.
              </p>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Product</th>
                    <th>Type</th>
                    <th>Qty</th>
                    <th>User</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleMovements.map((mv) => (
                    <tr key={mv.id}>
                      <td data-label="When">{mv.created_at ? String(mv.created_at).slice(0, 19) : '—'}</td>
                      <td data-label="Product">
                        <strong className="list-prod-name">{displayProductName(mv.product_name)}</strong>
                        <div className="muted inv-child">
                          {mv.reason || '—'} · {mv.quantity_before} → {mv.quantity_after}
                        </div>
                      </td>
                      <td data-label="Type">{mv.movement_type}</td>
                      <td data-label="Qty">{mv.quantity}</td>
                      <td data-label="User">{mv.created_by_name || mv.created_by_email || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'adjust' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Adjust stock</h2>
            <button
              type="button"
              onClick={() => {
                setFormFlash({});
                setAdjConfirming(false);
                setAdjustDrawerOpen(true);
              }}
              aria-label="Adjust stock"
            >
              Adjust stock
            </button>
          </div>
          <p className="muted inv-child">
            Use this only to correct on-hand quantity. Receive stock in Manage stock. Move stock with
            Stock transfer. Count with Stock count.
          </p>
          <div className="list-toolbar">
            <input
              value={adjustSearch}
              onChange={(e) => setAdjustSearch(e.target.value)}
              placeholder="Search products to adjust"
              aria-label="Search products for stock adjustment"
            />
          </div>
          {adjustVisible.length === 0 ? (
            <p className="muted inv-child">
              {adjustEligible.length === 0
                ? 'No eligible products to adjust.'
                : 'No products match this search.'}
            </p>
          ) : (
            <>
              <p className="muted inv-child">
                {adjustLowOutCount} of {adjustVisible.length} listed product(s) are low or out of stock.
              </p>
              <div className="cat-table-wrap">
                <table className="table cat-table">
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>SKU</th>
                      <th>Qty</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {adjustVisible.map((p) => (
                      <tr key={p.id}>
                        <td data-label="Product">
                          <strong className="list-prod-name">{displayProductName(p.name)}</strong>
                        </td>
                        <td data-label="SKU" className="list-secondary">{p.sku || '—'}</td>
                        <td data-label="Qty">{p.stock_qty ?? 0}</td>
                        <td className="cat-actions">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedId(p.id);
                              setFormFlash({});
                              setAdjConfirming(false);
                              setAdjustDrawerOpen(true);
                            }}
                            aria-label={`Adjust ${p.name}`}
                          >
                            Adjust
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {adjustDrawerOpen ? (
            <FormModal
              title="Correct stock quantity"
              busy={saveBusy}
              dirty={adjustFormDirty}
              onClose={() => {
                setAdjustDrawerOpen(false);
                setAdjConfirming(false);
              }}
            >
                <label className="muted" htmlFor="adj-product">
                  Product
                </label>
                <select
                  id="adj-product"
                  value={selectedId}
                  onChange={(e) => {
                    setSelectedId(e.target.value);
                    setAdjConfirming(false);
                  }}
                  aria-label="Adjustment product"
                >
                  <option value="">Select product</option>
                  {managedProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku}) — on-hand {p.stock_qty}
                    </option>
                  ))}
                </select>
                <label className="muted">Quantity change (+ or −)</label>
                <input
                  value={adjQty}
                  onChange={(e) => {
                    setAdjQty(e.target.value);
                    setAdjConfirming(false);
                  }}
                  placeholder="-1"
                  aria-label="Stock adjustment quantity"
                />
                <label className="muted">Reason</label>
                <select
                  value={adjReason}
                  onChange={(e) => {
                    setAdjReason(e.target.value);
                    setAdjConfirming(false);
                  }}
                  aria-label="Adjustment reason"
                >
                  <option value="">Select reason</option>
                  <option value="damage">Damaged</option>
                  <option value="theft">Theft</option>
                  <option value="expiry">Expired</option>
                  <option value="found">Found</option>
                  <option value="lost">Lost</option>
                </select>
                {!hideWarehouseUx ? (
                <select
                  value={adjWarehouseId}
                  onChange={(e) => setAdjWarehouseId(e.target.value)}
                  aria-label="Stock adjustment warehouse"
                >
                  <option value="">Company stock (no location)</option>
                  {storeWarehouses
                    .filter((w) => w.is_active !== false)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name || w.code || w.id.slice(0, 8)}
                      </option>
                    ))}
                </select>
                ) : null}
                <input
                  value={adjNotes}
                  onChange={(e) => setAdjNotes(e.target.value)}
                  placeholder="Notes (optional)"
                  aria-label="Stock adjustment notes"
                />
                {adjConfirming ? (
                  <p className="muted inv-child">
                    Confirm: change on-hand by {adjQty} because {adjReason}. This is recorded and cannot
                    be undone.
                  </p>
                ) : null}
                <div className="cat-save-row">
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={postStockAdjust}
                    disabled={!selectedId || !adjReason || saveBusy}
                    aria-label="Post stock adjustment"
                  >
                    {saveBusy ? 'Saving…' : adjConfirming ? 'Confirm adjustment' : 'Post adjustment'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </div>
            </FormModal>
          ) : null}
        </div>
      )}

      {tab === 'stockout' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Stock out</h2>
            <button
              type="button"
              onClick={() => {
                setFormFlash({});
                setStockOutDrawerOpen(true);
              }}
              aria-label="Issue stock"
            >
              Issue stock
            </button>
          </div>
          <p className="muted inv-child">
            Issue outgoing quantity with a reason. Earliest-expiry batches are used when you do not pick
            a batch.
          </p>
          {stockOutDrawerOpen ? (
            <FormModal
              title="Issue stock"
              busy={saveBusy}
              dirty={stockOutFormDirty}
              onClose={() => setStockOutDrawerOpen(false)}
            >
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  aria-label="Stock-out product"
                >
                  <option value="">Select product</option>
                  {managedProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku}) — {p.stock_qty}
                    </option>
                  ))}
                </select>
                <input
                  value={outQty}
                  onChange={(e) => setOutQty(e.target.value)}
                  placeholder="Quantity"
                  aria-label="Stock-out quantity"
                />
                <select
                  value={outRefType}
                  onChange={(e) => setOutRefType(e.target.value)}
                  aria-label="Stock-out reference type"
                >
                  <option value="">Select reference type</option>
                  <option value="sale">Sale</option>
                  <option value="transfer">Transfer</option>
                  <option value="adjustment">Adjustment</option>
                  <option value="damage">Damage</option>
                  <option value="internal">Internal use</option>
                  <option value="other">Other</option>
                </select>
                <input
                  value={outRefId}
                  onChange={(e) => setOutRefId(e.target.value)}
                  placeholder="Reference (optional)"
                  aria-label="Stock-out reference id"
                />
                {!hideWarehouseUx ? (
                <select
                  value={outWarehouseId}
                  onChange={(e) => setOutWarehouseId(e.target.value)}
                  aria-label="Stock-out warehouse"
                >
                  <option value="">Company stock (no location)</option>
                  {storeWarehouses
                    .filter((w) => w.is_active !== false)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name || w.code || w.id.slice(0, 8)}
                      </option>
                    ))}
                </select>
                ) : null}
                <select value={outVariantId} onChange={(e) => {
                  const id = e.target.value;
                  setOutVariantId(id);
                  const row = variants.find((v) => v.id === id);
                  if (row?.product_id) setSelectedId(row.product_id);
                }} aria-label="Stock-out variant">
                  <option value="">Variant (optional)</option>
                  {selectorVariants.map((v) => (
                    <option key={v.id} value={v.id}>
                      {variantOptionLabel(v, products)}
                    </option>
                  ))}
                </select>
                <select value={outBatchId} onChange={(e) => setOutBatchId(e.target.value)} aria-label="Stock-out batch">
                  <option value="">Earliest expiry (automatic)</option>
                  {batches
                    .filter((b) => Number(b.quantity) > 0)
                    .map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.batch_number} — qty {b.quantity}
                      </option>
                    ))}
                </select>
                <input
                  value={outNotes}
                  onChange={(e) => setOutNotes(e.target.value)}
                  placeholder="Notes (optional)"
                  aria-label="Stock-out notes"
                />
                <div className="cat-save-row">
                  <button
                    type="button"
                    className="btn-ok"
                    onClick={postStockOut}
                    disabled={!selectedId || !outRefType || saveBusy}
                    aria-label="Post stock out"
                  >
                    {saveBusy ? 'Saving…' : 'Post stock out'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </div>
            </FormModal>
          ) : null}
        </div>
      )}

      {tab === 'lowstock' && (
        <div className="card cat-panel">
          <div className="list-page-head">
            <div>
              <h2 style={{ margin: 0 }}>Low stock</h2>
              <p className="muted" style={{ margin: '4px 0 0' }}>
                On-hand above zero and at or below max(minimum stock, reorder). Out of stock is listed on Products.
              </p>
            </div>
          </div>
          <div className="list-toolbar">
            <input
              value={lowStockSearch}
              onChange={(e) => setLowStockSearch(e.target.value)}
              placeholder="Search name, SKU, category"
              aria-label="Search low stock"
            />
          </div>
          {lowStockBusy ? (
            <p className="muted">Loading…</p>
          ) : !lowStockPayload ? (
            <div className="list-empty">
              <p>Could not load low stock.</p>
              <button type="button" onClick={() => loadLowStock()} aria-label="Retry low stock">
                Retry
              </button>
            </div>
          ) : lowStockRows.length === 0 ? (
            <div className="list-empty">
              <p>No products are in the low-stock band.</p>
            </div>
          ) : (
            <div className="list-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>SKU</th>
                    <th>Category</th>
                    <th>Qty on hand</th>
                    <th>Reorder/min</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {lowStockRows.map((row: any) => (
                    <tr key={row.key}>
                      <td data-label="Product"><span className="list-prod-name">{displayProductName(row.name)}</span></td>
                      <td data-label="SKU" className="list-secondary">{row.sku}</td>
                      <td data-label="Category" className="list-secondary">{row.category}</td>
                      <td data-label="Qty on hand" className="list-qty-low">{row.qty}</td>
                      <td data-label="Reorder/min">{row.floor}</td>
                      <td data-label="Status">{row.status}</td>
                      <td className="cat-actions">
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedId(row.id);
                            setDrawerOpen(true);
                            setProductEditMode(false);
                            setFormFlash({});
                          }}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === 'whstock' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>{whLowOnly ? 'Low stock' : 'Manage stock'}</h2>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => {
                  setFormFlash({});
                  setReceiveDrawerOpen(true);
                }}
                aria-label="Receive stock"
              >
                Receive stock
              </button>
            </div>
          </div>
          <p className="muted inv-child">
            View quantity, receive stock, and set reorder levels. Quantity corrections belong on Adjust stock.
          </p>
          <div className="cat-toolbar">
            {!hideWarehouseUx ? (
            <select
              value={whStockWarehouseId}
              onChange={(e) => setWhStockWarehouseId(e.target.value)}
              aria-label="Warehouse stock warehouse"
            >
              <option value="">Select location</option>
              {storeWarehouses
                .filter((w) => w.is_active !== false)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name || w.code || w.id.slice(0, 8)}
                  </option>
                ))}
            </select>
            ) : null}
            <input
              value={whSearch}
              onChange={(e) => setWhSearch(e.target.value)}
              placeholder="Search products"
              aria-label="Search warehouse stock"
            />
            <select
              value={whLowOnly ? 'low' : 'all'}
              onChange={(e) => setWhLowOnly(e.target.value === 'low')}
              aria-label="Low stock filter"
            >
              <option value="all">All products</option>
              <option value="low">Low stock</option>
            </select>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={whStockIncludeZero}
                onChange={(e) => setWhStockIncludeZero(e.target.checked)}
                aria-label="Warehouse stock include zero"
              />
              <span className="muted">Include zero</span>
            </label>
            <button type="button" onClick={() => loadWarehouseStock()} disabled={!whStockWarehouseId} aria-label="Refresh warehouse stock">
              Refresh
            </button>
            <button
              type="button"
              onClick={() => {
                setFormFlash({});
                setReorderDrawerOpen(true);
              }}
              aria-label="Set reorder level"
            >
              Set reorder
            </button>
          </div>
          <p className="muted inv-child" style={{ margin: 0 }}>
            {whStockMeta.warehouse_name
              ? `${whStockMeta.warehouse_name} — ${whStockMeta.count ?? 0} products · total ${whStockMeta.total_quantity ?? 0}`
              : hideWarehouseUx
                ? 'Loading store stock'
                : 'Pick a location to load stock'}
          </p>
          {!whStockWarehouseId ? (
            <p className="muted">{hideWarehouseUx ? 'No warehouse is available for this store' : 'Pick a location to load stock'}</p>
          ) : whStockBusy ? (
            <p className="muted">Loading…</p>
          ) : whStockFailed ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>Could not load stock for this location.</p>
              <button
                type="button"
                onClick={() => loadWarehouseStock()}
                aria-label="Retry warehouse stock"
                style={{ marginTop: 8 }}
              >
                Retry
              </button>
            </div>
          ) : visibleWhRows.length === 0 ? (
            <div className="cat-empty">
              <p style={{ margin: 0 }}>{whLowOnly ? 'No low-stock products here.' : 'No stock rows yet.'}</p>
              {!whLowOnly ? (
                <p className="muted" style={{ margin: '8px 0 0' }}>
                  Receive stock into this location, or include zero-quantity rows.
                </p>
              ) : null}
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>SKU</th>
                    <th>Qty</th>
                    <th>Reorder</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleWhRows.map((r) => (
                    <tr key={r.product_id}>
                      <td data-label="Product">
                        <strong className="list-prod-name">{displayProductName(r.name)}</strong>
                      </td>
                      <td data-label="SKU" className="list-secondary">{r.sku || '—'}</td>
                      <td data-label="Qty">{r.quantity}</td>
                      <td data-label="Reorder">
                        {r.low_stock_floor ?? r.reorder_level} / {r.reorder_qty}
                      </td>
                      <td data-label="Status" style={{ color: r.is_out_of_stock || warehouseRowIsLow(r) ? '#b91c1c' : undefined }}>
                        {r.is_out_of_stock || Number(r.quantity) <= 0
                          ? 'Out of stock'
                          : warehouseRowIsLow(r)
                            ? 'Low'
                            : 'OK'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {receiveDrawerOpen ? (
            <FormModal
              title="Receive stock"
              busy={saveBusy}
              dirty={receiveFormDirty}
              onClose={() => setReceiveDrawerOpen(false)}
            >
                <select
                  value={selectedId}
                  onChange={(e) => setSelectedId(e.target.value)}
                  aria-label="Receive stock product"
                >
                  <option value="">Select product</option>
                  {managedProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({p.sku})
                    </option>
                  ))}
                </select>
                {!hideWarehouseUx ? (
                <select
                  value={whStockWarehouseId}
                  onChange={(e) => {
                    setWhStockWarehouseId(e.target.value);
                    setStockWarehouseId(e.target.value);
                  }}
                  aria-label="Receive stock location"
                >
                  <option value="">Select location</option>
                  {storeWarehouses
                    .filter((w) => w.is_active !== false)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {w.name || w.code}
                      </option>
                    ))}
                </select>
                ) : null}
                <input
                  value={stockQty}
                  onChange={(e) => setStockQty(e.target.value)}
                  placeholder="Quantity"
                  aria-label="Receive stock quantity"
                />
                <input
                  value={batchNumber}
                  onChange={(e) => setBatchNumber(e.target.value)}
                  placeholder="Batch (optional)"
                  aria-label="Receive stock batch"
                />
                <input
                  type="date"
                  value={expiryDate}
                  onChange={(e) => setExpiryDate(e.target.value)}
                  aria-label="Receive stock expiry"
                />
                <div className="cat-save-row">
                  <button
                    type="button"
                    onClick={() => {
                      if (whStockWarehouseId) setStockWarehouseId(whStockWarehouseId);
                      stockInBatch();
                    }}
                    disabled={!selectedId || !whStockWarehouseId || saveBusy}
                    aria-label="Receive stock"
                  >
                    {saveBusy ? 'Saving…' : 'Receive stock'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </div>
            </FormModal>
          ) : null}
          {reorderDrawerOpen ? (
            <FormModal
              title="Set reorder level"
              busy={saveBusy}
              dirty={reorderFormDirty}
              onClose={() => setReorderDrawerOpen(false)}
            >
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
                  aria-label="Warehouse reorder product"
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
                  aria-label="Warehouse reorder level"
                />
                <input
                  value={whReorderQty}
                  onChange={(e) => setWhReorderQty(e.target.value)}
                  placeholder="Reorder qty"
                  aria-label="Warehouse reorder qty"
                />
                <div className="cat-save-row">
                  <button
                    type="button"
                    onClick={saveWarehouseReorder}
                    disabled={!whStockWarehouseId || !whReorderProductId || saveBusy}
                    aria-label="Save warehouse reorder policy"
                  >
                    {saveBusy ? 'Saving…' : 'Save reorder'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </div>
            </FormModal>
          ) : null}
        </div>
      )}

      {tab === 'transfers' && retailTransfers && (
        <div className="card cat-panel">
          <div className="list-page-head cat-head">
            <div>
              <h2 style={{ margin: 0 }}>Stock Transfer</h2>
              <p className="muted" style={{ margin: '4px 0 0' }}>
                Move stock from one warehouse to another. Request, ship, then receive.
              </p>
            </div>
            <button
              type="button"
              className="list-btn-primary"
              onClick={() => {
                setFormFlash({});
                setXferConfirming(false);
                setXferDrawerOpen(true);
              }}
              aria-label="Add Transfer"
            >
              Add Transfer
            </button>
          </div>
          <div className="list-toolbar cat-toolbar">
            <input
              value={xferSearch}
              onChange={(e) => setXferSearch(e.target.value)}
              placeholder="Search reference, warehouse, status"
              aria-label="Search stock transfers"
            />
            <input
              type="date"
              value={xferDateFrom}
              onChange={(e) => setXferDateFrom(e.target.value)}
              aria-label="Transfer date from"
            />
            <input
              type="date"
              value={xferDateTo}
              onChange={(e) => setXferDateTo(e.target.value)}
              aria-label="Transfer date to"
            />
            <select
              value={xferFromFilter}
              onChange={(e) => setXferFromFilter(e.target.value)}
              aria-label="Filter by from warehouse"
            >
              <option value="">From store / warehouse</option>
              {warehouses
                .filter((w) => w.store_id)
                .map((w) => (
                  <option key={w.id} value={w.id}>
                    {warehouseLabel(w.id)}
                  </option>
                ))}
            </select>
            <select
              value={xferToFilter}
              onChange={(e) => setXferToFilter(e.target.value)}
              aria-label="Filter by to warehouse"
            >
              <option value="">To store / warehouse</option>
              {warehouses
                .filter((w) => w.store_id)
                .map((w) => (
                  <option key={`to-${w.id}`} value={w.id}>
                    {warehouseLabel(w.id)}
                  </option>
                ))}
            </select>
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
                    | 'cancelled',
                )
              }
              aria-label="Stock transfer status filter"
            >
              <option value="all">All statuses</option>
              <option value="draft">Draft only</option>
              <option value="requested">Requested only</option>
              <option value="in_transit">In transit only</option>
              <option value="received">Received only</option>
              <option value="cancelled">Cancelled only</option>
            </select>
            <button type="button" onClick={() => loadTransfers()} aria-label="Refresh stock transfers">
              Refresh
            </button>
          </div>
          {xferBusy ? <p className="muted">Loading transfers…</p> : null}
          {error && tab === 'transfers' ? (
            <p className="list-toast err" role="alert">
              {error}
            </p>
          ) : null}
          {!xferBusy && visibleTransfers.length === 0 ? (
            <div className="list-empty cat-empty">
              <p style={{ margin: 0 }}>
                {transfers.length === 0 ? 'No transfers yet.' : 'No transfers for this filter.'}
              </p>
              <p className="muted" style={{ margin: '8px 0 0' }}>
                Create a transfer, approve, ship, then receive at the destination.
              </p>
              <button
                type="button"
                className="list-btn-primary"
                style={{ marginTop: 12 }}
                onClick={() => {
                  setFormFlash({});
                  setXferConfirming(false);
                  setXferDrawerOpen(true);
                }}
              >
                Add Transfer
              </button>
            </div>
          ) : !xferBusy ? (
            <div className="list-table-wrap cat-table-wrap">
              <table className="table cat-table">
                <thead>
                  <tr>
                    <th>From store / warehouse</th>
                    <th>To store / warehouse</th>
                    <th>Products</th>
                    <th>Qty</th>
                    <th>Reference</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {xferPaged.rows.map((t) => (
                    <Fragment key={t.id}>
                    <tr>
                      <td data-label="From">{warehouseLabel(t.from_warehouse_id)}</td>
                      <td data-label="To">{warehouseLabel(t.to_warehouse_id)}</td>
                      <td data-label="Products">{transferProductCount(t)}</td>
                      <td data-label="Qty">{transferQtyTotal(t)}</td>
                      <td data-label="Reference">
                        <strong>{t.transfer_number}</strong>
                        <div className="muted inv-child">{t.rejection_reason || ''}</div>
                      </td>
                      <td data-label="Date">{formatTransferDate(t.created_at)}</td>
                      <td data-label="Status">
                        <span className={`xfer-status xfer-status--${t.status || 'draft'}`}>{t.status}</span>
                      </td>
                      <td className="cat-actions">
                        <button
                          type="button"
                          onClick={() => setXferDetailId(xferDetailId === t.id ? '' : t.id)}
                          aria-label={`${xferDetailId === t.id ? 'Hide' : 'Show'} stock transfer lines ${t.id}`}
                        >
                          {xferDetailId === t.id ? 'Hide lines' : 'Lines'}
                        </button>
                        {t.status === 'draft' && (
                          <button
                            type="button"
                            className="btn-ok"
                            onClick={() => transferAct(t.id, 'submit')}
                            disabled={saveBusy}
                            aria-label={`Submit stock transfer ${t.id}`}
                          >
                            Submit
                          </button>
                        )}
                        {t.status === 'requested' && !t.fully_approved && (
                          <button
                            type="button"
                            className="btn-ok"
                            onClick={() => transferAct(t.id, 'approve')}
                            disabled={saveBusy}
                            aria-label={`Approve stock transfer ${t.id}`}
                          >
                            Approve
                          </button>
                        )}
                        {t.can_ship && (
                          <button
                            type="button"
                            className="btn-ok"
                            onClick={() => transferAct(t.id, 'ship')}
                            disabled={saveBusy}
                            aria-label={`Ship stock transfer ${t.id}`}
                          >
                            Ship
                          </button>
                        )}
                        {t.status === 'in_transit' && (
                          <button
                            type="button"
                            className="btn-ok"
                            onClick={() => transferAct(t.id, 'receive')}
                            disabled={saveBusy}
                            aria-label={`Receive stock transfer ${t.id}`}
                          >
                            Receive
                          </button>
                        )}
                        {['draft', 'requested', 'in_transit'].includes(t.status) && (
                          <button
                            type="button"
                            className="btn-danger"
                            onClick={() => transferAct(t.id, 'cancel')}
                            disabled={saveBusy}
                            aria-label={`Cancel stock transfer ${t.id}`}
                          >
                            Cancel
                          </button>
                        )}
                        {t.status === 'requested' && !t.fully_approved && (
                          <button
                            type="button"
                            className="btn-danger"
                            onClick={() => transferAct(t.id, 'reject')}
                            disabled={saveBusy}
                            aria-label={`Reject stock transfer ${t.id}`}
                          >
                            Reject
                          </button>
                        )}
                      </td>
                    </tr>
                    {xferDetailId === t.id ? (
                      <tr>
                        <td colSpan={8}>
                          <table className="table">
                            <thead>
                              <tr>
                                <th>Product</th>
                                <th>SKU</th>
                                <th>Qty</th>
                                <th>Shipped</th>
                                <th>Received</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(t.items || []).map((line: any) => {
                                const prod = products.find((p) => p.id === line.product_id);
                                return (
                                  <tr key={line.id || `${t.id}-${line.product_id}`}>
                                    <td>
                                      {prod ? displayProductName(prod.name) : line.product_id}
                                    </td>
                                    <td>{prod?.sku || '—'}</td>
                                    <td>{line.quantity}</td>
                                    <td>{line.shipped_qty ?? '—'}</td>
                                    <td>{line.received_qty ?? '—'}</td>
                                  </tr>
                                );
                              })}
                              {!(t.items || []).length ? (
                                <tr>
                                  <td colSpan={5} className="muted">
                                    No product lines
                                  </td>
                                </tr>
                              ) : null}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    ) : null}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {xferPaged.total > 0 && !xferBusy ? (
            <div className="list-pager">
              <span className="muted">
                {xferPaged.total} entries · page {xferPaged.page} of {xferPaged.pages}
              </span>
              <div className="list-pager-nav">
                <button
                  type="button"
                  disabled={xferPaged.page <= 1}
                  onClick={() => setXferPage(xferPaged.page - 1)}
                  aria-label="Previous transfer page"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={xferPaged.page >= xferPaged.pages}
                  onClick={() => setXferPage(xferPaged.page + 1)}
                  aria-label="Next transfer page"
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
          <div className="list-toolbar cat-toolbar">
            <input
              value={xferRejectReason}
              onChange={(e) => setXferRejectReason(e.target.value)}
              placeholder="Required before Reject or Cancel"
              aria-label="Stock transfer reject reason"
            />
            {formFlash.ok ? (
              <p className="form-flash ok" role="status">
                {formFlash.ok}
              </p>
            ) : null}
            {formFlash.err ? (
              <p className="form-flash err" role="alert">
                {formFlash.err}
              </p>
            ) : null}
          </div>
          {xferDrawerOpen ? (
            <FormModal
              title="Create stock transfer"
              busy={saveBusy}
              dirty={Boolean(xferReference.trim() || xferNotes.trim() || xferLines.some((l) => l.product_id || l.qty))}
              onClose={() => {
                setXferDrawerOpen(false);
                setXferConfirming(false);
              }}
            >
            <p className="muted inv-child" style={{ margin: 0 }}>
                  Number {invNumbering.stock_transfer_numbering?.preview || 'assigned when you save'}
                </p>
                <label className="muted">From store / warehouse</label>
                <select
                  value={xferFromWh}
                  onChange={(e) => {
                    setXferFromWh(e.target.value);
                    setXferConfirming(false);
                  }}
                  aria-label="Stock transfer from warehouse"
                >
                  <option value="">Select source</option>
                  {storeWarehouses
                    .filter((w) => w.store_id)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {warehouseLabel(w.id)}
                      </option>
                    ))}
                </select>
                <label className="muted">To store / warehouse</label>
                <select
                  value={xferToWh}
                  onChange={(e) => {
                    setXferToWh(e.target.value);
                    setXferConfirming(false);
                  }}
                  aria-label="Stock transfer to warehouse"
                >
                  <option value="">Select destination</option>
                  {warehouses
                    .filter((w) => w.store_id)
                    .map((w) => (
                      <option key={w.id} value={w.id}>
                        {warehouseLabel(w.id)}
                      </option>
                    ))}
                </select>
                <label className="muted">Product search</label>
                <input
                  value={xferProductQuery}
                  onChange={(e) => setXferProductQuery(e.target.value)}
                  placeholder="Filter products by name or SKU"
                  aria-label="Search transfer products"
                />
                <label className="muted">Reference (optional)</label>
                <input
                  value={xferReference}
                  onChange={(e) => setXferReference(e.target.value)}
                  placeholder="Your reference"
                  aria-label="Stock transfer reference"
                />
                <label className="muted">Product lines</label>
                {xferLines.map((line, idx) => (
                  <div key={line.key} className="xfer-line-row">
                    <select
                      value={line.product_id}
                      onChange={(e) => {
                        setXferConfirming(false);
                        setXferLines((rows) =>
                          rows.map((r) =>
                            r.key === line.key ? { ...r, product_id: e.target.value } : r,
                          ),
                        );
                      }}
                      aria-label={`Transfer product line ${idx + 1}`}
                    >
                      <option value="">Select product</option>
                      {xferProductOptions.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} ({p.sku})
                        </option>
                      ))}
                    </select>
                    <span className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                      Avail {line.product_id ? (xferAvail[line.product_id] ?? '—') : '—'}
                    </span>
                    <input
                      value={line.qty}
                      onChange={(e) => {
                        setXferConfirming(false);
                        setXferLines((rows) =>
                          rows.map((r) => (r.key === line.key ? { ...r, qty: e.target.value } : r)),
                        );
                      }}
                      placeholder="Qty"
                      aria-label={`Transfer quantity line ${idx + 1}`}
                    />
                    {xferLines.length > 1 ? (
                      <button
                        type="button"
                        className="btn-danger"
                        onClick={() => {
                          setXferConfirming(false);
                          setXferLines((rows) => rows.filter((r) => r.key !== line.key));
                        }}
                        aria-label={`Remove transfer line ${idx + 1}`}
                      >
                        Remove
                      </button>
                    ) : null}
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() =>
                    setXferLines((rows) => [
                      ...rows,
                      { key: String(Date.now()), product_id: '', qty: '1' },
                    ])
                  }
                  aria-label="Add transfer product line"
                >
                  Add product line
                </button>
                <input
                  value={xferNotes}
                  onChange={(e) => setXferNotes(e.target.value)}
                  placeholder="Notes (optional)"
                  aria-label="Stock transfer notes"
                />
                {xferConfirming ? (
                  <p className="muted" style={{ margin: 0 }}>
                    Confirm: {warehouseLabel(xferFromWh)} → {warehouseLabel(xferToWh)}
                    {xferParsed.ok
                      ? ` · ${xferParsed.items.length} products · ${xferParsed.items.reduce((s, i) => s + i.quantity, 0)} qty`
                      : ''}
                  </p>
                ) : null}
                <div className="cat-save-row">
                  {xferConfirming ? (
                    <button
                      type="button"
                      onClick={() => setXferConfirming(false)}
                      disabled={saveBusy}
                      aria-label="Edit stock transfer before confirm"
                    >
                      Back
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={createWarehouseTransfer}
                    disabled={!xferFromWh || !xferToWh || saveBusy}
                    aria-label={xferConfirming ? 'Confirm stock transfer' : 'Review stock transfer'}
                  >
                    {saveBusy ? 'Saving…' : xferConfirming ? 'Confirm create' : 'Review transfer'}
                  </button>
                  {formFlash.ok ? (
                    <p className="form-flash ok" role="status">
                      {formFlash.ok}
                    </p>
                  ) : null}
                  {formFlash.err ? (
                    <p className="form-flash err" role="alert">
                      {formFlash.err}
                    </p>
                  ) : null}
                </div>
            </FormModal>
          ) : null}
        </div>
      )}
    </>
  );
}
