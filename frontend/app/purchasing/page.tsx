'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { useTabQuery } from '../../lib/tabQuery';

type Tab = 'suppliers' | 'requests' | 'orders' | 'grn' | 'invoices' | 'returns' | 'settings';
const PURCHASING_TABS: Tab[] = [
  'suppliers',
  'requests',
  'orders',
  'grn',
  'invoices',
  'returns',
  'settings',
];
type SupplierContact = {
  id: string;
  name: string;
  email?: string | null;
  phone?: string | null;
  designation?: string | null;
  is_primary?: boolean;
};
type Supplier = {
  id: string;
  name: string;
  code?: string | null;
  party_type?: string | null;
  category?: string | null;
  status?: string;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  notes?: string | null;
  payment_terms_days?: number;
  early_pay_discount_pct?: number | null;
  early_pay_discount_days?: number | null;
  credit_limit?: number;
  contacts?: SupplierContact[];
};
type SupplierHistory = {
  orders: { id: string; po_number: string; status: string; total_amount: number }[];
  invoices: { id: string; invoice_number: string; status: string; total_amount: number }[];
  returns: { id: string; return_number: string; status: string; total_amount: number }[];
  payments: { id: string; amount: number; payment_method: string }[];
};
type Product = { id: string; name: string; sku: string; cost_price: number };
type PoItem = {
  id: string;
  product_id: string;
  quantity: number;
  received_qty: number;
  unit_price: number;
  tax_rate?: number;
  discount?: number;
  line_total?: number;
  outstanding_qty: number;
};
type PurchaseOrder = {
  id: string;
  po_number: string;
  supplier_id: string;
  status: string;
  total_amount: number;
  subtotal?: number;
  tax_amount?: number;
  purchase_request_id?: string | null;
  revision?: number;
  amendment_count?: number;
  delivery_address?: string | null;
  notes?: string | null;
  items: PoItem[];
};
type PoAmendment = {
  id: string;
  revision: number;
  reason: string;
  created_at?: string;
  changes?: { before?: { header?: { total_amount?: number } }; after?: { header?: { total_amount?: number } } };
};
type PurchaseRequest = {
  id: string;
  request_number: string;
  supplier_id: string;
  status: string;
  department?: string | null;
  required_date?: string | null;
  purchase_order_id?: string | null;
  rejection_reason?: string | null;
  estimated_total?: number;
  approval_step?: number;
  approval_steps_required?: number;
  awaiting_level?: number | null;
  awaiting_roles?: string[];
  items: { id: string; product_id: string; quantity: number; unit_price: number }[];
};
type ApprovalLevel = { min_amount: number; roles: string[]; label?: string };
type GrnItem = {
  id: string;
  product_id: string;
  accepted_qty: number;
  received_qty: number;
};
type Grn = {
  id: string;
  grn_number: string;
  purchase_order_id: string;
  supplier_id: string;
  status: string;
  items: GrnItem[];
};
type PurchaseReturn = {
  id: string;
  return_number: string;
  debit_note_number?: string;
  goods_receipt_id: string;
  status: string;
  reason: string;
  total_amount: number;
  items?: { id: string; product_id: string; quantity: number; line_total: number }[];
};
type PurchaseInvoice = {
  id: string;
  invoice_number: string;
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
  has_attachment?: boolean;
  attachment_url?: string | null;
};

