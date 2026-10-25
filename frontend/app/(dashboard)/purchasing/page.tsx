'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import FormModal from '../../../components/FormModal';
import PageHeader from '../../../components/PageHeader';
import PartyContactsPanel from '../../../components/PartyContactsPanel';
import AttachmentPreview from '../../../components/AttachmentPreview';
import RowActions, { type RowActionItem } from '../../../components/RowActions';
import StatusChip from '../../../components/StatusChip';
import { api } from '../../../lib/api';
import { fetchAttachment, uploadAttachment } from '../../../lib/attachments';
import { openDocumentPrint } from '../../../lib/documentPrint';
import { createPaintGet, peekPrefetch } from '../../../lib/prefetchCache';
import { AmountField } from '../../../components/AmountField';
import { getMe } from '../../../lib/meCache';
import { useStoreContext } from '../../../lib/storeContext';
import { tenantIsMultiStore } from '../../../lib/tenantNav';
import { formatDate, formatNumber } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import './purchase-ui.css';

type Tab = 'suppliers' | 'requests' | 'orders' | 'grn' | 'invoices' | 'returns' | 'history';

const PURCHASING_TABS: Tab[] = ['suppliers', 'requests', 'orders', 'grn', 'invoices', 'returns', 'history'];

function isPurchasingTab(value: string | null): value is Tab {
  return Boolean(value && (PURCHASING_TABS as string[]).includes(value));
}

function sameParty(a?: string | null, b?: string | null) {
  const left = String(a || '').trim().toLowerCase();
  const right = String(b || '').trim().toLowerCase();
  return Boolean(left) && left === right;
}

function asList<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    const rec = data as Record<string, unknown>;
    if (Array.isArray(rec.items)) return rec.items as T[];
    if (Array.isArray(rec.data)) return rec.data as T[];
  }
  return [];
}

async function openPurchasingPrint(path: string) {
  return openDocumentPrint(path);
}

type BillLineDraft = {
  key: string;
  productId: string;
  qty: string;
  unitCost: string;
  taxRate: string;
  discount: string;
};

type PoLineDraft = {
  key: string;
  productId: string;
  unitId: string;
  qty: string;
  unitPrice: string;
  discount: string;
};

type AmendLineDraft = {
  key: string;
  productId: string;
  unitId: string;
  qty: string;
  unitPrice: string;
  discount: string;
  taxRate: string;
};

type PrLineDraft = {
  key: string;
  productId: string;
  qty: string;
  notes: string;
};

type ReturnLineDraft = {
  key: string;
  grnItemId: string;
  qty: string;
};

function newBillLineKey() {
  return `bl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function emptyBillLine(): BillLineDraft {
  return { key: newBillLineKey(), productId: '', qty: '1', unitCost: '0', taxRate: '', discount: '0' };
}

function emptyPoLine(): PoLineDraft {
  return {
    key: `po-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    productId: '',
    unitId: '',
    qty: '10',
    unitPrice: '0',
    discount: '0',
  };
}

function emptyAmendLine(): AmendLineDraft {
  return {
    key: `am-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    productId: '',
    unitId: '',
    qty: '1',
    unitPrice: '0',
    discount: '0',
    taxRate: '',
  };
}

function amendLinesFromPo(po: PurchaseOrder): AmendLineDraft[] {
  const rows = (po.items || []).map((line) => ({
    key: line.id,
    productId: line.product_id,
    unitId: line.unit_id || '',
    qty: String(line.quantity ?? ''),
    unitPrice: String(line.unit_price ?? ''),
    discount: String(line.discount ?? 0),
    taxRate: line.tax_rate == null ? '' : String(line.tax_rate),
  }));
  return rows.length ? rows : [emptyAmendLine()];
}

function emptyReturnLine(): ReturnLineDraft {
  return {
    key: `ret-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    grnItemId: '',
    qty: '',
  };
}

