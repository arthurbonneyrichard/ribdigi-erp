'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Tab = 'requests' | 'orders' | 'grn' | 'invoices' | 'returns';
type Supplier = { id: string; name: string };
type Product = { id: string; name: string; sku: string; cost_price: number };
type PurchaseRequest = {
  id: string;
  request_number: string;
  status: string;
  preferred_supplier_id?: string | null;
  department?: string | null;
  notes?: string | null;
  converted_po_id?: string | null;
  items: { id: string; product_id: string; quantity: number }[];
  purchase_order?: { id: string; po_number: string };
};
type PoItem = {
  id: string;
  product_id: string;
  quantity: number;
  received_qty: number;
  unit_price: number;
  outstanding_qty: number;
};
type PurchaseOrder = {
  id: string;
  po_number: string;
  supplier_id: string;
  status: string;
  total_amount: number;
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
};

export default function Page() {
  const [tab, setTab] = useState<Tab>('requests');
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [requests, setRequests] = useState<PurchaseRequest[]>([]);
  const [grns, setGrns] = useState<Grn[]>([]);
  const [invoices, setInvoices] = useState<PurchaseInvoice[]>([]);
  const [returns, setReturns] = useState<PurchaseReturn[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<PurchaseOrder | null>(null);
  const [supplierId, setSupplierId] = useState('');
  const [supplierName, setSupplierName] = useState('');
  const [productId, setProductId] = useState('');
  const [qty, setQty] = useState('10');
  const [unitPrice, setUnitPrice] = useState('0');
  const [prSupplierId, setPrSupplierId] = useState('');
  const [prProductId, setPrProductId] = useState('');
  const [prQty, setPrQty] = useState('10');
  const [prDepartment, setPrDepartment] = useState('');
  const [prNotes, setPrNotes] = useState('');
  const [prBusy, setPrBusy] = useState('');
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
  const [manualInvTaxRate, setManualInvTaxRate] = useState('15');
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

  async function refresh() {
    const [poRes, prRes, supRes, prodRes, grnRes, invRes, retRes] = await Promise.all([
      api('/purchasing/orders'),
      api('/purchasing/requests'),
      api('/suppliers'),
      api('/products'),
      api('/purchasing/grn'),
      api('/purchasing/invoices'),
      api('/purchasing/returns'),
    ]);
    setOrders(poRes.data || []);
    setRequests(prRes.data || []);
    setSuppliers(supRes.data || []);
    setProducts(prodRes.data || []);
    setGrns(grnRes.data || []);
    setInvoices(invRes.data || []);
    setReturns(retRes.data || []);
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
        body: JSON.stringify({ name: supplierName }),
      });
      setSupplierId(r.data.id);
      setSupplierName('');
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
      setMessage(`Created ${r.data.po_number}`);
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
                          Approve
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
                  <td colSpan={5} className="muted">
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
        <div style={{ display: 'flex', gap: 8 }}>
          <input value={supplierName} onChange={(e) => setSupplierName(e.target.value)} placeholder="Supplier name" />
          <button onClick={createSupplier} disabled={!supplierName.trim()}>
            Add
          </button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Create purchase order</h3>
        <div style={{ display: 'grid', gap: 8 }}>
          <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
            <option value="">Select supplier</option>
            {suppliers.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
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
                <th>Total</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>
                    <button
                      onClick={() => setSelected(o)}
                      style={{ background: 'none', border: 0, color: '#1d4ed8', cursor: 'pointer' }}
                    >
                      {o.po_number}
                    </button>
                  </td>
                  <td>{o.status}</td>
                  <td>{o.total_amount}</td>
                  <td style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {o.status === 'draft' && <button onClick={() => sendPo(o.id)}>Email</button>}
                    {o.status === 'sent' && (
                      <button onClick={() => sendPo(o.id, true)}>Resend</button>
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
                  </tr>
                </thead>
                <tbody>
                  {selected.items.map((i) => (
                    <tr key={i.id}>
                      <td>{i.product_id}</td>
                      <td>{i.quantity}</td>
                      <td>{i.received_qty}</td>
                      <td>{i.outstanding_qty}</td>
                      <td>{i.unit_price}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
