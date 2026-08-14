'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import PartyContactsPanel from '../../components/PartyContactsPanel';
import { api } from '../../lib/api';
import { formatNumber, type FormatPrefs } from '../../lib/format';

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
  const [groups, setGroups] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [variants, setVariants] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [customerId, setCustomerId] = useState('');
  const [storeId, setStoreId] = useState('');
  const [currency, setCurrency] = useState('');
  const [exchangeRate, setExchangeRate] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerCode, setCustomerCode] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerAddress, setCustomerAddress] = useState('');
  const [customerProfileType, setCustomerProfileType] = useState('registered');
  const [customerStatus, setCustomerStatus] = useState('active');
  const [customerLat, setCustomerLat] = useState('');
  const [customerLng, setCustomerLng] = useState('');
  const [customerGroupId, setCustomerGroupId] = useState('');
  const [creditLimit, setCreditLimit] = useState('0');
  const [paymentTermsDays, setPaymentTermsDays] = useState('30');
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDiscount, setNewGroupDiscount] = useState('0');
  const [useGroupPrice, setUseGroupPrice] = useState(true);
  const [productId, setProductId] = useState('');
  const [variantId, setVariantId] = useState('');
  const [unitId, setUnitId] = useState('');
  const [units, setUnits] = useState<any[]>([]);
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
  const [invPrefix, setInvPrefix] = useState('INV');
  const [invNext, setInvNext] = useState('1');
  const [invPreview, setInvPreview] = useState('');
  const [qtPrefix, setQtPrefix] = useState('QT');
  const [qtNext, setQtNext] = useState('1');
  const [qtPreview, setQtPreview] = useState('');
  const [srPrefix, setSrPrefix] = useState('SR');
  const [srNext, setSrNext] = useState('1');
  const [srPreview, setSrPreview] = useState('');
  const [cnPrefix, setCnPrefix] = useState('CN');
  const [cnNext, setCnNext] = useState('1');
  const [cnPreview, setCnPreview] = useState('');
  const [fmt, setFmt] = useState<FormatPrefs | null>(null);

  async function refresh() {
    const [invRes, custRes, prodRes, unitRes, qRes, oRes, rRes, storeRes, settingsRes, groupRes, tenantRes] =
      await Promise.all([
        api('/sales/invoices'),
        api('/customers'),
        api('/products'),
        api('/catalog/units').catch(() => ({ data: [] })),
        api('/sales/quotations'),
        api('/sales/orders'),
        api('/sales/returns'),
        api('/stores'),
        api('/sales/settings').catch(() => ({ data: null })),
        api('/customers/groups').catch(() => ({ data: [] })),
        api('/tenants/me').catch(() => ({ data: null })),
      ]);
    setInvoices(invRes.data || []);
    setCustomers(custRes.data || []);
    setProducts(prodRes.data || []);
    setUnits((unitRes.data || []).filter((u: any) => u.is_active !== false));
    setQuotations(qRes.data || []);
    setOrders(oRes.data || []);
    setReturns(rRes.data || []);
    setStores(storeRes.data || []);
    setGroups(groupRes.data || []);
    if (tenantRes.data) setFmt(tenantRes.data);
    const numbering = settingsRes.data?.invoice_numbering;
    if (numbering) {
      setInvPrefix(numbering.prefix || 'INV');
      setInvNext(String(numbering.next_number ?? 1));
      setInvPreview(numbering.preview || '');
    }
    const qt = settingsRes.data?.quotation_numbering;
    if (qt) {
      setQtPrefix(qt.prefix || 'QT');
      setQtNext(String(qt.next_number ?? 1));
      setQtPreview(qt.preview || '');
    }
    const sr = settingsRes.data?.sales_return_numbering;
    if (sr) {
      setSrPrefix(sr.prefix || 'SR');
      setSrNext(String(sr.next_number ?? 1));
      setSrPreview(sr.preview || '');
    }
    const cn = settingsRes.data?.credit_note_numbering;
    if (cn) {
      setCnPrefix(cn.prefix || 'CN');
      setCnNext(String(cn.next_number ?? 1));
      setCnPreview(cn.preview || '');
    }
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
    if (variant && !useGroupPrice) setUnitPrice(String(variant.selling_price ?? 0));
  }, [variantId, variants, useGroupPrice]);

  useEffect(() => {
    if (!productId || !useGroupPrice) return;
    let cancelled = false;
    const qs = new URLSearchParams();
    if (customerId) qs.set('customer_id', customerId);
    if (variantId) qs.set('variant_id', variantId);
    api(`/products/${productId}/price?${qs.toString()}`)
      .then((r) => {
        if (!cancelled && r.data?.unit_price != null) {
          setUnitPrice(String(r.data.unit_price));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [productId, variantId, customerId, useGroupPrice]);

  const lineItems = [
    {
      product_id: productId,
      variant_id: variantId || null,
      unit_id: unitId || null,
      quantity: Number(qty),
      ...(useGroupPrice ? {} : { unit_price: Number(unitPrice) }),
      tax_rate: taxRate === '' ? null : Number(taxRate),
    },
  ];

  const linePayload = {
    customer_id: customerId,
    store_id: storeId || null,
    delivery_date: deliveryDate ? new Date(deliveryDate).toISOString() : null,
    delivery_address: deliveryAddress.trim() || null,
    items: lineItems,
  };

  const invoicePayload = {
    customer_id: customerId,
    store_id: storeId || null,
    items: lineItems,
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
          code: customerCode.trim() || null,
          profile_type: customerProfileType || 'registered',
          status: customerStatus || 'active',
          email: customerEmail || null,
          phone: customerPhone.trim() || null,
          address: customerAddress.trim() || null,
          latitude: customerLat === '' ? null : Number(customerLat),
          longitude: customerLng === '' ? null : Number(customerLng),
          credit_limit: Number(creditLimit) || 0,
          payment_terms_days: Number(paymentTermsDays) || 0,
          customer_group_id: customerGroupId || null,
        }),
      });
      setCustomerId(r.data.id);
      setCustomerName('');
      setCustomerCode('');
      setCustomerEmail('');
      setCustomerPhone('');
      setCustomerAddress('');
      setCustomerProfileType('registered');
      setCustomerStatus('active');
      setCustomerLat('');
      setCustomerLng('');
      setCustomerGroupId('');
      setPaymentTermsDays('30');
      await refresh();
      setMessage('Customer created');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createGroup() {
    setError('');
    try {
      await api('/customers/groups', {
        method: 'POST',
        body: JSON.stringify({
          name: newGroupName,
          discount_percent: Number(newGroupDiscount) || 0,
        }),
      });
      setNewGroupName('');
      setNewGroupDiscount('0');
      await refresh();
      setMessage('Customer group created');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function assignCustomerGroup() {
    if (!customerId || !customerGroupId) {
      setError('Select a customer and group to assign');
      return;
    }
    setError('');
    try {
      await api(`/customers/${customerId}`, {
        method: 'PATCH',
        body: JSON.stringify({ customer_group_id: customerGroupId }),
      });
      await refresh();
      setMessage('Customer group assigned');
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

  async function saveInvoiceNumbering() {
    setError('');
    setMessage('');
    try {
      const r = await api('/sales/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          invoice_numbering: {
            prefix: invPrefix.trim(),
            next_number: Math.max(1, Number(invNext) || 1),
          },
          quotation_numbering: {
            prefix: qtPrefix.trim(),
            next_number: Math.max(1, Number(qtNext) || 1),
          },
          sales_return_numbering: {
            prefix: srPrefix.trim(),
            next_number: Math.max(1, Number(srNext) || 1),
          },
          credit_note_numbering: {
            prefix: cnPrefix.trim(),
            next_number: Math.max(1, Number(cnNext) || 1),
          },
        }),
      });
      const numbering = r.data?.invoice_numbering;
      if (numbering) {
        setInvPrefix(numbering.prefix);
        setInvNext(String(numbering.next_number));
        setInvPreview(numbering.preview);
      }
      const qt = r.data?.quotation_numbering;
      if (qt) {
        setQtPrefix(qt.prefix);
        setQtNext(String(qt.next_number));
        setQtPreview(qt.preview);
      }
      const sr = r.data?.sales_return_numbering;
      if (sr) {
        setSrPrefix(sr.prefix);
        setSrNext(String(sr.next_number));
        setSrPreview(sr.preview);
      }
      const cn = r.data?.credit_note_numbering;
      if (cn) {
        setCnPrefix(cn.prefix);
        setCnNext(String(cn.next_number));
        setCnPreview(cn.preview);
      }
      setMessage(
        `Numbering saved — INV ${numbering?.preview || ''} / QT ${qt?.preview || ''} / SR ${sr?.preview || ''} / CN ${cn?.preview || ''}`.trim(),
      );
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

  async function postInvoice(inv: any) {
    setError('');
    try {
      const r = await api(`/sales/invoices/${inv.id}/post`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      setMessage(r.message || 'Posted');
      setSelected(r.data);
      await refresh();
    } catch (err: any) {
      const detail = err?.detail;
      if (
        err?.status === 409 &&
        detail &&
        typeof detail === 'object' &&
        detail.code === 'CREDIT_LIMIT_EXCEEDED'
      ) {
        const over = detail.over_by != null ? ` (over by ${detail.over_by})` : '';
        const ok = window.confirm(
          `Credit limit exceeded${over}. Post anyway with manager override?\n` +
            `Limit ${detail.credit_limit} · balance ${detail.current_balance} · invoice ${detail.invoice_total_base ?? detail.amount}`,
        );
        if (!ok) {
          setError(detail.message || err.message);
          return;
        }
        const reason =
          window.prompt('Override reason (optional)', 'Approved over-limit credit sale') || undefined;
        try {
          const r = await api(`/sales/invoices/${inv.id}/post`, {
            method: 'POST',
            body: JSON.stringify({
              override_credit_limit: true,
              override_reason: reason,
            }),
          });
          setMessage(
            r.data?.credit_limit_overridden
              ? `${r.message || 'Posted'} (credit limit overridden)`
              : r.message || 'Posted',
          );
          setSelected(r.data);
          await refresh();
        } catch (err2: any) {
          setError(err2.message);
        }
        return;
      }
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
        <h3 style={{ margin: 0 }}>Document numbering</h3>
        <p className="muted" style={{ margin: 0 }}>
          Pattern <code>{'{PREFIX}-{YYYY}-{NNNN}'}</code>
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Invoice</span>
          <input
            value={invPrefix}
            onChange={(e) => setInvPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={invNext}
            onChange={(e) => setInvNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{invPreview || '—'}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Quotation</span>
          <input
            value={qtPrefix}
            onChange={(e) => setQtPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={qtNext}
            onChange={(e) => setQtNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{qtPreview || '—'}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Return</span>
          <input
            value={srPrefix}
            onChange={(e) => setSrPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={srNext}
            onChange={(e) => setSrNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{srPreview || '—'}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Credit note</span>
          <input
            value={cnPrefix}
            onChange={(e) => setCnPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={cnNext}
            onChange={(e) => setCnNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{cnPreview || '—'}</span>
          <button type="button" onClick={saveInvoiceNumbering}>
            Save numbering
          </button>
        </div>
      </div>

      <div className="card" style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <strong>Customer groups</strong>
          {groups.map((g) => (
            <span key={g.id} className="muted">
              {g.name} (−{g.discount_percent}%)
            </span>
          ))}
          <input
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            placeholder="New group name"
          />
          <input
            value={newGroupDiscount}
            onChange={(e) => setNewGroupDiscount(e.target.value)}
            placeholder="Discount %"
            style={{ width: 100 }}
          />
          <button type="button" onClick={createGroup}>
            Add group
          </button>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">Customer</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code ? `${c.code} — ` : ''}
                {c.name}
                {c.profile_type === 'walk_in' ? ' (walk-in)' : ''}
                {c.status === 'inactive' ? ' [inactive]' : ''}
                {c.customer_group ? ` [${c.customer_group.name}]` : ''}
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
            value={customerCode}
            onChange={(e) => setCustomerCode(e.target.value)}
            placeholder="Code"
            style={{ width: 100 }}
          />
          <select
            value={customerProfileType}
            onChange={(e) => setCustomerProfileType(e.target.value)}
            title="Customer type"
          >
            <option value="registered">Registered</option>
            <option value="walk_in">Walk-in</option>
          </select>
          <select value={customerStatus} onChange={(e) => setCustomerStatus(e.target.value)} title="Status">
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <input
            value={customerEmail}
            onChange={(e) => setCustomerEmail(e.target.value)}
            placeholder="Customer email"
          />
          <input
            value={customerPhone}
            onChange={(e) => setCustomerPhone(e.target.value)}
            placeholder="Phone"
            style={{ width: 120 }}
          />
          <input
            value={customerAddress}
            onChange={(e) => setCustomerAddress(e.target.value)}
            placeholder="Address"
            style={{ minWidth: 160 }}
          />
          <input
            value={customerLat}
            onChange={(e) => setCustomerLat(e.target.value)}
            placeholder="Lat"
            style={{ width: 90 }}
            title="GPS latitude"
          />
          <input
            value={customerLng}
            onChange={(e) => setCustomerLng(e.target.value)}
            placeholder="Lng"
            style={{ width: 90 }}
            title="GPS longitude"
          />
          <select value={customerGroupId} onChange={(e) => setCustomerGroupId(e.target.value)}>
            <option value="">Group (optional)</option>
            {groups
              .filter((g) => g.is_active !== false)
              .map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name} (−{g.discount_percent}%)
                </option>
              ))}
          </select>
          <input value={creditLimit} onChange={(e) => setCreditLimit(e.target.value)} placeholder="Credit limit" />
          <input
            value={paymentTermsDays}
            onChange={(e) => setPaymentTermsDays(e.target.value)}
            placeholder="Net days"
            style={{ width: 90 }}
            title="Payment terms (days)"
          />
          <button onClick={createCustomer}>Add customer</button>
          <button type="button" onClick={assignCustomerGroup}>
            Assign group
          </button>
        </div>
        {customerId ? (
          <PartyContactsPanel
            kind="customer"
            partyId={customerId}
            partyLabel={customers.find((c) => c.id === customerId)?.name || 'Selected customer'}
          />
        ) : null}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
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
          <select value={unitId} onChange={(e) => setUnitId(e.target.value)}>
            <option value="">Unit (default)</option>
            {units.map((u) => (
              <option key={u.id} value={u.id}>
                {u.code}
              </option>
            ))}
          </select>
          <input value={qty} onChange={(e) => setQty(e.target.value)} placeholder="Qty" style={{ width: 80 }} />
          <input
            value={unitPrice}
            onChange={(e) => {
              setUseGroupPrice(false);
              setUnitPrice(e.target.value);
            }}
            placeholder="Price"
            style={{ width: 100 }}
          />
          <label style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <input
              type="checkbox"
              checked={useGroupPrice}
              onChange={(e) => setUseGroupPrice(e.target.checked)}
            />
            Group price
          </label>
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
                <td>{formatNumber(q.total_amount, fmt)}</td>
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
                <td>{formatNumber(o.total_amount, fmt)}</td>
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
                <td>{formatNumber(inv.total_amount, fmt)}</td>
                <td>{formatNumber(inv.paid_amount, fmt)}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(inv)}>View</button>
                  {inv.status === 'draft' && (
                    <>
                      <button onClick={() => postInvoice(inv)}>Post</button>
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
                <td>{formatNumber(r.total_amount, fmt)}</td>
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
          <h3>
            {selected.invoice_number || 'Selected'} — {selected.status}
          </h3>
          {selected.emailed_to && (
            <p className="muted" style={{ marginBottom: 8 }}>
              Last emailed to {selected.emailed_to}
              {selected.emailed_at ? ` · ${String(selected.emailed_at).slice(0, 19)}` : ''}
            </p>
          )}
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
              {(selected.items || []).map((it: any) => (
                <tr key={it.id}>
                  <td>
                    {it.product_id}
                    {it.is_reverse_charge ? ' · RC' : ''}
                  </td>
                  <td>{it.quantity}</td>
                  <td>{it.unit_price}</td>
                  <td>{it.tax_rate}</td>
                  <td>
                    {it.line_tax ?? 0}
                    {(it.tax_components || []).length
                      ? ` (${(it.tax_components || [])
                          .map((c: any) => `${c.name || c.code}:${c.amount}`)
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
              <div className="kpi">{selected.subtotal ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Tax</div>
              <div className="kpi">{selected.tax_amount ?? 0}</div>
            </div>
            <div className="card">
              <div className="muted">Total</div>
              <div className="kpi">{selected.total_amount ?? 0}</div>
            </div>
          </div>
          {(selected.tax_breakdown?.by_rate || []).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <h4 style={{ margin: '8px 0' }}>Tax breakdown</h4>
              <table className="table">
                <thead>
                  <tr>
                    <th>Rate</th>
                    <th>Taxable</th>
                    <th>Tax</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {selected.tax_breakdown.by_rate.map((r: any, idx: number) => (
                    <tr key={`${r.tax_rate}-${idx}`}>
                      <td>{r.tax_rate}%</td>
                      <td>{r.taxable}</td>
                      <td>{r.tax}</td>
                      <td>{r.is_reverse_charge ? 'Reverse charge' : 'Standard'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {selected.reverse_charge_tax > 0 && (
                <p className="muted">
                  Reverse-charge tax (memo): {selected.reverse_charge_tax}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
