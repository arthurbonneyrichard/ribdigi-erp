'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';

type Tab = 'invoices' | 'quotations' | 'orders' | 'returns';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function downloadInvoicePdf(
  invoiceId: string,
  invoiceNumber: string,
  template: 'a4' | 'thermal',
  paper = '80mm'
) {
  const token = localStorage.getItem('token');
  const tenant = localStorage.getItem('tenant');
  const qs =
    template === 'thermal'
      ? `template=thermal&format=pdf&paper=${encodeURIComponent(paper)}`
      : 'template=a4&format=pdf';
  const res = await fetch(`${apiBase}/sales/invoices/${invoiceId}/print?${qs}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(
      typeof detail === 'string' ? detail : detail?.message || body.message || 'PDF download failed'
    );
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `invoice-${invoiceNumber || invoiceId.slice(0, 8)}-${template}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Page() {
  const [tab, setTab] = useState<Tab>('invoices');
  const [invoices, setInvoices] = useState<any[]>([]);
  const [quotations, setQuotations] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [returns, setReturns] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [variants, setVariants] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [customerId, setCustomerId] = useState('');
  const [storeId, setStoreId] = useState('');
  const [currency, setCurrency] = useState('');
  const [exchangeRate, setExchangeRate] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [creditLimit, setCreditLimit] = useState('0');
  const [productId, setProductId] = useState('');
  const [variantId, setVariantId] = useState('');
  const [qty, setQty] = useState('1');
  const [unitPrice, setUnitPrice] = useState('0');
  const [taxRate, setTaxRate] = useState('');
  const [invoiceId, setInvoiceId] = useState('');
  const [returnReason, setReturnReason] = useState('other');
  const [restock, setRestock] = useState(true);
  const [payAmount, setPayAmount] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  async function refresh() {
    const [invRes, custRes, prodRes, qRes, oRes, rRes, storeRes] = await Promise.all([
      api('/sales/invoices'),
      api('/customers'),
      api('/products'),
      api('/sales/quotations'),
      api('/sales/orders'),
      api('/sales/returns'),
      api('/stores'),
    ]);
    setInvoices(invRes.data || []);
    setCustomers(custRes.data || []);
    setProducts(prodRes.data || []);
    setQuotations(qRes.data || []);
    setOrders(oRes.data || []);
    setReturns(rRes.data || []);
    setStores(storeRes.data || []);
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setVariantId('');
    setVariants([]);
    if (!productId) return;
    const product = products.find((p) => p.id === productId);
    if (product) setUnitPrice(String(product.selling_price ?? 0));
    api(`/products/${productId}/variants`)
      .then((r) => setVariants((r.data || []).filter((v: any) => v.is_active !== false)))
      .catch(() => setVariants([]));
  }, [productId, products]);

  useEffect(() => {
    if (!variantId) return;
    const variant = variants.find((v) => v.id === variantId);
    if (variant) setUnitPrice(String(variant.selling_price ?? 0));
  }, [variantId, variants]);

  const linePayload = {
    customer_id: customerId,
    store_id: storeId || null,
    delivery_date: deliveryDate ? new Date(deliveryDate).toISOString() : null,
    delivery_address: deliveryAddress.trim() || null,
    items: [
      {
        product_id: productId,
        variant_id: variantId || null,
        quantity: Number(qty),
        unit_price: Number(unitPrice),
        tax_rate: taxRate === '' ? null : Number(taxRate),
      },
    ],
  };

  const invoicePayload = {
    customer_id: customerId,
    store_id: storeId || null,
    items: linePayload.items,
    currency: currency.trim() || null,
    exchange_rate: exchangeRate === '' ? null : Number(exchangeRate),
  };

  async function createCustomer() {
    setError('');
    try {
      const r = await api('/customers', {
        method: 'POST',
        body: JSON.stringify({
          name: customerName,
          email: customerEmail || null,
          credit_limit: Number(creditLimit) || 0,
        }),
      });
      setCustomerId(r.data.id);
      setCustomerName('');
      setCustomerEmail('');
      await refresh();
      setMessage('Customer created');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createInvoice() {
    setError('');
    try {
      const r = await api('/sales/invoices', { method: 'POST', body: JSON.stringify(invoicePayload) });
      setMessage(`Draft ${r.data.invoice_number} created`);
      setSelected(r.data);
      setTab('invoices');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createQuotation() {
    setError('');
    try {
      const r = await api('/sales/quotations', { method: 'POST', body: JSON.stringify(linePayload) });
      setMessage(`Quotation ${r.data.quotation_number} created`);
      setSelected(r.data);
      setTab('quotations');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createOrder() {
    setError('');
    try {
      const r = await api('/sales/orders', { method: 'POST', body: JSON.stringify(linePayload) });
      setMessage(`Order ${r.data.order_number} created`);
      setSelected(r.data);
      setTab('orders');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createReturn() {
    setError('');
    try {
      const r = await api('/sales/returns', {
        method: 'POST',
        body: JSON.stringify({
          sales_invoice_id: invoiceId,
          reason: returnReason,
          restock,
          items: [{ product_id: productId, variant_id: variantId || null, quantity: Number(qty) }],
        }),
      });
      setMessage(`Return ${r.data.return_number} drafted`);
      setSelected(r.data);
      setTab('returns');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function act(path: string, label: string, body: Record<string, unknown> = {}) {
    setError('');
    try {
      const r = await api(path, { method: 'POST', body: JSON.stringify(body) });
      setMessage(r.message || label);
      setSelected(r.data);
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function pay() {
    if (!selected?.id || !selected.customer_id) return;
    setError('');
    try {
      const r = await api('/sales/payments', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: selected.customer_id,
          sales_invoice_id: selected.id,
          amount: Number(payAmount),
        }),
      });
      setMessage(r.message || 'Payment recorded');
      setPayAmount('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  return (
    <Shell>
      <h1>Sales</h1>
      <p className="muted">Quotations → orders → invoices → returns</p>
      {error && <p style={{ color: '#b91c1c' }}>{error}</p>}
      {message && <p style={{ color: '#047857' }}>{message}</p>}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {(
          [
            ['invoices', 'Invoices'],
            ['quotations', 'Quotations'],
            ['orders', 'Orders'],
            ['returns', 'Returns'],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} disabled={tab === id}>
            {label}
          </button>
        ))}
      </div>

      <div className="card" style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">Customer</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.email ? ` (${c.email})` : ''}
              </option>
            ))}
          </select>
          <select value={storeId} onChange={(e) => setStoreId(e.target.value)}>
            <option value="">Store (required to confirm orders)</option>
            {stores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
          <input
            type="date"
            value={deliveryDate}
            onChange={(e) => setDeliveryDate(e.target.value)}
            title="Delivery date"
          />
          <input
            value={deliveryAddress}
            onChange={(e) => setDeliveryAddress(e.target.value)}
            placeholder="Delivery address"
            style={{ minWidth: 180 }}
          />
          <input
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            placeholder="Currency (blank=base)"
            style={{ width: 140 }}
          />
          <input
            value={exchangeRate}
            onChange={(e) => setExchangeRate(e.target.value)}
            placeholder="FX rate (optional)"
            style={{ width: 120 }}
          />
          <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="New customer" />
          <input
            value={customerEmail}
            onChange={(e) => setCustomerEmail(e.target.value)}
            placeholder="Customer email"
          />
          <input value={creditLimit} onChange={(e) => setCreditLimit(e.target.value)} placeholder="Credit limit" />
          <button onClick={createCustomer}>Add customer</button>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select value={productId} onChange={(e) => setProductId(e.target.value)}>
            <option value="">Product</option>
            {products.map((p) => (
              <option key={p.id} value={p.id}>
                {p.sku} — {p.name}
              </option>
            ))}
          </select>
          {variants.length > 0 && (
            <select value={variantId} onChange={(e) => setVariantId(e.target.value)}>
              <option value="">Variant (optional)</option>
              {variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.sku} — {v.name} ({v.selling_price})
                </option>
              ))}
            </select>
          )}
          <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Qty" style={{ width: 80 }} />
          <input value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)} placeholder="Price" style={{ width: 100 }} />
          <input value={taxRate} onChange={(e) => setTaxRate(e.target.value)} placeholder="Tax %" style={{ width: 80 }} />
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={createQuotation}>Create quotation</button>
          <button onClick={createOrder}>Create order</button>
          <button onClick={createInvoice}>Create invoice</button>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={invoiceId} onChange={(e) => setInvoiceId(e.target.value)}>
            <option value="">Return from invoice</option>
            {invoices
              .filter((i) => ['posted', 'sent', 'partial', 'overdue', 'paid'].includes(i.status))
              .map((i) => (
                <option key={i.id} value={i.id}>
                  {i.invoice_number}
                </option>
              ))}
          </select>
          <select value={returnReason} onChange={(e) => setReturnReason(e.target.value)}>
            {['damaged', 'wrong_item', 'defective', 'customer_change', 'other'].map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <label>
            <input type="checkbox" checked={restock} onChange={(e) => setRestock(e.target.checked)} /> Restock
          </label>
          <button onClick={createReturn}>Create return</button>
        </div>
      </div>

      {tab === 'quotations' && (
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Status</th>
              <th>Total</th>
              <th>Valid</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {quotations.map((q) => (
              <tr key={q.id}>
                <td>{q.quotation_number}</td>
                <td>{q.status}</td>
                <td>{q.total_amount}</td>
                <td>{q.valid_until ? String(q.valid_until).slice(0, 10) : '—'}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(q)}>View</button>
                  {q.status === 'draft' && (
                    <button onClick={() => act(`/sales/quotations/${q.id}/send`, 'Quotation emailed')}>
                      Email
                    </button>
                  )}
                  {q.status === 'sent' && (
                    <button onClick={() => act(`/sales/quotations/${q.id}/send`, 'Quotation re-emailed')}>
                      Resend
                    </button>
                  )}
                  {['draft', 'sent'].includes(q.status) && (
                    <>
                      <button onClick={() => act(`/sales/quotations/${q.id}/accept`, 'Accepted')}>Accept</button>
                      <button onClick={() => act(`/sales/quotations/${q.id}/convert-order`, 'Order')}>→ Order</button>
                      <button onClick={() => act(`/sales/quotations/${q.id}/convert-invoice`, 'Invoice')}>→ Invoice</button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'orders' && (
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Status</th>
              <th>Store</th>
              <th>Reserved</th>
              <th>Delivery</th>
              <th>Total</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {orders.map((o) => (
              <tr key={o.id}>
                <td>{o.order_number}</td>
                <td>{o.status}</td>
                <td>
                  {stores.find((s) => s.id === o.store_id)?.name ||
                    (o.store_id ? o.store_id.slice(0, 8) : '—')}
                </td>
                <td>
                  {o.reservation_status
                    ? `${o.reserved_qty ?? 0} (${o.reservation_status})`
                    : '—'}
                </td>
                <td>
                  {o.delivery_date
                    ? new Date(o.delivery_date).toLocaleDateString()
                    : '—'}
                  {o.delivery_address ? ` · ${o.delivery_address}` : ''}
                </td>
                <td>{o.total_amount}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(o)}>View</button>
                  {o.status === 'draft' && (
                    <button
                      onClick={() =>
                        act(
                          `/sales/orders/${o.id}/confirm`,
                          'Confirmed',
                          storeId || o.store_id
                            ? {
                                store_id: storeId || o.store_id,
                                delivery_date: deliveryDate
                                  ? new Date(deliveryDate).toISOString()
                                  : null,
                                delivery_address: deliveryAddress.trim() || null,
                              }
                            : {}
                        )
                      }
                    >
                      Confirm
                    </button>
                  )}
                  {o.can_process && (
                    <button onClick={() => act(`/sales/orders/${o.id}/process`, 'Processing')}>
                      Process
                    </button>
                  )}
                  {o.can_ship && (
                    <button onClick={() => act(`/sales/orders/${o.id}/ship`, 'Shipped')}>Ship</button>
                  )}
                  {o.can_deliver && (
                    <button onClick={() => act(`/sales/orders/${o.id}/deliver`, 'Delivered')}>
                      Deliver
                    </button>
                  )}
                  {o.can_invoice && (
                    <button onClick={() => act(`/sales/orders/${o.id}/convert-invoice`, 'Invoice')}>
                      → Invoice
                    </button>
                  )}
                  {o.can_cancel && (
                    <button onClick={() => act(`/sales/orders/${o.id}/cancel`, 'Cancelled')}>
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'invoices' && (
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Status</th>
              <th>Store</th>
              <th>Total</th>
              <th>Paid</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.invoice_number}</td>
                <td>{inv.status}</td>
                <td>
                  {stores.find((s) => s.id === inv.store_id)?.name ||
                    (inv.store_id ? inv.store_id.slice(0, 8) : '—')}
                </td>
                <td>{inv.total_amount}</td>
                <td>{inv.paid_amount}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(inv)}>View</button>
                  {inv.status === 'draft' && (
                    <>
                      <button onClick={() => act(`/sales/invoices/${inv.id}/post`, 'Posted')}>Post</button>
                      <button onClick={() => act(`/sales/invoices/${inv.id}/cancel`, 'Cancelled')}>Cancel</button>
                    </>
                  )}
                  {inv.can_print && (
                    <>
                      <button
                        onClick={() =>
                          downloadInvoicePdf(inv.id, inv.invoice_number, 'a4')
                            .then(() => setMessage(`Downloaded A4 ${inv.invoice_number}`))
                            .catch((err) => setError(err.message))
                        }
                      >
                        Print A4
                      </button>
                      <button
                        onClick={() =>
                          downloadInvoicePdf(inv.id, inv.invoice_number, 'thermal', '80mm')
                            .then(() => setMessage(`Downloaded thermal ${inv.invoice_number}`))
                            .catch((err) => setError(err.message))
                        }
                      >
                        Print thermal
                      </button>
                    </>
                  )}
                  {inv.can_email && (
                    <button onClick={() => act(`/sales/invoices/${inv.id}/send`, 'Invoice emailed')}>
                      {inv.emailed_at ? 'Resend email' : 'Email'}
                    </button>
                  )}
                  {inv.status === 'overdue' && (
                    <span className="muted" style={{ alignSelf: 'center' }}>
                      {inv.days_overdue}d overdue
                    </span>
                  )}
                  {['posted', 'sent', 'partial', 'overdue'].includes(inv.status) && (
                    <>
                      <input
                        value={selected?.id === inv.id ? payAmount : ''}
                        onChange={(e) => {
                          setSelected(inv);
                          setPayAmount(e.target.value);
                        }}
                        placeholder="Pay"
                        style={{ width: 80 }}
                      />
                      <button
                        onClick={() => {
                          setSelected(inv);
                          pay();
                        }}
                      >
                        Pay
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'returns' && (
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Credit note</th>
              <th>Status</th>
              <th>Settlement</th>
              <th>Reason</th>
              <th>Total</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {returns.map((r) => (
              <tr key={r.id}>
                <td>{r.return_number}</td>
                <td>{r.credit_note_number || '—'}</td>
                <td>{r.status}</td>
                <td>
                  {r.settlement_method || '—'}
                  {r.refunded_amount > 0 ? ` (refunded ${r.refunded_amount})` : ''}
                </td>
                <td>{r.reason}</td>
                <td>{r.total_amount}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(r)}>View</button>
                  {r.status === 'draft' && (
                    <>
                      <button
                        onClick={() =>
                          act(`/sales/returns/${r.id}/post`, 'Posted (credit)', {
                            settlement_method: 'adjust',
                          })
                        }
                      >
                        Post credit
                      </button>
                      <button
                        onClick={() =>
                          act(`/sales/returns/${r.id}/post`, 'Posted (refund)', {
                            settlement_method: 'refund',
                            payment_method: 'cash',
                          })
                        }
                      >
                        Post + refund
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selected && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Selected</h3>
          {selected.emailed_to && (
            <p className="muted" style={{ marginBottom: 8 }}>
              Last emailed to {selected.emailed_to}
              {selected.emailed_at ? ` · ${String(selected.emailed_at).slice(0, 19)}` : ''}
            </p>
          )}
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{JSON.stringify(selected, null, 2)}</pre>
        </div>
      )}
    </Shell>
  );
}