export default function Page() {
  const [tab, setTab] = useTabQuery(PURCHASING_TABS, 'requests');
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [grns, setGrns] = useState<Grn[]>([]);
  const [invoices, setInvoices] = useState<PurchaseInvoice[]>([]);
  const [returns, setReturns] = useState<PurchaseReturn[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<PurchaseOrder | null>(null);
  const [supplierId, setSupplierId] = useState('');
  const [supplierName, setSupplierName] = useState('');
  const [supplierCode, setSupplierCode] = useState('');
  const [supplierType, setSupplierType] = useState('');
  const [supplierCategory, setSupplierCategory] = useState('');
  const [supplierEmail, setSupplierEmail] = useState('');
  const [supplierPhone, setSupplierPhone] = useState('');
  const [supplierAddress, setSupplierAddress] = useState('');
  const [supplierNotes, setSupplierNotes] = useState('');
  const [supplierTerms, setSupplierTerms] = useState('0');
  const [supplierEarlyPayPct, setSupplierEarlyPayPct] = useState('');
  const [supplierEarlyPayDays, setSupplierEarlyPayDays] = useState('');
  const [supplierCredit, setSupplierCredit] = useState('0');
  const [selectedSupplierId, setSelectedSupplierId] = useState('');
  const [supplierHistory, setSupplierHistory] = useState<SupplierHistory | null>(null);
  const [contactName, setContactName] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [contactPrimary, setContactPrimary] = useState(false);
  const [emailOnSend, setEmailOnSend] = useState(true);
  const [amendReason, setAmendReason] = useState('');
  const [amendQty, setAmendQty] = useState('');
  const [amendPrice, setAmendPrice] = useState('');
  const [amendTaxRate, setAmendTaxRate] = useState('');
  const [amendDiscount, setAmendDiscount] = useState('');
  const [amendDeliveryAddress, setAmendDeliveryAddress] = useState('');
  const [amendments, setAmendments] = useState<PoAmendment[]>([]);
  const [productId, setProductId] = useState('');
  const [qty, setQty] = useState('10');
  const [unitPrice, setUnitPrice] = useState('0');
  const [poTaxRate, setPoTaxRate] = useState('0');
  const [poDiscount, setPoDiscount] = useState('0');
  const [poDeliveryAddress, setPoDeliveryAddress] = useState('');
  const [prDepartment, setPrDepartment] = useState('');
  const [prRequiredDate, setPrRequiredDate] = useState('');
  const [rejectReason, setRejectReason] = useState('');
  const [prLevels, setPrLevels] = useState<ApprovalLevel[]>([]);
  const [receiveLines, setReceiveLines] = useState<
    Record<
      string,
      { accepted: string; rejected: string; reason: string; batch: string; expiry: string }
    >
  >({});
  const [grnId, setGrnId] = useState('');
  const [returnLines, setReturnLines] = useState<Record<string, string>>({});
  const [returnReason, setReturnReason] = useState('other');
  const [invoiceGrnId, setInvoiceGrnId] = useState('');
  const [supplierInvoiceNo, setSupplierInvoiceNo] = useState('');
  const [manualInvSupplierId, setManualInvSupplierId] = useState('');
  const [manualInvProductId, setManualInvProductId] = useState('');
  const [manualInvQty, setManualInvQty] = useState('1');
  const [manualInvPrice, setManualInvPrice] = useState('0');
  const [manualInvTaxRate, setManualInvTaxRate] = useState('15');
  const [manualInvRc, setManualInvRc] = useState(false);
  const [ocrFor, setOcrFor] = useState<string | null>(null);
  const [ocrDraft, setOcrDraft] = useState<{
    supplier_invoice_number: string;
    notes: string;
    invoice_date: string;
  } | null>(null);
  const [ocrMeta, setOcrMeta] = useState<any>(null);
  const [invoiceStatusFilter, setInvoiceStatusFilter] = useState('');
  const [returnStatusFilter, setReturnStatusFilter] = useState('');
  const [prStatusFilter, setPrStatusFilter] = useState('');
  const [poStatusFilter, setPoStatusFilter] = useState('');
  const [grnStatusFilter, setGrnStatusFilter] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function refresh(opts?: {
    invoiceStatus?: string;
    returnStatus?: string;
    prStatus?: string;
    poStatus?: string;
    grnStatus?: string;
  }) {
    const status = opts?.invoiceStatus !== undefined ? opts.invoiceStatus : invoiceStatusFilter;
    const retStatus = opts?.returnStatus !== undefined ? opts.returnStatus : returnStatusFilter;
    const prStatus = opts?.prStatus !== undefined ? opts.prStatus : prStatusFilter;
    const poStatus = opts?.poStatus !== undefined ? opts.poStatus : poStatusFilter;
    const grnStatus = opts?.grnStatus !== undefined ? opts.grnStatus : grnStatusFilter;
    const invPath = status
      ? `/purchasing/invoices?status=${encodeURIComponent(status)}`
      : '/purchasing/invoices';
    const retPath = retStatus
      ? `/purchasing/returns?status=${encodeURIComponent(retStatus)}`
      : '/purchasing/returns';
    const prPath = prStatus
      ? `/purchasing/requests?status=${encodeURIComponent(prStatus)}`
      : '/purchasing/requests';
    const poPath = poStatus
      ? `/purchasing/orders?status=${encodeURIComponent(poStatus)}`
      : '/purchasing/orders';
    const grnPath = grnStatus
      ? `/purchasing/grn?status=${encodeURIComponent(grnStatus)}`
      : '/purchasing/grn';
    const [prRes, poRes, supRes, prodRes, grnRes, invRes, retRes, settingsRes] = await Promise.all([
      api(prPath),
      api(poPath),
      api('/suppliers'),
      api('/products'),
      api(grnPath),
      api(invPath),
      api(retPath),
      api('/purchasing/settings'),
    ]);
    setRequests(prRes.data || []);
    setOrders(poRes.data || []);
    setSuppliers(supRes.data || []);
    setProducts(prodRes.data || []);
    setGrns(grnRes.data || []);
    setInvoices(invRes.data || []);
    setReturns(retRes.data || []);
    setPrLevels(settingsRes.data?.levels || []);
  }

  function writeQueryParam(key: string, next: string) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (!next) url.searchParams.delete(key);
    else url.searchParams.set(key, next);
    const qs = url.searchParams.toString();
    window.history.replaceState({}, '', qs ? `${url.pathname}?${qs}` : url.pathname);
  }

  function setInvoiceStatus(next: string) {
    setInvoiceStatusFilter(next);
    writeQueryParam('status', next);
    refresh({ invoiceStatus: next }).catch((err) => setError(err.message));
  }

  function setReturnStatus(next: string) {
    setReturnStatusFilter(next);
    writeQueryParam('return_status', next);
    refresh({ returnStatus: next }).catch((err) => setError(err.message));
  }

  function setPrStatus(next: string) {
    setPrStatusFilter(next);
    writeQueryParam('pr_status', next);
    refresh({ prStatus: next }).catch((err) => setError(err.message));
  }

  function setPoStatus(next: string) {
    setPoStatusFilter(next);
    writeQueryParam('po_status', next);
    refresh({ poStatus: next }).catch((err) => setError(err.message));
  }

  function setGrnStatus(next: string) {
    setGrnStatusFilter(next);
    writeQueryParam('grn_status', next);
    refresh({ grnStatus: next }).catch((err) => setError(err.message));
  }

  // Stage 110 P1 / Stage 114 P1 / Stage 115 P1 — Shell PR/PO/GRN/returns + purchase invoice status leaves honor URL params
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get('status')?.trim() || '';
    const retRaw = params.get('return_status')?.trim() || '';
    const prRaw = params.get('pr_status')?.trim() || '';
    const poRaw = params.get('po_status')?.trim() || '';
    const grnRaw = params.get('grn_status')?.trim() || '';
    const allowed = ['draft', 'unpaid', 'partial', 'overdue', 'paid', 'cancelled', 'outstanding'];
    const retAllowed = ['draft', 'posted'];
    const prAllowed = ['draft', 'pending', 'approved', 'rejected', 'cancelled', 'converted'];
    const poAllowed = ['draft', 'sent', 'partially_received', 'received', 'cancelled', 'open'];
    const grnAllowed = ['draft', 'posted'];
    if (allowed.includes(raw)) setInvoiceStatusFilter(raw);
    if (retAllowed.includes(retRaw)) setReturnStatusFilter(retRaw);
    if (prAllowed.includes(prRaw)) setPrStatusFilter(prRaw);
    if (poAllowed.includes(poRaw)) setPoStatusFilter(poRaw);
    if (grnAllowed.includes(grnRaw)) setGrnStatusFilter(grnRaw);
    refresh({
      invoiceStatus: allowed.includes(raw) ? raw : '',
      returnStatus: retAllowed.includes(retRaw) ? retRaw : '',
      prStatus: prAllowed.includes(prRaw) ? prRaw : '',
      poStatus: poAllowed.includes(poRaw) ? poRaw : '',
      grnStatus: grnAllowed.includes(grnRaw) ? grnRaw : '',
    }).catch((err) => setError(err.message));
  }, []);

  // Stage 106 E1 — honor Shell #purchase-settings
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const hash = (window.location.hash || '').replace(/^#/, '');
    if (!hash) return;
    if (hash === 'purchase-settings' && tab !== 'settings') setTab('settings');
    const t = window.setTimeout(() => {
      const el = document.getElementById(hash);
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 80);
    return () => window.clearTimeout(t);
  }, [tab]);

  useEffect(() => {
    const product = products.find((p) => p.id === productId);
    if (product) setUnitPrice(String(product.cost_price ?? 0));
  }, [productId, products]);

  useEffect(() => {
    if (!selected) {
      setReceiveLines({});
      return;
    }
    const next: typeof receiveLines = {};
    for (const item of selected.items) {
      next[item.id] = {
        accepted: String(item.outstanding_qty ?? 0),
        rejected: '0',
        reason: '',
        batch: '',
        expiry: '',
      };
    }
    setReceiveLines(next);
  }, [selected?.id]);

  useEffect(() => {
    const product = products.find((p) => p.id === manualInvProductId);
    if (product) setManualInvPrice(String(product.cost_price ?? 0));
  }, [manualInvProductId, products]);

  useEffect(() => {
    const grn = grns.find((g) => g.id === grnId);
    if (grn?.items?.length) {
      const next: Record<string, string> = {};
      for (const item of grn.items) {
        next[item.id] = '';
      }
      setReturnLines(next);
    } else {
      setReturnLines({});
    }
  }, [grnId, grns]);

  function resetSupplierForm() {
    setSupplierName('');
    setSupplierCode('');
    setSupplierType('');
    setSupplierCategory('');
    setSupplierEmail('');
    setSupplierPhone('');
    setSupplierAddress('');
    setSupplierNotes('');
    setSupplierTerms('0');
    setSupplierEarlyPayPct('');
    setSupplierEarlyPayDays('');
    setSupplierCredit('0');
  }

  function loadSupplierForm(s: Supplier) {
    setSelectedSupplierId(s.id);
    setSupplierId(s.id);
    setSupplierName(s.name || '');
    setSupplierCode(s.code || '');
    setSupplierType(s.party_type || '');
    setSupplierCategory(s.category || '');
    setSupplierEmail(s.email || '');
    setSupplierPhone(s.phone || '');
    setSupplierAddress(s.address || '');
    setSupplierNotes(s.notes || '');
    setSupplierTerms(String(s.payment_terms_days ?? 0));
    setSupplierEarlyPayPct(
      s.early_pay_discount_pct == null ? '' : String(s.early_pay_discount_pct)
    );
    setSupplierEarlyPayDays(
      s.early_pay_discount_days == null ? '' : String(s.early_pay_discount_days)
    );
    setSupplierCredit(String(s.credit_limit ?? 0));
  }

  function supplierEarlyPayPayload() {
    const pctEmpty = supplierEarlyPayPct.trim() === '';
    const daysEmpty = supplierEarlyPayDays.trim() === '';
    if (pctEmpty && daysEmpty) {
      return { early_pay_discount_pct: null, early_pay_discount_days: null };
    }
    return {
      early_pay_discount_pct: Number(supplierEarlyPayPct) || 0,
      early_pay_discount_days: Number(supplierEarlyPayDays) || 0,
    };
  }

  async function createSupplier() {
    setError('');
    try {
      const r = await api('/suppliers', {
        method: 'POST',
        body: JSON.stringify({
          name: supplierName,
          code: supplierCode || undefined,
          party_type: supplierType || undefined,
          category: supplierCategory || undefined,
          email: supplierEmail || undefined,
          phone: supplierPhone || undefined,
          address: supplierAddress || undefined,
          notes: supplierNotes || undefined,
          payment_terms_days: Number(supplierTerms) || 0,
          ...supplierEarlyPayPayload(),
          credit_limit: Number(supplierCredit) || 0,
        }),
      });
      setSupplierId(r.data.id);
      setSelectedSupplierId(r.data.id);
      resetSupplierForm();
      await refresh();
      const detail = await api(`/suppliers/${r.data.id}`);
      loadSupplierForm(detail.data);
      setMessage('Supplier created');
      setTab('suppliers');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveSupplier() {
    if (!selectedSupplierId) return;
    setError('');
    try {
      const r = await api(`/suppliers/${selectedSupplierId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: supplierName,
          code: supplierCode || null,
          party_type: supplierType || null,
          category: supplierCategory || null,
          email: supplierEmail || null,
          phone: supplierPhone || null,
          address: supplierAddress || null,
          notes: supplierNotes || null,
          payment_terms_days: Number(supplierTerms) || 0,
          ...supplierEarlyPayPayload(),
          credit_limit: Number(supplierCredit) || 0,
        }),
      });
      loadSupplierForm(r.data);
      await refresh();
      setMessage('Supplier updated');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deactivateSupplier(id: string) {
    setError('');
    try {
      await api(`/suppliers/${id}`, { method: 'DELETE' });
      if (selectedSupplierId === id) {
        setSelectedSupplierId('');
        resetSupplierForm();
        setSupplierHistory(null);
      }
      await refresh();
      setMessage('Supplier deactivated');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadHistory(id: string) {
    setError('');
    try {
      const r = await api(`/suppliers/${id}/history`);
      setSupplierHistory(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function addContact() {
    if (!selectedSupplierId || !contactName.trim()) return;
    setError('');
    try {
      await api(`/suppliers/${selectedSupplierId}/contacts`, {
        method: 'POST',
        body: JSON.stringify({
          name: contactName,
          email: contactEmail || undefined,
          phone: contactPhone || undefined,
          is_primary: contactPrimary,
        }),
      });
      setContactName('');
      setContactEmail('');
      setContactPhone('');
      setContactPrimary(false);
      const r = await api(`/suppliers/${selectedSupplierId}`);
      loadSupplierForm(r.data);
      await refresh();
      setMessage('Contact added');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function removeContact(contactId: string) {
    if (!selectedSupplierId) return;
    setError('');
    try {
      await api(`/suppliers/${selectedSupplierId}/contacts/${contactId}`, { method: 'DELETE' });
      const r = await api(`/suppliers/${selectedSupplierId}`);
      loadSupplierForm(r.data);
      await refresh();
      setMessage('Contact removed');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createPr() {
    setError('');
    setMessage('');
    try {
      const r = await api('/purchasing/requests', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: supplierId,
          department: prDepartment || undefined,
          required_date: prRequiredDate ? new Date(prRequiredDate).toISOString() : undefined,
          items: [
            {
              product_id: productId,
              quantity: Number(qty),
              unit_price: Number(unitPrice),
              tax_rate: 0,
            },
          ],
        }),
      });
      setMessage(`Created ${r.data.request_number}`);
      setTab('requests');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function submitPr(id: string) {
    setError('');
    try {
      const r = await api(`/purchasing/requests/${id}/submit`, { method: 'POST' });
      setMessage(`Submitted ${r.data.request_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function approvePr(id: string) {
    setError('');
    try {
      const r = await api(`/purchasing/requests/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      const status = r.data?.status;
      setMessage(
        status === 'approved'
          ? `Approved ${r.data.request_number}`
          : `${r.data.request_number}: level approved; awaiting L${r.data.approval_step}`
      );
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function savePrMatrix() {
    setError('');
    try {
      const r = await api('/purchasing/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          levels: prLevels.map((l) => ({
            min_amount: Number(l.min_amount) || 0.01,
            roles: l.roles,
            label: l.label || undefined,
          })),
        }),
      });
      setPrLevels(r.data?.levels || []);
      setMessage('PR approval matrix saved');
    } catch (err: any) {
      setError(err.message);
    }
  }

  function updatePrLevel(idx: number, patch: Partial<ApprovalLevel>) {
    setPrLevels((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  }

  async function rejectPr(id: string) {
    setError('');
    try {
      const r = await api(`/purchasing/requests/${id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: rejectReason || undefined }),
      });
      setMessage(`Rejected ${r.data.request_number}`);
      setRejectReason('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function convertPr(id: string) {
    setError('');
    try {
      const r = await api(`/purchasing/requests/${id}/convert`, { method: 'POST' });
      setMessage(`Converted to ${r.data.purchase_order.po_number}`);
      setSelected(r.data.purchase_order);
      setTab('orders');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createPo() {
    setError('');
    setMessage('');
    try {
      const r = await api('/purchasing/orders', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: supplierId,
          delivery_address: poDeliveryAddress || null,
          items: [
            {
              product_id: productId,
              quantity: Number(qty),
              unit_price: Number(unitPrice),
              tax_rate: Number(poTaxRate) || 0,
              discount: Number(poDiscount) || 0,
            },
          ],
        }),
      });
      setMessage(`Created ${r.data.po_number}`);
      await refresh();
      setSelected(r.data);
      setTab('orders');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadAmendments(poId: string) {
    try {
      const r = await api(`/purchasing/orders/${poId}/amendments`);
      setAmendments(r.data || []);
    } catch {
      setAmendments([]);
    }
  }

  async function amendSelectedPo() {
    if (!selected) return;
    setError('');
    if (!amendReason.trim()) {
      setError('Amendment reason is required');
      return;
    }
    try {
      const line = selected.items[0];
      const items = line
        ? [
            {
              id: line.id,
              product_id: line.product_id,
              quantity: Number(amendQty || line.quantity),
              unit_price: Number(amendPrice || line.unit_price),
              tax_rate: Number(amendTaxRate || line.tax_rate || 0),
              discount: Number(amendDiscount || line.discount || 0),
            },
          ]
        : undefined;
      const r = await api(`/purchasing/orders/${selected.id}/amend`, {
        method: 'POST',
        body: JSON.stringify({
          reason: amendReason,
          delivery_address: amendDeliveryAddress,
          items,
        }),
      });
      setMessage(`Amended ${r.data.po_number} to revision ${r.data.revision}`);
      setAmendReason('');
      setSelected(r.data);
      setAmendDeliveryAddress(r.data.delivery_address || '');
      await loadAmendments(r.data.id);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function sendPo(poId: string) {
    setError('');
    try {
      const qs = emailOnSend ? '' : '?email=false';
      const r = await api(`/purchasing/orders/${poId}/send${qs}`, { method: 'POST' });
      const delivery = r.data?.delivery;
      setMessage(
        delivery?.sent
          ? `Sent ${r.data.po_number} and emailed ${delivery.to}`
          : `Sent ${r.data.po_number}`
      );
      await refresh();
      setSelected(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function printPo(poId: string) {
    setError('');
    try {
      const r = await api(`/purchasing/orders/${poId}/print`);
      const text = r.data?.text || '';
      const win = window.open('', '_blank', 'noopener,noreferrer,width=720,height=800');
      if (win) {
        win.document.write(`<pre style="font:14px/1.4 monospace;padding:16px">${text.replace(/</g, '&lt;')}</pre>`);
        win.document.close();
        win.focus();
      }
      setMessage(`Print view ready for ${r.data?.po?.po_number || 'PO'}`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function printDebitNote(returnId: string) {
    setError('');
    try {
      const r = await api(`/purchasing/returns/${returnId}/print`);
      const text = r.data?.text || '';
      const win = window.open('', '_blank', 'noopener,noreferrer,width=720,height=800');
      if (win) {
        win.document.write(`<pre style="font:14px/1.4 monospace;padding:16px">${text.replace(/</g, '&lt;')}</pre>`);
        win.document.close();
        win.focus();
      }
      setMessage(
        `Debit note print ready for ${r.data?.return?.debit_note_number || r.data?.return?.return_number || 'return'}`
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function receiveSelectedPo() {
    if (!selected) return;
    setError('');
    try {
      const items = selected.items
        .filter((i) => i.outstanding_qty > 0)
        .map((i) => {
          const line = receiveLines[i.id] || {
            accepted: '0',
            rejected: '0',
            reason: '',
            batch: '',
            expiry: '',
          };
          const accepted = Number(line.accepted) || 0;
          const rejected = Number(line.rejected) || 0;
          return {
            po_item_id: i.id,
            received_qty: accepted + rejected,
            accepted_qty: accepted,
            rejected_qty: rejected,
            rejection_reason: rejected > 0 ? line.reason || undefined : undefined,
            batch_number: line.batch || undefined,
            expiry_date: line.expiry ? new Date(line.expiry).toISOString() : undefined,
          };
        })
        .filter((i) => i.received_qty > 0);
      if (!items.length) {
        setError('Enter accepted and/or rejected quantities to receive');
        return;
      }
      const r = await api('/purchasing/grn', {
        method: 'POST',
        body: JSON.stringify({ purchase_order_id: selected.id, items }),
      });
      setMessage(`Posted ${r.data.grn_number}`);
      await refresh();
      const updated = await api(`/purchasing/orders/${selected.id}`);
      setSelected(updated.data);
      setTab('grn');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function cancelPo(poId: string) {
    setError('');
    try {
      const r = await api(`/purchasing/orders/${poId}/cancel`, { method: 'POST' });
      setMessage(`Cancelled ${r.data.po_number}`);
      await refresh();
      setSelected(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createReturn() {
    setError('');
    const items = Object.entries(returnLines)
      .map(([goods_receipt_item_id, qty]) => ({
        goods_receipt_item_id,
        quantity: Number(qty),
      }))
      .filter((row) => Number.isFinite(row.quantity) && row.quantity > 0);
    if (!grnId) {
      setError('Select a GRN');
      return;
    }
    if (!items.length) {
      setError('Enter a return quantity on at least one GRN line');
      return;
    }
    try {
      const r = await api('/purchasing/returns', {
        method: 'POST',
        body: JSON.stringify({
          goods_receipt_id: grnId,
          reason: returnReason,
          items,
        }),
      });
      setMessage(
        `Return ${r.data.return_number} drafted (${r.data.items?.length || items.length} line${
          (r.data.items?.length || items.length) === 1 ? '' : 's'
        })`
      );
      setTab('returns');
      setGrnId('');
      setReturnLines({});
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createInvoiceFromGrn() {
    setError('');
    try {
      const r = await api('/purchasing/invoices', {
        method: 'POST',
        body: JSON.stringify({
          goods_receipt_id: invoiceGrnId,
          supplier_invoice_number: supplierInvoiceNo || undefined,
        }),
      });
      setMessage(`Invoice ${r.data.invoice_number} drafted`);
      setTab('invoices');
      setSupplierInvoiceNo('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createManualInvoice() {
    setError('');
    try {
      const r = await api('/purchasing/invoices', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: manualInvSupplierId,
          supplier_invoice_number: supplierInvoiceNo || undefined,
          is_reverse_charge: manualInvRc,
          items: [
            {
              product_id: manualInvProductId,
              quantity: Number(manualInvQty),
              unit_price: Number(manualInvPrice),
              tax_rate: Number(manualInvTaxRate),
            },
          ],
        }),
      });
      setMessage(
        `Invoice ${r.data.invoice_number} drafted` +
          (r.data.is_reverse_charge ? ` (RC tax ${r.data.reverse_charge_tax})` : '')
      );
      setTab('invoices');
      setSupplierInvoiceNo('');
      setManualInvRc(false);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function approveInvoice(id: string) {
    setError('');
    try {
      const r = await api(`/purchasing/invoices/${id}/approve`, { method: 'POST', body: '{}' });
      setMessage(`Approved ${r.data.invoice_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

  async function uploadInvoiceAttachment(id: string, file: File) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${apiBase}/purchasing/invoices/${id}/attachment`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail?.message || body.detail || body.message || 'Upload failed');
      setMessage(`Attachment uploaded for ${body.data?.invoice_number || id}`);
      await refresh();
    } catch (err: any) {
      setError(typeof err.message === 'string' ? err.message : 'Upload failed');
    }
  }

  async function downloadInvoiceAttachment(id: string) {
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}/purchasing/invoices/${id}/attachment`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Download failed');
      }
      const blob = await res.blob();
      const cd = res.headers.get('Content-Disposition') || '';
      const match = cd.match(/filename="?([^"]+)"?/);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = match?.[1] || `invoice-${id.slice(0, 8)}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message);
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
      setError(err.message);
    }
  }

  async function applyInvoiceOcr() {
    if (!ocrFor || !ocrDraft) return;
    setError('');
    setMessage('');
    try {
      const body: Record<string, unknown> = { confirm: true };
      if (ocrDraft.supplier_invoice_number !== '') {
        body.supplier_invoice_number = ocrDraft.supplier_invoice_number;
      }
      if (ocrDraft.notes !== '') body.notes = ocrDraft.notes;
      if (ocrDraft.invoice_date !== '') body.invoice_date = ocrDraft.invoice_date;
      await api(`/purchasing/invoices/${ocrFor}/ocr-apply`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      setMessage('OCR suggestions applied to draft invoice');
      setOcrFor(null);
      setOcrDraft(null);
      setOcrMeta(null);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function postReturn(id: string) {
    setError('');
    try {
      const r = await api(`/purchasing/returns/${id}/post`, { method: 'POST', body: '{}' });
      setMessage(`Posted ${r.data.return_number} / ${r.data.debit_note_number}`);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  const selectedGrn = grns.find((g) => g.id === grnId);

  return (
    <Shell>
      <h1>Purchasing</h1>
      <p className="muted">Requests → purchase orders → GRN → invoices → returns</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(
          [
            ['suppliers', 'Suppliers'],
            ['requests', 'Requests'],
            ['orders', 'Orders'],
            ['grn', 'GRNs'],
            ['invoices', 'Invoices'],
            ['returns', 'Returns'],
            ['settings', 'Settings'],
          ] as const
        ).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} disabled={tab === id}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'suppliers' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>{selectedSupplierId ? 'Edit supplier' : 'New supplier'}</h3>
          <div style={{ display: 'grid', gap: 8, maxWidth: 560 }}>
            <input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="Name *" />
            <input value={supplierCode} onChange={(e) => setSupplierCode(e.target.value)} placeholder="Code" />
            <select value={supplierType} onChange={(e) => setSupplierType(e.target.value)}>
              <option value="">Type</option>
              <option value="manufacturer">Manufacturer</option>
              <option value="distributor">Distributor</option>
              <option value="wholesaler">Wholesaler</option>
              <option value="other">Other</option>
            </select>
            <input value={supplierCategory} onChange={(e) => setSupplierCategory(e.target.value)} placeholder="Category" />
            <input value={supplierEmail} onChange={(e) => setSupplierEmail(e.target.value)} placeholder="Email" />
            <input value={supplierPhone} onChange={(e) => setSupplierPhone(e.target.value)} placeholder="Phone" />
            <textarea value={supplierAddress} onChange={(e) => setSupplierAddress(e.target.value)} placeholder="Address" rows={2} />
            <textarea value={supplierNotes} onChange={(e) => setSupplierNotes(e.target.value)} placeholder="Notes" rows={2} />
            <input value={supplierTerms} onChange={(e) => setSupplierTerms(e.target.value)} placeholder="Payment terms (days)" />
            <input
              value={supplierEarlyPayPct}
              onChange={(e) => setSupplierEarlyPayPct(e.target.value)}
              placeholder="Early pay discount % (blank = tenant default)"
            />
            <input
              value={supplierEarlyPayDays}
              onChange={(e) => setSupplierEarlyPayDays(e.target.value)}
              placeholder="Early pay window days (blank = tenant default)"
            />
            <input value={supplierCredit} onChange={(e) => setSupplierCredit(e.target.value)} placeholder="Credit limit" />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {!selectedSupplierId ? (
                <button onClick={createSupplier} disabled={!supplierName.trim()}>
                  Create supplier
                </button>
              ) : (
                <>
                  <button onClick={saveSupplier} disabled={!supplierName.trim()}>
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setSelectedSupplierId('');
                      resetSupplierForm();
                      setSupplierHistory(null);
                    }}
                  >
                    New
                  </button>
                  <button onClick={() => loadHistory(selectedSupplierId)}>History</button>
                  <button onClick={() => deactivateSupplier(selectedSupplierId)}>Deactivate</button>
                </>
              )}
            </div>
          </div>
          {selectedSupplierId && (
            <div style={{ marginTop: 16, maxWidth: 560 }}>
              <h4>Contacts</h4>
              <ul>
                {(suppliers.find((s) => s.id === selectedSupplierId)?.contacts || []).map((c) => (
                  <li key={c.id} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                    <span>
                      {c.name}
                      {c.is_primary ? ' (primary)' : ''}
                      {c.email ? ` — ${c.email}` : ''}
                      {c.phone ? ` — ${c.phone}` : ''}
                    </span>
                    <button onClick={() => removeContact(c.id)}>Remove</button>
                  </li>
                ))}
              </ul>
              <div style={{ display: 'grid', gap: 8 }}>
                <input value={contactName} onChange={(e) => setContactName(e.target.value)} placeholder="Contact name" />
                <input value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} placeholder="Contact email" />
                <input value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} placeholder="Contact phone" />
                <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <input type="checkbox" checked={contactPrimary} onChange={(e) => setContactPrimary(e.target.checked)} />
                  Primary contact
                </label>
                <button onClick={addContact} disabled={!contactName.trim()}>
                  Add contact
                </button>
              </div>
            </div>
          )}
          {supplierHistory && (
            <div style={{ marginTop: 16 }}>
              <h4>Purchase history</h4>
              <p className="muted">
                {supplierHistory.orders.length} POs · {supplierHistory.invoices.length} invoices ·{' '}
                {supplierHistory.returns.length} returns · {supplierHistory.payments.length} payments
              </p>
              <ul>
                {supplierHistory.orders.slice(0, 8).map((o) => (
                  <li key={o.id}>
                    {o.po_number} — {o.status} — {o.total_amount}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Code</th>
                <th>Status</th>
                <th>Terms</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {suppliers.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td>{s.code || '—'}</td>
                  <td>{s.status || 'active'}</td>
                  <td>{s.payment_terms_days ?? 0}d</td>
                  <td>
                    <button
                      onClick={() => {
                        loadSupplierForm(s);
                        loadHistory(s.id);
                      }}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'settings' && (
        <div className="card" style={{ marginBottom: 16 }} id="purchase-settings">
          <h3>Purchase settings</h3>
          <p className="muted" style={{ marginBottom: 8 }}>
            PR approval matrix — estimated total must exceed a level&apos;s min to require that step (Store
            Manager → Company Admin by default). Company admins can save changes.
          </p>
          {prLevels.length === 0 ? (
            <p className="muted">No approval levels loaded.</p>
          ) : (
            prLevels.map((lvl, idx) => (
              <div
                key={idx}
                style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}
              >
                <span className="muted">L{idx + 1}</span>
                <input
                  value={lvl.min_amount}
                  onChange={(e) => updatePrLevel(idx, { min_amount: Number(e.target.value) || 0 })}
                  placeholder="Min amount"
                  style={{ width: 100 }}
                />
                <input
                  value={lvl.label || ''}
                  onChange={(e) => updatePrLevel(idx, { label: e.target.value })}
                  placeholder="Label"
                  style={{ width: 140 }}
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
                  placeholder="roles"
                  style={{ minWidth: 220, flex: 1 }}
                />
              </div>
            ))
          )}
          <button type="button" onClick={savePrMatrix} disabled={prLevels.length === 0}>
            Save matrix
          </button>
        </div>
      )}

      {tab === 'requests' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>Create purchase request</h3>
          <div style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
            <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
              <option value="">Preferred supplier</option>
              {suppliers
                .filter((s) => (s.status || 'active') === 'active')
                .map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.code ? ` (${s.code})` : ''}
                </option>
              ))}
            </select>
            <select value={productId} onChange={(e) => setProductId(e.target.value)}>
              <option value="">Product</option>
              {products.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.sku})
                </option>
              ))}
            </select>
            <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Quantity" />
            <input value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} placeholder="Est. unit price" />
            <input value={prDepartment} onChange={(e) => setPrDepartment(e.target.value)} placeholder="Department (optional)" />
            <input type="date" value={prRequiredDate} onChange={(e) => setPrRequiredDate(e.target.value)} />
            <button onClick={createPr} disabled={!supplierId || !productId}>
              Create request
            </button>
          </div>
        </div>
      )}

      {tab === 'orders' && (
      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Create purchase order</h3>
        <div style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
          <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">Select supplier</option>
            {suppliers
              .filter((s) => (s.status || 'active') === 'active')
              .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
                {s.code ? ` (${s.code})` : ''}
              </option>
            ))}
          </select>
          <select value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">Select product</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>
          <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Quantity" />
          <input value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} placeholder="Unit price" />
          <input value={poTaxRate} onChange={(e) => setPoTaxRate(e.target.value)} placeholder="Tax rate %" />
          <input value={poDiscount} onChange={(e) => setPoDiscount(e.target.value)} placeholder="Line discount" />
          <textarea
            value={poDeliveryAddress}
            onChange={(e) => setPoDeliveryAddress(e.target.value)}
            placeholder="Delivery address"
            rows={2}
          />
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={emailOnSend} onChange={(e) => setEmailOnSend(e.target.checked)} />
            Email supplier when sending PO
          </label>
          <button onClick={createPo} disabled={!supplierId || !productId}>
            Create draft PO
          </button>
        </div>
      </div>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Create purchase invoice from GRN</h3>
        <div style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
          <select value={invoiceGrnId} onChange={(e) => setInvoiceGrnId(e.target.value)}>
            <option value="">Select GRN</option>
            {grns.map((g) => (
              <option key={g.id} value={g.id}>
                {g.grn_number}
              </option>
            ))}
          </select>
          <input
            value={supplierInvoiceNo}
            onChange={(e) => setSupplierInvoiceNo(e.target.value)}
            placeholder="Supplier invoice #"
          />
          <button onClick={createInvoiceFromGrn} disabled={!invoiceGrnId}>
            Draft invoice from GRN
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Create manual purchase invoice</h3>
        <div style={{ display: 'grid', gap: 8, maxWidth: 480 }}>
          <select value={manualInvSupplierId} onChange={(e) => setManualInvSupplierId(e.target.value)}>
            <option value="">Select supplier</option>
            {suppliers
              .filter((s) => (s.status || 'active') === 'active')
              .map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select value={manualInvProductId} onChange={(e) => setManualInvProductId(e.target.value)}>
            <option value="">Select product</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.sku})
              </option>
            ))}
          </select>
          <input value={manualInvQty} onChange={(e) => setManualInvQty(e.target.value)} placeholder="Quantity" />
          <input value={manualInvPrice} onChange={(e) => setManualInvPrice(e.target.value)} placeholder="Unit price" />
          <input
            value={manualInvTaxRate}
            onChange={(e) => setManualInvTaxRate(e.target.value)}
            placeholder="Tax rate %"
          />
          <input
            value={supplierInvoiceNo}
            onChange={(e) => setSupplierInvoiceNo(e.target.value)}
            placeholder="Supplier invoice #"
          />
          <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="checkbox" checked={manualInvRc} onChange={(e) => setManualInvRc(e.target.checked)} />
            Reverse charge (self-assess VAT; AP = net)
          </label>
          <button onClick={createManualInvoice} disabled={!manualInvSupplierId || !manualInvProductId}>
            Draft manual invoice
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Create purchase return</h3>
        <p className="muted" style={{ marginBottom: 8 }}>
          Select a posted GRN and enter quantities on one or more lines (Stage 8 P1).
        </p>
        <div style={{ display: 'grid', gap: 8, maxWidth: 720 }}>
          <select value={grnId} onChange={(e) => setGrnId(e.target.value)}>
            <option value="">Select GRN</option>
            {grns.map((g) => (
              <option key={g.id} value={g.id}>
                {g.grn_number} ({g.status})
              </option>
            ))}
          </select>
          <select value={returnReason} onChange={(e) => setReturnReason(e.target.value)}>
            <option value="damaged">Damaged</option>
            <option value="wrong_item">Wrong item</option>
            <option value="expiry">Expiry</option>
            <option value="quality">Quality</option>
            <option value="other">Other</option>
          </select>
          {selectedGrn ? (
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Accepted</th>
                  <th>Return qty</th>
                </tr>
              </thead>
              <tbody>
                {(selectedGrn.items || []).map((i) => {
                  const product = products.find((p) => p.id === i.product_id);
                  return (
                    <tr key={i.id}>
                      <td>{product?.name || i.product_id}</td>
                      <td>{i.accepted_qty}</td>
                      <td>
                        <input
                          value={returnLines[i.id] ?? ''}
                          onChange={(e) =>
                            setReturnLines((prev) => ({ ...prev, [i.id]: e.target.value }))
                          }
                          placeholder="0"
                          style={{ width: 100 }}
                          inputMode="decimal"
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="muted">Choose a GRN to edit return lines</p>
          )}
          <button
            onClick={createReturn}
            disabled={
              !grnId ||
              !Object.values(returnLines).some((q) => Number(q) > 0)
            }
          >
            Draft return
          </button>
        </div>
      </div>

      {tab === 'requests' && (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
            <strong>PR status</strong>
            <select
              value={prStatusFilter}
              onChange={(e) => setPrStatus(e.target.value)}
              aria-label="Filter purchase requests by status"
            >
              <option value="">All statuses</option>
              {['draft', 'pending', 'approved', 'rejected', 'cancelled', 'converted'].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="card" style={{ marginBottom: 16, maxWidth: 480 }}>
            <label className="muted">Rejection reason (optional)</label>
            <input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} placeholder="Reason" />
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Approval</th>
                <th>Est. total</th>
                <th>Department</th>
                <th>PO</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((r) => (
                <tr key={r.id}>
                  <td>{r.request_number}</td>
                  <td>{r.status}</td>
                  <td>
                    {r.status === 'pending'
                      ? `L${r.awaiting_level || r.approval_step || 1}/${r.approval_steps_required || 1}`
                      : r.approval_steps_required
                        ? `${r.approval_steps_required} level(s)`
                        : '—'}
                    {r.status === 'pending' && r.awaiting_roles?.length ? (
                      <div className="muted">{r.awaiting_roles.join(', ')}</div>
                    ) : null}
                  </td>
                  <td>{r.estimated_total ?? '—'}</td>
                  <td>{r.department || '—'}</td>
                  <td>{r.purchase_order_id ? r.purchase_order_id.slice(0, 8) : '—'}</td>
                  <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {r.status === 'draft' && <button onClick={() => submitPr(r.id)}>Submit</button>}
                    {r.status === 'pending' && (
                      <>
                        <button onClick={() => approvePr(r.id)}>Approve</button>
                        <button onClick={() => rejectPr(r.id)}>Reject</button>
                      </>
                    )}
                    {r.status === 'approved' && <button onClick={() => convertPr(r.id)}>Convert to PO</button>}
                    {r.rejection_reason && <span className="muted">{r.rejection_reason}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'orders' && (
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
            <strong>PO status</strong>
            <select
              value={poStatusFilter}
              onChange={(e) => setPoStatus(e.target.value)}
              aria-label="Filter purchase orders by status"
            >
              <option value="">All statuses</option>
              {['draft', 'open', 'sent', 'partially_received', 'received', 'cancelled'].map((s) => (
                <option key={s} value={s}>
                  {s === 'open' ? 'open (sent/partially_received)' : s}
                </option>
              ))}
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>PO</th>
                <th>Rev</th>
                <th>Status</th>
                <th>Total</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>
                    <button
                      onClick={() => {
                        setSelected(o);
                        setAmendQty(String(o.items[0]?.quantity ?? ''));
                        setAmendPrice(String(o.items[0]?.unit_price ?? ''));
                        setAmendTaxRate(String(o.items[0]?.tax_rate ?? 0));
                        setAmendDiscount(String(o.items[0]?.discount ?? 0));
                        setAmendDeliveryAddress(o.delivery_address || '');
                        loadAmendments(o.id);
                      }}
                      style={{ background: 'none', border: 0, color: '#1d4ed8', cursor: 'pointer' }}
                    >
                      {o.po_number}
                    </button>
                  </td>
                  <td>{o.revision ?? 1}</td>
                  <td>{o.status}</td>
                  <td>{o.total_amount}</td>
                  <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {o.status === 'draft' && <button onClick={() => sendPo(o.id)}>Send</button>}
                    <button onClick={() => printPo(o.id)}>Print</button>
                    {(o.status === 'draft' || o.status === 'sent') && (
                      <button onClick={() => cancelPo(o.id)}>Cancel</button>
                    )}
                    {(o.status === 'sent' || o.status === 'partially_received') && (
                      <button
                        onClick={() => {
                          setSelected(o);
                          setAmendQty(String(o.items[0]?.quantity ?? ''));
                          setAmendPrice(String(o.items[0]?.unit_price ?? ''));
                          setAmendTaxRate(String(o.items[0]?.tax_rate ?? 0));
                          setAmendDiscount(String(o.items[0]?.discount ?? 0));
                          setAmendDeliveryAddress(o.delivery_address || '');
                          loadAmendments(o.id);
                        }}
                      >
                        Amend / Receive…
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {selected && (
            <div className="card" style={{ marginTop: 16 }}>
              <h3>
                {selected.po_number} — {selected.status} (rev {selected.revision ?? 1})
              </h3>
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Ordered</th>
                    <th>Received</th>
                    <th>Outstanding</th>
                    <th>Accept</th>
                    <th>Reject</th>
                    <th>Reject reason</th>
                    <th>Batch</th>
                    <th>Expiry</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.items.map((i) => {
                    const line = receiveLines[i.id] || {
                      accepted: '0',
                      rejected: '0',
                      reason: '',
                      batch: '',
                      expiry: '',
                    };
                    const editable = i.outstanding_qty > 0 && (selected.status === 'sent' || selected.status === 'partially_received');
                    return (
                      <tr key={i.id}>
                        <td>{products.find((p) => p.id === i.product_id)?.name || i.product_id}</td>
                        <td>{i.quantity}</td>
                        <td>{i.received_qty}</td>
                        <td>{i.outstanding_qty}</td>
                        <td>
                          <input
                            style={{ width: 72 }}
                            disabled={!editable}
                            value={line.accepted}
                            onChange={(e) =>
                              setReceiveLines((prev) => ({
                                ...prev,
                                [i.id]: { ...line, accepted: e.target.value },
                              }))
                            }
                          />
                        </td>
                        <td>
                          <input
                            style={{ width: 72 }}
                            disabled={!editable}
                            value={line.rejected}
                            onChange={(e) =>
                              setReceiveLines((prev) => ({
                                ...prev,
                                [i.id]: { ...line, rejected: e.target.value },
                              }))
                            }
                          />
                        </td>
                        <td>
                          <input
                            style={{ width: 120 }}
                            disabled={!editable}
                            value={line.reason}
                            onChange={(e) =>
                              setReceiveLines((prev) => ({
                                ...prev,
                                [i.id]: { ...line, reason: e.target.value },
                              }))
                            }
                          />
                        </td>
                        <td>
                          <input
                            style={{ width: 100 }}
                            disabled={!editable}
                            value={line.batch}
                            placeholder="Batch #"
                            onChange={(e) =>
                              setReceiveLines((prev) => ({
                                ...prev,
                                [i.id]: { ...line, batch: e.target.value },
                              }))
                            }
                          />
                        </td>
                        <td>
                          <input
                            type="date"
                            disabled={!editable}
                            value={line.expiry}
                            onChange={(e) =>
                              setReceiveLines((prev) => ({
                                ...prev,
                                [i.id]: { ...line, expiry: e.target.value },
                              }))
                            }
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {(selected.status === 'sent' || selected.status === 'partially_received' || selected.status === 'draft') && (
                <div style={{ marginTop: 16, display: 'grid', gap: 8, maxWidth: 480 }}>
                  <h4>Amend PO</h4>
                  <input
                    value={amendReason}
                    onChange={(e) => setAmendReason(e.target.value)}
                    placeholder="Amendment reason (required for sent POs)"
                  />
                  <input
                    value={amendQty}
                    onChange={(e) => setAmendQty(e.target.value)}
                    placeholder="Line qty (first line)"
                  />
                  <input
                    value={amendPrice}
                    onChange={(e) => setAmendPrice(e.target.value)}
                    placeholder="Unit price (first line)"
                  />
                  <input
                    value={amendTaxRate}
                    onChange={(e) => setAmendTaxRate(e.target.value)}
                    placeholder="Tax rate % (first line)"
                  />
                  <input
                    value={amendDiscount}
                    onChange={(e) => setAmendDiscount(e.target.value)}
                    placeholder="Line discount (first line)"
                  />
                  <textarea
                    value={amendDeliveryAddress}
                    onChange={(e) => setAmendDeliveryAddress(e.target.value)}
                    placeholder="Delivery address"
                    rows={2}
                  />
                  <button type="button" onClick={amendSelectedPo} disabled={!amendReason.trim()}>
                    Save amendment
                  </button>
                </div>
              )}
              {(selected.status === 'sent' || selected.status === 'partially_received') && (
                <button type="button" style={{ marginTop: 12 }} onClick={receiveSelectedPo}>
                  Post GRN
                </button>
              )}
              {amendments.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4>Amendment history</h4>
                  <ul>
                    {amendments.map((a) => (
                      <li key={a.id}>
                        Rev {a.revision}: {a.reason}
                        {a.changes?.before?.header?.total_amount != null &&
                        a.changes?.after?.header?.total_amount != null
                          ? ` (${a.changes.before.header.total_amount} → ${a.changes.after.header.total_amount})`
                          : ''}
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
        <>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
            <strong>GRN status</strong>
            <select
              value={grnStatusFilter}
              onChange={(e) => setGrnStatus(e.target.value)}
              aria-label="Filter GRNs by status"
            >
              <option value="">All statuses</option>
              <option value="draft">draft</option>
              <option value="posted">posted</option>
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>GRN</th>
                <th>PO</th>
                <th>Status</th>
                <th>Lines</th>
              </tr>
            </thead>
            <tbody>
              {grns.map((g) => (
                <tr key={g.id}>
                  <td>{g.grn_number}</td>
                  <td>{g.purchase_order_id}</td>
                  <td>{g.status}</td>
                  <td>{g.items?.length || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {tab === 'invoices' && (
        <>
          <div
            style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}
          >
            <strong>Outstanding / status</strong>
            <select
              value={invoiceStatusFilter}
              onChange={(e) => setInvoiceStatus(e.target.value)}
              aria-label="Filter purchase invoices by status"
            >
              <option value="">All statuses</option>
              {['draft', 'outstanding', 'unpaid', 'partial', 'overdue', 'paid', 'cancelled'].map((s) => (
                <option key={s} value={s}>
                  {s === 'outstanding' ? 'outstanding (unpaid/partial/overdue)' : s}
                </option>
              ))}
            </select>
            <span className="muted">Deep-link: ?tab=invoices&amp;status=outstanding</span>
          </div>
          {ocrDraft && ocrFor && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3>Supplier invoice OCR</h3>
              <p className="muted">
                Engine: {ocrMeta?.engine || '—'} · Confidence: {ocrMeta?.confidence ?? '—'}
                {ocrMeta?.suggestions?.ocr_amount != null
                  ? ` · OCR amount ${ocrMeta.suggestions.ocr_amount}`
                  : ''}
              </p>
              <div style={{ display: 'grid', gap: 8, maxWidth: 520 }}>
                <input
                  value={ocrDraft.supplier_invoice_number}
                  onChange={(e) =>
                    setOcrDraft({ ...ocrDraft, supplier_invoice_number: e.target.value })
                  }
                  placeholder="Supplier invoice #"
                />
                <input
                  value={ocrDraft.invoice_date}
                  onChange={(e) => setOcrDraft({ ...ocrDraft, invoice_date: e.target.value })}
                  placeholder="Invoice date YYYY-MM-DD"
                />
                <input
                  value={ocrDraft.notes}
                  onChange={(e) => setOcrDraft({ ...ocrDraft, notes: e.target.value })}
                  placeholder="Notes"
                />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" onClick={applyInvoiceOcr}>
                    Apply to draft
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setOcrFor(null);
                      setOcrDraft(null);
                      setOcrMeta(null);
                    }}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          )}
        <table className="table">
          <thead>
            <tr>
              <th>Invoice</th>
              <th>Supplier #</th>
              <th>Status</th>
              <th>Total</th>
              <th>RC</th>
              <th>Due</th>
              <th>AP posted</th>
              <th>File</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.invoice_number}</td>
                <td>{inv.supplier_invoice_number || '—'}</td>
                <td>{inv.status}</td>
                <td>{inv.total_amount}</td>
                <td>
                  {inv.is_reverse_charge
                    ? `${inv.reverse_charge_tax ?? 0}`
                    : '—'}
                </td>
                <td>{inv.balance_due}</td>
                <td>{inv.ap_posted ? 'yes' : 'no (via GRN)'}</td>
                <td>{inv.has_attachment ? 'yes' : '—'}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                  {inv.status === 'draft' && (
                    <button onClick={() => approveInvoice(inv.id)}>Approve</button>
                  )}
                  <label style={{ cursor: 'pointer' }}>
                    <span className="muted" style={{ textDecoration: 'underline' }}>
                      Upload
                    </span>
                    <input
                      type="file"
                      accept="application/pdf,image/png,image/jpeg,image/webp,image/gif"
                      style={{ display: 'none' }}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) uploadInvoiceAttachment(inv.id, file);
                        e.target.value = '';
                      }}
                    />
                  </label>
                  {inv.has_attachment && (
                    <>
                      <button onClick={() => downloadInvoiceAttachment(inv.id)}>Download</button>
                      {inv.status === 'draft' && (
                        <button onClick={() => suggestInvoiceOcr(inv.id)}>OCR</button>
                      )}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </>
      )}

      {tab === 'returns' && (
        <>
          <p className="muted" style={{ marginBottom: 12 }}>
            Purchase returns start as draft; Post is required before the debit note is recognized.
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
            <strong>Return status</strong>
            <select
              value={returnStatusFilter}
              onChange={(e) => setReturnStatus(e.target.value)}
              aria-label="Filter purchase returns by status"
            >
              <option value="">All statuses</option>
              <option value="draft">draft</option>
              <option value="posted">posted</option>
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Return</th>
                <th>Debit note</th>
                <th>Lines</th>
                <th>Reason</th>
                <th>Status</th>
                <th>Total</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {returns.map((r) => (
                <tr key={r.id}>
                  <td>{r.return_number}</td>
                  <td>{r.debit_note_number || '—'}</td>
                  <td>{r.items?.length ?? '—'}</td>
                  <td>{r.reason}</td>
                  <td>{r.status}</td>
                  <td>{r.total_amount}</td>
                  <td>
                    {r.status === 'draft' && (
                      <button
                        title="Post required before debit note recognition"
                        onClick={() => postReturn(r.id)}
                      >
                        Post
                      </button>
                    )}
                    {r.status === 'posted' && (
                      <button onClick={() => printDebitNote(r.id)}>Print debit note</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Shell>
  );
}
