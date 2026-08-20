'use client';

import { useEffect, useState } from 'react';
import Shell from '../../components/Shell';
import PartyContactsPanel from '../../components/PartyContactsPanel';
import { api } from '../../lib/api';
import { formatNumber, type FormatPrefs } from '../../lib/format';
import { useStoreContext } from '../../lib/storeContext';

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
  const [invoiceManageFilter, setInvoiceManageFilter] = useState<
    'all' | 'draft' | 'posted' | 'sent' | 'partial' | 'paid' | 'overdue' | 'cancelled'
  >('all');
  const [quotations, setQuotations] = useState<any[]>([]);
  const [quotationManageFilter, setQuotationManageFilter] = useState<
    'all' | 'draft' | 'sent' | 'accepted' | 'rejected' | 'expired' | 'converted'
  >('all');
  const [orders, setOrders] = useState<any[]>([]);
  const [orderManageFilter, setOrderManageFilter] = useState<
    | 'all'
    | 'draft'
    | 'confirmed'
    | 'processing'
    | 'shipped'
    | 'delivered'
    | 'invoiced'
    | 'cancelled'
  >('all');
  const [returns, setReturns] = useState<any[]>([]);
  const [returnManageFilter, setReturnManageFilter] = useState<
    'all' | 'draft' | 'posted' | 'cancelled'
  >('all');
  const [customers, setCustomers] = useState<any[]>([]);
  const [groups, setGroups] = useState<any[]>([]);
  const [groupManageFilter, setGroupManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [products, setProducts] = useState<any[]>([]);
  const [stores, setStores] = useState<any[]>([]);
  const [variants, setVariants] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [customerId, setCustomerId] = useState('');
  const [customerManageFilter, setCustomerManageFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [storeId, setStoreId] = useState('');
  const { storeId: ctxStoreId, setStoreId: setCtxStoreId } = useStoreContext();
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
  const [creditOverrideReason, setCreditOverrideReason] = useState('');
  const [quoteRejectReason, setQuoteRejectReason] = useState('');
  const [soCancelReason, setSoCancelReason] = useState('');
  const [siCancelReason, setSiCancelReason] = useState('');
  const [srCancelReason, setSrCancelReason] = useState('');
  const [docEmailTo, setDocEmailTo] = useState('');
  const [paymentTermsDays, setPaymentTermsDays] = useState('30');
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDiscount, setNewGroupDiscount] = useState('0');
  const [groupDiscountDrafts, setGroupDiscountDrafts] = useState<Record<string, string>>({});
  const [useGroupPrice, setUseGroupPrice] = useState(true);
  const [productId, setProductId] = useState('');
  const [variantId, setVariantId] = useState('');
  const [unitId, setUnitId] = useState('');
  const [units, setUnits] = useState<any[]>([]);
  const [qty, setQty] = useState('1');
  const [unitPrice, setUnitPrice] = useState('0');
  const [taxRate, setTaxRate] = useState('');
  const [lineDiscount, setLineDiscount] = useState('');
  const [headerDiscount, setHeaderDiscount] = useState('');
  const [invoiceReverseCharge, setInvoiceReverseCharge] = useState(false);
  const [invoiceId, setInvoiceId] = useState('');
  const [returnReason, setReturnReason] = useState('');
  const [returnCondition, setReturnCondition] = useState('');
  const [returnNotes, setReturnNotes] = useState('');
  const [docNotes, setDocNotes] = useState('');
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
  const [soPrefix, setSoPrefix] = useState('SO');
  const [soNext, setSoNext] = useState('1');
  const [soPreview, setSoPreview] = useState('');
  const [srPrefix, setSrPrefix] = useState('SR');
  const [srNext, setSrNext] = useState('1');
  const [srPreview, setSrPreview] = useState('');
  const [cnPrefix, setCnPrefix] = useState('CN');
  const [cnNext, setCnNext] = useState('1');
  const [cnPreview, setCnPreview] = useState('');
  const [rcpPrefix, setRcpPrefix] = useState('RCP');
  const [rcpNext, setRcpNext] = useState('1');
  const [rcpPreview, setRcpPreview] = useState('');
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
        api('/stores').catch(() => ({ data: [] })),
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
    if (ctxStoreId && (storeRes.data || []).some((s: any) => s.id === ctxStoreId)) {
      setStoreId(ctxStoreId);
    }
    setGroups(groupRes.data || []);
    setGroupDiscountDrafts(
      Object.fromEntries((groupRes.data || []).map((g: any) => [g.id, String(g.discount_percent ?? 0)]))
    );
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
    const so = settingsRes.data?.sales_order_numbering;
    if (so) {
      setSoPrefix(so.prefix || 'SO');
      setSoNext(String(so.next_number ?? 1));
      setSoPreview(so.preview || '');
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
    const rcp = settingsRes.data?.payment_receipt_numbering;
    if (rcp) {
      setRcpPrefix(rcp.prefix || 'RCP');
      setRcpNext(String(rcp.next_number ?? 1));
      setRcpPreview(rcp.preview || '');
    }
  }

  useEffect(() => {
    refresh().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (ctxStoreId) setStoreId(ctxStoreId);
  }, [ctxStoreId]);

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

  const lineDisc = Math.max(0, Number(lineDiscount) || 0);
  const hdrDisc = Math.max(0, Number(headerDiscount) || 0);
  const lineItems = [
    {
      product_id: productId,
      variant_id: variantId || null,
      unit_id: unitId || null,
      quantity: Number(qty),
      ...(useGroupPrice ? {} : { unit_price: Number(unitPrice) }),
      tax_rate: taxRate === '' ? null : Number(taxRate),
      discount: lineDisc,
    },
  ];

  const linePayload = {
    customer_id: customerId,
    store_id: storeId || null,
    delivery_date: deliveryDate.trim() || null,
    // null when blank so Create order does not 422 (AddressValue).
    delivery_address: deliveryAddress.trim() || null,
    discount_amount: hdrDisc,
    notes: docNotes.trim() || null,
    items: lineItems,
  };

  const invoicePayload = {
    customer_id: customerId,
    store_id: storeId || null,
    items: lineItems,
    discount_amount: hdrDisc,
    notes: docNotes.trim() || null,
    currency: currency.trim() || null,
    exchange_rate: exchangeRate === '' ? null : Number(exchangeRate),
    is_reverse_charge: invoiceReverseCharge,
  };

  async function createCustomer() {
    setError('');
    try {
      const r = await api('/customers', {
        method: 'POST',
        body: JSON.stringify({
          name: customerName.trim(),
          code: customerCode.trim() || null,
          profile_type: customerProfileType || 'registered',
          status: customerStatus || 'active',
          email: customerEmail || null,
          phone: customerPhone.trim() || null,
          // null when blank so Create does not 422 (AddressValue).
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

  async function setCustomerActive(isActive: boolean) {
    if (!customerId) {
      setError('Select a customer first');
      return;
    }
    setError('');
    try {
      const r = await api(`/customers/${customerId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: isActive ? 'active' : 'inactive' }),
      });
      await refresh();
      setMessage(
        isActive
          ? `Customer ${r.data?.name || ''} activated`
          : `Customer ${r.data?.name || ''} deactivated`,
      );
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createGroup() {
    const name = newGroupName.trim();
    if (!name) {
      setError('Customer group name is required.');
      return;
    }
    setError('');
    try {
      await api('/customers/groups', {
        method: 'POST',
        body: JSON.stringify({
          name,
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

  async function setGroupActive(group: { id: string; name: string }, is_active: boolean) {
    setError('');
    try {
      await api(`/customers/groups/${group.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active }),
      });
      await refresh();
      setMessage(is_active ? `Group ${group.name} activated` : `Group ${group.name} deactivated`);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function saveGroupDiscount(group: { id: string; name: string }) {
    setError('');
    try {
      const pct = Number(groupDiscountDrafts[group.id] ?? 0);
      await api(`/customers/groups/${group.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ discount_percent: pct }),
      });
      await refresh();
      setMessage(`Group ${group.name} discount updated`);
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
      setLineDiscount('');
      setHeaderDiscount('');
      setDocNotes('');
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
          sales_order_numbering: {
            prefix: soPrefix.trim(),
            next_number: Math.max(1, Number(soNext) || 1),
          },
          sales_return_numbering: {
            prefix: srPrefix.trim(),
            next_number: Math.max(1, Number(srNext) || 1),
          },
          credit_note_numbering: {
            prefix: cnPrefix.trim(),
            next_number: Math.max(1, Number(cnNext) || 1),
          },
          payment_receipt_numbering: {
            prefix: rcpPrefix.trim(),
            next_number: Math.max(1, Number(rcpNext) || 1),
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
      const so = r.data?.sales_order_numbering;
      if (so) {
        setSoPrefix(so.prefix);
        setSoNext(String(so.next_number));
        setSoPreview(so.preview);
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
      const rcp = r.data?.payment_receipt_numbering;
      if (rcp) {
        setRcpPrefix(rcp.prefix);
        setRcpNext(String(rcp.next_number));
        setRcpPreview(rcp.preview);
      }
      setMessage(
        `Numbering saved — INV ${numbering?.preview || ''} / QT ${qt?.preview || ''} / SO ${so?.preview || ''} / SR ${sr?.preview || ''} / CN ${cn?.preview || ''} / RCP ${rcp?.preview || ''}`.trim(),
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
      setLineDiscount('');
      setHeaderDiscount('');
      setDocNotes('');
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
      setLineDiscount('');
      setHeaderDiscount('');
      setDocNotes('');
      setTab('orders');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function createReturn() {
    setError('');
    setMessage('');
    if (!returnReason.trim()) {
      setError('Select a return reason');
      return;
    }
    if (!returnCondition.trim()) {
      setError('Select a return condition');
      return;
    }
    try {
      const r = await api('/sales/returns', {
        method: 'POST',
        body: JSON.stringify({
          sales_invoice_id: invoiceId,
          reason: returnReason,
          restock,
          notes: returnNotes.trim() || null,
          items: [
            {
              product_id: productId,
              variant_id: variantId || null,
              quantity: Number(qty),
              condition: returnCondition,
            },
          ],
        }),
      });
      setMessage(`Return ${r.data.return_number} drafted`);
      setSelected(r.data);
      setReturnReason('');
      setReturnCondition('');
      setReturnNotes('');
      setTab('returns');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function act(path: string, label: string, body: Record<string, unknown> = {}) {
    setError('');
    setMessage('');
    if (path.includes('/quotations/') && path.endsWith('/reject')) {
      const reason = quoteRejectReason.trim();
      if (!reason) {
        setError('Enter a reject reason before rejecting a quotation');
        return;
      }
      body = { ...body, reason };
    }
    if (path.includes('/orders/') && path.endsWith('/cancel')) {
      const reason = soCancelReason.trim();
      if (!reason) {
        setError('Enter a cancel reason before cancelling a sales order');
        return;
      }
      body = { ...body, reason };
    }
    if (path.includes('/invoices/') && path.endsWith('/cancel')) {
      const reason = siCancelReason.trim();
      if (!reason) {
        setError('Enter a cancel reason before cancelling a sales invoice');
        return;
      }
      body = { ...body, reason };
    }
    if (path.includes('/returns/') && path.endsWith('/cancel')) {
      const reason = srCancelReason.trim();
      if (!reason) {
        setError('Enter a cancel reason before cancelling a sales return');
        return;
      }
      body = { ...body, reason };
    }
    try {
      let requestPath = path;
      if (
        (path.includes('/quotations/') || path.includes('/invoices/')) &&
        path.endsWith('/send') &&
        docEmailTo.trim()
      ) {
        requestPath = `${path}?to=${encodeURIComponent(docEmailTo.trim())}`;
      }
      const r = await api(requestPath, { method: 'POST', body: JSON.stringify(body) });
      if (path.includes('/quotations/') && path.endsWith('/reject')) {
        setQuoteRejectReason('');
      }
      if (path.includes('/orders/') && path.endsWith('/cancel')) {
        setSoCancelReason('');
      }
      if (path.includes('/invoices/') && path.endsWith('/cancel')) {
        setSiCancelReason('');
      }
      if (path.includes('/returns/') && path.endsWith('/cancel')) {
        setSrCancelReason('');
      }
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
        const reason = creditOverrideReason.trim();
        if (!reason) {
          setError('Enter a credit override reason before posting over the limit');
          return;
        }
        try {
          const r = await api(`/sales/invoices/${inv.id}/post`, {
            method: 'POST',
            body: JSON.stringify({
              override_credit_limit: true,
              override_reason: reason,
            }),
          });
          setCreditOverrideReason('');
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

  const managedGroups = groups.filter((g) => {
    if (groupManageFilter === 'all') return true;
    const active = g.is_active !== false;
    return groupManageFilter === 'inactive' ? !active : active;
  });
  const managedReturns = returns.filter((r) => {
    if (returnManageFilter === 'all') return true;
    return (r.status || 'draft') === returnManageFilter;
  });
  const managedInvoices = invoices.filter((inv) => {
    if (invoiceManageFilter === 'all') return true;
    return (inv.status || 'draft') === invoiceManageFilter;
  });
  const managedQuotations = quotations.filter((q) => {
    if (quotationManageFilter === 'all') return true;
    return (q.status || 'draft') === quotationManageFilter;
  });
  const managedOrders = orders.filter((o) => {
    if (orderManageFilter === 'all') return true;
    return (o.status || 'draft') === orderManageFilter;
  });

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
          <span className="muted">Order</span>
          <input
            value={soPrefix}
            onChange={(e) => setSoPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={soNext}
            onChange={(e) => setSoNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{soPreview || '—'}</span>
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
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Receipt</span>
          <input
            value={rcpPrefix}
            onChange={(e) => setRcpPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
          />
          <input
            value={rcpNext}
            onChange={(e) => setRcpNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
          />
          <span className="muted">{rcpPreview || '—'}</span>
          <button type="button" onClick={saveInvoiceNumbering}>
            Save numbering
          </button>
        </div>
      </div>

      <div className="erp-split">
        <div className="card">
          <h3>Customer</h3>
          <div className="erp-stack" style={{ marginBottom: 0 }}>
        <div style={{ display: 'grid', gap: 8 }}>
          <strong>Customer groups</strong>
          <p className="muted" style={{ margin: 0 }}>
            Soft-deactivate hides a group from assign/create pickers; existing customers keep the link
            but pricing ignores inactive groups until reassigned or reactivated.
          </p>
          <select
            value={groupManageFilter}
            onChange={(e) => setGroupManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
            title="Filter manage customer group list by status"
            aria-label="Customer group status filter"
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'grid', gap: 6 }}>
            {managedGroups.map((g) => (
              <li
                key={g.id}
                style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}
              >
                <span>
                  {g.code} — {g.name}
                  {g.is_active === false ? ' [inactive]' : ''}
                </span>
                <input
                  value={groupDiscountDrafts[g.id] ?? String(g.discount_percent ?? 0)}
                  onChange={(e) =>
                    setGroupDiscountDrafts((prev) => ({ ...prev, [g.id]: e.target.value }))
                  }
                  placeholder="Discount %"
                  style={{ width: 90 }}
                  title="Discount percent"
                  aria-label={`${g.name} discount percent`}
                />
                <button type="button" onClick={() => saveGroupDiscount(g)}>
                  Save discount
                </button>
                <button
                  type="button"
                  className={g.is_active === false ? 'btn-ok' : 'btn-danger'}
                  onClick={() => setGroupActive(g, g.is_active === false)}
                >
                  {g.is_active === false ? 'Activate' : 'Deactivate'}
                </button>
              </li>
            ))}
          </ul>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <input
              aria-label="Customer group name"
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
            <button
              type="button"
              aria-label="Add group"
              onClick={createGroup}
              disabled={!newGroupName.trim()}
            >
              Add group
            </button>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select
            value={customerManageFilter}
            onChange={(e) => {
              const next = e.target.value as 'all' | 'active' | 'inactive';
              setCustomerManageFilter(next);
              if (customerId) {
                const row = customers.find((c) => c.id === customerId);
                const st = (row?.status || 'active') as string;
                if (next === 'active' && st === 'inactive') setCustomerId('');
                if (next === 'inactive' && st !== 'inactive') setCustomerId('');
              }
            }}
            title="Filter manage customer list by status"
            aria-label="Customer status filter"
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
          <select
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            title="Manage customer"
            aria-label="Manage customer"
          >
            <option value="">Manage customer…</option>
            {customers
              .filter((c) => {
                if (customerManageFilter === 'all') return true;
                const st = c.status || 'active';
                return customerManageFilter === 'inactive' ? st === 'inactive' : st !== 'inactive';
              })
              .map((c) => (
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
          {customerId ? (
            <button
              type="button"
              className={
                (customers.find((c) => c.id === customerId)?.status || 'active') === 'inactive'
                  ? 'btn-ok'
                  : 'btn-danger'
              }
              onClick={() =>
                setCustomerActive(
                  (customers.find((c) => c.id === customerId)?.status || 'active') === 'inactive',
                )
              }
            >
              {(customers.find((c) => c.id === customerId)?.status || 'active') === 'inactive'
                ? 'Activate'
                : 'Deactivate'}
            </button>
          ) : null}
          <select
            value={
              customerId &&
              (customers.find((c) => c.id === customerId)?.status || 'active') !== 'inactive'
                ? customerId
                : ''
            }
            onChange={(e) => setCustomerId(e.target.value)}
            title="Customer for new sales"
            aria-label="Sale customer"
          >
            <option value="">Sale customer</option>
            {customers
              .filter((c) => c.status !== 'inactive')
              .map((c) => (
              <option key={c.id} value={c.id}>
                {c.code ? `${c.code} — ` : ''}
                {c.name}
                {c.profile_type === 'walk_in' ? ' (walk-in)' : ''}
                {c.customer_group ? ` [${c.customer_group.name}]` : ''}
                {c.email ? ` (${c.email})` : ''}
              </option>
            ))}
          </select>
          <select
            value={storeId}
            onChange={(e) => {
              setStoreId(e.target.value);
              setCtxStoreId(e.target.value);
            }}
          >
            <option value="">Store (required to confirm orders)</option>
            {stores
              .filter((s) => s.is_active !== false)
              .map((s) => (
              <option key={s.id} value={s.id}>
                {s.code} — {s.name}
              </option>
            ))}
          </select>
          <input
            aria-label="SO delivery date"
            type="text"
            placeholder="YYYY-MM-DD"
            title="Delivery date (optional YYYY-MM-DD)"
            value={deliveryDate}
            onChange={(e) => setDeliveryDate(e.target.value)}
          />
          <input
            value={deliveryAddress}
            onChange={(e) => setDeliveryAddress(e.target.value)}
            placeholder="Delivery address"
            aria-label="SO delivery address"
            style={{ minWidth: 180 }}
          />
          <input
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            placeholder="Currency (blank=base)"
            aria-label="Sales invoice currency"
            pattern="[A-Z]{3}"
            maxLength={3}
            title="ISO-4217 currency (blank = company base)"
            style={{ width: 140 }}
          />
          <input
            value={exchangeRate}
            onChange={(e) => setExchangeRate(e.target.value)}
            placeholder="FX rate (optional)"
            style={{ width: 120 }}
          />
          <input
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
            placeholder="New customer"
            aria-label="Customer name"
            title="Customer name (1–180 chars; letters/digits required)"
          />
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
            placeholder="Phone (E.164 e.g. +233...)"
            aria-label="Customer phone"
            style={{ width: 160 }}
          />
          <input
            value={customerAddress}
            onChange={(e) => setCustomerAddress(e.target.value)}
            placeholder="Address"
            aria-label="Customer address"
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
          <button type="button" onClick={createCustomer} aria-label="Add customer">
            Add customer
          </button>
          <button type="button" onClick={assignCustomerGroup}>
            Assign group
          </button>
        </div>
        {customerId &&
          (customers.find((c) => c.id === customerId)?.status || 'active') === 'inactive' && (
            <p className="muted" style={{ margin: 0 }}>
              Inactive — hidden from new sale / quote / order / POS pickers; existing documents can still
              settle.
            </p>
          )}
        {customerId ? (
          <PartyContactsPanel
            kind="customer"
            partyId={customerId}
            partyLabel={customers.find((c) => c.id === customerId)?.name || 'Selected customer'}
          />
        ) : null}
          </div>
        </div>
        <div className="card">
          <h3>Create sale</h3>
          <div className="erp-stack" style={{ marginBottom: 0 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            aria-label="Sales product"
          >
            <option value="">Product</option>
            {products
              .filter((p) => p.is_active !== false)
              .map((p) => (
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
          <input
            value={lineDiscount}
            onChange={(e) => setLineDiscount(e.target.value)}
            placeholder="Line discount"
            aria-label="Line discount"
            style={{ width: 110 }}
            title="Line discount amount (tax before discount)"
          />
          <input
            value={headerDiscount}
            onChange={(e) => setHeaderDiscount(e.target.value)}
            placeholder="Header discount"
            aria-label="Header discount"
            style={{ width: 120 }}
            title="Document-level discount amount"
          />
          <input
            value={docNotes}
            onChange={(e) => setDocNotes(e.target.value)}
            placeholder="Notes (optional)"
            aria-label="Sales document notes"
            title="Optional notes (1–500 chars; letters/digits required)"
            style={{ minWidth: 180 }}
          />
        </div>
        <p className="muted" style={{ margin: '4px 0 0', fontSize: 12 }}>
          Line discount is stored on the line (tax before discount). Header discount reduces the
          document total — same model as Purchasing invoices.
        </p>
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
          <input
            type="checkbox"
            checked={invoiceReverseCharge}
            onChange={(e) => setInvoiceReverseCharge(e.target.checked)}
          />
          Reverse charge (tax memo only — not charged to customer)
        </label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={createQuotation} aria-label="Create quotation">
            Create quotation
          </button>
          <button onClick={createOrder} aria-label="Create order">
            Create order
          </button>
          <button onClick={createInvoice} aria-label="Create invoice">
            Create invoice
          </button>
        </div>
          </div>
        </div>
      </div>

      {tab === 'quotations' && (
        <>
          <div className="card" style={{ marginBottom: 12 }}>
            <label>
              Reject reason{' '}
              <input
                value={quoteRejectReason}
                onChange={(e) => setQuoteRejectReason(e.target.value)}
                placeholder="Required before Reject"
                aria-label="Quotation reject reason"
                title="Required reason for Reject (1–500 chars; letters/digits required)"
                style={{ minWidth: 280 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Used by Reject on draft/sent quotations (stored as <code>rejection_reason</code>).
            </p>
            <label style={{ display: 'block', marginTop: 8 }}>
              Email override{' '}
              <input
                type="email"
                value={docEmailTo}
                onChange={(e) => setDocEmailTo(e.target.value)}
                placeholder="Optional to= (omit → customer email)"
                aria-label="Document email override to"
                style={{ minWidth: 280 }}
              />
            </label>
          </div>
        <select
          value={quotationManageFilter}
          onChange={(e) =>
            setQuotationManageFilter(
              e.target.value as
                | 'all'
                | 'draft'
                | 'sent'
                | 'accepted'
                | 'rejected'
                | 'expired'
                | 'converted'
            )
          }
          title="Filter quotation list by status"
          aria-label="Quotation status filter"
          style={{ marginBottom: 12 }}
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft only</option>
          <option value="sent">Sent only</option>
          <option value="accepted">Accepted only</option>
          <option value="rejected">Rejected only</option>
          <option value="expired">Expired only</option>
          <option value="converted">Converted only</option>
        </select>
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Status</th>
              <th>Total</th>
              <th>Valid</th>
              <th>Reject reason</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedQuotations.map((q) => (
              <tr key={q.id}>
                <td>{q.quotation_number}</td>
                <td>{q.status}</td>
                <td>{formatNumber(q.total_amount, fmt)}</td>
                <td>{q.valid_until ? String(q.valid_until).slice(0, 10) : '—'}</td>
                <td>{q.rejection_reason || '—'}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(q)}>View</button>
                  {q.status === 'draft' && (
                    <button
                      onClick={() => act(`/sales/quotations/${q.id}/send`, 'Quotation emailed')}
                      aria-label="Email quotation"
                    >
                      Email
                    </button>
                  )}
                  {q.status === 'sent' && (
                    <button
                      onClick={() => act(`/sales/quotations/${q.id}/send`, 'Quotation re-emailed')}
                      aria-label="Resend quotation email"
                    >
                      Resend
                    </button>
                  )}
                  {['draft', 'sent'].includes(q.status) && (
                    <>
                      <button className="btn-ok" onClick={() => act(`/sales/quotations/${q.id}/accept`, 'Accepted')}>Accept</button>
                      <button
                        className="btn-danger"
                        onClick={() => act(`/sales/quotations/${q.id}/reject`, 'Rejected')}
                        aria-label={`Reject quotation ${q.id}`}
                        disabled={!quoteRejectReason.trim()}
                        title={
                          quoteRejectReason.trim()
                            ? 'Reject quotation'
                            : 'Enter a reject reason before rejecting'
                        }
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        className="btn-ok"
                        onClick={() => act(`/sales/quotations/${q.id}/convert-order`, 'Order')}
                      >
                        → Order
                      </button>
                      <button
                        type="button"
                        className="btn-ok"
                        onClick={() => act(`/sales/quotations/${q.id}/convert-invoice`, 'Invoice')}
                      >
                        → Invoice
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {managedQuotations.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">
                  {quotations.length === 0
                    ? 'No quotations yet'
                    : 'No quotations for this filter'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </>
      )}

      {tab === 'orders' && (
        <>
          <div className="card" style={{ marginBottom: 12 }}>
            <label>
              Cancel reason{' '}
              <input
                value={soCancelReason}
                onChange={(e) => setSoCancelReason(e.target.value)}
                placeholder="Required before Cancel"
                title="Required cancel reason (1–500 chars; letters/digits required)"
                aria-label="Sales order cancel reason"
                style={{ minWidth: 280 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Appended to order notes and audit (<code>POST .../orders/.../cancel</code>{' '}
              {'{ reason }'}).
            </p>
          </div>
          <select
            value={orderManageFilter}
            onChange={(e) =>
              setOrderManageFilter(
                e.target.value as
                  | 'all'
                  | 'draft'
                  | 'confirmed'
                  | 'processing'
                  | 'shipped'
                  | 'delivered'
                  | 'invoiced'
                  | 'cancelled'
              )
            }
            title="Filter sales order list by status"
            aria-label="Sales order status filter"
            style={{ marginBottom: 12 }}
          >
            <option value="all">All statuses</option>
            <option value="draft">Draft only</option>
            <option value="confirmed">Confirmed only</option>
            <option value="processing">Processing only</option>
            <option value="shipped">Shipped only</option>
            <option value="delivered">Delivered only</option>
            <option value="invoiced">Invoiced only</option>
            <option value="cancelled">Cancelled only</option>
          </select>
          <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Status</th>
              <th>Store</th>
              <th>Reserved</th>
              <th>Delivery</th>
              <th>Total</th>
              <th>Notes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedOrders.map((o) => (
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
                <td className="muted" style={{ maxWidth: 220, whiteSpace: 'pre-wrap' }}>
                  {o.notes || '—'}
                </td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(o)}>View</button>
                  {o.status === 'draft' && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() =>
                        act(
                          `/sales/orders/${o.id}/confirm`,
                          'Confirmed',
                          storeId || o.store_id
                            ? {
                                store_id: storeId || o.store_id,
                                delivery_date: deliveryDate.trim() || null,
                                // Omit blank delivery so Confirm does not 422 (AddressValue).
                                ...(deliveryAddress.trim()
                                  ? { delivery_address: deliveryAddress.trim() }
                                  : {}),
                              }
                            : {}
                        )
                      }
                    >
                      Confirm
                    </button>
                  )}
                  {o.can_process && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => act(`/sales/orders/${o.id}/process`, 'Processing')}
                    >
                      Process
                    </button>
                  )}
                  {o.can_ship && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => act(`/sales/orders/${o.id}/ship`, 'Shipped')}
                    >
                      Ship
                    </button>
                  )}
                  {o.can_deliver && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => act(`/sales/orders/${o.id}/deliver`, 'Delivered')}
                    >
                      Deliver
                    </button>
                  )}
                  {o.can_invoice && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => act(`/sales/orders/${o.id}/convert-invoice`, 'Invoice')}
                    >
                      → Invoice
                    </button>
                  )}
                  {o.can_cancel && (
                    <button
                      className="btn-danger"
                      onClick={() => act(`/sales/orders/${o.id}/cancel`, 'Cancelled')}
                      aria-label={`Cancel sales order ${o.id}`}
                    >
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {managedOrders.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  {orders.length === 0
                    ? 'No sales orders yet'
                    : 'No sales orders for this filter'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </>
      )}

      {tab === 'invoices' && (
        <>
          <div className="card" style={{ marginBottom: 12 }}>
            <label>
              Credit override reason{' '}
              <input
                value={creditOverrideReason}
                onChange={(e) => setCreditOverrideReason(e.target.value)}
                placeholder="Required when posting over credit limit"
                style={{ minWidth: 300 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Used when Post hits credit limit and you confirm manager override (sent as{' '}
              <code>override_reason</code>).
            </p>
          </div>
          <div className="card" style={{ marginBottom: 12 }}>
            <label>
              Cancel reason{' '}
              <input
                value={siCancelReason}
                onChange={(e) => setSiCancelReason(e.target.value)}
                placeholder="Required before Cancel"
                title="Required cancel reason (1–500 chars; letters/digits required)"
                aria-label="Sales invoice cancel reason"
                style={{ minWidth: 280 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Appended to draft invoice notes and audit (<code>POST .../invoices/.../cancel</code>{' '}
              {'{ reason }'}). Draft only.
            </p>
            <label style={{ display: 'block', marginTop: 8 }}>
              Email override{' '}
              <input
                type="email"
                value={docEmailTo}
                onChange={(e) => setDocEmailTo(e.target.value)}
                placeholder="Optional to= (omit → customer email)"
                aria-label="Document email override to"
                style={{ minWidth: 280 }}
              />
            </label>
          </div>
        <select
          value={invoiceManageFilter}
          onChange={(e) =>
            setInvoiceManageFilter(
              e.target.value as
                | 'all'
                | 'draft'
                | 'posted'
                | 'sent'
                | 'partial'
                | 'paid'
                | 'overdue'
                | 'cancelled'
            )
          }
          title="Filter sales invoice list by status"
          aria-label="Sales invoice status filter"
          style={{ marginBottom: 12 }}
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft only</option>
          <option value="posted">Posted only</option>
          <option value="sent">Sent only</option>
          <option value="partial">Partial only</option>
          <option value="paid">Paid only</option>
          <option value="overdue">Overdue only</option>
          <option value="cancelled">Cancelled only</option>
        </select>
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Status</th>
              <th>Store</th>
              <th>Total</th>
              <th>Paid</th>
              <th>Notes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedInvoices.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.invoice_number}</td>
                <td>{inv.status}</td>
                <td>
                  {stores.find((s) => s.id === inv.store_id)?.name ||
                    (inv.store_id ? inv.store_id.slice(0, 8) : '—')}
                </td>
                <td>{formatNumber(inv.total_amount, fmt)}</td>
                <td>{formatNumber(inv.paid_amount, fmt)}</td>
                <td className="muted" style={{ maxWidth: 220, whiteSpace: 'pre-wrap' }}>
                  {inv.notes || '—'}
                </td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(inv)}>View</button>
                  {inv.status === 'draft' && (
                    <>
                      <button type="button" className="btn-ok" onClick={() => postInvoice(inv)}>
                        Post
                      </button>
                      <button
                        className="btn-danger"
                        onClick={() => act(`/sales/invoices/${inv.id}/cancel`, 'Cancelled')}
                        aria-label={`Cancel sales invoice ${inv.id}`}
                      >
                        Cancel
                      </button>
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
                    <button
                      onClick={() => act(`/sales/invoices/${inv.id}/send`, 'Invoice emailed')}
                      aria-label={inv.emailed_at ? 'Resend invoice email' : 'Email invoice'}
                    >
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
            {managedInvoices.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  {invoices.length === 0
                    ? 'No invoices yet'
                    : 'No sales invoices for this filter'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </>
      )}

      {tab === 'returns' && (
        <>
          <div className="card" style={{ marginBottom: 16 }}>
            <h3>Create return</h3>
            <div className="erp-form-grid">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={invoiceId}
            onChange={(e) => setInvoiceId(e.target.value)}
            aria-label="Return from invoice"
          >
            <option value="">Return from invoice</option>
            {invoices
              .filter((i) => ['posted', 'sent', 'partial', 'overdue', 'paid'].includes(i.status))
              .map((i) => (
                <option key={i.id} value={i.id}>
                  {i.invoice_number}
                </option>
              ))}
          </select>
          <select
            value={returnReason}
            onChange={(e) => setReturnReason(e.target.value)}
            aria-label="Return reason"
          >
            <option value="">Select reason</option>
            {['damaged', 'wrong_item', 'defective', 'customer_change', 'other'].map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <select
            value={returnCondition}
            onChange={(e) => setReturnCondition(e.target.value)}
            aria-label="Return condition"
          >
            <option value="">Select condition</option>
            <option value="sellable">sellable</option>
            <option value="discard">discard</option>
          </select>
          <label>
            <input type="checkbox" checked={restock} onChange={(e) => setRestock(e.target.checked)} /> Restock
          </label>
          <input
            value={returnNotes}
            onChange={(e) => setReturnNotes(e.target.value)}
            placeholder="Return notes (optional)"
            aria-label="Sales return notes"
            title="Optional notes (1–500 chars; letters/digits required)"
            style={{ minWidth: 220 }}
          />
          <button
            onClick={createReturn}
            disabled={!invoiceId || !productId || !returnReason || !returnCondition}
            aria-label="Create sales return"
          >
            Create return
          </button>
        </div>
                  </div>
          </div>
          <div className="card" style={{ marginBottom: 12 }}>
            <label>
              Cancel reason{' '}
              <input
                value={srCancelReason}
                onChange={(e) => setSrCancelReason(e.target.value)}
                placeholder="Required before Cancel"
                style={{ minWidth: 280 }}
              />
            </label>
            <p className="muted" style={{ marginTop: 6 }}>
              Appended to draft return notes and audit (<code>POST .../returns/.../cancel</code>{' '}
              {'{ reason }'}). Draft only.
            </p>
          </div>
        <select
          value={returnManageFilter}
          onChange={(e) =>
            setReturnManageFilter(
              e.target.value as 'all' | 'draft' | 'posted' | 'cancelled'
            )
          }
          title="Filter sales return list by status"
          aria-label="Sales return status filter"
          style={{ marginBottom: 12 }}
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft only</option>
          <option value="posted">Posted only</option>
          <option value="cancelled">Cancelled only</option>
        </select>
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              <th>Credit note</th>
              <th>Status</th>
              <th>Settlement</th>
              <th>Reason</th>
              <th>Total</th>
              <th>Notes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedReturns.map((r) => (
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
                <td className="muted" style={{ maxWidth: 220, whiteSpace: 'pre-wrap' }}>
                  {r.notes || '—'}
                </td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(r)}>View</button>
                  {r.status === 'draft' && (
                    <>
                      <button
                        type="button"
                        className="btn-ok"
                        onClick={() =>
                          act(`/sales/returns/${r.id}/post`, 'Posted (credit)', {
                            settlement_method: 'adjust',
                          })
                        }
                      >
                        Post credit
                      </button>
                      <button
                        type="button"
                        className="btn-ok"
                        onClick={() =>
                          act(`/sales/returns/${r.id}/post`, 'Posted (refund)', {
                            settlement_method: 'refund',
                            payment_method: 'cash',
                          })
                        }
                      >
                        Post + refund
                      </button>
                      <button className="btn-danger" onClick={() => act(`/sales/returns/${r.id}/cancel`, 'Cancelled')}>
                        Cancel
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {managedReturns.length === 0 && (
              <tr>
                <td colSpan={8} className="muted">
                  {returns.length === 0
                    ? 'No returns yet'
                    : 'No sales returns for this filter'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </>
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
                <th>Discount</th>
                <th>Condition</th>
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
                  <td>{it.discount ?? 0}</td>
                  <td>{it.condition || '—'}</td>
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
              <div className="muted">Discount</div>
              <div className="kpi">{selected.discount_amount ?? 0}</div>
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
                  {selected.is_reverse_charge ? ' · header RC' : ''}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