function emptyPrLine(): PrLineDraft {
  return {
    key: `pr-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    productId: '',
    qty: '10',
    notes: '',
  };
}

function ensureTrailingBlank<T extends { productId: string }>(rows: T[], makeBlank: () => T): T[] {
  if (!rows.length) return [makeBlank()];
  if (rows[rows.length - 1].productId.trim()) return [...rows, makeBlank()];
  return rows;
}

function isValidPoLine(line: PoLineDraft) {
  const qty = Number(line.qty);
  const unit = Number(line.unitPrice);
  const disc = Number(line.discount);
  return (
    Boolean(line.productId.trim()) &&
    Number.isFinite(qty) &&
    qty > 0 &&
    Number.isFinite(unit) &&
    unit >= 0 &&
    Number.isFinite(disc) &&
    disc >= 0
  );
}

function billLineMerch(line: BillLineDraft) {
  const qty = Number(line.qty);
  const unit = Number(line.unitCost);
  if (!Number.isFinite(qty) || !Number.isFinite(unit) || qty <= 0 || unit < 0) return 0;
  return qty * unit;
}

function billLineTax(line: BillLineDraft) {
  const rate = line.taxRate.trim() === '' ? 0 : Number(line.taxRate);
  if (!Number.isFinite(rate) || rate < 0) return 0;
  return billLineMerch(line) * (rate / 100);
}

function billLineTotal(line: BillLineDraft) {
  const disc = Math.max(0, Number(line.discount) || 0);
  return Math.max(billLineMerch(line) + billLineTax(line) - disc, 0);
}

function isValidBillLine(line: BillLineDraft) {
  const qty = Number(line.qty);
  const unit = Number(line.unitCost);
  const disc = Number(line.discount);
  const tax = line.taxRate.trim() === '' ? 0 : Number(line.taxRate);
  return (
    Boolean(line.productId.trim()) &&
    Number.isFinite(qty) &&
    qty > 0 &&
    Number.isFinite(unit) &&
    unit >= 0 &&
    Number.isFinite(disc) &&
    disc >= 0 &&
    Number.isFinite(tax) &&
    tax >= 0
  );
}

function friendlyPurchaseError(raw: unknown): string {
  const m = String((raw as { message?: string })?.message || raw || 'Something went wrong. Try again.');
  if (/nothing left to receive/i.test(m)) return 'This order is already fully received.';
  if (/already received|fully received|409/i.test(m)) return 'Those goods were already received. Refresh the list.';
  if (/rejection reason/i.test(m)) return 'Add a reason for any rejected quantity.';
  if (/batch number required/i.test(m)) return m;
  if (/cannot reach|failed to fetch/i.test(m)) {
    return 'Cannot reach the server. Check your connection and try again.';
  }
  return m;
}

/** Keep aligned with backend SystemRoleValue / rbac.VALID_ROLES (PR approval matrix). */
const SYSTEM_ROLES = [
  'super_admin',
  'platform_owner',
  'platform_admin',
  'platform_support',
  'platform_finance',
  'company_admin',
  'store_manager',
  'sales_officer',
  'inventory_officer',
  'accountant',
  'cashier',
  'hotel_manager',
] as const;

type Supplier = {
  id: string;
  name: string;
  code?: string | null;
  email?: string | null;
  profile_type?: string | null;
  category?: string | null;
  status?: string | null;
  total_paid?: number;
  amount_left?: number;
  base_currency?: string;
  totals_by_currency?: { currency: string; total_paid: number; amount_left: number }[];
};
type Product = { id: string; name: string; sku: string; cost_price: number; tracks_batches?: boolean; is_active?: boolean };
type PurchaseRequest = {
  id: string;
  request_number: string;
  status: string;
  preferred_supplier_id?: string | null;
  department?: string | null;
  notes?: string | null;
  rejection_reason?: string | null;
  converted_po_id?: string | null;
  approval_step?: number;
  approval_steps_required?: number;
  awaiting_level?: number | null;
  awaiting_roles?: string[];
  items: { id: string; product_id: string; quantity: number; product_name?: string }[];
  purchase_order?: { id: string; po_number: string };
};
type PoItem = {
  id: string;
  product_id: string;
  product_name?: string;
  sku?: string;
  quantity: number;
  received_qty: number;
  unit_id?: string | null;
  unit_price: number;
  tax_rate?: number;
  discount?: number;
  line_total?: number;
  outstanding_qty: number;
};
type Unit = { id: string; code: string; name: string; is_active?: boolean };
type PoAmendment = {
  id: string;
  revision_no: number;
  reason?: string | null;
  notified_supplier?: boolean;
  emailed_to?: string | null;
  created_at?: string;
};
type PurchaseOrder = {
  id: string;
  po_number: string;
  supplier_id: string;
  status: string;
  total_amount: number;
  paid_amount?: number;
  balance_due?: number;
  notes?: string | null;
  delivery_address?: string | null;
  due_date?: string | null;
  revision_no?: number;
  can_amend?: boolean;
  can_cancel?: boolean;
  amendments?: PoAmendment[];
  emailed_at?: string | null;
  emailed_to?: string | null;
  delivery?: { to?: string; mode?: string };
  created_at?: string;
  items: PoItem[];
};
type GrnItem = {
  id: string;
  product_id: string;
  product_name?: string;
  sku?: string;
  accepted_qty: number;
  remaining_return_qty?: number;
  received_qty: number;
  rejected_qty?: number;
  rejection_reason?: string | null;
  batch_number?: string | null;
  manufacturing_date?: string | null;
  expiry_date?: string | null;
};
type Grn = {
  id: string;
  grn_number: string;
  purchase_order_id: string;
  supplier_id: string;
  status: string;
  items: GrnItem[];
  created_at?: string;
  received_at?: string;
};
type PurchaseReturn = {
  id: string;
  return_number: string;
  debit_note_number?: string;
  supplier_id?: string | null;
  goods_receipt_id: string;
  status: string;
  reason: string;
  total_amount: number;
  discount_amount?: number;
  subtotal?: number;
  tax_amount?: number;
  can_cancel?: boolean;
  notes?: string | null;
  created_at?: string;
};
type PurchaseInvoice = {
  id: string;
  invoice_number: string;
  supplier_id: string;
  purchase_order_id?: string | null;
  supplier_invoice_number?: string;
  goods_receipt_id?: string;
  status: string;
  total_amount: number;
  tax_amount?: number;
  reverse_charge_tax?: number;
  is_reverse_charge?: boolean;
  paid_amount: number;
  balance_due: number;
  ap_posted: boolean;
  currency?: string | null;
  exchange_rate?: number | null;
  has_attachment?: boolean;
  attachment_url?: string | null;
  subtotal?: number;
  discount_amount?: number;
  can_cancel?: boolean;
  notes?: string | null;
  created_at?: string;
  invoice_date?: string | null;
  warehouse_id?: string | null;
  store_id?: string | null;
  items?: {
    id: string;
    product_id: string;
    product_name?: string;
    sku?: string;
    quantity: number;
    unit_price: number;
    tax_rate: number;
    discount?: number;
    line_subtotal?: number;
    line_tax?: number;
    line_total: number;
    tax_components?: { name?: string; code?: string; amount?: number }[] | null;
  }[];
  tax_breakdown?: {
    by_rate?: { tax_rate: number; taxable: number; tax: number }[];
    tax_amount?: number;
    reverse_charge_tax?: number;
    is_reverse_charge?: boolean;
  };
};

export default function Page() {
  const { storeId } = useStoreContext();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>('suppliers');
  const [poPrefix, setPoPrefix] = useState('');
  const [poNext, setPoNext] = useState('');
  const [grnPrefix, setGrnPrefix] = useState('');
  const [piPrefix, setPiPrefix] = useState('');
  const [prPrefix, setPrPrefix] = useState('');
  const [pretPrefix, setPretPrefix] = useState('');
  const [dnPrefix, setDnPrefix] = useState('');
  const [spPrefix, setSpPrefix] = useState('');
  useEffect(() => {
    const next = searchParams.get('tab');
    if (isPurchasingTab(next) && next !== tab) setTab(next);
  }, [searchParams, tab]);
  function selectTab(id: Tab) {
    setTab(id);
    if (id !== 'suppliers') setSupplierDrawer(false);
    router.replace(`/purchasing?tab=${id}`, { scroll: false });
  }
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [poManageFilter, setPoManageFilter] = useState<
    'all' | 'draft' | 'sent' | 'partially_received' | 'received' | 'cancelled'
  >('all');
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [prManageFilter, setPrManageFilter] = useState<
    'all' | 'draft' | 'pending' | 'approved' | 'rejected' | 'converted'
  >('all');
  const formatPrefs = useCompanyFormat();
  const [grns, setGrns] = useState<Grn[]>([]);
  const [invoices, setInvoices] = useState<PurchaseInvoice[]>([]);
  const [piManageFilter, setPiManageFilter] = useState<
    'all' | 'draft' | 'unpaid' | 'partial' | 'paid' | 'overdue' | 'cancelled'
  >('all');
  const [selectedInvoice, setSelectedInvoice] = useState<PurchaseInvoice | null>(null);
  const [returns, setReturns] = useState<PurchaseReturn[]>([]);
  const [returnManageFilter, setReturnManageFilter] = useState<
    'all' | 'draft' | 'posted' | 'cancelled'
  >('all');
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [warehouses, setWarehouses] = useState<any[]>([]);
  const [warehouseId, setWarehouseId] = useState('');
  const [billWarehouseId, setBillWarehouseId] = useState('');
  const [hideWarehouseUx, setHideWarehouseUx] = useState(false);
  const storeWarehouses = useMemo(
    () => warehouses.filter((w: any) => !w.store_id || !storeId || String(w.store_id) === String(storeId)),
    [warehouses, storeId],
  );
  useEffect(() => {
    getMe()
      .then((r) => setHideWarehouseUx(!tenantIsMultiStore(r.data)))
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!storeWarehouses.length) {
      if (warehouseId) setWarehouseId('');
      return;
    }
    if (!hideWarehouseUx && !storeId) {
      if (warehouseId) setWarehouseId('');
      return;
    }
    const ids = new Set(storeWarehouses.map((w: any) => String(w.id)));
    const pick = (cur: string) => (cur && ids.has(String(cur)) ? cur : String(storeWarehouses[0].id));
    setWarehouseId((cur) => pick(cur));
  }, [hideWarehouseUx, storeId, storeWarehouses, warehouseId]);
  useEffect(() => {
    if (!storeWarehouses.length) {
      if (billWarehouseId) setBillWarehouseId('');
      return;
    }
    if (!hideWarehouseUx && !storeId) {
      if (billWarehouseId) setBillWarehouseId('');
      return;
    }
    const ids = new Set(storeWarehouses.map((w: any) => String(w.id)));
    const pick = (cur: string) => (cur && ids.has(String(cur)) ? cur : String(storeWarehouses[0].id));
    setBillWarehouseId((cur) => pick(cur));
  }, [hideWarehouseUx, storeId, storeWarehouses, billWarehouseId]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [selected, setSelected] = useState<PurchaseOrder | null>(null);
  const [receiveOrderId, setReceiveOrderId] = useState('');
  const [receiveDrafts, setReceiveDrafts] = useState<
    Record<
      string,
      {
        received: string;
        accepted: string;
        rejected: string;
        reason: string;
        batch: string;
        mfg: string;
        expiry: string;
      }
    >
  >({});
  const [supplierId, setSupplierId] = useState('');
  const [supplierManageFilter, setSupplierManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [supplierName, setSupplierName] = useState('');
  const [supplierCode, setSupplierCode] = useState('');
  const [supplierEmail, setSupplierEmail] = useState('');
  const [supplierPhone, setSupplierPhone] = useState('');
  const [supplierAddress, setSupplierAddress] = useState('');
  const [supplierProfileType, setSupplierProfileType] = useState('registered');
  const [supplierCategory, setSupplierCategory] = useState('');
  const [supplierStatus, setSupplierStatus] = useState('active');
  const [supplierLat, setSupplierLat] = useState('');
  const [supplierLng, setSupplierLng] = useState('');
  const [supplierTermsDays, setSupplierTermsDays] = useState('30');
  const [poLines, setPoLines] = useState<PoLineDraft[]>(() => [emptyPoLine()]);
  const [poDeliveryAddress, setPoDeliveryAddress] = useState('');
  const [poNotes, setPoNotes] = useState('');
  const [amendLines, setAmendLines] = useState<AmendLineDraft[]>(() => [emptyAmendLine()]);
  const [amendNotes, setAmendNotes] = useState('');
  const [amendDeliveryAddress, setAmendDeliveryAddress] = useState('');
  const [amendDueDate, setAmendDueDate] = useState('');
  const [amendReason, setAmendReason] = useState('');
  const [amendNotify, setAmendNotify] = useState(false);
  const [prSupplierId, setPrSupplierId] = useState('');
  const [prLines, setPrLines] = useState<PrLineDraft[]>(() => [emptyPrLine()]);
  const [prDepartment, setPrDepartment] = useState('');
  const [prNotes, setPrNotes] = useState('');
  const [prRequiredDate, setPrRequiredDate] = useState('');
  const [prBusy, setPrBusy] = useState('');
  const [prRejectReason, setPrRejectReason] = useState('');
  const [poCancelReason, setPoCancelReason] = useState('');
  const [piCancelReason, setPiCancelReason] = useState('');
  const [prCancelReason, setPrCancelReason] = useState('');
  const [poEmailTo, setPoEmailTo] = useState('');
  const [poOptionsOpen, setPoOptionsOpen] = useState(false);
  const [amendEmailTo, setAmendEmailTo] = useState('');
  const [prLevels, setPrLevels] = useState<{ roles: string[]; label?: string }[]>([
    { roles: ['store_manager'], label: 'Store Manager' },
    { roles: ['company_admin', 'super_admin'], label: 'Company Admin' },
  ]);
  const [grnId, setGrnId] = useState('');
  const [returnLines, setReturnLines] = useState<ReturnLineDraft[]>(() => [emptyReturnLine()]);
  const [returnReason, setReturnReason] = useState('');
  const [returnNotes, setReturnNotes] = useState('');
  const [invoiceGrnId, setInvoiceGrnId] = useState('');
  const [supplierInvoiceNo, setSupplierInvoiceNo] = useState('');
  const [invNotes, setInvNotes] = useState('');
  const [invAttachmentUrl, setInvAttachmentUrl] = useState('');
  const [grnNotes, setGrnNotes] = useState('');
  const [manualInvSupplierId, setManualInvSupplierId] = useState('');
  const [billLines, setBillLines] = useState<BillLineDraft[]>([]);
  const [billPickProductId, setBillPickProductId] = useState('');
  const [billPickQty, setBillPickQty] = useState('1');
  const [billPickUnitCost, setBillPickUnitCost] = useState('0');
  const [billPickTax, setBillPickTax] = useState('');
  const [billPickDiscount, setBillPickDiscount] = useState('0');
  const [manualInvHeaderDiscount, setManualInvHeaderDiscount] = useState('0');
  const [grnInvHeaderDiscount, setGrnInvHeaderDiscount] = useState('0');
  const [invCurrency, setInvCurrency] = useState('');
  const [invExchangeRate, setInvExchangeRate] = useState('');
  const [manualInvRc, setManualInvRc] = useState(false);
  const billPreview = useMemo(() => {
    const lines = billLines.filter(isValidBillLine);
    const subtotal = lines.reduce((sum, line) => sum + billLineMerch(line), 0);
    const lineDiscount = lines.reduce((sum, line) => sum + Math.max(0, Number(line.discount) || 0), 0);
    const tax = lines.reduce((sum, line) => sum + billLineTax(line), 0);
    const headerDiscount = Math.max(0, Number(manualInvHeaderDiscount) || 0);
    const total = manualInvRc
      ? Math.max(subtotal - headerDiscount, 0)
      : Math.max(subtotal + tax - headerDiscount, 0);
    return { lines, subtotal, lineDiscount, tax, headerDiscount, total };
  }, [billLines, manualInvHeaderDiscount, manualInvRc]);
  const [ocrFor, setOcrFor] = useState<string | null>(null);
  const [ocrDraft, setOcrDraft] = useState<{
    supplier_invoice_number: string;
    notes: string;
    invoice_date: string;
  } | null>(null);
  const [ocrMeta, setOcrMeta] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [attachPreview, setAttachPreview] = useState<{ apiPath: string; title: string } | null>(null);
  const [saveBusy, setSaveBusy] = useState(false);
  const [listQuery, setListQuery] = useState('');
  const [supplierDrawer, setSupplierDrawer] = useState(false);
  const [prCreateOpen, setPrCreateOpen] = useState(false);
  const [poCreateOpen, setPoCreateOpen] = useState(false);
  const [billCreateOpen, setBillCreateOpen] = useState(false);
  const [billManualOpen, setBillManualOpen] = useState(false);
  const [returnCreateOpen, setReturnCreateOpen] = useState(false);
  const paintGet = useMemo(() => createPaintGet(), []);

  async function refresh() {
    const get = paintGet.get;
    const peekPo = peekPrefetch('/purchasing/orders');
    if (peekPo?.data) setOrders(asList<PurchaseOrder>(peekPo.data));
    const peekSup = peekPrefetch('/suppliers');
    if (peekSup?.data) setSuppliers(asList<Supplier>(peekSup.data));
    const [poRes, prRes, settingsRes, supRes, prodRes, unitRes, whRes, grnRes, invRes, retRes] =
      await Promise.all([
      get('/purchasing/orders'),
      get('/purchasing/requests'),
      get('/purchasing/requests/settings'),
      get('/suppliers'),
      get('/products'),
      get('/catalog/units').catch(() => ({ data: [] })),
      get('/warehouses').catch(() => ({ data: [] })),
      get('/purchasing/grn'),
      get('/purchasing/invoices'),
      get('/purchasing/returns'),
    ]);
    paintGet.done();
    setOrders(asList<PurchaseOrder>(poRes.data));
    setRequests(asList<PurchaseRequest>(prRes.data));
    setPrLevels(settingsRes.data?.levels || []);
    setSuppliers(asList<Supplier>(supRes.data));
    setProducts(asList<Product>(prodRes.data));
    setUnits(asList<Unit>(unitRes.data).filter((u) => u.is_active !== false));
    setWarehouses(asList(whRes.data));
    setGrns(asList<Grn>(grnRes.data));
    setInvoices(asList<PurchaseInvoice>(invRes.data));
    setReturns(asList<PurchaseReturn>(retRes.data));
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  async function createSupplier() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setSaveBusy(true);
    try {
      const r = await api('/suppliers', {
        method: 'POST',
        body: JSON.stringify({
          name: supplierName.trim(),
          code: supplierCode.trim() || null,
          profile_type: supplierProfileType || 'registered',
          category: supplierCategory.trim() || null,
          status: supplierStatus || 'active',
          email: supplierEmail.trim() || null,
          phone: supplierPhone.trim() || null,
          // null when blank so Create does not 422 (AddressValue).
          address: supplierAddress.trim() || null,
          latitude: supplierLat === '' ? null : Number(supplierLat),
          longitude: supplierLng === '' ? null : Number(supplierLng),
          payment_terms_days: Number(supplierTermsDays) || 0,
        }),
      });
      setSupplierId(r.data.id);
      setSupplierName('');
      setSupplierCode('');
      setSupplierEmail('');
      setSupplierPhone('');
      setSupplierAddress('');
      setSupplierProfileType('registered');
      setSupplierCategory('');
      setSupplierStatus('active');
      setSupplierLat('');
      setSupplierLng('');
      setSupplierTermsDays('30');
      await refresh();
      setMessage('Supplier created');
      setSupplierDrawer(false);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setSaveBusy(false);
    }
  }

  async function setSupplierActive(isActive: boolean) {
    if (!supplierId) {
      setError('Select a supplier first');
      return;
    }
    setError('');
    try {
      const r = await api(`/suppliers/${supplierId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: isActive ? 'active' : 'inactive' }),
      });
      await refresh();
      setMessage(
        isActive
          ? `Supplier ${r.data?.name || ''} activated`
          : `Supplier ${r.data?.name || ''} deactivated`,
      );
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function createPo() {
    if (saveBusy) return;
    const lines = poLines.filter(isValidPoLine);
    if (!supplierId.trim()) {
      setError('Select a supplier first.');
      return;
    }
    if (!lines.length) {
      setError('Add at least one product line with quantity and unit price.');
      return;
    }
    setError('');
    setMessage('');
    setSaveBusy(true);
    try {
      const r = await api('/purchasing/orders', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: supplierId.trim(),
          // null when blank so Create does not 422 (AddressValue).
          delivery_address: poDeliveryAddress.trim() || null,
          notes: poNotes.trim() || null,
          warehouse_id: warehouseId.trim() || null,
          items: lines.map((line) => ({
            product_id: line.productId.trim(),
            quantity: Number(line.qty),
            unit_id: line.unitId.trim() || null,
            unit_price: Number(line.unitPrice),
            discount: Math.max(0, Number(line.discount) || 0),
            // tax is resolved from product or company default
          })),
        }),
      });
      const noEmail = !(suppliers.find((s) => s.id === supplierId)?.email || '').trim();
      setMessage(
        noEmail
          ? `Created ${r.data.po_number}. Print the order and hand it to the supplier. When they deliver, receive the goods.`
          : `Created ${r.data.po_number}. Email or print the order. When the supplier delivers, receive the goods.`,
      );
      setPoDeliveryAddress('');
      setPoNotes('');
      setWarehouseId('');
      setPoLines([emptyPoLine()]);
      await refresh();
      setSelected(r.data);
      setTab('orders');
      setPoCreateOpen(false);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setSaveBusy(false);
    }
  }

  async function printPo(po: PurchaseOrder) {
    setError('');
    try {
      let current = po;
      if (po.status === 'draft') {
        const issued = await api(`/purchasing/orders/${po.id}/issue`, { method: 'POST' });
        current = issued.data;
      }
      await openPurchasingPrint(`/purchasing/orders/${current.id}/print?format=pdf`);
      setMessage(
        `${current.po_number} is ready to print. Hand the paper to the supplier. When they deliver, receive the goods.`,
      );
      await refresh();
      setSelected(current);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function sendPo(poId: string, resend = false) {
    setError('');
    try {
      const qs = poEmailTo.trim() ? `?to=${encodeURIComponent(poEmailTo.trim())}` : '';
      const r = await api(`/purchasing/orders/${poId}/send${qs}`, { method: 'POST' });
      const to = r.data?.delivery?.to || r.data?.emailed_to || 'supplier';
      const mode = r.data?.delivery?.mode ? ` (${r.data.delivery.mode})` : '';
      setMessage(
        resend
          ? `Re-emailed ${r.data.po_number} to ${to}${mode}`
          : `Emailed ${r.data.po_number} to ${to}${mode}`,
      );
      await refresh();
      setSelected(r.data);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function sendPurchasingDoc(path: string, okMessage: string) {
    setError('');
    try {
      const qs = poEmailTo.trim() ? `?to=${encodeURIComponent(poEmailTo.trim())}` : '';
      const r = await api(`${path}${qs}`, { method: 'POST' });
      const to = r.data?.delivery?.to || r.data?.emailed_to || 'recipient';
      setMessage(r.message || `${okMessage} ${to}`);
      await refresh();
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function cancelPo(po: PurchaseOrder) {
    setError('');
    setMessage('');
    const reason = poCancelReason.trim();
    if (!reason) {
      setPoOptionsOpen(true);
      setError('Enter a cancel reason before cancelling a purchase order');
      return;
    }
    try {
      const r = await api(`/purchasing/orders/${po.id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setMessage(r.message || `Cancelled ${r.data?.po_number || po.po_number}`);
      setPoCancelReason('');
      await refresh();
      setSelected(r.data);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  function openAmend(po: PurchaseOrder) {
    setSelected(po);
    const drafts: Record<
      string,
      {
        received: string;
        accepted: string;
        rejected: string;
        reason: string;
        batch: string;
        mfg: string;
        expiry: string;
      }
    > = {};
    for (const i of po.items.filter((x) => x.outstanding_qty > 0)) {
      const out = String(i.outstanding_qty);
      drafts[i.id] = {
        received: out,
        accepted: out,
        rejected: '0',
        reason: '',
        batch: '',
        mfg: '',
        expiry: '',
      };
    }
    setReceiveDrafts(drafts);
    setAmendLines(amendLinesFromPo(po));
    setAmendNotes(po.notes || '');
    setAmendDeliveryAddress(po.delivery_address || '');
    setAmendDueDate(po.due_date ? String(po.due_date).slice(0, 10) : '');
    setAmendReason('');
    setAmendNotify(po.status === 'sent');
  }

  async function amendPo() {
    if (!selected?.id || !selected.items?.length) return;
    setError('');
    setMessage('');
    const reason = amendReason.trim();
    if (!reason) {
      setError('Enter an amendment reason before saving');
      return;
    }
    const lines = amendLines.filter((line) => line.productId.trim());
    if (!lines.length) {
      setError('Add at least one product before saving the amendment');
      return;
    }
    try {
      const r = await api(`/purchasing/orders/${selected.id}/amend`, {
        method: 'POST',
        body: JSON.stringify({
          reason,
          notes: amendNotes.trim() || null,
          // Omit blank delivery so Amend does not 422 (AddressValue); leave prior.
          ...(amendDeliveryAddress.trim()
            ? { delivery_address: amendDeliveryAddress.trim() }
            : {}),
          // Omit blank due date so Amend does not 422 (IsoDateQueryValue); leave prior.
          ...(amendDueDate.trim() ? { due_date: amendDueDate.trim() } : {}),
          notify_supplier: amendNotify,
          ...(amendNotify && amendEmailTo.trim()
            ? { to: amendEmailTo.trim() }
            : {}),
          items: lines.map((line) => ({
            product_id: line.productId.trim(),
            quantity: Number(line.qty),
            unit_id: line.unitId.trim() || null,
            unit_price: Number(line.unitPrice),
            discount: Math.max(0, Number(line.discount) || 0),
            ...(line.taxRate.trim() ? { tax_rate: Number(line.taxRate) } : {}),
          })),
        }),
      });
      const rev = r.data?.revision_no ?? r.data?.amendment?.revision_no;
      setMessage(r.message || `Amended ${r.data.po_number} (rev.${rev})`);
      setAmendReason('');
      await refresh();
      setSelected(r.data);
      if (r.data?.items) setAmendLines(amendLinesFromPo(r.data));
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function receiveAll(po: PurchaseOrder) {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setSaveBusy(true);
    try {
      const items = po.items
        .filter((i) => i.outstanding_qty > 0)
        .map((i) => {
          const d = receiveDrafts[i.id] || {
            received: String(i.outstanding_qty),
            accepted: String(i.outstanding_qty),
            rejected: '0',
            reason: '',
            batch: '',
            mfg: '',
            expiry: '',
          };
          const product = products.find((p) => p.id === i.product_id);
          if (product?.tracks_batches && !(d.batch || '').trim()) {
            throw new Error(`Batch number required for ${product.name || i.product_id}`);
          }
          return {
            // trim so Post GRN / Receive all (UuidIdValue po_item_id) do not 422
            po_item_id: String(i.id).trim(),
            received_qty: i.outstanding_qty,
            accepted_qty: i.outstanding_qty,
            rejected_qty: 0,
            batch_number: d.batch.trim() || undefined,
            manufacturing_date: d.mfg.trim() || undefined,
            expiry_date: d.expiry.trim() || undefined,
          };
        });
      if (!items.length) {
        setError('Nothing left to receive');
        setSaveBusy(false);
        return;
      }
      const r = await api('/purchasing/grn', {
        method: 'POST',
        body: JSON.stringify({
          // trim so Post GRN (UuidIdValue purchase_order_id) does not 422 on whitespace
          purchase_order_id: String(po.id).trim(),
          notes: grnNotes.trim() || null,
          items,
        }),
      });
      setMessage(`Posted ${r.data.grn_number}. Add the supplier bill for every accepted line.`);
      if (r.data?.id) setInvoiceGrnId(String(r.data.id));
      setGrnNotes('');
      await refresh();
      const updated = await api(`/purchasing/orders/${po.id}`);
      setSelected(updated.data);
      focusReceivedOrder(updated.data);
      selectTab('grn');
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setSaveBusy(false);
    }
  }

  async function postPartialReceive(po: PurchaseOrder) {
    if (saveBusy) return;
    setError('');
    setMessage('');
    setSaveBusy(true);
    try {
      const items = po.items
        .filter((i) => i.outstanding_qty > 0)
        .map((i) => {
          const d = receiveDrafts[i.id] || {
            received: String(i.outstanding_qty),
            accepted: String(i.outstanding_qty),
            rejected: '0',
            reason: '',
            batch: '',
            mfg: '',
            expiry: '',
          };
          const received_qty = Number(d.received) || 0;
          const accepted_qty = Number(d.accepted) || 0;
          const rejected_qty = Number(d.rejected) || 0;
          const effectiveRejected =
            rejected_qty > 0
              ? rejected_qty
              : accepted_qty < received_qty
                ? received_qty - accepted_qty
                : 0;
          if (effectiveRejected > 0 && !d.reason.trim()) {
            throw new Error('Enter a rejection reason for lines with rejected qty');
          }
          const product = products.find((p) => p.id === i.product_id);
          if (accepted_qty > 0 && product?.tracks_batches && !(d.batch || '').trim()) {
            throw new Error(`Batch number required for ${product.name || i.product_id}`);
          }
          return {
            // trim so Post GRN (UuidIdValue po_item_id) does not 422 on whitespace
            po_item_id: String(i.id).trim(),
            received_qty,
            accepted_qty,
            rejected_qty,
            rejection_reason: d.reason.trim() || undefined,
            batch_number: d.batch.trim() || undefined,
            manufacturing_date: d.mfg.trim() || undefined,
            expiry_date: d.expiry.trim() || undefined,
          };
        })
        .filter((i) => i.received_qty > 0);
      if (!items.length) {
        setError('Enter a received quantity on at least one line');
        setSaveBusy(false);
        return;
      }
      const r = await api('/purchasing/grn', {
        method: 'POST',
        body: JSON.stringify({
          // trim so Post GRN (UuidIdValue purchase_order_id) does not 422 on whitespace
          purchase_order_id: String(po.id).trim(),
          notes: grnNotes.trim() || null,
          items,
        }),
      });
      const rejectedLines = (r.data.items || []).filter((x: GrnItem) => (x.rejected_qty || 0) > 0);
      setMessage(
        rejectedLines.length
          ? `Posted ${r.data.grn_number} (${rejectedLines.length} line(s) with rejected qty). Add the supplier bill for every accepted line.`
          : `Posted ${r.data.grn_number}. Add the supplier bill for every accepted line.`
      );
      if (r.data?.id) setInvoiceGrnId(String(r.data.id));
      setGrnNotes('');
      await refresh();
      const updated = await api(`/purchasing/orders/${po.id}`);
      setSelected(updated.data);
      focusReceivedOrder(updated.data);
      selectTab('grn');
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setSaveBusy(false);
    }
  }

  async function createReturn() {
    if (saveBusy) return;
    setError('');
    setMessage('');
    if (!returnReason.trim()) {
      setError('Select a return reason');
      return;
    }
    const lines = returnLines.filter((line) => line.grnItemId.trim() && Number(line.qty) > 0);
    if (!lines.length) {
      setError('Enter a return quantity on at least one product');
      return;
    }
    for (const line of lines) {
      const source = (selectedGrn?.items || []).find((i) => i.id === line.grnItemId);
      const remaining = Number(source?.remaining_return_qty ?? source?.accepted_qty ?? 0);
      const qty = Number(line.qty);
      if (!Number.isFinite(qty) || qty <= 0) {
        setError('Return quantity must be positive');
        return;
      }
      if (qty > remaining + 1e-9) {
        setError(`Return quantity cannot exceed remaining accepted qty (${remaining})`);
        return;
      }
    }
    setSaveBusy(true);
    try {
      const r = await api('/purchasing/returns', {
        method: 'POST',
        body: JSON.stringify({
          // trim so Draft return (UuidIdValue goods_receipt_id) does not 422 on whitespace
          goods_receipt_id: grnId.trim(),
          reason: returnReason,
          notes: returnNotes.trim() || null,
          items: lines.map((line) => ({
            goods_receipt_item_id: line.grnItemId.trim(),
            quantity: Number(line.qty),
          })),
        }),
      });
      setMessage(`Return ${r.data.return_number} drafted`);
      setReturnReason('');
      setReturnNotes('');
      setTab('returns');
      await refresh();
      setReturnCreateOpen(false);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setSaveBusy(false);
    }
  }

  async function createInvoiceFromGrn() {
    if (saveBusy) return;
    setError('');
    setSaveBusy(true);
    try {
      const headerDisc = Math.max(0, Number(grnInvHeaderDiscount) || 0);
      const r = await api('/purchasing/invoices', {
        method: 'POST',
        body: JSON.stringify({
          // trim so Draft from GRN (UuidIdValue goods_receipt_id) does not 422
          goods_receipt_id: invoiceGrnId.trim(),
          supplier_invoice_number: supplierInvoiceNo.trim() || null,
          notes: invNotes.trim() || null,
          attachment_url: invAttachmentUrl.trim() || null,
          discount_amount: headerDisc,
          currency: invCurrency.trim() || null,
          exchange_rate: invExchangeRate === '' ? null : Number(invExchangeRate),
        }),
      });
      setMessage(
        `Invoice ${r.data.invoice_number} drafted` +
          (r.data.currency ? ` (${r.data.currency} @ ${r.data.exchange_rate})` : '')
      );
      setTab('invoices');
      setSupplierInvoiceNo('');
      setInvNotes('');
      setInvAttachmentUrl('');
      setGrnInvHeaderDiscount('0');
      setInvCurrency('');
      setInvExchangeRate('');
      await refresh();
      setBillCreateOpen(false);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setSaveBusy(false);
    }
  }

  function addBillProduct() {
    const productId = billPickProductId.trim();
    const product = products.find((p) => p.id === productId);
    if (!product) {
      setError('Choose a product first');
      return;
    }
    const draft: BillLineDraft = {
      ...emptyBillLine(),
      productId,
      qty: billPickQty,
      unitCost: billPickUnitCost,
      taxRate: billPickTax,
      discount: billPickDiscount,
    };
    if (!isValidBillLine(draft)) {
      setError('Add at least one product line with quantity and unit cost.');
      return;
    }
    setError('');
    setBillLines((rows) => [...rows, draft]);
    setBillPickProductId('');
    setBillPickQty('1');
    setBillPickUnitCost('0');
    setBillPickTax('');
    setBillPickDiscount('0');
  }

  async function createManualInvoice() {
    if (saveBusy) return;
    setError('');
    const lines = billLines.filter(isValidBillLine);
    if (lines.length < 1) {
      setError('Add at least one product line with quantity and unit cost.');
      return;
    }
    setSaveBusy(true);
    try {
      const headerDisc = Math.max(0, Number(manualInvHeaderDiscount) || 0);
      const r = await api('/purchasing/invoices', {
        method: 'POST',
        body: JSON.stringify({
          // trim so Draft manual PI (UuidIdValue supplier_id / product_id) does not 422
          supplier_id: manualInvSupplierId.trim(),
          supplier_invoice_number: supplierInvoiceNo.trim() || null,
          notes: invNotes.trim() || null,
          attachment_url: invAttachmentUrl.trim() || null,
          is_reverse_charge: manualInvRc,
          discount_amount: headerDisc,
          currency: invCurrency.trim() || null,
          exchange_rate: invExchangeRate === '' ? null : Number(invExchangeRate),
          warehouse_id: billWarehouseId.trim() || null,
          store_id: storeId || null,
          items: lines.map((line) => ({
            product_id: line.productId.trim(),
            quantity: Number(line.qty),
            unit_price: Number(line.unitCost),
            discount: Math.max(0, Number(line.discount) || 0),
            ...(line.taxRate.trim() !== '' ? { tax_rate: Number(line.taxRate) } : {}),
          })),
        }),
      });
      setMessage(
        `Invoice ${r.data.invoice_number} drafted` +
          (r.data.is_reverse_charge ? ` (RC tax ${r.data.reverse_charge_tax})` : '') +
          (r.data.currency ? ` (${r.data.currency} @ ${r.data.exchange_rate})` : '')
      );
      setTab('invoices');
      setSupplierInvoiceNo('');
      setInvNotes('');
      setInvAttachmentUrl('');
      setBillLines([]);
      setBillPickProductId('');
      setBillPickQty('1');
      setBillPickUnitCost('0');
      setBillPickTax('');
      setBillPickDiscount('0');
      setManualInvHeaderDiscount('0');
      setManualInvRc(false);
      setInvCurrency('');
      setInvExchangeRate('');
      await refresh();
      setBillManualOpen(false);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setSaveBusy(false);
    }
  }

  async function approveInvoice(id: string) {
    setError('');
    try {
      const r = await api(`/purchasing/invoices/${id}/approve`, { method: 'POST', body: '{}' });
      setMessage(`Approved ${r.data.invoice_number}`);
      await refresh();
      if (selectedInvoice?.id === id) setSelectedInvoice(r.data);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function cancelInvoice(inv: PurchaseInvoice) {
    setError('');
    setMessage('');
    const reason = piCancelReason.trim();
    if (!reason) {
      setError('Enter a cancel reason before cancelling a purchase invoice');
      return;
    }
    try {
      const r = await api(`/purchasing/invoices/${inv.id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setMessage(r.message || `Cancelled ${r.data?.invoice_number || inv.invoice_number}`);
      setPiCancelReason('');
      await refresh();
      setSelectedInvoice(r.data);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function uploadInvoiceAttachment(id: string, file: File) {
    setError('');
    try {
      const body = await uploadAttachment(`/purchasing/invoices/${id}/attachment`, file);
      setMessage(`Attachment uploaded for ${body.data?.invoice_number || id}`);
      await refresh();
    } catch (err: any) {
      setError(typeof err.message === 'string' ? err.message : 'Upload failed');
    }
  }

  async function downloadInvoiceAttachment(id: string) {
    setError('');
    try {
      const { blob, filename } = await fetchAttachment(`/purchasing/invoices/${id}/attachment`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || `invoice-${id.slice(0, 8)}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function suggestInvoiceOcr(id: string) {
    setError('');
    setMessage('');
    try {
      const r = await api(`/purchasing/invoices/${id}/ocr-suggest`, { method: 'POST', body: '{}' });
      const s = r.data?.suggestions || {};
      setOcrFor(id);
      setOcrMeta(r.data);
      setOcrDraft({
        supplier_invoice_number: s.supplier_invoice_number || '',
        notes: s.notes || '',
        invoice_date: s.invoice_date || '',
      });
      setMessage(
        r.data?.warnings?.length
          ? `OCR ready (${r.data.engine}) — ${r.data.warnings[0]}`
          : `OCR suggestions ready (${r.data?.engine || 'ocr'})`,
      );
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function applyInvoiceOcr() {
    if (!ocrFor || !ocrDraft) return;
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = {};
      if (ocrDraft.supplier_invoice_number.trim() !== '') {
        body.supplier_invoice_number = ocrDraft.supplier_invoice_number.trim();
      }
      const ocrNotes = ocrDraft.notes.trim();
      if (ocrNotes !== '') body.notes = ocrNotes;
      const invoiceDate = ocrDraft.invoice_date.trim();
      if (invoiceDate !== '') body.invoice_date = invoiceDate;
      await api(`/purchasing/invoices/${ocrFor}`, { method: 'PATCH', body: JSON.stringify(body) });
      setMessage('OCR suggestions applied to draft invoice');
      setOcrFor(null);
      setOcrDraft(null);
      setOcrMeta(null);
      await refresh();
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function postReturn(id: string) {
    setError('');
    try {
      const r = await api(`/purchasing/returns/${id}/post`, { method: 'POST', body: '{}' });
      setMessage(`Posted ${r.data.return_number} / ${r.data.debit_note_number}`);
      await refresh();
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function cancelReturn(ret: PurchaseReturn) {
    setError('');
    setMessage('');
    const reason = prCancelReason.trim();
    if (!reason) {
      setError('Enter a cancel reason before cancelling a purchase return');
      return;
    }
    try {
      const r = await api(`/purchasing/returns/${ret.id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
      setMessage(r.message || `Cancelled ${r.data?.return_number || ret.return_number}`);
      setPrCancelReason('');
      await refresh();
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  async function createRequest() {
    if (saveBusy) return;
    const lines = prLines.filter((line) => line.productId.trim() && Number(line.qty) > 0);
    if (!lines.length) {
      setError('Add at least one product line.');
      return;
    }
    setError('');
    setMessage('');
    setSaveBusy(true);
    try {
      const r = await api('/purchasing/requests', {
        method: 'POST',
        body: JSON.stringify({
          preferred_supplier_id: prSupplierId.trim() || null,
          department: prDepartment.trim() || null,
          notes: prNotes.trim() || null,
          required_date: prRequiredDate.trim() || null,
          items: lines.map((line) => ({
            product_id: line.productId.trim(),
            quantity: Number(line.qty) || 1,
            notes: line.notes.trim() || null,
          })),
        }),
      });
      setMessage(`Created ${r.data.request_number}`);
      setPrNotes('');
      setPrLines([emptyPrLine()]);
      setPrRequiredDate('');
      await refresh();
      setTab('requests');
      setPrCreateOpen(false);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setSaveBusy(false);
    }
  }

  async function savePrSettings() {
    setError('');
    setMessage('');
    try {
      const r = await api('/purchasing/requests/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          levels: prLevels.map((l) => ({
            roles: l.roles,
            // null when blank so Save does not 422 (ApprovalLevelLabelValue).
            label: (l.label || '').trim() || null,
          })),
        }),
      });
      setPrLevels(r.data?.levels || []);
      setMessage(`PR approval matrix saved (${r.data?.steps_required || prLevels.length} levels)`);
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    }
  }

  function updatePrLevel(idx: number, patch: Partial<(typeof prLevels)[0]>) {
    setPrLevels((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  }

  async function prAction(id: string, action: 'submit' | 'approve' | 'reject' | 'convert') {
    setError('');
    setMessage('');
    if (action === 'reject') {
      const reason = prRejectReason.trim();
      if (!reason) {
        setError('Enter a reject reason before rejecting a purchase request');
        return;
      }
    }
    setPrBusy(`${action}:${id}`);
    try {
      const body =
        action === 'reject'
          ? JSON.stringify({ reason: prRejectReason.trim() })
          : action === 'convert'
            ? '{}'
            : '{}';
      const r = await api(`/purchasing/requests/${id}/${action}`, {
        method: 'POST',
        body,
      });
      if (action === 'reject') {
        setPrRejectReason('');
      }
      if (action === 'convert') {
        setMessage(
          `Converted ${r.data.request_number} → ${r.data.purchase_order?.po_number || 'draft PO'}`
        );
        setTab('orders');
      } else {
        setMessage(`${r.data.request_number} is now ${r.data.status}`);
      }
      await refresh();
    } catch (err: any) {
      setError(friendlyPurchaseError(err));
    } finally {
      setPrBusy('');
    }
  }

  const selectedGrn = grns.find((g) => g.id === grnId);
  const productName = (id: string, item?: { product_name?: string }) =>
    item?.product_name || products.find((p) => p.id === id)?.name || 'Item';
  const managedReturns = returns.filter((r) => {
    if (returnManageFilter === 'all') return true;
    return (r.status || 'draft') === returnManageFilter;
  });
  const managedOrders = orders.filter((o) => {
    if (poManageFilter === 'all') return true;
    return (o.status || 'draft') === poManageFilter;
  });
  const managedRequests = requests.filter((r) => {
    if (prManageFilter === 'all') return true;
    return (r.status || 'draft') === prManageFilter;
  });
  const managedInvoices = invoices.filter((inv) => {
    if (piManageFilter === 'all') return true;
    return (inv.status || 'draft') === piManageFilter;
  });

  const supplierNameOf = (id?: string | null, orderId?: string | null) => {
    const direct = suppliers.find((s) => sameParty(s.id, id));
    if (direct?.name) return direct.name;
    const order = orders.find((o) => sameParty(o.id, orderId));
    const via = suppliers.find((s) => sameParty(s.id, order?.supplier_id));
    if (via?.name) return via.name;
    if (String(id || order?.supplier_id || '').trim()) return 'Unknown supplier';
    return '—';
  };
  const billSupplierName = (inv: {
    supplier_id?: string | null;
    purchase_order_id?: string | null;
    goods_receipt_id?: string | null;
  }) => {
    const grn = grns.find((g) => sameParty(g.id, inv.goods_receipt_id));
    return supplierNameOf(inv.supplier_id, inv.purchase_order_id || grn?.purchase_order_id);
  };
  const openBillSummary = (supplierId: string) => {
    const rows = invoices.filter((inv) => {
      const owner = String(inv.supplier_id || '').trim()
        || orders.find((o) => sameParty(o.id, inv.purchase_order_id))?.supplier_id
        || '';
      return (
        sameParty(owner, supplierId) &&
        (inv.status === 'unpaid' || inv.status === 'partial' || inv.status === 'overdue')
      );
    });
    const due = rows.reduce((sum, inv) => {
      const balance = Number(inv.balance_due);
      if (Number.isFinite(balance)) return sum + balance;
      return sum + Math.max(Number(inv.total_amount || 0) - Number(inv.paid_amount || 0), 0);
    }, 0);
    return { count: rows.length, due: Math.round(due * 100) / 100 };
  };
  function focusReceivedOrder(po: PurchaseOrder | null) {
    if (po && (po.status === 'sent' || po.status === 'partially_received')) {
      setReceiveOrderId(po.id);
      const drafts: Record<
        string,
        {
          received: string;
          accepted: string;
          rejected: string;
          reason: string;
          batch: string;
          mfg: string;
          expiry: string;
        }
      > = {};
      for (const i of (po.items || []).filter((x) => x.outstanding_qty > 0)) {
        const out = String(i.outstanding_qty);
        drafts[i.id] = {
          received: out,
          accepted: out,
          rejected: '0',
          reason: '',
          batch: '',
          mfg: '',
          expiry: '',
        };
      }
      setReceiveDrafts(drafts);
      return;
    }
    setReceiveOrderId('');
    setReceiveDrafts({});
  }
  const poNumberOf = (id: string) => orders.find((o) => o.id === id)?.po_number || id.slice(0, 8);
  const productNameOf = (id: string, item?: { product_name?: string }) =>
    item?.product_name || products.find((p) => p.id === id)?.name || 'Item';
  const receivableOrders = orders.filter(
    (o) => o.status === 'sent' || o.status === 'partially_received',
  );
  const receivePo = receivableOrders.find((o) => o.id === receiveOrderId) || null;
  const openBills = invoices.filter((inv) =>
    inv.status === 'unpaid' || inv.status === 'partial' || inv.status === 'overdue',
  );
  const supplierMoney = (s: Supplier | undefined, field: 'total_paid' | 'amount_left') => {
    const lines = s?.totals_by_currency || [];
    const base = s?.base_currency || '';
    if (lines.length > 1 || (lines.length === 1 && lines[0].currency !== base)) {
      return (
        <span className="purchase-ui-money-lines">
          {lines.map((row) => (
            <span key={row.currency}>
              {row.currency} {formatNumber(row[field], formatPrefs)}
            </span>
          ))}
        </span>
      );
    }
    return formatNumber(s?.[field] ?? 0, formatPrefs);
  };
  const grnBillMoney = (grnId: string) => {
    const bills = invoices.filter(
      (inv) => inv.goods_receipt_id === grnId && inv.status !== 'cancelled' && inv.status !== 'draft',
    );
    if (bills.length === 0) return null;
    const byCurrency = new Map<string, { currency: string; paid: number; left: number }>();
    for (const inv of bills) {
      const currency = String(inv.currency || '').trim() || 'base';
      const row = byCurrency.get(currency) || { currency, paid: 0, left: 0 };
      row.paid += Number(inv.paid_amount || 0);
      const balance = Number(inv.balance_due);
      row.left += Number.isFinite(balance)
        ? balance
        : Math.max(Number(inv.total_amount || 0) - Number(inv.paid_amount || 0), 0);
      byCurrency.set(currency, row);
    }
    const lines = Array.from(byCurrency.values()).map((row) => ({
      currency: row.currency === 'base' ? '' : row.currency,
      paid: Math.round(row.paid * 100) / 100,
      left: Math.round(row.left * 100) / 100,
    }));
    if (lines.length === 1) return { paid: lines[0].paid, left: lines[0].left, lines };
    return { paid: null, left: null, lines };
  };
  const formatGrnBillField = (
    money: { paid: number | null; left: number | null; lines: { currency: string; paid: number; left: number }[] } | null,
    field: 'paid' | 'left',
  ) => {
    if (!money) return '—';
    if (money.lines.length > 1) {
      return (
        <span className="purchase-ui-money-lines">
          {money.lines.map((row) => (
            <span key={`${row.currency || 'base'}-${field}`}>
              {row.currency ? `${row.currency} ` : ''}
              {formatNumber(row[field], formatPrefs)}
            </span>
          ))}
        </span>
      );
    }
    return formatNumber(money[field] ?? 0, formatPrefs);
  };
  const purchaseHistory = useMemo(() => {
    const stamp = (iso?: string | null) => (iso ? String(iso) : '');
    const rows: { key: string; at: string; kind: string; ref: string; party: string; status: string; amount: string }[] =
      [];
    for (const o of orders) {
      rows.push({
        key: `po-${o.id}`,
        at: stamp(o.created_at),
        kind: 'Order',
        ref: o.po_number,
        party: supplierNameOf(o.supplier_id),
        status: o.status,
        amount: String(o.total_amount ?? ''),
      });
    }
    for (const g of grns) {
      rows.push({
        key: `grn-${g.id}`,
        at: stamp(g.created_at),
        kind: 'Received',
        ref: g.grn_number,
        party: supplierNameOf(g.supplier_id, g.purchase_order_id),
        status: g.status,
        amount: String((g.items || []).reduce((s, i) => s + Number(i.accepted_qty || 0), 0)),
      });
    }
    for (const inv of invoices) {
      rows.push({
        key: `inv-${inv.id}`,
        at: stamp(inv.created_at || inv.invoice_date),
        kind: 'Bill',
        ref: inv.invoice_number,
        party: billSupplierName(inv),
        status: inv.status,
        amount: String(inv.total_amount ?? ''),
      });
    }
    for (const ret of returns) {
      const g = grns.find((x) => x.id === ret.goods_receipt_id);
      rows.push({
        key: `ret-${ret.id}`,
        at: stamp(ret.created_at),
        kind: 'Return',
        ref: ret.return_number,
        party: supplierNameOf(ret.supplier_id || g?.supplier_id, g?.purchase_order_id),
        status: ret.status,
        amount: String(ret.total_amount ?? ''),
      });
    }
    rows.sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
    return rows;
  }, [orders, grns, invoices, returns, suppliers]);
  const filteredSuppliers = suppliers.filter((s) => {
    const st = s.status || 'active';
    if (supplierManageFilter === 'inactive' && st !== 'inactive') return false;
    if (supplierManageFilter === 'active' && st === 'inactive') return false;
    if (!listQuery.trim()) return true;
    const q = listQuery.trim().toLowerCase();
    return `${s.name} ${s.code || ''} ${s.category || ''}`.toLowerCase().includes(q);
  });

  return (
    <div className="purch-desk purchase-ui-page">
      <PageHeader className="cat-head" title="Purchasing">
        <p className="purchase-ui-path">
          <span>1 Suppliers</span>
          <span>2 Orders</span>
          <span>3 Receive goods</span>
          <span>4 Supplier bills</span>
          <span>5 Returns</span>
        </p>
        <p className="purchase-ui-links">
          <a href="/credit?kind=payable">Supplier balances</a>
          <a href="/credit?kind=payable&panel=pay">Record a supplier payment</a>
        </p>
      </PageHeader>
      {error ? <p className="form-flash err">{error}</p> : null}
      {message ? <p className="form-flash ok">{message}</p> : null}

      <nav className="sales-toolbar" aria-label="Purchasing workflow">
        {(
          [
            ['suppliers', 'Suppliers'],
            ['orders', 'Orders'],
            ['grn', 'Receive Goods'],
            ['invoices', 'Supplier Bills'],
            ['returns', 'Returns'],
            ['requests', 'Requests'],
            ['history', 'History'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? 'sales-tab is-on' : 'sales-tab'}
            onClick={() => selectTab(id)}
            disabled={tab === id}
            aria-current={tab === id ? 'page' : undefined}
            aria-label={`Show purchasing ${id} tab`}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === 'requests' && (
        <>
          <div className="purchase-ui-actions">
            <button type="button" className="btn-primary" onClick={() => setPrCreateOpen(true)} aria-label="Create purchase request">
              Create purchase request
            </button>
          </div>
          <details className="purchase-ui-settings">
            <summary>Approval settings</summary>
          <div className="erp-split">
          <div className="card">
            <h3>PR approval matrix</h3>
            <p className="muted" style={{ marginBottom: 8 }}>
              Role chain (no amount thresholds). Default: Store Manager → Company Admin. Roles are
              comma-separated.
            </p>
            {prLevels.map((lvl, idx) => (
              <div
                key={idx}
                className="purch-level-row"
              >
                <span className="muted">L{idx + 1}</span>
                <input
                  value={lvl.label || ''}
                  onChange={(e) => updatePrLevel(idx, { label: e.target.value })}
                  placeholder="Label"
                  title="Optional level label"
                  aria-label={`PR approval level ${idx + 1} label`}
                />
                <input
                  value={(lvl.roles || []).join(', ')}
                  onChange={(e) =>
                    updatePrLevel(idx, {
                      roles: e.target.value
                        .split(',')
                        .map((s) => s.trim())
                        .filter(Boolean),
                    })
                  }
                  placeholder="Roles (comma-separated system roles)"
                  list="pr-approval-system-roles"
                  aria-label={`PR approval level ${idx + 1} roles`}
                />
                <button
                  type="button"
                  onClick={() => setPrLevels((prev) => prev.filter((_, i) => i !== idx))}
                  disabled={prLevels.length <= 1}
                  aria-label={`Remove PR approval level ${idx + 1}`}
                >
                  Remove
                </button>
              </div>
            ))}
            <datalist id="pr-approval-system-roles">
              {SYSTEM_ROLES.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() =>
                  setPrLevels((prev) => [...prev, { roles: ['company_admin'], label: `Level ${prev.length + 1}` }])
                }
                disabled={prLevels.length >= 5}
                aria-label="Add PR approval level"
              >
                Add level
              </button>
              <button type="button" onClick={savePrSettings} aria-label="Save PR approval matrix">
                Save matrix
              </button>
            </div>
          </div>
          </div>
          </details>
          {prCreateOpen ? (
          <FormModal
            title="Create purchase request"
            busy={saveBusy}
            dirty={Boolean(prLines.some((line) => line.productId.trim()) || prNotes.trim() || prDepartment.trim())}
            onClose={() => setPrCreateOpen(false)}
          >
            <div className="erp-form-grid">
              <select
                value={prSupplierId}
                onChange={(e) => setPrSupplierId(e.target.value)}
                aria-label="Purchase request preferred supplier"
              >
                <option value="">Preferred supplier (optional)</option>
                {suppliers
                  .filter((s) => s.status !== 'inactive')
                  .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <input
                value={prDepartment}
                onChange={(e) => setPrDepartment(e.target.value)}
                placeholder="Requesting department (optional)"
                aria-label="Purchase request department"
                title="Requesting department"
              />
              <input
                aria-label="Purchase request required date"
                type="text"
                placeholder="YYYY-MM-DD"
                title="Required by date (optional)"
                value={prRequiredDate}
                onChange={(e) => setPrRequiredDate(e.target.value)}
              />
              <input
                value={prNotes}
                onChange={(e) => setPrNotes(e.target.value)}
                placeholder="Notes (optional)"
                aria-label="Purchase request notes"
                title="Optional notes"
              />
            </div>
            <p className="muted" style={{ marginTop: 8 }}>
              Add every product for this supplier. Choosing a product opens the next line.
            </p>
            <div className="cat-table-wrap" style={{ marginTop: 8 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Qty</th>
                    <th>Line notes</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {prLines.map((line) => (
                    <tr key={line.key}>
                      <td>
                        <select
                          value={line.productId}
                          onChange={(e) => {
                            const productId = e.target.value;
                            setPrLines((rows) =>
                              ensureTrailingBlank(
                                rows.map((row) =>
                                  row.key === line.key ? { ...row, productId } : row,
                                ),
                                emptyPrLine,
                              ),
                            );
                          }}
                          aria-label="Purchase request product"
                        >
                          <option value="">Select product</option>
                          {products
                            .filter((p) => p.is_active !== false)
                            .map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.name} ({p.sku})
                              </option>
                            ))}
                        </select>
                      </td>
                      <td>
                        <input
                          value={line.qty}
                          onChange={(e) =>
                            setPrLines((rows) =>
                              rows.map((row) =>
                                row.key === line.key ? { ...row, qty: e.target.value } : row,
                              ),
                            )
                          }
                          placeholder="Quantity"
                          aria-label="Purchase request quantity"
                        />
                      </td>
                      <td>
                        <input
                          value={line.notes}
                          onChange={(e) =>
                            setPrLines((rows) =>
                              rows.map((row) =>
                                row.key === line.key ? { ...row, notes: e.target.value } : row,
                              ),
                            )
                          }
                          placeholder="Line notes (optional)"
                          aria-label="Purchase request line notes"
                          title="Optional per-line notes"
                        />
                      </td>
                      <td>
                        <button
                          type="button"
                          onClick={() =>
                            setPrLines((rows) =>
                              rows.length <= 1
                                ? [emptyPrLine()]
                                : rows.filter((row) => row.key !== line.key),
                            )
                          }
                          aria-label="Remove purchase request line"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
              <button
                type="button"
                onClick={() => setPrLines((rows) => [...rows, emptyPrLine()])}
                aria-label="Add purchase request product"
              >
                Add product
              </button>
              <button
                onClick={createRequest}
                disabled={!prLines.some((line) => line.productId.trim()) || saveBusy}
                aria-label="Create draft purchase request"
              >
                {saveBusy ? 'Saving…' : 'Create draft PR'}
              </button>
            </div>
          </FormModal>
          ) : null}
          <div className="card">
            <label className="field">
              <span>Reject reason</span>
              <input
                className="purch-reason"
                value={prRejectReason}
                onChange={(e) => setPrRejectReason(e.target.value)}
                placeholder="Required before Reject"
                aria-label="Purchase request reject reason"
                title="Required reason for Reject"
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Used by Reject on pending requests (stored as <code>rejection_reason</code>).
            </p>
          </div>
          <div className="card cat-panel">
          <div className="purch-filter-row">
          <select
            value={prManageFilter}
            onChange={(e) =>
              setPrManageFilter(
                e.target.value as
                  | 'all'
                  | 'draft'
                  | 'pending'
                  | 'approved'
                  | 'rejected'
                  | 'converted'
              )
            }
            title="Filter purchase request list by status"
            aria-label="Purchase request status filter"
          >
            <option value="all">All statuses</option>
            <option value="draft">Draft only</option>
            <option value="pending">Pending only</option>
            <option value="approved">Approved only</option>
            <option value="rejected">Rejected only</option>
            <option value="converted">Converted only</option>
          </select>
          </div>
          <div className="cat-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th className="col-id">Number</th>
                <th className="col-status">Status</th>
                <th className="col-status">Approval</th>
                <th>Department</th>
                <th className="col-text">Lines</th>
                <th className="col-text">Reject reason</th>
                <th className="col-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {managedRequests.map((r) => {
                const prActions: RowActionItem[] = [
                  {
                    key: 'print',
                    label: 'Print',
                    ariaLabel: 'Print purchase request',
                    onClick: () => {
                      openPurchasingPrint(`/purchasing/requests/${r.id}/print?format=pdf`).catch((err) =>
                        setError(String(err)),
                      );
                    },
                  },
                  {
                    key: 'email',
                    label: 'Email',
                    ariaLabel: 'Email purchase request',
                    onClick: () =>
                      sendPurchasingDoc(`/purchasing/requests/${r.id}/send`, 'Purchase request emailed to'),
                  },
                  {
                    key: 'submit',
                    label: 'Submit',
                    hidden: r.status !== 'draft',
                    disabled: prBusy === `submit:${r.id}`,
                    ariaLabel: `Submit purchase request ${r.id}`,
                    onClick: () => prAction(r.id, 'submit'),
                  },
                  {
                    key: 'approve',
                    label: `Approve L${r.awaiting_level || r.approval_step || 1}`,
                    variant: 'ok',
                    hidden: r.status !== 'pending',
                    disabled: prBusy === `approve:${r.id}`,
                    ariaLabel: `Approve purchase request ${r.id}`,
                    onClick: () => prAction(r.id, 'approve'),
                  },
                  {
                    key: 'reject',
                    label: 'Reject',
                    variant: 'danger',
                    hidden: r.status !== 'pending',
                    disabled: prBusy === `reject:${r.id}` || !prRejectReason.trim(),
                    title: prRejectReason.trim()
                      ? 'Reject purchase request'
                      : 'Enter a reject reason before rejecting',
                    ariaLabel: `Reject purchase request ${r.id}`,
                    onClick: () => prAction(r.id, 'reject'),
                  },
                  {
                    key: 'convert',
                    label: 'Convert to PO',
                    variant: 'ok',
                    hidden: r.status !== 'approved',
                    disabled: prBusy === `convert:${r.id}`,
                    ariaLabel: `Convert purchase request ${r.id}`,
                    onClick: () => prAction(r.id, 'convert'),
                  },
                  {
                    key: 'converted',
                    hidden: r.status !== 'converted',
                    node: (
                      <span className="muted">{r.converted_po_id ? 'PO linked' : 'Converted'}</span>
                    ),
                  },
                ];
                return (
                <tr key={r.id}>
                  <td className="col-id">{r.request_number}</td>
                  <td className="col-status"><StatusChip value={r.status} /></td>
                  <td className="col-status">
                    {r.status === 'pending'
                      ? `L${r.awaiting_level || r.approval_step || 1}/${r.approval_steps_required || 1}`
                      : r.approval_steps_required
                        ? `${r.approval_steps_required} level(s)`
                        : '—'}
                  </td>
                  <td>{r.department || '—'}</td>
                  <td className="col-text">
                    {(r.items || [])
                      .map((i) => `${productName(i.product_id, i)} × ${i.quantity}`)
                      .join(', ') || '—'}
                  </td>
                  <td className="col-text muted">{r.rejection_reason || '—'}</td>
                  <td className="col-actions">
                    <RowActions label={`More actions for ${r.request_number || r.id}`} primaryMax={1} items={prActions} />
                  </td>
                </tr>
                );
              })}
              {managedRequests.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">
                    {requests.length === 0
                      ? 'Create a purchase request when you need approval before an order.'
                      : 'No purchase requests for this filter, so choose All statuses to see them.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
          </div>
        </>
      )}

      {tab === 'suppliers' && (
        <>
        <div className="card cat-panel">
          <div className="cat-head">
            <h2>Suppliers</h2>
            <button
              type="button"
              className={supplierDrawer ? undefined : 'btn-primary'}
              onClick={() => setSupplierDrawer((open) => !open)}
              aria-expanded={supplierDrawer}
              aria-label={supplierDrawer ? 'Close add supplier form' : 'Add supplier'}
            >
              {supplierDrawer ? 'Cancel' : 'Add supplier'}
            </button>
          </div>
          <p className="purchase-ui-lead">Add a supplier, then use Orders to buy from that supplier.</p>
          <div className="cat-toolbar">
            <input
              className="sales-search"
              value={listQuery}
              onChange={(e) => setListQuery(e.target.value)}
              placeholder="Search suppliers"
              aria-label="Search suppliers"
            />
            <select
              value={supplierManageFilter}
              onChange={(e) => {
                const next = e.target.value as 'all' | 'active' | 'inactive';
                setSupplierManageFilter(next);
                if (supplierId) {
                  const row = suppliers.find((s) => s.id === supplierId);
                  const st = (row?.status || 'active') as string;
                  if (next === 'active' && st === 'inactive') setSupplierId('');
                  if (next === 'inactive' && st !== 'inactive') setSupplierId('');
                }
              }}
              aria-label="Supplier status filter"
            >
              <option value="all">All statuses</option>
              <option value="active">Active only</option>
              <option value="inactive">Inactive only</option>
            </select>
          </div>
          {filteredSuppliers.length === 0 ? (
            <div className="cat-empty">
              <p>
                {suppliers.length === 0
                  ? 'Add a supplier to start a purchase order.'
                  : 'Choose All statuses or clear the search to see suppliers.'}
              </p>
            </div>
          ) : (
            <div className="cat-table-wrap">
              <table className="table cat-table purchase-ui-stack">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th className="col-id">Code</th>
                    <th className="col-status">Status</th>
                    <th className="col-num">Open bills</th>
                    <th className="col-num">Total paid</th>
                    <th className="col-num">Amount left</th>
                    <th className="col-actions">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSuppliers.map((s) => {
                    const owed = openBillSummary(s.id);
                    const supplierActions: RowActionItem[] = [
                      {
                        key: 'manage',
                        label: 'Manage',
                        ariaLabel: `Manage ${s.name}`,
                        onClick: () => setSupplierId(s.id),
                      },
                      {
                        key: 'balance',
                        label: 'Balance',
                        ariaLabel: `Balance for ${s.name}`,
                        onClick: () => {
                          window.location.href = `/credit?kind=payable&supplier=${s.id}`;
                        },
                      },
                      {
                        key: 'pay',
                        label: 'Record payment',
                        ariaLabel: `Record payment for ${s.name}`,
                        onClick: () => {
                          window.location.href = `/credit?kind=payable&panel=pay&supplier=${s.id}`;
                        },
                      },
                    ];
                    return (
                    <tr key={s.id}>
                      <td data-label="Name"><strong>{s.name}</strong></td>
                      <td className="col-id" data-label="Code">{s.code || '—'}</td>
                      <td className="col-status" data-label="Status">
                        <StatusChip value={s.status === 'inactive' ? 'inactive' : 'active'} />
                      </td>
                      <td className="col-num" data-label="Open bills">
                        {owed.count === 0 ? '—' : owed.count}
                      </td>
                      <td className="col-num" data-label="Total paid" aria-label={`Total paid to ${s.name}`}>
                        {supplierMoney(s, 'total_paid')}
                      </td>
                      <td className="col-num" data-label="Amount left" aria-label={`Amount left for ${s.name}`}>
                        {supplierMoney(s, 'amount_left')}
                      </td>
                      <td className="col-actions">
                        <RowActions label={`More actions for ${s.name}`} primaryMax={1} items={supplierActions} />
                      </td>
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {supplierDrawer ? (
      <FormModal
        title="Add supplier"
        busy={saveBusy}
        dirty={Boolean(supplierName.trim() || supplierCode.trim() || supplierEmail.trim() || supplierPhone.trim())}
        onClose={() => setSupplierDrawer(false)}
      >
        <div className="erp-form-grid">
          <label className="field">
            <span>Name</span>
            <input
              value={supplierName}
              onChange={(e) => setSupplierName(e.target.value)}
              placeholder="Supplier name"
              aria-label="Supplier name"
              title="Supplier name"
            />
          </label>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              value={supplierEmail}
              onChange={(e) => setSupplierEmail(e.target.value)}
              placeholder="Email"
              aria-label="Supplier email"
            />
          </label>
          <label className="field">
            <span>Phone</span>
            <input
              value={supplierPhone}
              onChange={(e) => setSupplierPhone(e.target.value)}
              placeholder="e.g. +233 24 123 4567"
              aria-label="Supplier phone"
            />
          </label>
          <label className="field">
            <span>Address</span>
            <input
              value={supplierAddress}
              onChange={(e) => setSupplierAddress(e.target.value)}
              placeholder="Address"
              aria-label="Supplier address"
            />
          </label>
          <label className="field">
            <span>Payment terms (days)</span>
            <input
              value={supplierTermsDays}
              onChange={(e) => setSupplierTermsDays(e.target.value)}
              placeholder="Net days"
              title="Payment terms (days)"
              aria-label="Supplier payment terms days"
            />
          </label>
          <details className="span-2">
            <summary>More details</summary>
            <div className="erp-form-grid" style={{ marginTop: 8 }}>
              <label className="field">
                <span>Code</span>
                <input
                  value={supplierCode}
                  onChange={(e) => setSupplierCode(e.target.value)}
                  placeholder="Optional code"
                  aria-label="Supplier code"
                  title="Supplier code"
                />
              </label>
              <label className="field">
                <span>Type</span>
                <select
                  value={supplierProfileType}
                  onChange={(e) => setSupplierProfileType(e.target.value)}
                  aria-label="Supplier profile type"
                  title="Supplier type"
                >
                  <option value="registered">Registered</option>
                  <option value="trade">Trade</option>
                  <option value="manufacturer">Manufacturer</option>
                  <option value="service">Service</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label className="field">
                <span>Category</span>
                <input
                  value={supplierCategory}
                  onChange={(e) => setSupplierCategory(e.target.value)}
                  placeholder="Optional category"
                  aria-label="Supplier category"
                  title="Supplier category"
                />
              </label>
              <label className="field">
                <span>Status</span>
                <select
                  value={supplierStatus}
                  onChange={(e) => setSupplierStatus(e.target.value)}
                  aria-label="Supplier status"
                  title="Status"
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </label>
              <label className="field">
                <span>Latitude</span>
                <input
                  value={supplierLat}
                  onChange={(e) => setSupplierLat(e.target.value)}
                  placeholder="−90 to 90"
                  title="GPS latitude (−90…90)"
                  aria-label="Supplier latitude"
                />
              </label>
              <label className="field">
                <span>Longitude</span>
                <input
                  value={supplierLng}
                  onChange={(e) => setSupplierLng(e.target.value)}
                  placeholder="−180 to 180"
                  title="GPS longitude (−180…180)"
                  aria-label="Supplier longitude"
                />
              </label>
            </div>
          </details>
          <button
            type="button"
            className="btn-primary"
            onClick={createSupplier}
            disabled={!supplierName.trim() || saveBusy}
            aria-label="Add supplier"
          >
            {saveBusy ? 'Saving…' : 'Add supplier'}
          </button>
        </div>
      </FormModal>
        ) : null}
        {supplierId ? (
      <div className="card">
        <h3>Supplier details</h3>
        <div className="cat-toolbar">
          <select
            value={supplierId}
            onChange={(e) => setSupplierId(e.target.value)}
            title="Select supplier to manage"
            aria-label="Manage supplier"
          >
            <option value="">Manage supplier…</option>
            {suppliers
              .filter((s) => {
                if (supplierManageFilter === 'all') return true;
                const st = s.status || 'active';
                return supplierManageFilter === 'inactive' ? st === 'inactive' : st !== 'inactive';
              })
              .map((s) => (
              <option key={s.id} value={s.id}>
                {s.code ? `${s.code} — ` : ''}
                {s.name}
                {s.status === 'inactive' ? ' [inactive]' : ''}
              </option>
            ))}
          </select>
            <button
              type="button"
              className={
                (suppliers.find((s) => s.id === supplierId)?.status || 'active') === 'inactive'
                  ? 'btn-ok'
                  : 'btn-danger'
              }
              onClick={() =>
                setSupplierActive(
                  (suppliers.find((s) => s.id === supplierId)?.status || 'active') === 'inactive',
                )
              }
              aria-label="Toggle supplier active status"
            >
              {(suppliers.find((s) => s.id === supplierId)?.status || 'active') === 'inactive'
                ? 'Activate'
                : 'Deactivate'}
            </button>
        </div>
        {(suppliers.find((s) => s.id === supplierId)?.status || 'active') === 'inactive' ? (
            <p className="muted" style={{ marginTop: 0 }}>
              Inactive — hidden from new PO / PR / manual invoice pickers; existing documents can still
              settle.
            </p>
          ) : null}
        {(() => {
          const managed = suppliers.find((s) => s.id === supplierId);
          return (
            <p className="purchase-ui-bill" style={{ marginTop: 0 }}>
              <span aria-label={`Supplier total paid ${managed?.name || ''}`.trim()}>
                Total paid {supplierMoney(managed, 'total_paid')}
              </span>
              <span aria-label={`Supplier amount left ${managed?.name || ''}`.trim()}>
                Amount left {supplierMoney(managed, 'amount_left')}
              </span>
            </p>
          );
        })()}
          <PartyContactsPanel
            kind="supplier"
            partyId={supplierId}
            partyLabel={suppliers.find((s) => s.id === supplierId)?.name || 'Selected supplier'}
          />
      </div>
        ) : null}
        </>
      )}
      {tab === 'orders' && (
      <>
      <div className="purchase-ui-actions">
        <button type="button" className="btn-primary" onClick={() => setPoCreateOpen(true)} aria-label="Add purchase order">
          Add purchase order
        </button>
        <button type="button" onClick={() => selectTab('suppliers')} aria-label="Quick add supplier">
          Quick add supplier
        </button>
      </div>
      <details className="purchase-ui-settings">
        <summary>Numbering</summary>
        <div className="purchase-ui-actions">
        <input value={poPrefix} onChange={(e) => setPoPrefix(e.target.value)} aria-label="Purchase order number prefix" placeholder="PO prefix" />
        <input value={poNext} onChange={(e) => setPoNext(e.target.value)} aria-label="Purchase order next number" placeholder="Next #" />
        <input value={grnPrefix} onChange={(e) => setGrnPrefix(e.target.value)} aria-label="GRN number prefix" placeholder="GRN prefix" />
        <input value={piPrefix} onChange={(e) => setPiPrefix(e.target.value)} aria-label="Purchase invoice number prefix" placeholder="PI prefix" />
        <input value={prPrefix} onChange={(e) => setPrPrefix(e.target.value)} aria-label="Purchase request number prefix" placeholder="PR prefix" />
        <input value={pretPrefix} onChange={(e) => setPretPrefix(e.target.value)} aria-label="Purchase return number prefix" placeholder="Return prefix" />
        <input value={dnPrefix} onChange={(e) => setDnPrefix(e.target.value)} aria-label="Debit note number prefix" placeholder="Debit note prefix" />
        <input value={spPrefix} onChange={(e) => setSpPrefix(e.target.value)} aria-label="Supplier payment number prefix" placeholder="Payment prefix" />
        <button
          type="button"
          aria-label="Save purchasing numbering"
          onClick={() => {
            const pack = (prefix: string, next = '') => {
              const p = prefix.trim();
              const n = next.trim();
              if (!p && !n) return undefined;
              const out: { prefix?: string; next_number?: number } = {};
              if (p) out.prefix = p;
              if (n) out.next_number = Number(n);
              return out;
            };
            const body: Record<string, unknown> = {};
            const po = pack(poPrefix, poNext);
            const grn = pack(grnPrefix);
            const pi = pack(piPrefix);
            const pr = pack(prPrefix);
            const pret = pack(pretPrefix);
            const dn = pack(dnPrefix);
            const sp = pack(spPrefix);
            if (po) body.purchase_order_numbering = po;
            if (grn) body.grn_numbering = grn;
            if (pi) body.purchase_invoice_numbering = pi;
            if (pr) body.purchase_request_numbering = pr;
            if (pret) body.purchase_return_numbering = pret;
            if (dn) body.debit_note_numbering = dn;
            if (sp) body.supplier_payment_numbering = sp;
            api('/purchasing/settings', { method: 'PATCH', body: JSON.stringify(body) }).catch((err) =>
              setError(err.message || 'Could not save numbering'),
            );
          }}
        >
          Save numbering
        </button>
        </div>
      </details>
      {poCreateOpen ? (
      <FormModal
        title="Add purchase order"
        busy={saveBusy}
        dirty={Boolean(
          supplierId ||
            poNotes.trim() ||
            poDeliveryAddress.trim() ||
            poLines.some((line) => line.productId.trim()),
        )}
        onClose={() => setPoCreateOpen(false)}
      >
        <div className="erp-form-grid">
          <select
            value={supplierId}
            onChange={(e) => setSupplierId(e.target.value)}
            aria-label="PO supplier"
          >
            <option value="">Select supplier</option>
            {suppliers
              .filter((s) => s.status !== 'inactive')
              .map((s) => (
              <option key={s.id} value={s.id}>
                {s.code ? `${s.code} — ` : ''}
                {s.name}
              </option>
            ))}
          </select>
          <input
            value={poDeliveryAddress}
            onChange={(e) => setPoDeliveryAddress(e.target.value)}
            placeholder="Delivery address (optional)"
            aria-label="PO delivery address"
          />
          <input
            value={poNotes}
            onChange={(e) => setPoNotes(e.target.value)}
            placeholder="PO notes (optional)"
            aria-label="PO notes"
            title="Optional notes"
          />
          {!hideWarehouseUx ? (
          <label className="field">
            <span>Warehouse (store context)</span>
            <select aria-label="PO warehouse" value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
              <option value="">Default / any</option>
              {storeWarehouses.map((w: any) => (
                <option key={w.id} value={w.id}>{w.code} — {w.name}</option>
              ))}
            </select>
          </label>
          ) : null}
          <span className="muted span-2">
            Add one or more product lines from this supplier. Use Add product for each extra line.
          </span>
        </div>
        <div className="cat-table-wrap erp-modal-lines" style={{ marginTop: 12 }}>
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>Unit</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Discount</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {poLines.map((line) => (
                <tr key={line.key}>
                  <td>
                    <select
                      value={line.productId}
                      onChange={(e) => {
                        const nextProductId = e.target.value;
                        const product = products.find((p) => p.id === nextProductId);
                        setPoLines((rows) =>
                          ensureTrailingBlank(
                            rows.map((row) =>
                              row.key === line.key
                                ? {
                                    ...row,
                                    productId: nextProductId,
                                    unitPrice: product
                                      ? String(product.cost_price ?? 0)
                                      : row.unitPrice,
                                  }
                                : row,
                            ),
                            emptyPoLine,
                          ),
                        );
                      }}
                      aria-label="PO product"
                    >
                      <option value="">Select product</option>
                      {products
                        .filter((p) => p.is_active !== false)
                        .map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name} ({p.sku})
                          </option>
                        ))}
                    </select>
                  </td>
                  <td>
                    <select
                      value={line.unitId}
                      onChange={(e) =>
                        setPoLines((rows) =>
                          rows.map((row) =>
                            row.key === line.key ? { ...row, unitId: e.target.value } : row,
                          ),
                        )
                      }
                      aria-label="PO unit"
                    >
                      <option value="">Unit (product default)</option>
                      {units.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.code} — {u.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      value={line.qty}
                      onChange={(e) =>
                        setPoLines((rows) =>
                          rows.map((row) =>
                            row.key === line.key ? { ...row, qty: e.target.value } : row,
                          ),
                        )
                      }
                      placeholder="Quantity"
                      aria-label="Purchase order quantity"
                    />
                  </td>
                  <td>
                    <AmountField
                      inline
                      value={line.unitPrice}
                      onChange={(e) =>
                        setPoLines((rows) =>
                          rows.map((row) =>
                            row.key === line.key ? { ...row, unitPrice: e.target.value } : row,
                          ),
                        )
                      }
                      placeholder="Unit price"
                      aria-label="Purchase order unit price"
                    />
                  </td>
                  <td>
                    <input
                      value={line.discount}
                      onChange={(e) =>
                        setPoLines((rows) =>
                          rows.map((row) =>
                            row.key === line.key ? { ...row, discount: e.target.value } : row,
                          ),
                        )
                      }
                      placeholder="Line discount"
                      type="number"
                      min={0}
                      step="0.01"
                      aria-label="Purchase order line discount"
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() =>
                        setPoLines((rows) =>
                          rows.length <= 1
                            ? [emptyPoLine()]
                            : rows.filter((row) => row.key !== line.key),
                        )
                      }
                      aria-label="Remove purchase order line"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          <button
            type="button"
            onClick={() => setPoLines((rows) => [...rows, emptyPoLine()])}
            aria-label="Add purchase order product"
          >
            Add product
          </button>
          <button
            className="btn-primary"
            onClick={createPo}
            disabled={!supplierId || !poLines.some(isValidPoLine) || saveBusy}
            aria-label="Create draft PO"
          >
            {saveBusy ? 'Saving…' : 'Create purchase order'}
          </button>
        </div>
        {message ? <p className="form-flash ok">{message}</p> : null}
      </FormModal>
      ) : null}

          <details
            className="card purchase-ui-settings"
            open={poOptionsOpen}
            onToggle={(e) => setPoOptionsOpen((e.currentTarget as HTMLDetailsElement).open)}
          >
            <summary>Cancel or email options</summary>
            <label className="field">
              <span>Reason for cancelling an order</span>
              <input
                className="purch-reason"
                value={poCancelReason}
                onChange={(e) => setPoCancelReason(e.target.value)}
                placeholder="Needed before you press Cancel on an order"
                aria-label="Purchase order cancel reason"
              />
            </label>
            <label className="field" style={{ marginTop: 8 }}>
              <span>Email the document to</span>
              <input
                type="email"
                className="purch-reason"
                value={poEmailTo}
                onChange={(e) => setPoEmailTo(e.target.value)}
                placeholder="Send to a different email (optional)"
                aria-label="Purchase order email override to"
              />
            </label>
            <p className="muted" style={{ margin: '8px 0 0' }}>
              This address also applies when you email a purchase request, goods received note,
              supplier bill, or debit note. If there is no email, print the document instead.
            </p>
          </details>

          <div className="card cat-panel">
          <div className="purch-filter-row">
          <select
            value={poManageFilter}
            onChange={(e) =>
              setPoManageFilter(
                e.target.value as
                  | 'all'
                  | 'draft'
                  | 'sent'
                  | 'partially_received'
                  | 'received'
                  | 'cancelled'
              )
            }
            title="Filter purchase order list by status"
            aria-label="Purchase order status filter"
          >
            <option value="all">All statuses</option>
            <option value="draft">Draft only</option>
            <option value="sent">Sent only</option>
            <option value="partially_received">Partially received only</option>
            <option value="received">Received only</option>
            <option value="cancelled">Cancelled only</option>
          </select>
          </div>
          <div className="cat-table-wrap">
          <table className="table purchase-ui-stack">
            <thead>
              <tr>
                <th className="col-id">PO</th>
                <th>Supplier</th>
                <th className="col-status">Status</th>
                <th className="col-num">Rev</th>
                <th className="col-num">Total</th>
                <th className="col-num">Amount paid</th>
                <th className="col-num">Amount left</th>
                <th className="col-text">Notes</th>
                <th className="col-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {managedOrders.map((o) => {
                const poActions: RowActionItem[] = [
                  {
                    key: 'print',
                    label: 'Print PO',
                    hidden: o.status === 'cancelled',
                    ariaLabel: 'Print purchase order',
                    onClick: () => printPo(o),
                  },
                  {
                    key: 'email',
                    label: 'Email',
                    hidden: o.status !== 'draft',
                    ariaLabel: 'Email purchase order',
                    onClick: () => sendPo(o.id),
                  },
                  {
                    key: 'resend',
                    label: 'Resend',
                    hidden: o.status !== 'sent',
                    ariaLabel: 'Resend purchase order email',
                    onClick: () => sendPo(o.id, true),
                  },
                  {
                    key: 'amend',
                    label: 'Amend',
                    hidden: !o.can_amend,
                    ariaLabel: `Amend purchase order ${o.id}`,
                    onClick: () => openAmend(o),
                  },
                  {
                    key: 'receive',
                    label: 'Receive goods',
                    variant: 'ok',
                    hidden: !(o.status === 'sent' || o.status === 'partially_received'),
                    ariaLabel: `Receive all for purchase order ${o.id}`,
                    onClick: () => {
                      focusReceivedOrder(o);
                      selectTab('grn');
                    },
                  },
                  {
                    key: 'cancel',
                    label: 'Cancel',
                    variant: 'danger',
                    hidden: !o.can_cancel,
                    ariaLabel: `Cancel purchase order ${o.id}`,
                    onClick: () => cancelPo(o),
                  },
                ];
                return (
                <tr key={o.id}>
                  <td className="col-id" data-label="PO">
                    <button
                      onClick={() => openAmend(o)}
                      style={{ background: 'none', border: 0, color: 'var(--deep-green, #006B2E)', cursor: 'pointer' }}
                      aria-label="GRN purchase order"
                    >
                      {o.po_number}
                    </button>
                  </td>
                  <td data-label="Supplier">{supplierNameOf(o.supplier_id)}</td>
                  <td className="col-status" data-label="Status"><StatusChip value={o.status} /></td>
                  <td className="col-num" data-label="Rev">{o.revision_no ?? 0}</td>
                  <td className="col-num" data-label="Total">{formatNumber(o.total_amount, formatPrefs)}</td>
                  <td className="col-num" data-label="Amount paid">{formatNumber(o.paid_amount ?? 0, formatPrefs)}</td>
                  <td className="col-num" data-label="Amount left">
                    {formatNumber(o.balance_due ?? Math.max(Number(o.total_amount || 0) - Number(o.paid_amount || 0), 0), formatPrefs)}
                  </td>
                  <td className="col-text muted" data-label="Notes">
                    {o.notes || '—'}
                  </td>
                  <td className="col-actions">
                    <RowActions label={`More actions for ${o.po_number || o.id}`} primaryMax={1} items={poActions} />
                  </td>
                </tr>
                );
              })}
              {managedOrders.length === 0 && (
                <tr>
                  <td colSpan={9} className="muted">
                    {orders.length === 0
                      ? 'Add a purchase order for a supplier.'
                      : 'No purchase orders for this filter, so choose All statuses to see them.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
          </div>
          {selected && (
            <div className="card" style={{ marginTop: 16 }}>
              <h3>
                {selected.po_number} — {selected.status}
                {selected.delivery_address ? ` · Ship to: ${selected.delivery_address}` : ''}
                {selected.revision_no ? ` · rev.${selected.revision_no}` : ''}
              </h3>
              {selected.status !== 'cancelled' && (
                <p style={{ marginTop: 0 }}>
                  <button
                    type="button"
                    onClick={() => printPo(selected)}
                    aria-label={`Print purchase order ${selected.id}`}
                  >
                    Print PO
                  </button>
                  {(selected.status === 'draft' || selected.status === 'sent') && (
                    <button
                      type="button"
                      onClick={() => sendPo(selected.id, selected.status === 'sent')}
                      aria-label={`Email purchase order ${selected.id}`}
                      style={{ marginLeft: 8 }}
                    >
                      {selected.status === 'sent' ? 'Resend email' : 'Email PO'}
                    </button>
                  )}
                  <span className="muted" style={{ marginLeft: 8 }}>
                    Hand the paper to a supplier who has no email. When they deliver, receive the goods.
                  </span>
                </p>
              )}
              {selected.can_cancel && (
                <p style={{ marginTop: 0 }}>
                  <button
                    type="button"
                    className="btn-danger"
                    onClick={() => cancelPo(selected)}
                    aria-label={`Cancel purchase order ${selected.id}`}
                  >
                    Cancel PO
                  </button>
                  <span className="muted" style={{ marginLeft: 8 }}>
                    Allowed while draft or sent with no receipts. Enter a cancel reason first.
                  </span>
                </p>
              )}
              {selected.notes && (
                <p className="muted" style={{ marginTop: 0, whiteSpace: 'pre-wrap' }}>
                  Notes: {selected.notes}
                </p>
              )}
              {selected.emailed_to && (
                <p style={{ marginTop: 0, color: 'var(--muted, #4D5D56)', fontSize: 14 }}>
                  Last emailed to {selected.emailed_to}
                  {selected.emailed_at ? ` · ${String(selected.emailed_at).slice(0, 19)}` : ''}
                </p>
              )}
              <div className="cat-table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>SKU</th>
                    <th>Ordered</th>
                    <th>Received</th>
                    <th>Outstanding</th>
                    <th>Unit price</th>
                    <th>Discount</th>
                    <th>Line total</th>
                    {(selected.status === 'sent' || selected.status === 'partially_received') && (
                      <>
                        <th>Receive</th>
                        <th>Accept</th>
                        <th>Reject</th>
                        <th>Reject reason</th>
                        <th>Batch</th>
                        <th>Mfg</th>
                        <th>Expiry</th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {selected.items.map((i) => {
                    const draft = receiveDrafts[i.id] || {
                      received: String(i.outstanding_qty),
                      accepted: String(i.outstanding_qty),
                      rejected: '0',
                      reason: '',
                      batch: '',
                      mfg: '',
                      expiry: '',
                    };
                    const receivable =
                      (selected.status === 'sent' || selected.status === 'partially_received') &&
                      i.outstanding_qty > 0;
                    const tracks = products.find((p) => p.id === i.product_id)?.tracks_batches;
                    return (
                      <tr key={i.id}>
                        <td>{productNameOf(i.product_id, i)}</td>
                        <td>{products.find((p) => p.id === i.product_id)?.sku || '—'}</td>
                        <td>{i.quantity}</td>
                        <td>{i.received_qty}</td>
                        <td>{i.outstanding_qty}</td>
                        <td>{i.unit_price}</td>
                        <td>{i.discount ?? 0}</td>
                        <td>{i.line_total ?? '—'}</td>
                        {(selected.status === 'sent' || selected.status === 'partially_received') && (
                          <>
                            <td>
                              {receivable ? (
                                <input
                                  style={{ width: 72 }}
                                  value={draft.received}
                                  aria-label={`GRN received qty ${i.id}`}
                                  onChange={(e) =>
                                    setReceiveDrafts((prev) => ({
                                      ...prev,
                                      [i.id]: { ...draft, received: e.target.value },
                                    }))
                                  }
                                />
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>
                              {receivable ? (
                                <input
                                  style={{ width: 72 }}
                                  value={draft.accepted}
                                  aria-label={`GRN accepted qty ${i.id}`}
                                  onChange={(e) =>
                                    setReceiveDrafts((prev) => ({
                                      ...prev,
                                      [i.id]: { ...draft, accepted: e.target.value },
                                    }))
                                  }
                                />
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>
                              {receivable ? (
                                <input
                                  style={{ width: 72 }}
                                  value={draft.rejected}
                                  aria-label={`GRN rejected qty ${i.id}`}
                                  onChange={(e) =>
                                    setReceiveDrafts((prev) => ({
                                      ...prev,
                                      [i.id]: { ...draft, rejected: e.target.value },
                                    }))
                                  }
                                />
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>
                              {receivable ? (
                                <input
                                  style={{ minWidth: 140 }}
                                  value={draft.reason}
                                  placeholder="Damaged / wrong item…"
                                  title="Required when rejecting qty"
                                  aria-label={`GRN rejection reason ${i.id}`}
                                  onChange={(e) =>
                                    setReceiveDrafts((prev) => ({
                                      ...prev,
                                      [i.id]: { ...draft, reason: e.target.value },
                                    }))
                                  }
                                />
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>
                              {receivable ? (
                                <input
                                  style={{ minWidth: 100 }}
                                  value={draft.batch}
                                  placeholder={tracks ? 'Batch required' : 'Batch (opt)'}
                                  aria-label="GRN batch number"
                                  title="Batch or lot number (needed for products tracked by batch)"
                                  onChange={(e) =>
                                    setReceiveDrafts((prev) => ({
                                      ...prev,
                                      [i.id]: { ...draft, batch: e.target.value },
                                    }))
                                  }
                                />
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>
                              {receivable ? (
                                <input
                                  aria-label="GRN manufacturing date"
                                  style={{ width: 120 }}
                                  type="text"
                                  placeholder="YYYY-MM-DD"
                                  title="Manufacturing date (optional)"
                                  value={draft.mfg}
                                  onChange={(e) =>
                                    setReceiveDrafts((prev) => ({
                                      ...prev,
                                      [i.id]: { ...draft, mfg: e.target.value },
                                    }))
                                  }
                                />
                              ) : (
                                '—'
                              )}
                            </td>
                            <td>
                              {receivable ? (
                                <input
                                  aria-label="GRN expiry date"
                                  style={{ width: 120 }}
                                  type="text"
                                  placeholder="YYYY-MM-DD"
                                  title="Expiry date (optional)"
                                  value={draft.expiry}
                                  onChange={(e) =>
                                    setReceiveDrafts((prev) => ({
                                      ...prev,
                                      [i.id]: { ...draft, expiry: e.target.value },
                                    }))
                                  }
                                />
                              ) : (
                                '—'
                              )}
                            </td>
                          </>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
              {(selected.status === 'sent' || selected.status === 'partially_received') &&
                selected.items.some((i) => i.outstanding_qty > 0) && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                    <input
                      value={grnNotes}
                      onChange={(e) => setGrnNotes(e.target.value)}
                      placeholder="GRN notes (optional)"
                      aria-label="GRN notes"
                      title="Optional notes"
                      style={{ minWidth: 220 }}
                    />
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => postPartialReceive(selected)}
                      aria-label="Post GRN"
                    >
                      Post GRN (accept / reject)
                    </button>
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => receiveAll(selected)}
                      aria-label="Receive all accepted"
                    >
                      Receive all accepted
                    </button>
                    <span className="muted">
                      Rejected qty requires a reason; only accepted qty is stocked. Batch/expiry apply to
                      accepted stock (required when product tracks batches).
                    </span>
                  </div>
                )}
              {selected.can_amend && (
                <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
                  <h4 style={{ margin: 0 }}>Amend every product</h4>
                  <p className="muted" style={{ margin: 0 }}>
                    Saving replaces the order lines with this list. Add or remove products before any goods are received.
                  </p>
                  <div className="cat-table-wrap">
                    <table className="table compact">
                      <thead>
                        <tr>
                          <th>Product</th>
                          <th>Unit</th>
                          <th>Qty</th>
                          <th>Price</th>
                          <th>Discount</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {amendLines.map((line, index) => (
                          <tr key={line.key}>
                            <td>
                              <select
                                aria-label={index === 0 ? 'PO amend product' : `PO amend product ${index + 1}`}
                                value={line.productId}
                                onChange={(e) => {
                                  const productId = e.target.value;
                                  const product = products.find((p) => p.id === productId);
                                  setAmendLines((rows) =>
                                    rows.map((row) =>
                                      row.key === line.key
                                        ? {
                                            ...row,
                                            productId,
                                            unitPrice: product ? String(product.cost_price ?? row.unitPrice) : row.unitPrice,
                                          }
                                        : row,
                                    ),
                                  );
                                }}
                              >
                                <option value="">Select product</option>
                                {products
                                  .filter((p) => p.is_active !== false)
                                  .map((p) => (
                                    <option key={p.id} value={p.id}>
                                      {p.name}
                                    </option>
                                  ))}
                              </select>
                            </td>
                            <td>
                              {index === 0 ? (
                                <select
                                  value={line.unitId}
                                  onChange={(e) =>
                                    setAmendLines((rows) =>
                                      rows.map((row) => (row.key === line.key ? { ...row, unitId: e.target.value } : row)),
                                    )
                                  }
                                  aria-label="PO unit"
                                >
                                  <option value="">Unit (product default)</option>
                                  {units.map((u) => (
                                    <option key={u.id} value={u.id}>
                                      {u.code}
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <select
                                  value={line.unitId}
                                  onChange={(e) =>
                                    setAmendLines((rows) =>
                                      rows.map((row) => (row.key === line.key ? { ...row, unitId: e.target.value } : row)),
                                    )
                                  }
                                  aria-label={`PO unit ${index + 1}`}
                                >
                                  <option value="">Unit (product default)</option>
                                  {units.map((u) => (
                                    <option key={u.id} value={u.id}>
                                      {u.code}
                                    </option>
                                  ))}
                                </select>
                              )}
                            </td>
                            <td>
                              <input
                                value={line.qty}
                                onChange={(e) =>
                                  setAmendLines((rows) =>
                                    rows.map((row) => (row.key === line.key ? { ...row, qty: e.target.value } : row)),
                                  )
                                }
                                placeholder="Quantity"
                                aria-label={index === 0 ? 'PO amend quantity' : `PO amend quantity ${index + 1}`}
                              />
                            </td>
                            <td>
                              {index === 0 ? (
                                <AmountField
                                  inline
                                  value={line.unitPrice}
                                  onChange={(e) =>
                                    setAmendLines((rows) =>
                                      rows.map((row) =>
                                        row.key === line.key ? { ...row, unitPrice: e.target.value } : row,
                                      ),
                                    )
                                  }
                                  placeholder="Unit price"
                                  aria-label="PO amend unit price"
                                />
                              ) : (
                                <AmountField
                                  inline
                                  value={line.unitPrice}
                                  onChange={(e) =>
                                    setAmendLines((rows) =>
                                      rows.map((row) =>
                                        row.key === line.key ? { ...row, unitPrice: e.target.value } : row,
                                      ),
                                    )
                                  }
                                  placeholder="Unit price"
                                  aria-label={`PO amend unit price ${index + 1}`}
                                />
                              )}
                            </td>
                            <td>
                              {index === 0 ? (
                                <input
                                  value={line.discount}
                                  onChange={(e) =>
                                    setAmendLines((rows) =>
                                      rows.map((row) =>
                                        row.key === line.key ? { ...row, discount: e.target.value } : row,
                                      ),
                                    )
                                  }
                                  placeholder="Line discount"
                                  type="number"
                                  min={0}
                                  step="0.01"
                                  aria-label="PO amend line discount"
                                />
                              ) : (
                                <input
                                  value={line.discount}
                                  onChange={(e) =>
                                    setAmendLines((rows) =>
                                      rows.map((row) =>
                                        row.key === line.key ? { ...row, discount: e.target.value } : row,
                                      ),
                                    )
                                  }
                                  placeholder="Line discount"
                                  type="number"
                                  min={0}
                                  step="0.01"
                                  aria-label={`PO amend line discount ${index + 1}`}
                                />
                              )}
                            </td>
                            <td>
                              <button
                                type="button"
                                className="btn-danger"
                                disabled={amendLines.length < 2}
                                onClick={() => setAmendLines((rows) => rows.filter((row) => row.key !== line.key))}
                                aria-label={`Remove amend product ${index + 1}`}
                              >
                                Remove
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <button
                    type="button"
                    onClick={() => setAmendLines((rows) => [...rows, emptyAmendLine()])}
                    aria-label="Add purchase order amend product"
                  >
                    Add product
                  </button>
                  <input
                    value={amendNotes}
                    onChange={(e) => setAmendNotes(e.target.value)}
                    placeholder="Notes"
                    aria-label="PO amend notes"
                    title="Notes (optional)"
                  />
                  <input
                    value={amendDeliveryAddress}
                    onChange={(e) => setAmendDeliveryAddress(e.target.value)}
                    placeholder="Delivery address"
                    aria-label="PO amend delivery address"
                  />
                  <input
                    aria-label="PO amend due date"
                    type="text"
                    placeholder="YYYY-MM-DD"
                    title="Due date (optional; leave blank to keep the current date)"
                    value={amendDueDate}
                    onChange={(e) => setAmendDueDate(e.target.value)}
                  />
                  <input
                    value={amendReason}
                    onChange={(e) => setAmendReason(e.target.value)}
                    placeholder="Required amendment reason"
                    title="Required amendment reason"
                    aria-label="Purchase order amend reason"
                  />
                  <p className="muted" style={{ margin: 0 }}>
                    Required. Stored on the amendment history.
                  </p>
                  <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="checkbox"
                      aria-label="PO amend notify supplier"
                      checked={amendNotify}
                      onChange={(e) => setAmendNotify(e.target.checked)}
                      disabled={selected.status !== 'sent' && !selected.emailed_at}
                    />
                    Email supplier about amendment
                  </label>
                  {amendNotify && (
                    <input
                      type="email"
                      value={amendEmailTo}
                      onChange={(e) => setAmendEmailTo(e.target.value)}
                      placeholder="Optional amend to= (omit → supplier email)"
                      aria-label="PO amend email override to"
                    />
                  )}
                  <button type="button" onClick={amendPo} aria-label="Save purchase order amendment">
                    Save amendment
                  </button>
                </div>
              )}
              {(selected.amendments || []).length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4>Amendment history</h4>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {selected.amendments!.map((a) => (
                      <li key={a.id}>
                        Rev.{a.revision_no}
                        {a.reason ? ` — ${a.reason}` : ''}
                        {a.notified_supplier ? ` · emailed ${a.emailed_to || 'supplier'}` : ''}
                        {a.created_at ? ` · ${String(a.created_at).slice(0, 19)}` : ''}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {tab === 'grn' && (
        <div className="card cat-panel">
        <div className="cat-head">
          <h2 style={{ margin: 0 }}>Receive goods</h2>
        </div>
        <p className="muted" style={{ margin: 0 }}>
          Choose the order to receive. Stock posts for that order only.
        </p>
        <div className="erp-form-grid" style={{ marginTop: 12 }}>
          <select
            value={receivableOrders.some((o) => o.id === receiveOrderId) ? receiveOrderId : ''}
            onChange={(e) => {
              const id = e.target.value;
              if (!id) {
                setReceiveOrderId('');
                return;
              }
              const po = orders.find((o) => o.id === id);
              if (!po) return;
              setReceiveOrderId(po.id);
              const already = po.items.some((i) => receiveDrafts[i.id]);
              if (!already) focusReceivedOrder(po);
            }}
            aria-label="Order to receive"
          >
            <option value="">Choose an order to receive</option>
            {receivableOrders.map((o) => (
              <option key={o.id} value={o.id}>
                {o.po_number} · {supplierNameOf(o.supplier_id)}
              </option>
            ))}
          </select>
        </div>
        {receivableOrders.length === 0 ? (
          <div className="cat-empty">
            <p>Email or print a purchase order, then choose it here when the supplier delivers.</p>
          </div>
        ) : null}
        {receivePo && (
          <div className="cat-table-wrap" style={{ marginTop: 12 }}>
            <table className="table compact">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Left</th>
                  <th>Receive</th>
                  <th>Accept</th>
                  <th>Reject</th>
                  <th>Batch</th>
                </tr>
              </thead>
              <tbody>
                {receivePo.items
                  .filter((i) => i.outstanding_qty > 0)
                  .map((i) => {
                    const draft = receiveDrafts[i.id] || {
                      received: String(i.outstanding_qty),
                      accepted: String(i.outstanding_qty),
                      rejected: '0',
                      reason: '',
                      batch: '',
                      mfg: '',
                      expiry: '',
                    };
                    const tracks = products.find((p) => p.id === i.product_id)?.tracks_batches;
                    return (
                      <tr key={i.id}>
                        <td>{productNameOf(i.product_id, i)}</td>
                        <td>{products.find((p) => p.id === i.product_id)?.sku || '—'}</td>
                        <td>{i.outstanding_qty}</td>
                        <td>
                          <input
                            value={draft.received}
                            onChange={(e) =>
                              setReceiveDrafts((d) => ({
                                ...d,
                                [i.id]: { ...draft, received: e.target.value },
                              }))
                            }
                            aria-label={`Receive qty ${i.id}`}
                            style={{ width: 80 }}
                          />
                        </td>
                        <td>
                          <input
                            value={draft.accepted}
                            onChange={(e) =>
                              setReceiveDrafts((d) => ({
                                ...d,
                                [i.id]: { ...draft, accepted: e.target.value },
                              }))
                            }
                            aria-label={`Accept qty ${i.id}`}
                            style={{ width: 80 }}
                          />
                        </td>
                        <td>
                          <input
                            value={draft.rejected}
                            onChange={(e) =>
                              setReceiveDrafts((d) => ({
                                ...d,
                                [i.id]: { ...draft, rejected: e.target.value },
                              }))
                            }
                            aria-label={`Reject qty ${i.id}`}
                            style={{ width: 80 }}
                          />
                        </td>
                        <td>
                          {tracks ? (
                            <input
                              value={draft.batch}
                              onChange={(e) =>
                                setReceiveDrafts((d) => ({
                                  ...d,
                                  [i.id]: { ...draft, batch: e.target.value },
                                }))
                              }
                              placeholder="Batch"
                              aria-label="GRN batch number"
                            />
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8, alignItems: 'center' }}>
              <input
                value={grnNotes}
                onChange={(e) => setGrnNotes(e.target.value)}
                placeholder="Notes (optional)"
                aria-label="GRN notes"
              />
              <button
                type="button"
                className="btn-ok"
                onClick={() => {
                  const po = orders.find((o) => o.id === receiveOrderId);
                  if (!po || (po.status !== 'sent' && po.status !== 'partially_received')) {
                    setError('Choose the order to receive.');
                    return;
                  }
                  void postPartialReceive(po);
                }}
                aria-label="Post GRN"
              >
                Receive lines
              </button>
              <button
                type="button"
                className="btn-ok"
                onClick={() => {
                  const po = orders.find((o) => o.id === receiveOrderId);
                  if (!po || (po.status !== 'sent' && po.status !== 'partially_received')) {
                    setError('Choose the order to receive.');
                    return;
                  }
                  void receiveAll(po);
                }}
                aria-label="Receive all accepted"
              >
                Receive all
              </button>
            </div>
          </div>
        )}
        <h3 style={{ marginTop: 24 }}>Received</h3>
        {grns.length === 0 ? (
          <div className="cat-empty">
            <p>Receive a sent order to list the goods receipt here.</p>
          </div>
        ) : (
        <div className="cat-table-wrap">
        <table className="table cat-table purchase-ui-stack">
          <thead>
            <tr>
              <th className="col-id">GRN</th>
              <th className="col-id">PO</th>
              <th>Supplier</th>
              <th className="col-date">Date received</th>
              <th className="col-status">Status</th>
              <th className="col-num">Accepted</th>
              <th className="col-num">Rejected</th>
              <th className="col-num">Amount paid</th>
              <th className="col-num">Amount left</th>
              <th className="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {grns.map((g) => {
              const accepted = (g.items || []).reduce((s, i) => s + Number(i.accepted_qty || 0), 0);
              const rejected = (g.items || []).reduce((s, i) => s + Number(i.rejected_qty || 0), 0);
              const billed = invoices.some(
                (inv) => inv.goods_receipt_id === g.id && inv.status !== 'cancelled',
              );
              const billMoney = grnBillMoney(g.id);
              const grnActions: RowActionItem[] = [
                {
                  key: 'print',
                  label: 'Print',
                  ariaLabel: 'Print goods received note',
                  onClick: () => {
                    openPurchasingPrint(`/purchasing/grn/${g.id}/print?format=pdf`).catch((err) =>
                      setError(String(err)),
                    );
                  },
                },
                {
                  key: 'email',
                  label: 'Email',
                  ariaLabel: 'Email goods received note',
                  onClick: () =>
                    sendPurchasingDoc(`/purchasing/grn/${g.id}/send`, 'Goods received note emailed to'),
                },
                {
                  key: 'bill',
                  label: 'Add purchase',
                  variant: 'ok',
                  ariaLabel: `Create supplier bill from ${g.grn_number}`,
                  hidden: !(accepted > 0 && !billed),
                  onClick: () => {
                    setInvoiceGrnId(g.id);
                    setBillCreateOpen(true);
                    selectTab('invoices');
                  },
                },
              ];
              return (
                <tr key={g.id}>
                  <td className="col-id" data-label="GRN">{g.grn_number}</td>
                  <td className="col-id" data-label="PO">{poNumberOf(g.purchase_order_id)}</td>
                  <td data-label="Supplier">{supplierNameOf(g.supplier_id, g.purchase_order_id)}</td>
                  <td className="col-date" data-label="Date received">
                    {formatDate(g.received_at || g.created_at, formatPrefs) || '—'}
                  </td>
                  <td className="col-status" data-label="Status">
                    <StatusChip value={g.status} />
                  </td>
                  <td className="col-num" data-label="Accepted">{accepted}</td>
                  <td className="col-num" data-label="Rejected">{rejected}</td>
                  <td className="col-num" data-label="Amount paid">
                    {formatGrnBillField(billMoney, 'paid')}
                  </td>
                  <td className="col-num" data-label="Amount left">
                    {formatGrnBillField(billMoney, 'left')}
                  </td>
                  <td className="col-actions">
                    {billed ? (
                      <span className="muted">Billed</span>
                    ) : (
                      <RowActions label={`More actions for ${g.grn_number}`} primaryMax={1} items={grnActions} />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
        )}
        </div>
      )}

      {tab === 'history' && (
        <div className="card cat-panel">
          <div className="cat-head">
            <h2 style={{ margin: 0 }}>Purchase history</h2>
          </div>
          <p className="muted" style={{ margin: 0 }}>
            Orders, goods received, supplier bills, and returns — not the reports summary.
          </p>
          <div className="cat-table-wrap">
          <table className="table cat-table">
            <thead>
              <tr>
                <th className="col-date">Date</th>
                <th>Type</th>
                <th className="col-id">Number</th>
                <th>Supplier</th>
                <th className="col-status">Status</th>
                <th className="col-num">Amount / qty</th>
              </tr>
            </thead>
            <tbody>
              {purchaseHistory.map((row) => (
                <tr key={row.key}>
                  <td className="col-date">{row.at ? String(row.at).slice(0, 10) : '—'}</td>
                  <td>{row.kind}</td>
                  <td className="col-id">{row.ref}</td>
                  <td>{row.party}</td>
                  <td className="col-status">
                    <StatusChip value={row.status} />
                  </td>
                  <td className="col-num">{row.amount || '—'}</td>
                </tr>
              ))}
              {purchaseHistory.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    Add a supplier, then create an order, to see history for that supplier.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {tab === 'invoices' && (
        <>
          <div className="purchase-ui-actions">
            <button type="button" className="btn-primary" onClick={() => setBillCreateOpen(true)} aria-label="Create supplier bill from received goods">
              Bill from GRN
            </button>
            <button type="button" onClick={() => setBillManualOpen(true)} aria-label="Create supplier bill">
              Create supplier bill
            </button>
          </div>
          <div className="purchase-ui-bills">
            {openBills.length > 0
              ? openBills.map((inv) => (
                <p key={inv.id} className="purchase-ui-bill">
                  <span>
                    {billSupplierName(inv)} · {inv.invoice_number} · {inv.status} · paid{' '}
                    {formatNumber(inv.paid_amount ?? 0, formatPrefs)} · left {formatNumber(inv.balance_due, formatPrefs)}
                  </span>
                  {inv.supplier_id ? (
                    <a href={`/credit?kind=payable&panel=pay&supplier=${inv.supplier_id}&bill=${inv.id}`}>
                      Pay {inv.invoice_number}
                    </a>
                  ) : null}
                </p>
              ))
              : invoices.length > 0
                ? <p className="muted">Approve a supplier bill to see what you owe that supplier.</p>
                : null}
          </div>
          <div className="erp-split">
      {billCreateOpen ? (
      <FormModal
        title="Create supplier bill from received goods"
        busy={saveBusy}
        dirty={Boolean(invoiceGrnId || supplierInvoiceNo.trim())}
        onClose={() => setBillCreateOpen(false)}
      >
        <div className="erp-form-grid">
          <select
            value={invoiceGrnId}
            onChange={(e) => setInvoiceGrnId(e.target.value)}
            aria-label="Purchase invoice GRN"
          >
            <option value="">Choose the delivery you received (GRN)</option>
            {grns.map((g) => (
              <option key={g.id} value={g.id}>
                {g.grn_number} · {supplierNameOf(g.supplier_id, g.purchase_order_id)}
              </option>
            ))}
          </select>
          <input
            value={supplierInvoiceNo}
            onChange={(e) => setSupplierInvoiceNo(e.target.value)}
            placeholder="Number on the supplier's invoice"
            aria-label="Supplier invoice number"
            title="Optional supplier invoice #"
          />
          <details className="span-2 purchase-bill-more">
            <summary>More options: notes, link to the bill, discount, foreign currency</summary>
            <div className="purchase-bill-more-body">
          <input
            value={invNotes}
            onChange={(e) => setInvNotes(e.target.value)}
            placeholder="Notes (optional)"
            aria-label="Purchase invoice notes"
            title="Optional notes"
          />
          <input
            value={invAttachmentUrl}
            onChange={(e) => setInvAttachmentUrl(e.target.value)}
            placeholder="Attachment URL (optional https://…)"
            aria-label="Purchase invoice attachment URL"
            title="Web link to the bill (optional, must start with https://)"
          />
          <input
            value={grnInvHeaderDiscount}
            onChange={(e) => setGrnInvHeaderDiscount(e.target.value)}
            placeholder="Header discount (0 = use PO line discounts)"
            aria-label="Purchase invoice header discount"
            type="number"
            min={0}
            step="0.01"
          />
          <input
            value={invCurrency}
            onChange={(e) => setInvCurrency(e.target.value.toUpperCase())}
            placeholder="Currency (blank=base)"
            aria-label="Purchase invoice currency"
            pattern="[A-Z]{3}"
            maxLength={3}
            title="Currency (leave blank for your company currency)"
            style={{ width: 140 }}
          />
          <input
            value={invExchangeRate}
            onChange={(e) => setInvExchangeRate(e.target.value)}
            placeholder="FX rate (optional)"
            style={{ width: 120 }}
            type="number"
            min={0}
            step="0.0001"
            aria-label="Purchase invoice FX rate"
          />
              <span className="muted">
                Discounts from the order carry over; leave the discount at 0 to keep them. Currency and rate are only
                for suppliers who bill in another currency.
              </span>
            </div>
          </details>
          {(() => {
            const billGrn = grns.find((g) => g.id === invoiceGrnId);
            const lines = (billGrn?.items || []).filter((i) => Number(i.accepted_qty || 0) > 0);
            if (!billGrn || !lines.length) return null;
            return (
              <ul className="muted span-2" style={{ margin: 0, paddingLeft: 18 }}>
                {lines.map((line) => (
                  <li key={line.id}>
                    {productNameOf(line.product_id, line)} · accepted {line.accepted_qty}
                  </li>
                ))}
              </ul>
            );
          })()}
          <button
            onClick={createInvoiceFromGrn}
            disabled={!invoiceGrnId || saveBusy}
            aria-label="Draft purchase invoice from GRN"
          >
            {saveBusy ? 'Saving…' : 'Create bill'}
          </button>
        </div>
      </FormModal>
      ) : null}
      {billManualOpen ? (
      <FormModal
        title="Create supplier bill"
        busy={saveBusy}
        dirty={Boolean(manualInvSupplierId || billPickProductId || billLines.some((line) => line.productId))}
        onClose={() => setBillManualOpen(false)}
      >
        <div className="erp-form-grid">
          <select
            value={manualInvSupplierId}
            onChange={(e) => setManualInvSupplierId(e.target.value)}
            aria-label="Purchase invoice supplier"
          >
            <option value="">Select supplier</option>
            {suppliers
              .filter((s) => s.status !== 'inactive')
              .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          {!hideWarehouseUx ? (
          <label className="field">
            <span>Warehouse (store context)</span>
            <select
              aria-label="Purchase invoice warehouse"
              value={billWarehouseId}
              onChange={(e) => setBillWarehouseId(e.target.value)}
            >
              <option value="">Default / any</option>
              {storeWarehouses.map((w: any) => (
                <option key={w.id} value={w.id}>{w.code} — {w.name}</option>
              ))}
            </select>
          </label>
          ) : null}
          <input
            value={supplierInvoiceNo}
            onChange={(e) => setSupplierInvoiceNo(e.target.value)}
            placeholder="Supplier invoice #"
            aria-label="Supplier invoice number"
            title="Optional supplier invoice #"
          />
          <input
            value={invNotes}
            onChange={(e) => setInvNotes(e.target.value)}
            placeholder="Notes (optional)"
            aria-label="Purchase invoice notes"
            title="Optional notes"
          />
          <input
            value={invAttachmentUrl}
            onChange={(e) => setInvAttachmentUrl(e.target.value)}
            placeholder="Attachment URL (optional https://…)"
            aria-label="Purchase invoice attachment URL"
            title="Web link to the bill (optional, must start with https://)"
          />
          <input
            value={invCurrency}
            onChange={(e) => setInvCurrency(e.target.value.toUpperCase())}
            placeholder="Currency (blank=base)"
            aria-label="Purchase invoice currency"
            pattern="[A-Z]{3}"
            maxLength={3}
            title="Currency (leave blank for your company currency)"
            style={{ width: 140 }}
          />
          <input
            value={invExchangeRate}
            onChange={(e) => setInvExchangeRate(e.target.value)}
            placeholder="FX rate (optional)"
            style={{ width: 120 }}
            type="number"
            min={0}
            step="0.0001"
            aria-label="Purchase invoice FX rate"
          />
          <input
            value={manualInvHeaderDiscount}
            onChange={(e) => setManualInvHeaderDiscount(e.target.value)}
            placeholder="Header discount amount"
            aria-label="Purchase invoice header discount"
            type="number"
            min={0}
            step="0.01"
          />
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={manualInvRc} onChange={(e) => setManualInvRc(e.target.checked)} aria-label="Purchase invoice reverse charge" />
            Reverse charge (self-assess VAT; AP = net)
          </label>
          <span className="muted span-2">
            One supplier and bill header. Choose a product, then Add product — that line stays, and you can add another.
            Header discount and FX apply once on the bill total (tax is not doubled). Draft saves the bill only; posting receives stock for every line at the selected warehouse.
          </span>
        </div>
        <div className="erp-form-grid erp-modal-lines" style={{ marginTop: 12 }}>
          <select
            value={billPickProductId}
            onChange={(e) => {
              const productId = e.target.value;
              const product = products.find((p) => p.id === productId);
              setBillPickProductId(productId);
              if (product) setBillPickUnitCost(String(product.cost_price ?? 0));
            }}
            aria-label="Purchase invoice product"
          >
            <option value="">Select product</option>
            {products
              .filter((p) => p.is_active !== false)
              .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>
          <input
            value={billPickQty}
            onChange={(e) => setBillPickQty(e.target.value)}
            placeholder="Quantity"
            aria-label="Purchase invoice quantity"
          />
          <AmountField
            value={billPickUnitCost}
            onChange={(e) => setBillPickUnitCost(e.target.value)}
            placeholder="Unit cost"
            aria-label="Purchase invoice unit price"
          />
          <input
            value={billPickTax}
            onChange={(e) => setBillPickTax(e.target.value)}
            placeholder="Tax rate % (blank = auto)"
            aria-label="Purchase invoice tax rate percent"
          />
          <input
            value={billPickDiscount}
            onChange={(e) => setBillPickDiscount(e.target.value)}
            placeholder="Line discount amount"
            aria-label="Purchase invoice line discount"
            type="number"
            min={0}
            step="0.01"
          />
          <button
            type="button"
            onClick={addBillProduct}
            aria-label="Add purchase invoice product"
          >
            Add product
          </button>
        </div>
        {products.filter((p) => p.is_active !== false).length === 0 ? (
          <p className="muted">No products in the catalog yet. Add them in Inventory, then come back.</p>
        ) : null}
        <div className="cat-table-wrap erp-modal-lines" style={{ marginTop: 12 }}>
          <table className="table">
            <thead>
              <tr>
                <th className="col-text">Product</th>
                <th>SKU</th>
                <th>Qty</th>
                <th>Unit cost</th>
                <th>Tax %</th>
                <th>Discount</th>
                <th>Line total</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {billLines.map((line, index) => {
                const product = products.find((p) => p.id === line.productId);
                return (
                <tr key={line.key}>
                  <td className="col-text">{product?.name || 'Product'}</td>
                  <td>{product?.sku || '—'}</td>
                  <td>
                    <input
                      value={line.qty}
                      onChange={(e) =>
                        setBillLines((rows) =>
                          rows.map((row) => (row.key === line.key ? { ...row, qty: e.target.value } : row)),
                        )
                      }
                      placeholder="Quantity"
                      aria-label={`Purchase invoice quantity ${index + 1}`}
                    />
                  </td>
                  <td>
                    <AmountField
                      inline
                      value={line.unitCost}
                      onChange={(e) =>
                        setBillLines((rows) =>
                          rows.map((row) => (row.key === line.key ? { ...row, unitCost: e.target.value } : row)),
                        )
                      }
                      placeholder="Unit cost"
                      aria-label={`Purchase invoice unit price ${index + 1}`}
                    />
                  </td>
                  <td>
                    <input
                      value={line.taxRate}
                      onChange={(e) =>
                        setBillLines((rows) =>
                          rows.map((row) => (row.key === line.key ? { ...row, taxRate: e.target.value } : row)),
                        )
                      }
                      placeholder="Tax rate % (blank = auto)"
                      aria-label={`Purchase invoice tax rate percent ${index + 1}`}
                    />
                  </td>
                  <td>
                    <input
                      value={line.discount}
                      onChange={(e) =>
                        setBillLines((rows) =>
                          rows.map((row) => (row.key === line.key ? { ...row, discount: e.target.value } : row)),
                        )
                      }
                      placeholder="Line discount amount"
                      aria-label={`Purchase invoice line discount ${index + 1}`}
                      type="number"
                      min={0}
                      step="0.01"
                    />
                  </td>
                  <td>{billLineTotal(line).toFixed(2)}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() =>
                        setBillLines((rows) => rows.filter((row) => row.key !== line.key))
                      }
                      aria-label="Remove purchase invoice line"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
                );
              })}
              {billLines.length === 0 ? (
                <tr>
                  <td colSpan={8} className="muted">
                    Choose a product above, then Add product. Each click keeps the earlier lines.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="grid" style={{ marginTop: 12 }}>
          <div className="card">
            <div className="muted">Subtotal</div>
            <div className="kpi">{billPreview.subtotal.toFixed(2)}</div>
          </div>
          <div className="card">
            <div className="muted">Line discounts</div>
            <div className="kpi">{billPreview.lineDiscount.toFixed(2)}</div>
          </div>
          <div className="card">
            <div className="muted">Header discount</div>
            <div className="kpi">{billPreview.headerDiscount.toFixed(2)}</div>
          </div>
          <div className="card">
            <div className="muted">{manualInvRc ? 'Tax (memo)' : 'Tax'}</div>
            <div className="kpi">{billPreview.tax.toFixed(2)}</div>
          </div>
          <div className="card">
            <div className="muted">Bill total</div>
            <div className="kpi">{billPreview.total.toFixed(2)}</div>
          </div>
        </div>
        <p className="muted">
          Bill total = subtotal {manualInvRc ? '' : '+ tax '}− header discount in document currency.
          Line discounts change line totals only; they are not added again to the header (no double-count).
          {invCurrency.trim() ? ` FX ${invCurrency.trim()} @ ${invExchangeRate || 'resolve'}.` : ''}
        </p>
        <button
          onClick={createManualInvoice}
          disabled={!manualInvSupplierId || billPreview.lines.length < 1 || saveBusy}
          aria-label="Draft manual purchase invoice"
        >
          {saveBusy ? 'Saving…' : 'Draft manual invoice'}
        </button>
      </FormModal>
      ) : null}
          </div>

          {ocrDraft && ocrFor && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3>Supplier invoice OCR</h3>
              <p className="muted">
                Apply only to {invoices.find((row) => row.id === ocrFor)?.invoice_number || 'this bill'}.
                Engine: {ocrMeta?.engine || '—'} · Confidence: {ocrMeta?.confidence ?? '—'}
                {ocrMeta?.suggestions?.ocr_amount != null
                  ? ` · OCR amount ${ocrMeta.suggestions.ocr_amount}`
                  : ''}
              </p>
              <div style={{ display: 'grid', gap: 8 }}>
                <input
                  value={ocrDraft.supplier_invoice_number}
                  onChange={(e) =>
                    setOcrDraft({ ...ocrDraft, supplier_invoice_number: e.target.value })
                  }
                  placeholder="Supplier invoice #"
                  aria-label="Supplier invoice number"
                  title="Optional supplier invoice #"
                />
                <input
                  aria-label="Purchase invoice OCR date"
                  value={ocrDraft.invoice_date}
                  onChange={(e) => setOcrDraft({ ...ocrDraft, invoice_date: e.target.value })}
                  placeholder="Invoice date YYYY-MM-DD"
                />
                <input
                  value={ocrDraft.notes}
                  onChange={(e) => setOcrDraft({ ...ocrDraft, notes: e.target.value })}
                  placeholder="Notes"
                  aria-label="Purchase invoice OCR notes"
                  title="Optional notes"
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" onClick={applyInvoiceOcr} aria-label="Apply purchase invoice OCR">
                    Apply to draft
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setOcrFor(null);
                      setOcrDraft(null);
                      setOcrMeta(null);
                    }}
                    aria-label="Dismiss purchase invoice OCR"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          )}
        <div className="card">
          <label className="field">
            <span>Cancel reason</span>
            <input
              className="purch-reason"
              value={piCancelReason}
              onChange={(e) => setPiCancelReason(e.target.value)}
              placeholder="Required before Cancel"
              title="Required cancel reason"
              aria-label="Purchase invoice cancel reason"
            />
          </label>
          <p className="muted" style={{ marginTop: 6 }}>
            Saved on the supplier bill notes.
          </p>
        </div>
        <div className="card cat-panel">
        <div className="purch-filter-row">
        <select
          value={piManageFilter}
          onChange={(e) =>
            setPiManageFilter(
              e.target.value as
                | 'all'
                | 'draft'
                | 'unpaid'
                | 'partial'
                | 'paid'
                | 'overdue'
                | 'cancelled'
            )
          }
          title="Filter purchase invoice list by status"
          aria-label="Purchase invoice status filter"
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft only</option>
          <option value="unpaid">Unpaid only</option>
          <option value="partial">Partial only</option>
          <option value="paid">Paid only</option>
          <option value="overdue">Overdue only</option>
          <option value="cancelled">Cancelled only</option>
        </select>
        </div>
        <div className="cat-table-wrap">
        <table className="table purchase-ui-stack">
          <thead>
            <tr>
              <th className="col-id">Invoice</th>
              <th>Supplier</th>
              <th className="col-id">Supplier #</th>
              <th className="col-status">Status</th>
              <th className="col-status">Currency</th>
              <th className="col-num">Total</th>
              <th className="col-num">RC</th>
              <th className="col-num">Amount paid</th>
              <th className="col-num">Amount left</th>
              <th className="col-status">AP posted</th>
              <th className="col-status">File</th>
              <th className="col-text">Notes</th>
              <th className="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedInvoices.map((inv) => {
              const piActions: RowActionItem[] = [
                {
                  key: 'print',
                  label: 'Print',
                  ariaLabel: 'Print supplier bill',
                  onClick: () => {
                    openPurchasingPrint(`/purchasing/invoices/${inv.id}/print?format=pdf`).catch((err) =>
                      setError(String(err)),
                    );
                  },
                },
                {
                  key: 'email',
                  label: 'Email',
                  ariaLabel: 'Email supplier bill',
                  onClick: () =>
                    sendPurchasingDoc(`/purchasing/invoices/${inv.id}/send`, 'Supplier bill emailed to'),
                },
                {
                  key: 'approve',
                  label: 'Approve',
                  variant: 'ok',
                  hidden: inv.status !== 'draft',
                  ariaLabel: `Approve purchase invoice ${inv.id}`,
                  onClick: () => approveInvoice(inv.id),
                },
                {
                  key: 'cancel',
                  label: 'Cancel',
                  variant: 'danger',
                  hidden: !inv.can_cancel,
                  ariaLabel: `Cancel purchase invoice ${inv.id}`,
                  onClick: () => cancelInvoice(inv),
                },
                {
                  key: 'pay',
                  label: 'Record payment',
                  hidden: !(
                    (inv.status === 'unpaid' || inv.status === 'partial' || inv.status === 'overdue') &&
                    inv.supplier_id
                  ),
                  ariaLabel: `Record payment for supplier bill ${inv.id}`,
                  onClick: () => {
                    window.location.href = `/credit?kind=payable&panel=pay&supplier=${inv.supplier_id}&bill=${inv.id}`;
                  },
                },
                {
                  key: 'upload',
                  node: (
                    <label style={{ cursor: 'pointer', display: 'block', width: '100%' }}>
                      <span className="muted" style={{ textDecoration: 'underline' }}>
                        Upload
                      </span>
                      <input
                        type="file"
                        accept="application/pdf,image/png,image/jpeg,image/webp,image/gif"
                        style={{ display: 'none' }}
                        aria-label={`Upload purchase invoice attachment ${inv.id}`}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) uploadInvoiceAttachment(inv.id, file);
                          e.target.value = '';
                        }}
                      />
                    </label>
                  ),
                },
                {
                  key: 'preview',
                  label: 'Preview',
                  hidden: !inv.has_attachment,
                  ariaLabel: `Preview purchase invoice attachment ${inv.id}`,
                  onClick: () =>
                    setAttachPreview({
                      apiPath: `/purchasing/invoices/${inv.id}/attachment`,
                      title: `Invoice attachment — ${inv.invoice_number || inv.id.slice(0, 8)}`,
                    }),
                },
                {
                  key: 'download',
                  label: 'Download',
                  hidden: !inv.has_attachment,
                  ariaLabel: 'Download purchase invoice attachment',
                  onClick: () => downloadInvoiceAttachment(inv.id),
                },
                {
                  key: 'ocr',
                  label: 'OCR',
                  hidden: !(inv.has_attachment && inv.status === 'draft'),
                  ariaLabel: `Suggest purchase invoice OCR ${inv.id}`,
                  onClick: () => suggestInvoiceOcr(inv.id),
                },
              ];
              return (
              <tr key={inv.id}>
                <td className="col-id" data-label="Invoice">
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const r = await api(`/purchasing/invoices/${inv.id}`);
                        setSelectedInvoice(r.data);
                        if (ocrFor && ocrFor !== inv.id) {
                          setOcrFor(null);
                          setOcrDraft(null);
                          setOcrMeta(null);
                        }
                      } catch (err: any) {
                        setError(friendlyPurchaseError(err));
                      }
                    }}
                    style={{ background: 'none', border: 0, color: 'var(--deep-green, #006B2E)', cursor: 'pointer' }}
                    aria-label={`View purchase invoice ${inv.id}`}
                  >
                    {inv.invoice_number}
                  </button>
                </td>
                <td data-label="Supplier">{billSupplierName(inv)}</td>
                <td className="col-id" data-label="Supplier #">{inv.supplier_invoice_number || '—'}</td>
                <td className="col-status" data-label="Status"><StatusChip value={inv.status} /></td>
                <td className="col-status" data-label="Currency">
                  {inv.currency
                    ? `${inv.currency}${inv.exchange_rate != null ? ` @ ${inv.exchange_rate}` : ''}`
                    : '—'}
                </td>
                <td className="col-num" data-label="Total">{formatNumber(inv.total_amount, formatPrefs)}</td>
                <td className="col-num" data-label="RC">
                  {inv.is_reverse_charge
                    ? `${inv.reverse_charge_tax ?? 0}`
                    : inv.tax_amount ?? '—'}
                </td>
                <td className="col-num" data-label="Amount paid">{formatNumber(inv.paid_amount ?? 0, formatPrefs)}</td>
                <td className="col-num" data-label="Amount left">{formatNumber(inv.balance_due, formatPrefs)}</td>
                <td className="col-status" data-label="AP posted">
                  <StatusChip value={inv.ap_posted ? 'posted' : 'draft'} label={inv.ap_posted ? 'Posted' : 'Via GRN'} />
                </td>
                <td className="col-status" data-label="File">
                  {inv.has_attachment ? <StatusChip value="active" label="Yes" /> : '—'}
                </td>
                <td className="col-text muted" data-label="Notes">
                  {inv.notes || '—'}
                </td>
                <td className="col-actions">
                  <RowActions label={`More actions for ${inv.invoice_number || inv.id}`} primaryMax={1} items={piActions} />
                </td>
              </tr>
              );
            })}
            {managedInvoices.length === 0 && (
              <tr>
                <td colSpan={13} className="muted">
                  {invoices.length === 0
                    ? 'Receive goods, then create a supplier bill for that supplier.'
                    : 'No purchase invoices for this filter, so choose All statuses to see them.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
        </div>
        {selectedInvoice && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3>
              {selectedInvoice.invoice_number}
              {' — '}
              {billSupplierName(selectedInvoice)}
              {' — '}
              {selectedInvoice.status}
              {selectedInvoice.currency
                ? ` · ${selectedInvoice.currency} @ ${selectedInvoice.exchange_rate ?? 1}`
                : ''}
              {selectedInvoice.warehouse_id
                ? ` · ${warehouses.find((w: any) => w.id === selectedInvoice.warehouse_id)?.code || selectedInvoice.warehouse_id}`
                : ''}
            </h3>
            {(selectedInvoice.status === 'unpaid' || selectedInvoice.status === 'partial' || selectedInvoice.status === 'overdue') && selectedInvoice.supplier_id ? (
              <p style={{ marginTop: 0 }}>
                <a
                  className="btn-primary"
                  href={`/credit?kind=payable&panel=pay&supplier=${selectedInvoice.supplier_id}&bill=${selectedInvoice.id}`}
                  aria-label={`Record payment for supplier bill ${selectedInvoice.id}`}
                >
                  Pay this bill
                </a>
              </p>
            ) : null}
            {selectedInvoice.can_cancel && (
              <p style={{ marginTop: 0 }}>
                <button
                  type="button"
                  className="btn-danger"
                  onClick={() => cancelInvoice(selectedInvoice)}
                  aria-label={`Cancel purchase invoice ${selectedInvoice.id}`}
                >
                  Cancel invoice
                </button>
                <span className="muted" style={{ marginLeft: 8 }}>
                  Allowed for draft, unpaid, or overdue bills with no payments. Enter a cancel reason first.
                  Reverses AP if posted.
                </span>
              </p>
            )}
            {selectedInvoice.notes && (
              <p className="muted" style={{ marginTop: 0, whiteSpace: 'pre-wrap' }}>
                Notes: {selectedInvoice.notes}
              </p>
            )}
            <div className="cat-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Qty</th>
                  <th>Unit</th>
                  <th>Tax %</th>
                  <th>Discount</th>
                  <th>Line tax</th>
                  <th>Line total</th>
                </tr>
              </thead>
              <tbody>
                {(selectedInvoice.items || []).map((it) => (
                  <tr key={it.id}>
                    <td>{productName(it.product_id, it)}</td>
                    <td>{products.find((p) => p.id === it.product_id)?.sku || '—'}</td>
                    <td>{it.quantity}</td>
                    <td>{it.unit_price}</td>
                    <td>{it.tax_rate}</td>
                    <td>{it.discount ?? 0}</td>
                    <td>
                      {it.line_tax ?? 0}
                      {(it.tax_components || []).length
                        ? ` (${(it.tax_components || [])
                            .map((c) => `${c.name || c.code}:${c.amount}`)
                            .join(', ')})`
                        : ''}
                    </td>
                    <td>{it.line_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
            <div className="grid" style={{ marginTop: 12 }}>
              <div className="card">
                <div className="muted">Subtotal</div>
                <div className="kpi">{selectedInvoice.subtotal ?? 0}</div>
              </div>
              <div className="card">
                <div className="muted">Tax</div>
                <div className="kpi">{selectedInvoice.tax_amount ?? 0}</div>
              </div>
              <div className="card">
                <div className="muted">Discount</div>
                <div className="kpi">{selectedInvoice.discount_amount ?? 0}</div>
              </div>
              <div className="card">
                <div className="muted">Total</div>
                <div className="kpi">{selectedInvoice.total_amount ?? 0}</div>
              </div>
            </div>
            {(selectedInvoice.tax_breakdown?.by_rate || []).length > 0 && (
              <div style={{ marginTop: 12 }}>
                <h4 style={{ margin: '8px 0' }}>Tax breakdown</h4>
                <table className="table">
                  <thead>
                    <tr>
                      <th>Rate</th>
                      <th>Taxable</th>
                      <th>Tax</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedInvoice.tax_breakdown!.by_rate!.map((r, idx) => (
                      <tr key={`${r.tax_rate}-${idx}`}>
                        <td>{r.tax_rate}%</td>
                        <td>{r.taxable}</td>
                        <td>{r.tax}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!!selectedInvoice.reverse_charge_tax && selectedInvoice.reverse_charge_tax > 0 && (
                  <p className="muted">
                    Reverse-charge tax (memo): {selectedInvoice.reverse_charge_tax}
                  </p>
                )}
              </div>
            )}
          </div>
        )}
        </>
      )}

      {tab === 'returns' && (
        <>
      <div style={{ marginBottom: 12 }}>
        <button type="button" className="btn-primary" onClick={() => setReturnCreateOpen(true)} aria-label="Create purchase return">
          Create purchase return
        </button>
      </div>
      {returnCreateOpen ? (
      <FormModal
        title="Create purchase return"
        busy={saveBusy}
        dirty={Boolean(grnId || returnReason || returnNotes.trim() || returnLines.some((line) => Number(line.qty) > 0))}
        onClose={() => setReturnCreateOpen(false)}
      >
        <div className="erp-form-grid">
          <select
            value={grnId}
            onChange={(e) => {
              const nextId = e.target.value;
              setGrnId(nextId);
              const receipt = grns.find((g) => g.id === nextId);
              const eligible = (receipt?.items || []).filter(
                (item) => Number(item.remaining_return_qty ?? item.accepted_qty ?? 0) > 0
              );
              setReturnLines(
                eligible.length
                  ? eligible.map((item) => ({ key: item.id, grnItemId: item.id, qty: '' }))
                  : [emptyReturnLine()]
              );
            }}
            aria-label="Return from GRN"
          >
            <option value="">Select GRN</option>
            {grns.map((g) => (
              <option key={g.id} value={g.id}>
                {g.grn_number} · {supplierNameOf(g.supplier_id, g.purchase_order_id)}
              </option>
            ))}
          </select>
          <p className="muted" style={{ margin: '4px 0 0' }}>
            Enter a quantity for every product you are sending back. Leave the other lines blank.
          </p>
          {returnLines.map((line, index) => {
            const source = (selectedGrn?.items || []).find((item) => item.id === line.grnItemId);
            const remaining = source?.remaining_return_qty ?? source?.accepted_qty;
            const lineOptions = (
              <>
                <option value="">Select GRN line</option>
                {(selectedGrn?.items || []).map((item) => (
                  <option key={item.id} value={item.id}>
                    {productName(item.product_id, item)} (remaining {item.remaining_return_qty ?? item.accepted_qty})
                  </option>
                ))}
              </>
            );
            const onLine = (grnItemId: string) =>
              setReturnLines((rows) => rows.map((row) => (row.key === line.key ? { ...row, grnItemId } : row)));
            const onQty = (qty: string) =>
              setReturnLines((rows) => rows.map((row) => (row.key === line.key ? { ...row, qty } : row)));
            return (
              <div key={line.key} className="erp-form-grid">
                {index === 0 ? (
                  <select
                    value={line.grnItemId}
                    onChange={(e) => onLine(e.target.value)}
                    disabled={!selectedGrn}
                    aria-label="Purchase return GRN line"
                  >
                    {lineOptions}
                  </select>
                ) : (
                  <select
                    value={line.grnItemId}
                    onChange={(e) => onLine(e.target.value)}
                    disabled={!selectedGrn}
                    aria-label={`Purchase return GRN line ${index + 1}`}
                  >
                    {lineOptions}
                  </select>
                )}
                {index === 0 ? (
                  <input
                    value={line.qty}
                    onChange={(e) => onQty(e.target.value)}
                    placeholder={remaining == null ? 'Return qty' : `Return qty (max ${remaining})`}
                    aria-label="Purchase return quantity"
                  />
                ) : (
                  <input
                    value={line.qty}
                    onChange={(e) => onQty(e.target.value)}
                    placeholder={remaining == null ? 'Return qty' : `Return qty (max ${remaining})`}
                    aria-label={`Purchase return quantity ${index + 1}`}
                  />
                )}
              </div>
            );
          })}
          <select
            value={returnReason}
            onChange={(e) => setReturnReason(e.target.value)}
            aria-label="Purchase return reason"
          >
            <option value="">Select reason</option>
            <option value="damaged">Damaged</option>
            <option value="wrong_item">Wrong item</option>
            <option value="expiry">Expiry</option>
            <option value="quality">Quality</option>
            <option value="other">Other</option>
          </select>
          <input
            value={returnNotes}
            onChange={(e) => setReturnNotes(e.target.value)}
            placeholder="Notes (optional)"
            aria-label="Purchase return notes"
            title="Optional notes"
          />
          <button
            onClick={createReturn}
            disabled={!grnId || !returnReason || saveBusy || !returnLines.some((line) => line.grnItemId.trim() && Number(line.qty) > 0)}
            aria-label="Create purchase return"
          >
            {saveBusy ? 'Saving…' : 'Draft return'}
          </button>
        </div>
      </FormModal>
      ) : null}
      <div className="card">
        <label className="field">
          <span>Cancel reason</span>
          <input
            className="purch-reason"
            value={prCancelReason}
            onChange={(e) => setPrCancelReason(e.target.value)}
            placeholder="Required before Cancel"
            title="Required cancel reason"
            aria-label="Purchase return cancel reason"
          />
        </label>
        <p className="muted" style={{ marginTop: 6 }}>
          Appended to draft return notes and audit (<code>POST .../returns/.../cancel</code>{' '}
          {'{ reason }'}). Draft only; no stock/AP.
        </p>
      </div>
        <div className="card cat-panel">
        <div className="purch-filter-row">
        <select
          value={returnManageFilter}
          onChange={(e) =>
            setReturnManageFilter(
              e.target.value as 'all' | 'draft' | 'posted' | 'cancelled'
            )
          }
          title="Filter purchase return list by status"
          aria-label="Purchase return status filter"
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft only</option>
          <option value="posted">Posted only</option>
          <option value="cancelled">Cancelled only</option>
        </select>
        </div>
        <div className="cat-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th className="col-id">Return</th>
              <th>Supplier</th>
              <th className="col-id">Debit note</th>
              <th className="col-status">Reason</th>
              <th className="col-status">Status</th>
              <th className="col-num">Discount</th>
              <th className="col-num">Total</th>
              <th className="col-text">Notes</th>
              <th className="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedReturns.map((r) => {
              const returnActions: RowActionItem[] = [
                {
                  key: 'post',
                  label: 'Post',
                  variant: 'ok',
                  hidden: r.status !== 'draft',
                  ariaLabel: `Post purchase return ${r.id}`,
                  onClick: () => postReturn(r.id),
                },
                {
                  key: 'cancel',
                  label: 'Cancel',
                  variant: 'danger',
                  hidden: r.status !== 'draft',
                  ariaLabel: `Cancel purchase return ${r.id}`,
                  onClick: () => cancelReturn(r),
                },
                {
                  key: 'print',
                  label: 'Print',
                  ariaLabel: `Print purchase return ${r.id}`,
                  onClick: () => {
                    openPurchasingPrint(`/purchasing/returns/${r.id}/print?format=pdf`).catch((err) =>
                      setError(String(err)),
                    );
                  },
                },
                {
                  key: 'email',
                  label: 'Email',
                  ariaLabel: 'Email purchase return',
                  onClick: () =>
                    sendPurchasingDoc(`/purchasing/returns/${r.id}/send`, 'Debit note emailed to'),
                },
              ];
              return (
              <tr key={r.id}>
                <td className="col-id">{r.return_number}</td>
                <td>{supplierNameOf(r.supplier_id || grns.find((g) => g.id === r.goods_receipt_id)?.supplier_id, grns.find((g) => g.id === r.goods_receipt_id)?.purchase_order_id)}</td>
                <td className="col-id">{r.debit_note_number || '—'}</td>
                <td className="col-status"><StatusChip value={r.reason} /></td>
                <td className="col-status"><StatusChip value={r.status} /></td>
                <td className="col-num">{r.discount_amount ?? 0}</td>
                <td className="col-num">{formatNumber(r.total_amount)}</td>
                <td className="col-text muted">
                  {r.notes || '—'}
                </td>
                <td className="col-actions">
                  <RowActions label={`More actions for ${r.return_number || r.id}`} primaryMax={1} items={returnActions} />
                </td>
              </tr>
              );
            })}
            {managedReturns.length === 0 && (
              <tr>
                <td colSpan={9} className="muted">
                  {returns.length === 0
                    ? 'Receive goods first, then create a purchase return for that supplier.'
                    : 'No purchase returns for this filter, so choose All statuses to see them.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
        </div>
        </>
      )}
      {attachPreview && (
        <AttachmentPreview
          open
          apiPath={attachPreview.apiPath}
          title={attachPreview.title}
          onClose={() => setAttachPreview(null)}
          onError={(msg) => setError(msg)}
        />
      )}
    </div>
  );
}
