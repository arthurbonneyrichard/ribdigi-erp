'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import { api } from '../../lib/api';
import { useTabQuery } from '../../lib/tabQuery';

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

type Tab = 'invoices' | 'quotations' | 'orders' | 'returns' | 'customers' | 'groups';
const SALES_TABS: Tab[] = ['invoices', 'quotations', 'orders', 'returns', 'customers', 'groups'];

export default function Page() {
  const [tab, setTab] = useTabQuery(SALES_TABS, 'invoices');
  const [invoices, setInvoices] = useState<any[]>([]);
  const [quotations, setQuotations] = useState<any[]>([]);
  const [orders, setOrders] = useState<any[]>([]);
  const [orderStatusFilter, setOrderStatusFilter] = useState('');
  const [quoteStatusFilter, setQuoteStatusFilter] = useState('');
  const [invoiceStatusFilter, setInvoiceStatusFilter] = useState('');
  const [returnStatusFilter, setReturnStatusFilter] = useState('');
  const [returns, setReturns] = useState<any[]>([]);
  const [customers, setCustomers] = useState<any[]>([]);
  const [customerGroups, setCustomerGroups] = useState<any[]>([]);
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
  const [customerType, setCustomerType] = useState('registered');
  const [customerEmail, setCustomerEmail] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerAddress, setCustomerAddress] = useState('');
  const [customerLatitude, setCustomerLatitude] = useState('');
  const [customerLongitude, setCustomerLongitude] = useState('');
  const [customerGroupId, setCustomerGroupId] = useState('');
  const [customerNotes, setCustomerNotes] = useState('');
  const [customerTerms, setCustomerTerms] = useState('0');
  const [creditLimit, setCreditLimit] = useState('0');
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [customerHistory, setCustomerHistory] = useState<any | null>(null);
  const [groupName, setGroupName] = useState('');
  const [groupDiscount, setGroupDiscount] = useState('0');
  const [selectedGroupId, setSelectedGroupId] = useState('');
  const [productId, setProductId] = useState('');
  const [variantId, setVariantId] = useState('');
  const [qty, setQty] = useState('1');
  const [unitPrice, setUnitPrice] = useState('0');
  const [taxRate, setTaxRate] = useState('');
  const [invoiceId, setInvoiceId] = useState('');
  const [returnReason, setReturnReason] = useState('other');
  const [restock, setRestock] = useState(true);
  const [payAmount, setPayAmount] = useState('');
  const [printTemplate, setPrintTemplate] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  // Stage 107 S1 / Stage 118 C1 — shareable ?active_only= for groups; ?status= for customers
  const [activeOnlyFilter, setActiveOnlyFilter] = useState(() => {
    if (typeof window === 'undefined') return false;
    const v = new URLSearchParams(window.location.search).get('active_only');
    return v === 'true' || v === '1';
  });
  const [customerStatusFilter, setCustomerStatusFilter] = useState(() => {
    if (typeof window === 'undefined') return '';
    const params = new URLSearchParams(window.location.search);
    const st = (params.get('customer_status') || '').trim().toLowerCase();
    if (st === 'active' || st === 'inactive') return st;
    const ao = params.get('active_only');
    if (ao === 'true' || ao === '1') return 'active';
    return '';
  });

  const activeCustomers = customers.filter((c) => (c.status || 'active') === 'active');

  function groupPrice(base: number, forCustomerId?: string) {
    const cid = forCustomerId || customerId;
    const cust = customers.find((c) => c.id === cid);
    const pct = Number(cust?.group_discount_percent || 0);
    if (!pct) return Number(base || 0);
    return Math.round(Number(base || 0) * (1 - pct / 100) * 10000) / 10000;
  }

  async function refresh(opts?: {
    invoiceStatus?: string;
    returnStatus?: string;
    quoteStatus?: string;
    orderStatus?: string;
    activeOnly?: boolean;
    customerStatus?: string;
  }) {
    const status = opts?.invoiceStatus !== undefined ? opts.invoiceStatus : invoiceStatusFilter;
    const retStatus = opts?.returnStatus !== undefined ? opts.returnStatus : returnStatusFilter;
    const quoteStatus = opts?.quoteStatus !== undefined ? opts.quoteStatus : quoteStatusFilter;
    const orderStatus = opts?.orderStatus !== undefined ? opts.orderStatus : orderStatusFilter;
    const activeOnly = opts?.activeOnly !== undefined ? opts.activeOnly : activeOnlyFilter;
    const customerStatus =
      opts?.customerStatus !== undefined ? opts.customerStatus : customerStatusFilter;
    const invPath = status
      ? `/sales/invoices?status=${encodeURIComponent(status)}`
      : '/sales/invoices';
    const retPath = retStatus
      ? `/sales/returns?status=${encodeURIComponent(retStatus)}`
      : '/sales/returns';
    const quotePath = quoteStatus
      ? `/sales/quotations?status=${encodeURIComponent(quoteStatus)}`
      : '/sales/quotations';
    const orderPath = orderStatus
      ? `/sales/orders?status=${encodeURIComponent(orderStatus)}`
      : '/sales/orders';
    // Stage 118 C1 — inactive-only via ?customer_status=inactive (API status=inactive)
    const custQs =
      customerStatus === 'inactive'
        ? '?status=inactive'
        : customerStatus === 'active'
          ? '?status=active'
          : '';
    const groupQs = activeOnly ? '?active_only=true' : '';
    const [invRes, custRes, prodRes, qRes, oRes, rRes, storeRes, groupRes] = await Promise.all([
      api(invPath),
      api(`/customers${custQs}`),
      api('/products'),
      api(quotePath),
      api(orderPath),
      api(retPath),
      api('/stores'),
      api(`/customers/groups${groupQs}`),
    ]);
    setInvoices(invRes.data || []);
    setCustomers(custRes.data || []);
    setProducts(prodRes.data || []);
    setQuotations(qRes.data || []);
    setOrders(oRes.data || []);
    setReturns(rRes.data || []);
    setStores(storeRes.data || []);
    setCustomerGroups(groupRes.data || []);
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

  // Stage 109 S1 / Stage 111 S1 / Stage 113 S1 / Stage 114 Q1 / Stage 115 O1 / Stage 116 S1 — Shell quote/order/invoice status leaves honor URL filters
  // Stage 109 S1 / Stage 111 S1 — Shell Draft/Posted Sales Returns honor return_status
  function setReturnStatus(next: string) {
    setReturnStatusFilter(next);
    writeQueryParam('return_status', next);
    refresh({ returnStatus: next }).catch((err) => setError(err.message));
  }

  function setQuoteStatus(next: string) {
    setQuoteStatusFilter(next);
    writeQueryParam('quote_status', next);
    refresh({ quoteStatus: next }).catch((err) => setError(err.message));
  }

  function setOrderStatus(next: string) {
    setOrderStatusFilter(next);
    writeQueryParam('order_status', next);
    refresh({ orderStatus: next }).catch((err) => setError(err.message));
  }

  function setActiveOnly(next: boolean) {
    setActiveOnlyFilter(next);
    writeQueryParam('active_only', next ? 'true' : '');
    refresh({ activeOnly: next }).catch((err) => setError(err.message));
  }

  function setCustomerListStatus(next: string) {
    setCustomerStatusFilter(next);
    writeQueryParam('customer_status', next);
    // Keep Active Customers Shell leaf (?active_only=true) in sync when selecting active
    if (next === 'active') writeQueryParam('active_only', 'true');
    else writeQueryParam('active_only', '');
    refresh({ customerStatus: next }).catch((err) => setError(err.message));
  }

  async function downloadCustomersExport() {
    // Stage 119 E1 — customers CSV export
    setError('');
    try {
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
      const res = await fetch(`${apiBase}/customers/export`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) throw new Error('Customer export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'customers_export.csv';
      a.click();
      URL.revokeObjectURL(url);
      setMessage('Customers CSV exported');
    } catch (err: any) {
      setError(err.message || 'Customer export failed');
    }
  }

  function resetCustomerForm() {
    setCustomerName('');
    setCustomerCode('');
    setCustomerType('registered');
    setCustomerEmail('');
    setCustomerPhone('');
    setCustomerAddress('');
    setCustomerLatitude('');
    setCustomerLongitude('');
    setCustomerGroupId('');
    setCustomerNotes('');
    setCustomerTerms('0');
    setCreditLimit('0');
  }

  function fillCustomerForm(c: any) {
    setSelectedCustomerId(c.id);
    setCustomerName(c.name || '');
    setCustomerCode(c.code || '');
    setCustomerType(c.party_type || 'registered');
    setCustomerEmail(c.email || '');
    setCustomerPhone(c.phone || '');
    setCustomerAddress(c.address || '');
    setCustomerLatitude(c.latitude != null ? String(c.latitude) : '');
    setCustomerLongitude(c.longitude != null ? String(c.longitude) : '');
    setCustomerGroupId(c.customer_group_id || '');
    setCustomerNotes(c.notes || '');
    setCustomerTerms(String(c.payment_terms_days ?? 0));
    setCreditLimit(String(c.credit_limit ?? 0));
    setCustomerHistory(null);
  }

  function customerPayload() {
    const lat = customerLatitude.trim() === '' ? null : Number(customerLatitude);
    const lon = customerLongitude.trim() === '' ? null : Number(customerLongitude);
    return {
      name: customerName,
      code: customerCode || null,
      party_type: customerType || 'registered',
      customer_group_id: customerGroupId || null,
      email: customerEmail || null,
      phone: customerPhone || null,
      address: customerAddress || null,
      latitude: lat,
      longitude: lon,
      notes: customerNotes || null,
      payment_terms_days: Number(customerTerms) || 0,
      credit_limit: Number(creditLimit) || 0,
    };
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get('status')?.trim() || '';
    const retRaw = params.get('return_status')?.trim() || '';
    const quoteRaw = params.get('quote_status')?.trim() || '';
    const orderRaw = params.get('order_status')?.trim() || '';
    const activeRaw = params.get('active_only');
    const activeOnly = activeRaw === 'true' || activeRaw === '1';
    const custStatusRaw = (params.get('customer_status') || '').trim().toLowerCase();
    const customerStatus =
      custStatusRaw === 'active' || custStatusRaw === 'inactive'
        ? custStatusRaw
        : activeOnly
          ? 'active'
          : '';
    const allowed = ['draft', 'posted', 'sent', 'paid', 'partial', 'unpaid', 'overdue', 'cancelled'];
    const retAllowed = ['draft', 'posted'];
    const quoteAllowed = ['draft', 'sent', 'accepted', 'rejected', 'expired'];
    const orderAllowed = ['draft', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled'];
    if (allowed.includes(raw)) setInvoiceStatusFilter(raw);
    if (retAllowed.includes(retRaw)) setReturnStatusFilter(retRaw);
    if (quoteAllowed.includes(quoteRaw)) setQuoteStatusFilter(quoteRaw);
    if (orderAllowed.includes(orderRaw)) setOrderStatusFilter(orderRaw);
    setActiveOnlyFilter(activeOnly);
    setCustomerStatusFilter(customerStatus);
    refresh({
      invoiceStatus: allowed.includes(raw) ? raw : '',
      returnStatus: retAllowed.includes(retRaw) ? retRaw : '',
      quoteStatus: quoteAllowed.includes(quoteRaw) ? quoteRaw : '',
      orderStatus: orderAllowed.includes(orderRaw) ? orderRaw : '',
      activeOnly,
      customerStatus,
    }).catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    setVariantId('');
    setVariants([]);
    if (!productId) return;
    const product = products.find((p) => p.id === productId);
    if (product) setUnitPrice(String(groupPrice(product.selling_price ?? 0)));
    api(`/products/${productId}/variants`)
      .then((r) => setVariants((r.data || []).filter((v: any) => v.is_active !== false)))
      .catch(() => setVariants([]));
  }, [productId, products]);

  useEffect(() => {
    if (!variantId) return;
    const variant = variants.find((v) => v.id === variantId);
    if (variant) setUnitPrice(String(groupPrice(variant.selling_price ?? 0)));
  }, [variantId, variants]);

  useEffect(() => {
    if (!productId) return;
    if (variantId) {
      const variant = variants.find((v) => v.id === variantId);
      if (variant) setUnitPrice(String(groupPrice(variant.selling_price ?? 0)));
      return;
    }
    const product = products.find((p) => p.id === productId);
    if (product) setUnitPrice(String(groupPrice(product.selling_price ?? 0)));
  }, [customerId, customers]);

  const selectedProduct = products.find((p) => p.id === productId);
  const availableQty =
    selectedProduct == null
      ? null
      : selectedProduct.available_qty != null
        ? Number(selectedProduct.available_qty)
        : Math.max(Number(selectedProduct.stock_qty || 0) - Number(selectedProduct.reserved_qty || 0), 0);

  const linePayload = {
    customer_id: customerId,
    store_id: storeId || null,
    delivery_date: deliveryDate ? `${deliveryDate}T00:00:00` : null,
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
    ...linePayload,
    currency: currency.trim() || null,
    exchange_rate: exchangeRate === '' ? null : Number(exchangeRate),
  };

  async function createCustomer() {
    setError('');
    try {
      const r = await api('/customers', {
        method: 'POST',
        body: JSON.stringify(customerPayload()),
      });
      setCustomerId(r.data.id);
      resetCustomerForm();
      setSelectedCustomerId(r.data.id);
      await refresh();
      setMessage('Customer created');
      setTab('customers');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveCustomer() {
    if (!selectedCustomerId) return;
    setError('');
    try {
      await api(`/customers/${selectedCustomerId}`, {
        method: 'PATCH',
        body: JSON.stringify(customerPayload()),
      });
      await refresh();
      setMessage('Customer updated');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveGroup() {
    setError('');
    try {
      const body = {
        name: groupName,
        discount_percent: Number(groupDiscount) || 0,
      };
      if (selectedGroupId) {
        await api(`/customers/groups/${selectedGroupId}`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        setMessage('Customer group updated');
      } else {
        await api('/customers/groups', { method: 'POST', body: JSON.stringify(body) });
        setMessage('Customer group created');
      }
      setGroupName('');
      setGroupDiscount('0');
      setSelectedGroupId('');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deactivateGroup(id: string) {
    setError('');
    try {
      await api(`/customers/groups/${id}`, { method: 'DELETE' });
      if (selectedGroupId === id) {
        setSelectedGroupId('');
        setGroupName('');
        setGroupDiscount('0');
      }
      await refresh();
      setMessage('Customer group deactivated');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function deactivateCustomer(id: string) {
    setError('');
    try {
      await api(`/customers/${id}`, { method: 'DELETE' });
      if (customerId === id) setCustomerId('');
      if (selectedCustomerId === id) {
        setSelectedCustomerId('');
        resetCustomerForm();
      }
      await refresh();
      setMessage('Customer deactivated');
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function loadCustomerHistory(id: string) {
    setError('');
    try {
      const r = await api(`/customers/${id}/history`);
      setCustomerHistory(r.data);
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
      if (err?.code === 'CREDIT_LIMIT_EXCEEDED' && path.includes('/post')) {
        const reason = window.prompt(
          `${err.message}\n\nEnter override reason (requires credit:approve):`,
        );
        if (reason && reason.trim().length >= 3) {
          return act(path, label, {
            credit_limit_override: true,
            credit_override_reason: reason.trim(),
          });
        }
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

  async function printInvoice(invId: string, template?: string, format: 'text' | 'pdf' | 'html' = 'html') {
    return printSalesDoc('invoices', invId, template, format);
  }

  async function printQuotation(quoteId: string, template?: string, format: 'text' | 'pdf' | 'html' = 'html') {
    return printSalesDoc('quotations', quoteId, template, format);
  }

  async function printCreditNote(returnId: string, template?: string, format: 'text' | 'pdf' | 'html' = 'html') {
    return printSalesDoc('returns', returnId, template, format);
  }

  async function printSalesDoc(
    kind: 'invoices' | 'quotations' | 'returns',
    docId: string,
    template?: string,
    format: 'text' | 'pdf' | 'html' = 'html',
  ) {
    setError('');
    try {
      const params = new URLSearchParams();
      if (template) params.set('template', template);
      params.set('format', format);
      const qs = `?${params.toString()}`;
      const path = `/sales/${kind}/${docId}/print${qs}`;
      if (format === 'text') {
        const r = await api(path);
        const text = r.data?.text || '';
        const win = window.open('', '_blank', 'noopener,noreferrer,width=720,height=800');
        if (win) {
          win.document.write(
            `<pre style="font:14px/1.4 monospace;padding:16px">${text.replace(/</g, '&lt;')}</pre>`
          );
          win.document.close();
          win.focus();
        }
        const label =
          kind === 'quotations' ? 'Quotation' : kind === 'returns' ? 'Credit note' : 'Invoice';
        setMessage(`${label} print (${r.data?.template || 'a4'}) ready`);
        return;
      }
      const token = localStorage.getItem('token');
      const tenant = localStorage.getItem('tenant');
      const res = await fetch(`${apiBase}${path}`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || body.message || 'Print failed');
      }
      if (format === 'html') {
        const html = await res.text();
        const win = window.open('', '_blank', 'noopener,noreferrer,width=820,height=900');
        if (!win) throw new Error('Pop-up blocked; allow pop-ups to print');
        win.document.write(html);
        win.document.close();
        win.focus();
        setMessage(
          kind === 'quotations'
            ? 'Quotation print view ready'
            : kind === 'returns'
              ? 'Credit note print view ready'
              : 'Branded invoice print view ready',
        );
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${
        kind === 'quotations' ? 'quotation' : kind === 'returns' ? 'credit-note' : 'invoice'
      }-${docId.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      setMessage(
        kind === 'quotations'
          ? 'Quotation PDF downloaded'
          : kind === 'returns'
            ? 'Credit note PDF downloaded'
            : 'Invoice PDF downloaded',
      );
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
            ['customers', 'Customers'],
            ['groups', 'Customer Groups'],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} disabled={tab === id}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'groups' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>{selectedGroupId ? 'Edit customer group' : 'New customer group'}</h3>
          <p className="muted">Group discount applies when catalog price is used (no manual unit price override).</p>
          <label className="muted" style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
            <input
              type="checkbox"
              checked={activeOnlyFilter}
              onChange={(e) => setActiveOnly(e.target.checked)}
            />
            Active groups only (shareable URL)
          </label>
          <div style={{ display: 'grid', gap: 8, maxWidth: 420 }}>
            <input value={groupName} onChange={(e) => setGroupName(e.target.value)} placeholder="Name *" />
            <input
              value={groupDiscount}
              onChange={(e) => setGroupDiscount(e.target.value)}
              placeholder="Discount %"
            />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button onClick={saveGroup} disabled={!groupName.trim()}>
                {selectedGroupId ? 'Save group' : 'Create group'}
              </button>
              {selectedGroupId && (
                <button
                  type="button"
                  onClick={() => {
                    setSelectedGroupId('');
                    setGroupName('');
                    setGroupDiscount('0');
                  }}
                >
                  New
                </button>
              )}
            </div>
          </div>
          <table className="table" style={{ marginTop: 16 }}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Discount %</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {customerGroups.map((g) => (
                <tr key={g.id}>
                  <td>{g.name}</td>
                  <td>{g.discount_percent}</td>
                  <td>{g.is_active ? 'active' : 'inactive'}</td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedGroupId(g.id);
                        setGroupName(g.name || '');
                        setGroupDiscount(String(g.discount_percent ?? 0));
                      }}
                    >
                      Open
                    </button>
                    {g.is_active && (
                      <button type="button" onClick={() => deactivateGroup(g.id)}>
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'customers' && (
        <div className="card" style={{ marginBottom: 16 }}>
          <h3>{selectedCustomerId ? 'Edit customer' : 'New customer'}</h3>
          <label className="muted" style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
            Customer list
            <select
              value={customerStatusFilter}
              onChange={(e) => setCustomerListStatus(e.target.value)}
              aria-label="Filter customers by status"
            >
              <option value="">All customers</option>
              <option value="active">Active only</option>
              <option value="inactive">Inactive only</option>
            </select>
            <button type="button" onClick={downloadCustomersExport}>
              Export customers CSV
            </button>
          </label>
          <div style={{ display: 'grid', gap: 8, maxWidth: 560 }}>
            <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} placeholder="Name *" />
            <input value={customerCode} onChange={(e) => setCustomerCode(e.target.value)} placeholder="Code" />
            <select value={customerType} onChange={(e) => setCustomerType(e.target.value)}>
              <option value="registered">Registered</option>
              <option value="walk-in">Walk-in</option>
            </select>
            <select value={customerGroupId} onChange={(e) => setCustomerGroupId(e.target.value)}>
              <option value="">No customer group</option>
              {customerGroups
                .filter((g) => g.is_active || g.id === customerGroupId)
                .map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name} ({g.discount_percent}% off)
                  </option>
                ))}
            </select>
            <input value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} placeholder="Email" />
            <input value={customerPhone} onChange={(e) => setCustomerPhone(e.target.value)} placeholder="Phone" />
            <textarea
              value={customerAddress}
              onChange={(e) => setCustomerAddress(e.target.value)}
              placeholder="Address"
              rows={2}
            />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <input
                value={customerLatitude}
                onChange={(e) => setCustomerLatitude(e.target.value)}
                placeholder="Latitude (GPS)"
              />
              <input
                value={customerLongitude}
                onChange={(e) => setCustomerLongitude(e.target.value)}
                placeholder="Longitude (GPS)"
              />
            </div>
            <textarea
              value={customerNotes}
              onChange={(e) => setCustomerNotes(e.target.value)}
              placeholder="Notes"
              rows={2}
            />
            <input
              value={customerTerms}
              onChange={(e) => setCustomerTerms(e.target.value)}
              placeholder="Payment terms (days)"
            />
            <input value={creditLimit} onChange={(e) => setCreditLimit(e.target.value)} placeholder="Credit limit" />
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {!selectedCustomerId ? (
                <button onClick={createCustomer} disabled={!customerName.trim()}>
                  Create customer
                </button>
              ) : (
                <>
                  <button onClick={saveCustomer} disabled={!customerName.trim()}>
                    Save
                  </button>
                  <button
                    onClick={() => {
                      setSelectedCustomerId('');
                      resetCustomerForm();
                      setCustomerHistory(null);
                    }}
                  >
                    New
                  </button>
                  <button onClick={() => loadCustomerHistory(selectedCustomerId)}>History</button>
                  <button onClick={() => deactivateCustomer(selectedCustomerId)}>Deactivate</button>
                </>
              )}
            </div>
          </div>
          {customerHistory && (
            <div style={{ marginTop: 16 }}>
              <h4>Sales history</h4>
              <p className="muted">
                {customerHistory.invoices?.length || 0} invoices · {customerHistory.quotations?.length || 0}{' '}
                quotations · {customerHistory.orders?.length || 0} orders · {customerHistory.returns?.length || 0}{' '}
                returns · {customerHistory.payments?.length || 0} payments
              </p>
              <ul>
                {(customerHistory.invoices || []).slice(0, 8).map((inv: any) => (
                  <li key={inv.id}>
                    {inv.invoice_number} — {inv.status} — {inv.total_amount}
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
                <th>Group</th>
                <th>Type</th>
                <th>Status</th>
                <th>Credit</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.code || '—'}</td>
                  <td>{c.customer_group_name || '—'}</td>
                  <td>{c.party_type || 'registered'}</td>
                  <td>{c.status || 'active'}</td>
                  <td>{c.credit_limit}</td>
                  <td>
                    <button type="button" onClick={() => fillCustomerForm(c)}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab !== 'customers' && tab !== 'groups' && (
      <div className="card" style={{ display: 'grid', gap: 8, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select value={customerId} onChange={(e) => setCustomerId(e.target.value)}>
            <option value="">Customer</option>
            {activeCustomers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.code ? ` (${c.code})` : ''}
                {c.party_type === 'walk-in' ? ' · walk-in' : ''}
              </option>
            ))}
          </select>
          <select value={storeId} onChange={(e) => setStoreId(e.target.value)}>
            <option value="">Store (optional)</option>
            {stores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
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
          <button type="button" onClick={() => setTab('customers')}>
            Manage customers
          </button>
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
        {selectedProduct && (
          <p className="muted">
            On hand {selectedProduct.stock_qty} · Reserved {selectedProduct.reserved_qty ?? 0} · Available{' '}
            {availableQty}
          </p>
        )}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input
            type="date"
            value={deliveryDate}
            onChange={(e) => setDeliveryDate(e.target.value)}
            title="Expected delivery date"
          />
          <input
            value={deliveryAddress}
            onChange={(e) => setDeliveryAddress(e.target.value)}
            placeholder="Delivery address (orders)"
            style={{ minWidth: 240, flex: 1 }}
          />
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
              .filter((i) => ['posted', 'sent', 'partial', 'paid', 'overdue'].includes(i.status))
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
      )}

      {tab === 'quotations' && (
        <>
          <p className="muted" style={{ marginBottom: 12 }}>
            → Order creates a draft sales order; Confirm is required to reserve stock. → Invoice creates a
            draft sales invoice; Post is required before AR recognition.
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
            <strong>Quotation status</strong>
            <select
              value={quoteStatusFilter}
              onChange={(e) => setQuoteStatus(e.target.value)}
              aria-label="Filter quotations by status"
            >
              <option value="">All statuses</option>
              {['draft', 'sent', 'accepted', 'rejected', 'expired'].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
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
                    <button onClick={() => printQuotation(q.id, printTemplate || undefined, 'html')}>
                      Print
                    </button>
                    <button onClick={() => printQuotation(q.id, printTemplate || undefined, 'pdf')}>
                      PDF
                    </button>
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
                        <button
                          title="Creates a draft order — Confirm required to reserve stock"
                          onClick={() =>
                            act(
                              `/sales/quotations/${q.id}/convert-order`,
                              'Converted to draft sales order — Confirm required to reserve stock'
                            )
                          }
                        >
                          → Order
                        </button>
                        <button
                          title="Creates a draft invoice — Post required before AR"
                          onClick={() =>
                            act(
                              `/sales/quotations/${q.id}/convert-invoice`,
                              'Converted to draft invoice — Post required before AR'
                            )
                          }
                        >
                          → Invoice
                        </button>
                      </>
                    )}
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
          <strong>Delivery status</strong>
          <select
            value={orderStatusFilter}
            onChange={(e) => setOrderStatus(e.target.value)}
            aria-label="Filter orders by delivery status"
          >
            <option value="">All statuses</option>
            {['draft', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled'].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <span className="muted">Server-side filter via order_status (Stage 99 T1)</span>
        </div>
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Status</th>
              <th>Delivery</th>
              <th>Store</th>
              <th>Reserved</th>
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
                  {o.delivery_date ? String(o.delivery_date).slice(0, 10) : '—'}
                  {o.delivery_address ? (
                    <div className="muted" style={{ maxWidth: 180 }}>
                      {o.delivery_address}
                    </div>
                  ) : null}
                </td>
                <td>
                  {stores.find((s) => s.id === o.store_id)?.name ||
                    (o.store_id ? o.store_id.slice(0, 8) : '—')}
                </td>
                <td>{o.reserved_qty_total ?? 0}</td>
                <td>{o.total_amount}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(o)}>View</button>
                  {o.status === 'draft' && (
                    <button onClick={() => act(`/sales/orders/${o.id}/confirm`, 'Confirmed')}>
                      Confirm (reserve)
                    </button>
                  )}
                  {o.status === 'confirmed' && (
                    <button onClick={() => act(`/sales/orders/${o.id}/process`, 'Processing')}>Process</button>
                  )}
                  {o.status === 'processing' && (
                    <button onClick={() => act(`/sales/orders/${o.id}/ship`, 'Shipped')}>Ship</button>
                  )}
                  {o.status === 'shipped' && (
                    <button onClick={() => act(`/sales/orders/${o.id}/deliver`, 'Delivered')}>Deliver</button>
                  )}
                  {['draft', 'confirmed', 'processing', 'shipped', 'delivered'].includes(o.status) && (
                    <button onClick={() => act(`/sales/orders/${o.id}/convert-invoice`, 'Invoice')}>→ Invoice</button>
                  )}
                  {['draft', 'confirmed', 'processing'].includes(o.status) && (
                    <button onClick={() => act(`/sales/orders/${o.id}/cancel`, 'Cancelled')}>Cancel</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </>
      )}

      {tab === 'invoices' && (
        <>
          <div className="card" style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <label className="muted">Status</label>
            <select
              value={invoiceStatusFilter}
              onChange={(e) => setInvoiceStatus(e.target.value)}
              aria-label="Filter invoices by status"
            >
              <option value="">All statuses</option>
              {['draft', 'posted', 'sent', 'unpaid', 'partial', 'paid', 'overdue', 'cancelled'].map((s) => (
                <option key={s} value={s}>
                  {s === 'unpaid' ? 'unpaid (posted/sent)' : s}
                </option>
              ))}
            </select>
            <label className="muted">Print template</label>
            <select value={printTemplate} onChange={(e) => setPrintTemplate(e.target.value)}>
              <option value="">Tenant default</option>
              <option value="a4">A4</option>
              <option value="thermal_80">Thermal 80mm</option>
              <option value="thermal_58">Thermal 58mm</option>
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Status</th>
                <th>Store</th>
                <th>Total</th>
                <th>Paid</th>
                <th>Emailed</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td>{inv.invoice_number}</td>
                  <td>
                    {inv.status}
                    {inv.is_overdue && inv.status !== 'overdue' ? ' (overdue)' : ''}
                  </td>
                  <td>
                    {stores.find((s) => s.id === inv.store_id)?.name ||
                      (inv.store_id ? inv.store_id.slice(0, 8) : '—')}
                  </td>
                  <td>{inv.total_amount}</td>
                  <td>{inv.paid_amount}</td>
                  <td className="muted">
                    {inv.emailed_to ? String(inv.emailed_at || '').slice(0, 10) : '—'}
                  </td>
                  <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    <button onClick={() => setSelected(inv)}>View</button>
                    {inv.status !== 'draft' && inv.status !== 'cancelled' && (
                      <>
                        <button onClick={() => printInvoice(inv.id, printTemplate || undefined, 'html')}>
                          Print
                        </button>
                        <button onClick={() => printInvoice(inv.id, printTemplate || undefined, 'pdf')}>
                          PDF
                        </button>
                      </>
                    )}
                    {inv.status === 'draft' && (
                      <>
                        <button onClick={() => act(`/sales/invoices/${inv.id}/post`, 'Posted')}>Post</button>
                        <button onClick={() => act(`/sales/invoices/${inv.id}/cancel`, 'Cancelled')}>Cancel</button>
                      </>
                    )}
                    {['posted', 'sent', 'partial', 'overdue', 'paid'].includes(inv.status) && (
                      <button
                        onClick={() =>
                          act(
                            `/sales/invoices/${inv.id}/send`,
                            inv.emailed_at ? 'Invoice re-emailed' : 'Invoice emailed'
                          )
                        }
                      >
                        {inv.emailed_at ? 'Resend' : 'Email'}
                      </button>
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
        </>
      )}

      {tab === 'returns' && (
        <>
          <p className="muted" style={{ marginBottom: 12 }}>
            Sales returns start as draft; Post is required before the credit note is recognized.
          </p>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12, flexWrap: 'wrap' }}>
            <strong>Return status</strong>
            <select
              value={returnStatusFilter}
              onChange={(e) => setReturnStatus(e.target.value)}
              aria-label="Filter sales returns by status"
            >
              <option value="">All statuses</option>
              <option value="draft">draft</option>
              <option value="posted">posted</option>
            </select>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Credit note</th>
                <th>Status</th>
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
                  <td>{r.reason}</td>
                  <td>{r.total_amount}</td>
                  <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    <button onClick={() => setSelected(r)}>View</button>
                    {r.status === 'draft' && (
                      <button
                        title="Post required before credit note recognition"
                        onClick={() =>
                          act(`/sales/returns/${r.id}/post`, 'Posted — credit note recognized')
                        }
                      >
                        Post
                      </button>
                    )}
                    {r.status === 'posted' && (
                      <>
                        <button onClick={() => printCreditNote(r.id, printTemplate || undefined, 'html')}>
                          Print
                        </button>
                        <button onClick={() => printCreditNote(r.id, printTemplate || undefined, 'pdf')}>
                          PDF
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {selected && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>Selected</h3>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12 }}>{JSON.stringify(selected, null, 2)}</pre>
        </div>
      )}
    </Shell>
  );
}
