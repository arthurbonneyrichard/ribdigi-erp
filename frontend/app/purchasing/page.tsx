'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import PartyContactsPanel from '../../components/PartyContactsPanel';
import { api } from '../../lib/api';

type Tab = 'requests' | 'orders' | 'grn' | 'invoices' | 'returns';
type Supplier = {
  id: string;
  name: string;
  code?: string | null;
  profile_type?: string | null;
  category?: string | null;
  status?: string | null;
};
type Product = { id: string; name: string; sku: string; cost_price: number };
type PurchaseRequest = {
  id: string;
  request_number: string;
  status: string;
  preferred_supplier_id?: string | null;
  department?: string | null;
  notes?: string | null;
  converted_po_id?: string | null;
  approval_step?: number;
  approval_steps_required?: number;
  awaiting_level?: number | null;
  awaiting_roles?: string[];
  items: { id: string; product_id: string; quantity: number }[];
  purchase_order?: { id: string; po_number: string };
};
type PoItem = {
  id: string;
  product_id: string;
  quantity: number;
  received_qty: number;
  unit_id?: string | null;
  unit_price: number;
  tax_rate?: number;
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
  notes?: string | null;
  delivery_address?: string | null;
  revision_no?: number;
  can_amend?: boolean;
  amendments?: PoAmendment[];
  emailed_at?: string | null;
  emailed_to?: string | null;
  delivery?: { to?: string; mode?: string };
  items: PoItem[];
};
type GrnItem = {
  id: string;
  product_id: string;
  accepted_qty: number;
  received_qty: number;
  rejected_qty?: number;
  rejection_reason?: string | null;
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
  subtotal?: number;
  items?: {
    id: string;
    product_id: string;
    quantity: number;
    unit_price: number;
    tax_rate: number;
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
  const [tab, setTab] = useState<Tab>('requests');
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [grns, setGrns] = useState<Grn[]>([]);
  const [invoices, setInvoices] = useState<PurchaseInvoice[]>([]);
  const [selectedInvoice, setSelectedInvoice] = useState<PurchaseInvoice | null>(null);
  const [returns, setReturns] = useState<PurchaseReturn[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [units, setUnits] = useState<Unit[]>([]);
  const [selected, setSelected] = useState<PurchaseOrder | null>(null);
  const [receiveDrafts, setReceiveDrafts] = useState<
    Record<string, { received: string; accepted: string; rejected: string; reason: string }>
  >({});
  const [supplierId, setSupplierId] = useState('');
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
  const [productId, setProductId] = useState('');
  const [unitId, setUnitId] = useState('');
  const [qty, setQty] = useState('10');
  const [unitPrice, setUnitPrice] = useState('0');
  const [poDeliveryAddress, setPoDeliveryAddress] = useState('');
  const [amendQty, setAmendQty] = useState('');
  const [amendPrice, setAmendPrice] = useState('');
  const [amendUnitId, setAmendUnitId] = useState('');
  const [amendNotes, setAmendNotes] = useState('');
  const [amendDeliveryAddress, setAmendDeliveryAddress] = useState('');
  const [amendReason, setAmendReason] = useState('');
  const [amendNotify, setAmendNotify] = useState(false);
  const [prSupplierId, setPrSupplierId] = useState('');
  const [prProductId, setPrProductId] = useState('');
  const [prQty, setPrQty] = useState('10');
  const [prDepartment, setPrDepartment] = useState('');
  const [prNotes, setPrNotes] = useState('');
  const [prBusy, setPrBusy] = useState('');
  const [prLevels, setPrLevels] = useState<{ roles: string[]; label?: string }[]>([
    { roles: ['store_manager'], label: 'Store Manager' },
    { roles: ['company_admin', 'super_admin'], label: 'Company Admin' },
  ]);
  const [grnId, setGrnId] = useState('');
  const [grnItemId, setGrnItemId] = useState('');
  const [returnQty, setReturnQty] = useState('1');
  const [returnReason, setReturnReason] = useState('other');
  const [invoiceGrnId, setInvoiceGrnId] = useState('');
  const [supplierInvoiceNo, setSupplierInvoiceNo] = useState('');
  const [manualInvSupplierId, setManualInvSupplierId] = useState('');
  const [manualInvProductId, setManualInvProductId] = useState('');
  const [manualInvQty, setManualInvQty] = useState('1');
  const [manualInvPrice, setManualInvPrice] = useState('0');
  const [manualInvTaxRate, setManualInvTaxRate] = useState('');
  const [manualInvRc, setManualInvRc] = useState(false);
  const [ocrFor, setOcrFor] = useState<string | null>(null);
  const [ocrDraft, setOcrDraft] = useState<{
    supplier_invoice_number: string;
    notes: string;
    invoice_date: string;
  } | null>(null);
  const [ocrMeta, setOcrMeta] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [poPrefix, setPoPrefix] = useState('PO');
  const [poNext, setPoNext] = useState('1');
  const [poPreview, setPoPreview] = useState('');
  const [grnPrefix, setGrnPrefix] = useState('GRN');
  const [grnNext, setGrnNext] = useState('1');
  const [grnPreview, setGrnPreview] = useState('');

  async function refresh() {
    const [poRes, prRes, settingsRes, numRes, supRes, prodRes, unitRes, grnRes, invRes, retRes] =
      await Promise.all([
      api('/purchasing/orders'),
      api('/purchasing/requests'),
      api('/purchasing/requests/settings'),
      api('/purchasing/settings').catch(() => ({ data: null })),
      api('/suppliers'),
      api('/products'),
      api('/catalog/units').catch(() => ({ data: [] })),
      api('/purchasing/grn'),
      api('/purchasing/invoices'),
      api('/purchasing/returns'),
    ]);
    setOrders(poRes.data || []);
    setRequests(prRes.data || []);
    setPrLevels(settingsRes.data?.levels || []);
    setSuppliers(supRes.data || []);
    setProducts(prodRes.data || []);
    setUnits((unitRes.data || []).filter((u: Unit) => u.is_active !== false));
    setGrns(grnRes.data || []);
    setInvoices(invRes.data || []);
    setReturns(retRes.data || []);
    const poNum = numRes.data?.purchase_order_numbering;
    if (poNum) {
      setPoPrefix(poNum.prefix || 'PO');
      setPoNext(String(poNum.next_number ?? 1));
      setPoPreview(poNum.preview || '');
    }
    const grnNum = numRes.data?.grn_numbering;
    if (grnNum) {
      setGrnPrefix(grnNum.prefix || 'GRN');
      setGrnNext(String(grnNum.next_number ?? 1));
      setGrnPreview(grnNum.preview || '');
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    const product = products.find((p) => p.id === productId);
    if (product) setUnitPrice(String(product.cost_price ?? 0));
  }, [productId, products]);

  useEffect(() => {
    const product = products.find((p) => p.id === manualInvProductId);
    if (product) setManualInvPrice(String(product.cost_price ?? 0));
  }, [manualInvProductId, products]);

  useEffect(() => {
    const grn = grns.find((g) => g.id === grnId);
    if (grn?.items?.length) {
      setGrnItemId(grn.items[0].id);
      setReturnQty(String(grn.items[0].accepted_qty || 1));
    } else {
      setGrnItemId('');
    }
  }, [grnId, grns]);

  async function createSupplier() {
    setError('');
    try {
      const r = await api('/suppliers', {
        method: 'POST',
        body: JSON.stringify({
          name: supplierName,
          code: supplierCode.trim() || null,
          profile_type: supplierProfileType || 'registered',
          category: supplierCategory.trim() || null,
          status: supplierStatus || 'active',
          email: supplierEmail.trim() || null,
          phone: supplierPhone.trim() || null,
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
          delivery_address: poDeliveryAddress.trim() || null,
          items: [
            {
              product_id: productId,
              quantity: Number(qty),
              unit_id: unitId || null,
              unit_price: Number(unitPrice),
              // omit tax_rate → backend resolves product/category/default (BR-12.2)
            },
          ],
        }),
      });
      setMessage(`Created ${r.data.po_number}`);
      setPoDeliveryAddress('');
      await refresh();
      setSelected(r.data);
      setTab('orders');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function sendPo(poId: string, resend = false) {
    setError('');
    try {
      const r = await api(`/purchasing/orders/${poId}/send`, { method: 'POST' });
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
      setError(err.message);
    }
  }

  function openAmend(po: PurchaseOrder) {
    setSelected(po);
    const drafts: Record<string, { received: string; accepted: string; rejected: string; reason: string }> =
      {};
    for (const i of po.items.filter((x) => x.outstanding_qty > 0)) {
      const out = String(i.outstanding_qty);
      drafts[i.id] = { received: out, accepted: out, rejected: '0', reason: '' };
    }
    setReceiveDrafts(drafts);
    const line = po.items?.[0];
    setAmendQty(String(line?.quantity ?? ''));
    setAmendPrice(String(line?.unit_price ?? ''));
    setAmendUnitId(line?.unit_id || '');
    setAmendNotes(po.notes || '');
    setAmendDeliveryAddress(po.delivery_address || '');
    setAmendReason('');
    setAmendNotify(po.status === 'sent');
  }

  async function amendPo() {
    if (!selected?.id || !selected.items?.length) return;
    setError('');
    setMessage('');
    try {
      const line = selected.items[0];
      const r = await api(`/purchasing/orders/${selected.id}/amend`, {
        method: 'POST',
        body: JSON.stringify({
          reason: amendReason.trim() || null,
          notes: amendNotes,
          delivery_address: amendDeliveryAddress,
          notify_supplier: amendNotify,
          items: [
            {
              product_id: line.product_id,
              quantity: Number(amendQty) || line.quantity,
              unit_id: amendUnitId || line.unit_id || null,
              unit_price: Number(amendPrice) || line.unit_price,
              ...(line.tax_rate != null ? { tax_rate: Number(line.tax_rate) } : {}),
            },
          ],
        }),
      });
      const rev = r.data?.revision_no ?? r.data?.amendment?.revision_no;
      setMessage(r.message || `Amended ${r.data.po_number} (rev.${rev})`);
      await refresh();
      setSelected(r.data);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function receiveAll(po: PurchaseOrder) {
    setError('');
    try {
      const items = po.items
        .filter((i) => i.outstanding_qty > 0)
        .map((i) => ({
          po_item_id: i.id,
          received_qty: i.outstanding_qty,
          accepted_qty: i.outstanding_qty,
          rejected_qty: 0,
        }));
      if (!items.length) {
        setError('Nothing left to receive');
        return;
      }
      const r = await api('/purchasing/grn', {
        method: 'POST',
        body: JSON.stringify({ purchase_order_id: po.id, items }),
      });
      setMessage(`Posted ${r.data.grn_number}`);
      await refresh();
      const updated = await api(`/purchasing/orders/${po.id}`);
      setSelected(updated.data);
      setReceiveDrafts({});
      setTab('grn');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function postPartialReceive(po: PurchaseOrder) {
    setError('');
    setMessage('');
    try {
      const items = po.items
        .filter((i) => i.outstanding_qty > 0)
        .map((i) => {
          const d = receiveDrafts[i.id] || {
            received: String(i.outstanding_qty),
            accepted: String(i.outstanding_qty),
            rejected: '0',
            reason: '',
          };
          const received_qty = Number(d.received) || 0;
          const accepted_qty = Number(d.accepted) || 0;
          const rejected_qty = Number(d.rejected) || 0;
          return {
            po_item_id: i.id,
            received_qty,
            accepted_qty,
            rejected_qty,
            rejection_reason: d.reason.trim() || undefined,
          };
        })
        .filter((i) => i.received_qty > 0);
      if (!items.length) {
        setError('Enter a received quantity on at least one line');
        return;
      }
      const r = await api('/purchasing/grn', {
        method: 'POST',
        body: JSON.stringify({ purchase_order_id: po.id, items }),
      });
      const rejectedLines = (r.data.items || []).filter((x: GrnItem) => (x.rejected_qty || 0) > 0);
      setMessage(
        rejectedLines.length
          ? `Posted ${r.data.grn_number} (${rejectedLines.length} line(s) with rejected qty)`
          : `Posted ${r.data.grn_number}`
      );
      await refresh();
      const updated = await api(`/purchasing/orders/${po.id}`);
      setSelected(updated.data);
      const drafts: Record<string, { received: string; accepted: string; rejected: string; reason: string }> =
        {};
      for (const i of (updated.data.items || []).filter((x: PoItem) => x.outstanding_qty > 0)) {
        const out = String(i.outstanding_qty);
        drafts[i.id] = { received: out, accepted: out, rejected: '0', reason: '' };
      }
      setReceiveDrafts(drafts);
      setTab('grn');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createReturn() {
    setError('');
    try {
      const r = await api('/purchasing/returns', {
        method: 'POST',
        body: JSON.stringify({
          goods_receipt_id: grnId,
          reason: returnReason,
          items: [{ goods_receipt_item_id: grnItemId, quantity: Number(returnQty) }],
        }),
      });
      setMessage(`Return ${r.data.return_number} drafted`);
      setTab('returns');
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
              ...(manualInvTaxRate.trim() !== ''
                ? { tax_rate: Number(manualInvTaxRate) }
                : {}),
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
      const body: Record<string, unknown> = {};
      if (ocrDraft.supplier_invoice_number !== '') {
        body.supplier_invoice_number = ocrDraft.supplier_invoice_number;
      }
      if (ocrDraft.notes !== '') body.notes = ocrDraft.notes;
      if (ocrDraft.invoice_date !== '') body.invoice_date = ocrDraft.invoice_date;
      await api(`/purchasing/invoices/${ocrFor}`, { method: 'PATCH', body: JSON.stringify(body) });
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

  async function createRequest() {
    setError('');
    setMessage('');
    try {
      const r = await api('/purchasing/requests', {
        method: 'POST',
        body: JSON.stringify({
          preferred_supplier_id: prSupplierId || null,
          department: prDepartment.trim() || null,
          notes: prNotes.trim() || null,
          items: [{ product_id: prProductId, quantity: Number(prQty) || 1 }],
        }),
      });
      setMessage(`Created ${r.data.request_number}`);
      setPrNotes('');
      await refresh();
      setTab('requests');
    } catch (err: any) {
      setError(err.message);
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
            label: l.label || undefined,
          })),
        }),
      });
      setPrLevels(r.data?.levels || []);
      setMessage(`PR approval matrix saved (${r.data?.steps_required || prLevels.length} levels)`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function savePurchasingNumbering() {
    setError('');
    setMessage('');
    try {
      const r = await api('/purchasing/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          purchase_order_numbering: {
            prefix: poPrefix.trim(),
            next_number: Math.max(1, Number(poNext) || 1),
          },
          grn_numbering: {
            prefix: grnPrefix.trim(),
            next_number: Math.max(1, Number(grnNext) || 1),
          },
        }),
      });
      const poNum = r.data?.purchase_order_numbering;
      if (poNum) {
        setPoPrefix(poNum.prefix);
        setPoNext(String(poNum.next_number));
        setPoPreview(poNum.preview);
      }
      const grnNum = r.data?.grn_numbering;
      if (grnNum) {
        setGrnPrefix(grnNum.prefix);
        setGrnNext(String(grnNum.next_number));
        setGrnPreview(grnNum.preview);
      }
      setMessage(`Numbering saved — PO ${poNum?.preview || ''} / GRN ${grnNum?.preview || ''}`.trim());
    } catch (err: any) {
      setError(err.message);
    }
  }

  function updatePrLevel(idx: number, patch: Partial<(typeof prLevels)[0]>) {
    setPrLevels((prev) => prev.map((l, i) => (i === idx ? { ...l, ...patch } : l)));
  }

  async function prAction(id: string, action: 'submit' | 'approve' | 'reject' | 'convert') {
    setError('');
    setMessage('');
    setPrBusy(`${action}:${id}`);
    try {
      const body =
        action === 'reject'
          ? JSON.stringify({ reason: 'Rejected from purchasing UI' })
          : action === 'convert'
            ? '{}'
            : '{}';
      const r = await api(`/purchasing/requests/${id}/${action}`, {
        method: 'POST',
        body,
      });
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
      setError(err.message);
    } finally {
      setPrBusy('');
    }
  }

  const selectedGrn = grns.find((g) => g.id === grnId);
  const productName = (id: string) => products.find((p) => p.id === id)?.name || id.slice(0, 8);

  return (
    <Shell>
      <h1>Purchasing</h1>
      <p className="muted">Requests → purchase orders → GRN → invoices → returns</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(
          [
            ['requests', 'Requests'],
            ['orders', 'Orders'],
            ['grn', 'GRNs'],
            ['invoices', 'Invoices'],
            ['returns', 'Returns'],
          ] as const
        ).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} disabled={tab === id}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'requests' && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Document numbering</h3>
            <p className="muted" style={{ marginBottom: 8 }}>
              Pattern <code>{'{PREFIX}-{YYYY}-{NNNN}'}</code>
            </p>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}>
              <span className="muted">PO</span>
              <input
                value={poPrefix}
                onChange={(e) => setPoPrefix(e.target.value.toUpperCase())}
                placeholder="Prefix"
                style={{ width: 100 }}
              />
              <input
                value={poNext}
                onChange={(e) => setPoNext(e.target.value)}
                placeholder="Next #"
                style={{ width: 90 }}
              />
              <span className="muted">{poPreview || '—'}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="muted">GRN</span>
              <input
                value={grnPrefix}
                onChange={(e) => setGrnPrefix(e.target.value.toUpperCase())}
                placeholder="Prefix"
                style={{ width: 100 }}
              />
              <input
                value={grnNext}
                onChange={(e) => setGrnNext(e.target.value)}
                placeholder="Next #"
                style={{ width: 90 }}
              />
              <span className="muted">{grnPreview || '—'}</span>
              <button type="button" onClick={savePurchasingNumbering}>
                Save numbering
              </button>
            </div>
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>PR approval matrix</h3>
            <p className="muted" style={{ marginBottom: 8 }}>
              Role chain (no amount thresholds). Default: Store Manager → Company Admin. Roles are
              comma-separated.
            </p>
            {prLevels.map((lvl, idx) => (
              <div
                key={idx}
                style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 8 }}
              >
                <span className="muted">L{idx + 1}</span>
                <input
                  value={lvl.label || ''}
                  onChange={(e) => updatePrLevel(idx, { label: e.target.value })}
                  placeholder="Label"
                  style={{ width: 160 }}
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
                  placeholder="Roles"
                  style={{ minWidth: 280, flex: 1 }}
                />
                <button
                  type="button"
                  onClick={() => setPrLevels((prev) => prev.filter((_, i) => i !== idx))}
                  disabled={prLevels.length <= 1}
                >
                  Remove
                </button>
              </div>
            ))}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() =>
                  setPrLevels((prev) => [...prev, { roles: ['company_admin'], label: `Level ${prev.length + 1}` }])
                }
                disabled={prLevels.length >= 5}
              >
                Add level
              </button>
              <button type="button" onClick={savePrSettings}>
                Save matrix
              </button>
            </div>
          </div>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Create purchase request</h3>
            <div style={{ display: 'grid', gap: 8 }}>
              <select value={prSupplierId} onChange={(e) => setPrSupplierId(e.target.value)}>
                <option value="">Preferred supplier (optional)</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <select value={prProductId} onChange={(e) => setPrProductId(e.target.value)}>
                <option value="">Select product</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.sku})
                  </option>
                ))}
              </select>
              <input value={prQty} onChange={(e) => setPrQty(e.target.value)} placeholder="Quantity" />
              <input
                value={prDepartment}
                onChange={(e) => setPrDepartment(e.target.value)}
                placeholder="Requesting department (optional)"
              />
              <input
                value={prNotes}
                onChange={(e) => setPrNotes(e.target.value)}
                placeholder="Notes (optional)"
              />
              <button onClick={createRequest} disabled={!prProductId}>
                Create draft PR
              </button>
            </div>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Status</th>
                <th>Approval</th>
                <th>Department</th>
                <th>Lines</th>
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
                  </td>
                  <td>{r.department || '—'}</td>
                  <td>
                    {(r.items || [])
                      .map((i) => `${productName(i.product_id)} × ${i.quantity}`)
                      .join(', ') || '—'}
                  </td>
                  <td style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {r.status === 'draft' && (
                      <button
                        type="button"
                        disabled={prBusy === `submit:${r.id}`}
                        onClick={() => prAction(r.id, 'submit')}
                      >
                        Submit
                      </button>
                    )}
                    {r.status === 'pending' && (
                      <>
                        <button
                          type="button"
                          disabled={prBusy === `approve:${r.id}`}
                          onClick={() => prAction(r.id, 'approve')}
                        >
                          Approve L{r.awaiting_level || r.approval_step || 1}
                        </button>
                        <button
                          type="button"
                          disabled={prBusy === `reject:${r.id}`}
                          onClick={() => prAction(r.id, 'reject')}
                        >
                          Reject
                        </button>
                      </>
                    )}
                    {r.status === 'approved' && (
                      <button
                        type="button"
                        disabled={prBusy === `convert:${r.id}`}
                        onClick={() => prAction(r.id, 'convert')}
                      >
                        Convert to PO
                      </button>
                    )}
                    {r.status === 'converted' && (
                      <span className="muted">{r.converted_po_id ? 'PO linked' : 'Converted'}</span>
                    )}
                  </td>
                </tr>
              ))}
              {requests.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    No purchase requests yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Quick add supplier</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="Supplier name" />
          <input
            value={supplierCode}
            onChange={(e) => setSupplierCode(e.target.value)}
            placeholder="Code"
            style={{ width: 100 }}
          />
          <select
            value={supplierProfileType}
            onChange={(e) => setSupplierProfileType(e.target.value)}
            title="Supplier type"
          >
            <option value="registered">Registered</option>
            <option value="trade">Trade</option>
            <option value="manufacturer">Manufacturer</option>
            <option value="service">Service</option>
            <option value="other">Other</option>
          </select>
          <input
            value={supplierCategory}
            onChange={(e) => setSupplierCategory(e.target.value)}
            placeholder="Category"
            style={{ width: 120 }}
          />
          <select value={supplierStatus} onChange={(e) => setSupplierStatus(e.target.value)} title="Status">
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <input
            value={supplierEmail}
            onChange={(e) => setSupplierEmail(e.target.value)}
            placeholder="Email"
          />
          <input
            value={supplierPhone}
            onChange={(e) => setSupplierPhone(e.target.value)}
            placeholder="Phone"
            style={{ width: 120 }}
          />
          <input
            value={supplierAddress}
            onChange={(e) => setSupplierAddress(e.target.value)}
            placeholder="Address"
            style={{ minWidth: 160 }}
          />
          <input
            value={supplierLat}
            onChange={(e) => setSupplierLat(e.target.value)}
            placeholder="Lat"
            style={{ width: 90 }}
            title="GPS latitude"
          />
          <input
            value={supplierLng}
            onChange={(e) => setSupplierLng(e.target.value)}
            placeholder="Lng"
            style={{ width: 90 }}
            title="GPS longitude"
          />
          <input
            value={supplierTermsDays}
            onChange={(e) => setSupplierTermsDays(e.target.value)}
            placeholder="Net days"
            style={{ width: 90 }}
            title="Payment terms (days)"
          />
          <button onClick={createSupplier} disabled={!supplierName.trim()}>
            Add
          </button>
        </div>
        {supplierId ? (
          <PartyContactsPanel
            kind="supplier"
            partyId={supplierId}
            partyLabel={suppliers.find((s) => s.id === supplierId)?.name || 'Selected supplier'}
          />
        ) : null}
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Create purchase order</h3>
        <div style={{ display: 'grid', gap: 8 }}>
          <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">Select supplier</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code ? `${s.code} — ` : ''}
                {s.name}
                {s.status === 'inactive' ? ' [inactive]' : ''}
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
          <select value={unitId} onChange={(e) => setUnitId(e.target.value)}>
            <option value="">Unit (product default)</option>
            {units.map((u) => (
              <option key={u.id} value={u.id}>
                {u.code} — {u.name}
              </option>
            ))}
          </select>
          <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Quantity" />
          <input value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} placeholder="Unit price" />
          <input
            value={poDeliveryAddress}
            onChange={(e) => setPoDeliveryAddress(e.target.value)}
            placeholder="Delivery address (optional)"
          />
          <button onClick={createPo} disabled={!supplierId || !productId}>
            Create draft PO
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Create purchase invoice from GRN</h3>
        <div style={{ display: 'grid', gap: 8 }}>
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
        <div style={{ display: 'grid', gap: 8 }}>
          <select value={manualInvSupplierId} onChange={(e) => setManualInvSupplierId(e.target.value)}>
            <option value="">Select supplier</option>
            {suppliers.map((s) => (
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
            placeholder="Tax rate % (blank = auto)"
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
        <div style={{ display: 'grid', gap: 8 }}>
          <select value={grnId} onChange={(e) => setGrnId(e.target.value)}>
            <option value="">Select GRN</option>
            {grns.map((g) => (
              <option key={g.id} value={g.id}>
                {g.grn_number}
              </option>
            ))}
          </select>
          <select value={grnItemId} onChange={(e) => setGrnItemId(e.target.value)} disabled={!selectedGrn}>
            <option value="">Select GRN line</option>
            {(selectedGrn?.items || []).map((i) => (
              <option key={i.id} value={i.id}>
                {i.product_id} (accepted {i.accepted_qty})
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
          <input value={returnQty} onChange={(e) => setReturnQty(e.target.value)} placeholder="Return qty" />
          <button onClick={createReturn} disabled={!grnId || !grnItemId}>
            Draft return
          </button>
        </div>
      </div>

      {tab === 'orders' && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>PO</th>
                <th>Status</th>
                <th>Rev</th>
                <th>Total</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>
                    <button
                      onClick={() => openAmend(o)}
                      style={{ background: 'none', border: 0, color: '#1d4ed8', cursor: 'pointer' }}
                    >
                      {o.po_number}
                    </button>
                  </td>
                  <td>{o.status}</td>
                  <td>{o.revision_no ?? 0}</td>
                  <td>{o.total_amount}</td>
                  <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {o.status === 'draft' && <button onClick={() => sendPo(o.id)}>Email</button>}
                    {o.status === 'sent' && (
                      <button onClick={() => sendPo(o.id, true)}>Resend</button>
                    )}
                    {o.can_amend && (
                      <button type="button" onClick={() => openAmend(o)}>
                        Amend
                      </button>
                    )}
                    {(o.status === 'sent' || o.status === 'partially_received') && (
                      <button onClick={() => receiveAll(o)}>Receive all</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {selected && (
            <div className="card" style={{ marginTop: 16 }}>
              <h3>
                {selected.po_number} — {selected.status}
                {selected.delivery_address ? ` · Ship to: ${selected.delivery_address}` : ''}
                {selected.revision_no ? ` · rev.${selected.revision_no}` : ''}
              </h3>
              {selected.emailed_to && (
                <p style={{ marginTop: 0, color: '#475569', fontSize: 14 }}>
                  Last emailed to {selected.emailed_to}
                  {selected.emailed_at ? ` · ${String(selected.emailed_at).slice(0, 19)}` : ''}
                </p>
              )}
              <table className="table">
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Ordered</th>
                    <th>Received</th>
                    <th>Outstanding</th>
                    <th>Unit price</th>
                    {(selected.status === 'sent' || selected.status === 'partially_received') && (
                      <>
                        <th>Receive</th>
                        <th>Accept</th>
                        <th>Reject</th>
                        <th>Reject reason</th>
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
                    };
                    const receivable =
                      (selected.status === 'sent' || selected.status === 'partially_received') &&
                      i.outstanding_qty > 0;
                    return (
                      <tr key={i.id}>
                        <td>{i.product_id}</td>
                        <td>{i.quantity}</td>
                        <td>{i.received_qty}</td>
                        <td>{i.outstanding_qty}</td>
                        <td>{i.unit_price}</td>
                        {(selected.status === 'sent' || selected.status === 'partially_received') && (
                          <>
                            <td>
                              {receivable ? (
                                <input
                                  style={{ width: 72 }}
                                  value={draft.received}
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
                          </>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {(selected.status === 'sent' || selected.status === 'partially_received') &&
                selected.items.some((i) => i.outstanding_qty > 0) && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
                    <button type="button" onClick={() => postPartialReceive(selected)}>
                      Post GRN (accept / reject)
                    </button>
                    <button type="button" onClick={() => receiveAll(selected)}>
                      Receive all accepted
                    </button>
                    <span className="muted">
                      Rejected qty requires a reason; only accepted qty is stocked.
                    </span>
                  </div>
                )}
              {selected.can_amend && (
                <div style={{ display: 'grid', gap: 8, marginTop: 12 }}>
                  <h4 style={{ margin: 0 }}>Amend (first line)</h4>
                  <select value={amendUnitId} onChange={(e) => setAmendUnitId(e.target.value)}>
                    <option value="">Unit (product default)</option>
                    {units.map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.code}
                      </option>
                    ))}
                  </select>
                  <input
                    value={amendQty}
                    onChange={(e) => setAmendQty(e.target.value)}
                    placeholder="Quantity"
                  />
                  <input
                    value={amendPrice}
                    onChange={(e) => setAmendPrice(e.target.value)}
                    placeholder="Unit price"
                  />
                  <input
                    value={amendNotes}
                    onChange={(e) => setAmendNotes(e.target.value)}
                    placeholder="Notes"
                  />
                  <input
                    value={amendDeliveryAddress}
                    onChange={(e) => setAmendDeliveryAddress(e.target.value)}
                    placeholder="Delivery address"
                  />
                  <input
                    value={amendReason}
                    onChange={(e) => setAmendReason(e.target.value)}
                    placeholder="Amendment reason"
                  />
                  <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <input
                      type="checkbox"
                      checked={amendNotify}
                      onChange={(e) => setAmendNotify(e.target.checked)}
                      disabled={selected.status !== 'sent' && !selected.emailed_at}
                    />
                    Email supplier about amendment
                  </label>
                  <button type="button" onClick={amendPo}>
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
        <table className="table">
          <thead>
            <tr>
              <th>GRN</th>
              <th>PO</th>
              <th>Status</th>
              <th>Lines</th>
              <th>Accepted</th>
              <th>Rejected</th>
              <th>Reject reasons</th>
            </tr>
          </thead>
          <tbody>
            {grns.map((g) => {
              const accepted = (g.items || []).reduce((s, i) => s + Number(i.accepted_qty || 0), 0);
              const rejected = (g.items || []).reduce((s, i) => s + Number(i.rejected_qty || 0), 0);
              const reasons = (g.items || [])
                .filter((i) => (i.rejected_qty || 0) > 0 && i.rejection_reason)
                .map((i) => i.rejection_reason)
                .join('; ');
              return (
                <tr key={g.id}>
                  <td>{g.grn_number}</td>
                  <td>{g.purchase_order_id}</td>
                  <td>{g.status}</td>
                  <td>{g.items?.length || 0}</td>
                  <td>{accepted}</td>
                  <td>{rejected}</td>
                  <td>{reasons || '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {tab === 'invoices' && (
        <>
          {ocrDraft && ocrFor && (
            <div className="card" style={{ marginBottom: 16 }}>
              <h3>Supplier invoice OCR</h3>
              <p className="muted">
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
                <td>
                  <button
                    type="button"
                    onClick={async () => {
                      try {
                        const r = await api(`/purchasing/invoices/${inv.id}`);
                        setSelectedInvoice(r.data);
                      } catch (err: any) {
                        setError(err.message);
                      }
                    }}
                    style={{ background: 'none', border: 0, color: '#1d4ed8', cursor: 'pointer' }}
                  >
                    {inv.invoice_number}
                  </button>
                </td>
                <td>{inv.supplier_invoice_number || '—'}</td>
                <td>{inv.status}</td>
                <td>{inv.total_amount}</td>
                <td>
                  {inv.is_reverse_charge
                    ? `${inv.reverse_charge_tax ?? 0}`
                    : inv.tax_amount ?? '—'}
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
        {selectedInvoice && (
          <div className="card" style={{ marginTop: 16 }}>
            <h3>
              {selectedInvoice.invoice_number} — {selectedInvoice.status}
            </h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Qty</th>
                  <th>Unit</th>
                  <th>Tax %</th>
                  <th>Line tax</th>
                  <th>Line total</th>
                </tr>
              </thead>
              <tbody>
                {(selectedInvoice.items || []).map((it) => (
                  <tr key={it.id}>
                    <td>{productName(it.product_id)}</td>
                    <td>{it.quantity}</td>
                    <td>{it.unit_price}</td>
                    <td>{it.tax_rate}</td>
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
        <table className="table">
          <thead>
            <tr>
              <th>Return</th>
              <th>Debit note</th>
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
                <td>{r.reason}</td>
                <td>{r.status}</td>
                <td>{r.total_amount}</td>
                <td>
                  {r.status === 'draft' && <button onClick={() => postReturn(r.id)}>Post</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Shell>
  );
}
