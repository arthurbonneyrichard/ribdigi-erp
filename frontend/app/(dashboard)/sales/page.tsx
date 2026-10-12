'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import FormModal from '../../../components/FormModal';
import PartyContactsPanel from '../../../components/PartyContactsPanel';
import { api, getAccessToken } from '../../../lib/api';
import { formatNumber, formatWhen, plainLabel, type FormatPrefs } from '../../../lib/format';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import { getMe } from '../../../lib/meCache';
import { usesWholesaleTrade } from '../../../lib/industries';
import { useStoreContext } from '../../../lib/storeContext';

type Tab = 'made' | 'invoices' | 'quotations' | 'orders' | 'returns' | 'coupons';

const SALES_TABS: Tab[] = ['made', 'invoices', 'quotations', 'orders', 'returns', 'coupons'];

function isSalesTab(value: string | null): value is Tab {
  return Boolean(value && (SALES_TABS as string[]).includes(value));
}

function channelLabel(value?: string | null) {
  if (value === 'wholesale') return 'Wholesale';
  if (value === 'retail') return 'Retail';
  return '—';
}

function saleWords(value?: string | null) {
  const code = String(value || '').trim().toLowerCase();
  if (!code) return '—';
  const mapped: Record<string, string> = {
    adjust: 'Credit on the account',
    refund: 'Cash refund',
    sellable: 'Good to sell again',
    discard: 'Do not restock',
    wrong_item: 'Wrong item',
    customer_change: 'Customer changed their mind',
    partial: 'Partly paid',
    percent: 'Percent off',
    fixed: 'Fixed amount',
    register: 'Register',
    invoice: 'Invoice',
  };
  return mapped[code] || plainLabel(code);
}

const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

async function downloadInvoicePdf(
  invoiceId: string,
  invoiceNumber: string,
  template: 'a4' | 'thermal',
  paper = '80mm'
) {
  const token = getAccessToken();
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

async function previewInvoicePdf(invoiceId: string, template: 'a4' | 'thermal') {
  const token = getAccessToken();
  const tenant = localStorage.getItem('tenant');
  const qs = template === 'thermal' ? 'template=thermal&format=pdf&paper=80mm' : 'template=a4&format=pdf';
  const res = await fetch(`${apiBase}/sales/invoices/${invoiceId}/print?${qs}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(tenant ? { 'X-Tenant-ID': tenant } : {}),
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    throw new Error(typeof detail === 'string' ? detail : detail?.message || 'Preview failed');
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener');
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export default function Page() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>('made');
  const [madeSales, setMadeSales] = useState<any[]>([]);
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
  const [customerCategory, setCustomerCategory] = useState('');
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
  const [newGroupCode, setNewGroupCode] = useState('');
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
  const [lineDiscountType, setLineDiscountType] = useState<'fixed' | 'percent'>('fixed');
  const [headerDiscount, setHeaderDiscount] = useState('');
  const [headerDiscountType, setHeaderDiscountType] = useState<'fixed' | 'percent'>('fixed');
  const [couponCode, setCouponCode] = useState('');
  const [coupons, setCoupons] = useState<any[]>([]);
  const [newCouponCode, setNewCouponCode] = useState('');
  const [newCouponName, setNewCouponName] = useState('');
  const [newCouponType, setNewCouponType] = useState<'fixed' | 'percent'>('percent');
  const [newCouponAmount, setNewCouponAmount] = useState('10');
  const [newCouponMin, setNewCouponMin] = useState('0');
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
  const [fmt, setFmt] = useState<FormatPrefs | null>(null);
  const [listSearch, setListSearch] = useState('');
  const [composerOpen, setComposerOpen] = useState(false);
  const [saveBusy, setSaveBusy] = useState(false);
  const [returnCreateOpen, setReturnCreateOpen] = useState(false);
  const [wholesaleOps, setWholesaleOps] = useState(false);
  const [fulfillQty, setFulfillQty] = useState<Record<string, string>>({});
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

  useEffect(() => {
    const next = searchParams.get('tab');
    if (isSalesTab(next)) setTab(next);
  }, [searchParams]);

  useEffect(() => {
    getMe()
      .then((r) => setWholesaleOps(usesWholesaleTrade(r.data?.industry)))
      .catch(() => undefined);
  }, []);

  async function refresh() {
    const [madeRes, invRes, custRes, prodRes, unitRes, qRes, oRes, rRes, storeRes, settingsRes, groupRes, tenantRes, couponRes] =
      await Promise.all([
        api('/sales/made').catch(() => ({ data: [] })),
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
        api('/sales/coupons').catch(() => ({ data: [] })),
      ]);
    setMadeSales(madeRes.data || []);
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
    setCoupons(couponRes.data || []);
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
    const customerTrim = customerId.trim();
    const variantTrim = variantId.trim();
    // omit blank so UuidIdValue Query customer_id / variant_id do not 422
    if (customerTrim) qs.set('customer_id', customerTrim);
    if (variantTrim) qs.set('variant_id', variantTrim);
    const qtyNum = Number(qty);
    if (Number.isFinite(qtyNum) && qtyNum > 0) qs.set('quantity', String(qtyNum));
    if (wholesaleOps) qs.set('sales_channel', 'wholesale');
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
  }, [productId, variantId, customerId, useGroupPrice, qty, wholesaleOps]);

  const lineDisc = Math.max(0, Number(lineDiscount) || 0);
  const hdrDisc = Math.max(0, Number(headerDiscount) || 0);
  const lineItems = [
    {
      product_id: productId.trim(),
      variant_id: variantId.trim() || null,
      unit_id: unitId.trim() || null,
      quantity: Number(qty),
      ...(useGroupPrice ? {} : { unit_price: Number(unitPrice) }),
      tax_rate: taxRate === '' ? null : Number(taxRate),
      discount: lineDiscountType === 'percent' ? 0 : lineDisc,
      discount_type: lineDiscountType,
      discount_percent: lineDiscountType === 'percent' ? Math.max(0, Math.min(100, lineDisc)) : 0,
    },
  ];

  const linePayload = {
    // trim so Create quotation / Create order (UuidIdValue customer_id) do not 422 on whitespace
    customer_id: customerId.trim(),
    // null when blank so Create order / invoice (UuidIdValue store_id) do not 422
    store_id: storeId.trim() || null,
    delivery_date: deliveryDate.trim() || null,
    // null when blank so Create order does not 422 (AddressValue).
    delivery_address: deliveryAddress.trim() || null,
    discount_amount: headerDiscountType === 'percent' ? 0 : hdrDisc,
    discount_type: headerDiscountType,
    discount_percent: headerDiscountType === 'percent' ? Math.max(0, Math.min(100, hdrDisc)) : 0,
    notes: docNotes.trim() || null,
    ...(wholesaleOps ? { sales_channel: 'wholesale' as const } : {}),
    items: lineItems,
  };

  const quotePayload = {
    customer_id: customerId.trim(),
    discount_amount: headerDiscountType === 'percent' ? 0 : hdrDisc,
    discount_type: headerDiscountType,
    discount_percent: headerDiscountType === 'percent' ? Math.max(0, Math.min(100, hdrDisc)) : 0,
    notes: docNotes.trim() || null,
    ...(wholesaleOps ? { sales_channel: 'wholesale' as const } : {}),
    items: lineItems,
  };

  const invoicePayload = {
    customer_id: customerId.trim(),
    store_id: storeId.trim() || null,
    items: lineItems,
    discount_amount: headerDiscountType === 'percent' ? 0 : hdrDisc,
    discount_type: headerDiscountType,
    discount_percent: headerDiscountType === 'percent' ? Math.max(0, Math.min(100, hdrDisc)) : 0,
    notes: docNotes.trim() || null,
    currency: currency.trim() || null,
    exchange_rate: exchangeRate === '' ? null : Number(exchangeRate),
    is_reverse_charge: invoiceReverseCharge,
    coupon_code: couponCode.trim() || null,
    ...(wholesaleOps ? { sales_channel: 'wholesale' as const } : {}),
  };

  async function createCustomer() {
    if (saveBusy) return;
    setError('');
    setSaveBusy(true);
    try {
      const r = await api('/customers', {
        method: 'POST',
        body: JSON.stringify({
          name: customerName.trim(),
          code: customerCode.trim() || null,
          profile_type: customerProfileType || 'registered',
          category: customerCategory.trim() || null,
          status: customerStatus || 'active',
          email: customerEmail.trim() || null,
          phone: customerPhone.trim() || null,
          // null when blank so Create does not 422 (AddressValue).
          address: customerAddress.trim() || null,
          latitude: customerLat === '' ? null : Number(customerLat),
          longitude: customerLng === '' ? null : Number(customerLng),
          credit_limit: Number(creditLimit) || 0,
          payment_terms_days: Number(paymentTermsDays) || 0,
          customer_group_id: customerGroupId.trim() || null,
        }),
      });
      setCustomerId(r.data.id);
      setCustomerName('');
      setCustomerCode('');
      setCustomerEmail('');
      setCustomerPhone('');
      setCustomerAddress('');
      setCustomerProfileType('registered');
      setCustomerCategory('');
      setCustomerStatus('active');
      setCustomerLat('');
      setCustomerLng('');
      setCustomerGroupId('');
      setPaymentTermsDays('30');
      await refresh();
      setMessage('Customer created');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaveBusy(false);
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
          code: newGroupCode.trim() || null,
          discount_percent: Number(newGroupDiscount) || 0,
        }),
      });
      setNewGroupName('');
      setNewGroupCode('');
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
        body: JSON.stringify({ customer_group_id: customerGroupId.trim() }),
      });
      await refresh();
      setMessage('Customer group assigned');
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

  async function createInvoice() {
    if (saveBusy) return;
    setError('');
    setSaveBusy(true);
    try {
      const r = await api('/sales/invoices', { method: 'POST', body: JSON.stringify(invoicePayload) });
      setMessage(`Draft ${r.data.invoice_number} created`);
      setSelected(r.data);
      setComposerOpen(false);
      setLineDiscount('');
      setHeaderDiscount('');
      setDocNotes('');
      setTab('invoices');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaveBusy(false);
    }
  }

  async function createQuotation() {
    if (saveBusy) return;
    setError('');
    setSaveBusy(true);
    try {
      const r = await api('/sales/quotations', { method: 'POST', body: JSON.stringify(quotePayload) });
      setMessage(`Quotation ${r.data.quotation_number} created`);
      setSelected(r.data);
      setComposerOpen(false);
      setLineDiscount('');
      setHeaderDiscount('');
      setDocNotes('');
      setTab('quotations');
      await refresh();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaveBusy(false);
    }
  }

  async function createOrder() {
    if (saveBusy) return;
    setError('');
    setSaveBusy(true);
    try {
      const r = await api('/sales/orders', { method: 'POST', body: JSON.stringify(linePayload) });
      setMessage(`Order ${r.data.order_number} created`);
      setSelected(r.data);
      setComposerOpen(false);
      setLineDiscount('');
      setHeaderDiscount('');
      setDocNotes('');
      setTab('orders');
      await refresh();
    } catch (err: any) {
      setError(err.message);
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
    if (!returnCondition.trim()) {
      setError('Select a return condition');
      return;
    }
    setSaveBusy(true);
    try {
      const r = await api('/sales/returns', {
        method: 'POST',
        body: JSON.stringify({
          // trim so Create return (UuidIdValue sales_invoice_id) does not 422 on whitespace
          sales_invoice_id: invoiceId.trim(),
          reason: returnReason,
          restock,
          notes: returnNotes.trim() || null,
          items: [
            {
              product_id: productId.trim(),
              variant_id: variantId.trim() || null,
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
      setReturnCreateOpen(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaveBusy(false);
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
  function matchesList(row: any) {
    const q = listSearch.trim().toLowerCase();
    if (!q) return true;
    const cust = customers.find((c) => c.id === row.customer_id);
    const hay = [
      row.number,
      row.customer,
      row.source,
      row.invoice_number,
      row.quotation_number,
      row.order_number,
      row.return_number,
      row.credit_note_number,
      row.status,
      row.notes,
      row.reason,
      cust?.name,
      cust?.code,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return hay.includes(q);
  }
  const managedReturns = returns.filter((r) => {
    if (returnManageFilter !== 'all' && (r.status || 'draft') !== returnManageFilter) return false;
    return matchesList(r);
  });
  const managedInvoices = invoices.filter((inv) => {
    if (invoiceManageFilter !== 'all' && (inv.status || 'draft') !== invoiceManageFilter) return false;
    return matchesList(inv);
  });
  const managedMade = madeSales.filter((row) => matchesList(row));
  const managedQuotations = quotations.filter((q) => {
    if (quotationManageFilter !== 'all' && (q.status || 'draft') !== quotationManageFilter) return false;
    return matchesList(q);
  });
  const managedOrders = orders.filter((o) => {
    if (orderManageFilter !== 'all' && (o.status || 'draft') !== orderManageFilter) return false;
    return matchesList(o);
  });

  const showChannel = wholesaleOps;
  const activeStores = stores.filter((s) => s.is_active !== false);
  const showStore = activeStores.length > 1;
  const showQuoteReject = managedQuotations.some((q) => q.rejection_reason);
  const showReserved = managedOrders.some((o) => o.reservation_status);
  const storeName = (id?: string | null) => (id ? stores.find((s) => s.id === id)?.name || '' : '');
  const quoteCols = 5 + (showChannel ? 1 : 0) + (showQuoteReject ? 1 : 0);
  const orderCols = 5 + (showChannel ? 1 : 0) + (showStore ? 1 : 0) + (showReserved ? 1 : 0);
  const invoiceCols = 5 + (showChannel ? 1 : 0) + (showStore ? 1 : 0);
  const drawerLines = selected?.items || [];
  const showFilled = drawerLines.some((it) => it.qty_fulfilled != null && it.qty_fulfilled !== '');
  const showCondition = drawerLines.some((it) => Boolean(it.condition));

  return (
    <div className="sales-desk">
      <header className="sales-desk-head">
        <div>
          <h1>Sales</h1>
          <p className="muted">
            {wholesaleOps
              ? 'All sales lists every completed invoice and register sale. Quotes and orders are not sales until they are invoiced.'
              : 'All sales lists every completed invoice and register sale.'}
          </p>
        </div>
        <button type="button" className="btn-primary" onClick={() => setComposerOpen(true)}>
          New
        </button>
      </header>

      <div className="sales-toolbar">
        {(
          [
            ['made', 'All sales'],
            ['invoices', 'Invoices'],
            ['quotations', 'Quotes'],
            ['orders', 'Orders'],
            ['returns', 'Returns'],
            ['coupons', 'Coupons'],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? 'sales-tab is-on' : 'sales-tab'}
            onClick={() => setTab(id)}
            disabled={tab === id}
            aria-label={id === 'made' ? 'Show all sales' : `Show sales ${id} tab`}
          >
            {label}
          </button>
        ))}
        <input
          className="sales-search"
          value={listSearch}
          onChange={(e) => setListSearch(e.target.value)}
          placeholder="Search number, customer, status…"
          aria-label="Search sales documents"
        />
      </div>
      {false && (
      <details className="sales-more">
        <summary>Document numbers</summary>
      <div className="card sales-more-body" style={{ display: 'grid', gap: 8 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">Invoice</span>
          <input
            value={invPrefix}
            onChange={(e) => setInvPrefix(e.target.value.toUpperCase())}
            placeholder="Prefix"
            style={{ width: 100 }}
            aria-label="Invoice number prefix"
            title="Document prefix (letters, digits, _ or -)"
          />
          <input
            value={invNext}
            onChange={(e) => setInvNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
            aria-label="Invoice next number"
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
            aria-label="Quotation number prefix"
            title="Document prefix (letters, digits, _ or -)"
          />
          <input
            value={qtNext}
            onChange={(e) => setQtNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
            aria-label="Quotation next number"
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
            aria-label="Sales order number prefix"
            title="Document prefix (letters, digits, _ or -)"
          />
          <input
            value={soNext}
            onChange={(e) => setSoNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
            aria-label="Sales order next number"
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
            aria-label="Sales return number prefix"
            title="Document prefix (letters, digits, _ or -)"
          />
          <input
            value={srNext}
            onChange={(e) => setSrNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
            aria-label="Sales return next number"
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
            aria-label="Credit note number prefix"
            title="Document prefix (letters, digits, _ or -)"
          />
          <input
            value={cnNext}
            onChange={(e) => setCnNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
            aria-label="Credit note next number"
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
            aria-label="Payment receipt number prefix"
            title="Document prefix (letters, digits, _ or -)"
          />
          <input
            value={rcpNext}
            onChange={(e) => setRcpNext(e.target.value)}
            placeholder="Next #"
            style={{ width: 90 }}
            aria-label="Payment receipt next number"
          />
          <span className="muted">{rcpPreview || '—'}</span>
          <button type="button" onClick={saveInvoiceNumbering} aria-label="Save sales numbering">
            Save numbering
          </button>
        </div>
      </div>
      </details>
      )}
      {(error || message) && !composerOpen && !selected ? (
        <p className={error ? 'sales-flash sales-flash-err' : 'sales-flash sales-flash-ok'} role={error ? 'alert' : undefined}>
          {error || message}
        </p>
      ) : null}

      {composerOpen ? (
      <FormModal
        title="New document"
        busy={saveBusy}
        dirty={Boolean(customerName.trim() || customerId || productId || docNotes.trim() || qty !== '1')}
        onClose={() => setComposerOpen(false)}
      >
        {(error || message) ? (
          <p className={error ? 'sales-flash sales-flash-err' : 'sales-flash sales-flash-ok'} role={error ? 'alert' : undefined}>
            {error || message}
          </p>
        ) : null}
      <div className="erp-split">
        <div className="card">
          <h3>Customer</h3>
          <div className="erp-stack" style={{ marginBottom: 0 }}>
        <details className="sales-more">
          <summary>Customer groups</summary>
        <div style={{ display: 'grid', gap: 8 }}>
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
                <button type="button" onClick={() => saveGroupDiscount(g)} aria-label={`Save customer group discount ${g.id}`}>
                  Save discount
                </button>
                <button
                  type="button"
                  className={g.is_active === false ? 'btn-ok' : 'btn-danger'}
                  onClick={() => setGroupActive(g, g.is_active === false)}
                  aria-label={
                    g.is_active === false
                      ? `Activate customer group ${g.id}`
                      : `Deactivate customer group ${g.id}`
                  }
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
              aria-label="Customer group code"
              value={newGroupCode}
              onChange={(e) => setNewGroupCode(e.target.value)}
              placeholder="Code (optional)"
              title="Customer group code (optional; 1–40 chars; blank → slug from name)"
              style={{ width: 140 }}
            />
            <input
              value={newGroupDiscount}
              onChange={(e) => setNewGroupDiscount(e.target.value)}
              placeholder="Discount %"
              aria-label="Customer group discount percent"
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
        </details>
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
                if (customerManageFilter === 'inactive') return (c.status || 'active') === 'inactive';
                return c.status !== 'inactive';
              })
              .map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.status === 'inactive' ? ' · Inactive' : ''}
              </option>
            ))}
          </select>
          {showStore ? (
          <select
            value={storeId}
            onChange={(e) => {
              setStoreId(e.target.value);
              setCtxStoreId(e.target.value);
            }}
            aria-label="Sale store"
          >
            <option value="">Choose a store</option>
            {activeStores.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          ) : null}
          <details className="sales-more">
            <summary>Currency</summary>
          <input
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            placeholder="Currency"
            aria-label="Sales invoice currency"
            pattern="[A-Z]{3}"
            maxLength={3}
            style={{ width: 140 }}
          />
          <input
            value={exchangeRate}
            onChange={(e) => setExchangeRate(e.target.value)}
            placeholder="Exchange rate"
            style={{ width: 120 }}
            aria-label="Sales invoice FX rate"
          />
          <input
            value={customerLat}
            onChange={(e) => setCustomerLat(e.target.value)}
            placeholder="Latitude"
            style={{ width: 90 }}
            aria-label="Customer latitude"
          />
          <input
            value={customerLng}
            onChange={(e) => setCustomerLng(e.target.value)}
            placeholder="Longitude"
            style={{ width: 90 }}
            aria-label="Customer longitude"
          />
          </details>
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
            aria-label="Customer code"
            title="Customer code (optional; 1–64 chars; letters/digits required)"
            style={{ width: 100 }}
          />
          <select
            value={customerProfileType}
            onChange={(e) => setCustomerProfileType(e.target.value)}
            aria-label="Customer profile type"
            title="Customer type"
          >
            <option value="registered">Registered</option>
            <option value="walk_in">Walk-in</option>
          </select>
          <input
            value={customerCategory}
            onChange={(e) => setCustomerCategory(e.target.value)}
            placeholder="Category"
            aria-label="Customer category"
            title="Customer category (optional; 1–80 chars; letters/digits required)"
            style={{ width: 120 }}
          />
          <select
            value={customerStatus}
            onChange={(e) => setCustomerStatus(e.target.value)}
            aria-label="Customer status"
            title="Status"
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <input
            value={customerEmail}
            onChange={(e) => setCustomerEmail(e.target.value)}
            placeholder="Customer email"
            aria-label="Customer email"
          />
          <input
            value={customerPhone}
            onChange={(e) => setCustomerPhone(e.target.value)}
            placeholder="Phone"
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
          <select
            value={customerGroupId}
            onChange={(e) => setCustomerGroupId(e.target.value)}
            aria-label="Customer group"
          >
            <option value="">Group (optional)</option>
            {groups
              .filter((g) => g.is_active !== false)
              .map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name} (−{g.discount_percent}%)
                </option>
              ))}
          </select>
          <input
            value={creditLimit}
            onChange={(e) => setCreditLimit(e.target.value)}
            placeholder="Credit limit"
            aria-label="Customer credit limit"
          />
          <input
            value={paymentTermsDays}
            onChange={(e) => setPaymentTermsDays(e.target.value)}
            placeholder="Net days"
            style={{ width: 90 }}
            title="Payment terms (days)"
            aria-label="Customer payment terms days"
          />
          <button type="button" onClick={createCustomer} aria-label="Add customer">
            Add customer
          </button>
          <button type="button" onClick={assignCustomerGroup} aria-label="Assign customer group">
            Assign group
          </button>
        </div>
        {customerId &&
          (customers.find((c) => c.id === customerId)?.status || 'active') === 'inactive' && (
            <p className="muted" style={{ margin: 0 }}>
              Inactive — not shown on new sales. Existing documents can still be settled.
            </p>
          )}
        {customerId ? (
          <details className="sales-more">
            <summary>Contacts</summary>
          <PartyContactsPanel
            kind="customer"
            partyId={customerId}
            partyLabel={customers.find((c) => c.id === customerId)?.name || 'Selected customer'}
          />
          </details>
        ) : null}
          </div>
        </div>
        <div className="card">
          <h3>Create sale</h3>
          <div className="erp-stack" style={{ marginBottom: 0 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            aria-label="Sale customer"
          >
            <option value="">Customer</option>
            {customers
              .filter((c) => c.is_active !== false && (c.status || 'active') === 'active')
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
          </select>
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
                {p.name} — {p.sku}
              </option>
            ))}
          </select>
          {variants.length > 0 && (
            <select
              value={variantId}
              onChange={(e) => setVariantId(e.target.value)}
              aria-label="Sales variant"
            >
              <option value="">Variant (optional)</option>
              {variants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} — {v.sku} ({v.selling_price})
                </option>
              ))}
            </select>
          )}
          <select
            value={unitId}
            onChange={(e) => setUnitId(e.target.value)}
            aria-label="Sales unit"
          >
            <option value="">Unit (default)</option>
            {units.map((u) => (
              <option key={u.id} value={u.id}>
                {u.code}
              </option>
            ))}
          </select>
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            placeholder="Qty"
            aria-label="Line quantity"
            style={{ width: 80 }}
          />
          {wholesaleOps && Number(products.find((p) => p.id === productId)?.min_order_qty || 0) > 0 ? (
            <span className="muted">
              Wholesale minimum {products.find((p) => p.id === productId)?.min_order_qty}
            </span>
          ) : null}
          <input
            value={unitPrice}
            onChange={(e) => {
              setUseGroupPrice(false);
              setUnitPrice(e.target.value);
            }}
            placeholder="Price"
            aria-label="Line unit price"
            style={{ width: 100 }}
          />
          <label style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <input
              type="checkbox"
              aria-label="Use customer group price"
              checked={useGroupPrice}
              onChange={(e) => setUseGroupPrice(e.target.checked)}
            />
            {wholesaleOps ? 'Quantity price' : 'Group price'}
          </label>
          <input
            value={taxRate}
            onChange={(e) => setTaxRate(e.target.value)}
            placeholder="Tax %"
            aria-label="Line tax percent"
            style={{ width: 80 }}
          />
          <select
            value={lineDiscountType}
            onChange={(e) => setLineDiscountType(e.target.value === 'percent' ? 'percent' : 'fixed')}
            aria-label="Line discount type"
          >
            <option value="fixed">Line discount amount</option>
            <option value="percent">Line discount %</option>
          </select>
          <input
            value={lineDiscount}
            onChange={(e) => setLineDiscount(e.target.value)}
            placeholder="Line discount"
            aria-label="Line discount"
            style={{ width: 110 }}
            title="Line discount amount (tax before discount)"
          />
          <select
            value={headerDiscountType}
            onChange={(e) => setHeaderDiscountType(e.target.value === 'percent' ? 'percent' : 'fixed')}
            aria-label="Header discount type"
          >
            <option value="fixed">Header discount amount</option>
            <option value="percent">Header discount %</option>
          </select>
          <input
            value={headerDiscount}
            onChange={(e) => setHeaderDiscount(e.target.value)}
            placeholder="Header discount"
            aria-label="Header discount"
            style={{ width: 120 }}
            title="Document-level discount amount"
          />
          <input
            value={couponCode}
            onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
            placeholder="Coupon code"
            aria-label="Invoice coupon code"
            style={{ width: 140 }}
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
        <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
          <input
            type="checkbox"
            checked={invoiceReverseCharge}
            onChange={(e) => setInvoiceReverseCharge(e.target.checked)}
            aria-label="Sales invoice reverse charge"
          />
          Reverse charge (tax memo only — not charged to customer)
        </label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={createQuotation} disabled={saveBusy} aria-label="Create quotation">
            {saveBusy ? 'Saving…' : 'Save quote'}
          </button>
          <button onClick={createOrder} disabled={saveBusy} aria-label="Create order">
            {saveBusy ? 'Saving…' : 'Save order'}
          </button>
          <button onClick={createInvoice} disabled={saveBusy} aria-label="Create invoice">
            {saveBusy ? 'Saving…' : 'Save invoice'}
          </button>
        </div>
        {(error || message) ? (
          <p className={error ? 'sales-flash sales-flash-err' : 'sales-flash sales-flash-ok'} role={error ? 'alert' : undefined}>
            {error || message}
          </p>
        ) : null}
          </div>
        </div>
      </div>
      </FormModal>
      ) : null}

      {tab === 'made' && (
        <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Number</th>
                <th>Customer</th>
                <th>Where</th>
                <th>Status</th>
                <th>Total</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {managedMade.map((row) => (
                <tr key={`${row.source}-${row.id}`}>
                  <td>{formatWhen(row.when, displayFmt)}</td>
                  <td>{row.number}</td>
                  <td>{row.customer || 'Walk-in'}</td>
                  <td>{saleWords(row.source)}</td>
                  <td>{saleWords(row.status)}</td>
                  <td>{formatNumber(row.total, displayFmt)}</td>
                  <td>
                    {row.invoice_id ? (
                      <button
                        type="button"
                        onClick={() => {
                          const inv = invoices.find((item) => item.id === row.invoice_id);
                          if (inv) setSelected(inv);
                        }}
                        aria-label={`View sales invoice ${row.invoice_id}`}
                      >
                        View
                      </button>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
              {!managedMade.length && (
                <tr>
                  <td colSpan={7} className="muted">
                    {listSearch.trim() ? 'No sales for this search' : 'No sales yet'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'quotations' && (
        <>
          <details className="sales-more" style={{ marginBottom: 12 }}>
            <summary>Reject or email a quote</summary>
          <div className="card sales-more-body">
            <label>
              Reject reason{' '}
              <input
                value={quoteRejectReason}
                onChange={(e) => setQuoteRejectReason(e.target.value)}
                placeholder="Required before Reject"
                aria-label="Quotation reject reason"
              />
            </label>
            <label style={{ display: 'block', marginTop: 8 }}>
              Email to{' '}
              <input
                type="email"
                value={docEmailTo}
                onChange={(e) => setDocEmailTo(e.target.value)}
                placeholder="Optional — uses customer email if blank"
                aria-label="Document email override to"
              />
            </label>
          </div>
          </details>
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
              {showChannel ? <th>Channel</th> : null}
              <th>Status</th>
              <th>Total</th>
              <th>Valid until</th>
              {showQuoteReject ? <th>Reject reason</th> : null}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedQuotations.map((q) => (
              <tr key={q.id}>
                <td>{q.quotation_number}</td>
                {showChannel ? <td>{channelLabel(q.sales_channel)}</td> : null}
                <td>{saleWords(q.status)}</td>
                <td>{formatNumber(q.total_amount, displayFmt)}</td>
                <td>{q.valid_until ? formatWhen(q.valid_until, displayFmt) : '—'}</td>
                {showQuoteReject ? <td>{q.rejection_reason || '—'}</td> : null}
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(q)} aria-label={`View quotation ${q.id}`}>View</button>
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
                      <button
                        className="btn-ok"
                        onClick={() => act(`/sales/quotations/${q.id}/accept`, 'Accepted')}
                        aria-label={`Accept quotation ${q.id}`}
                      >
                        Accept
                      </button>
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
                        aria-label={`Convert quotation to order ${q.id}`}
                      >
                        → Order
                      </button>
                      <button
                        type="button"
                        className="btn-ok"
                        onClick={() => act(`/sales/quotations/${q.id}/convert-invoice`, 'Invoice')}
                        aria-label={`Convert quotation to invoice ${q.id}`}
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
                <td colSpan={quoteCols} className="muted">
                  {quotations.length === 0
                    ? 'No quotes yet'
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
          <details className="sales-more" style={{ marginBottom: 12 }}>
            <summary>Cancel an order</summary>
          <div className="card sales-more-body">
            <label>
              Cancel reason{' '}
              <input
                value={soCancelReason}
                onChange={(e) => setSoCancelReason(e.target.value)}
                placeholder="Required before Cancel"
                aria-label="Sales order cancel reason"
              />
            </label>
          </div>
          </details>
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
              {showChannel ? <th>Channel</th> : null}
              <th>Status</th>
              {showStore ? <th>Store</th> : null}
              {showReserved ? <th>Reserved</th> : null}
              <th>Delivery</th>
              <th>Total</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedOrders.map((o) => (
              <tr key={o.id}>
                <td>{o.order_number}</td>
                {showChannel ? <td>{channelLabel(o.sales_channel)}</td> : null}
                <td>{saleWords(o.status)}</td>
                {showStore ? <td>{storeName(o.store_id) || '—'}</td> : null}
                {showReserved ? (
                <td>
                  {o.reservation_status
                    ? `${formatNumber(o.reserved_qty ?? 0, displayFmt)} ${saleWords(o.reservation_status)}`
                    : '—'}
                </td>
                ) : null}
                <td>
                  {o.delivery_date ? formatWhen(o.delivery_date, displayFmt) : '—'}
                  {o.delivery_address ? ` · ${o.delivery_address}` : ''}
                </td>
                <td>{formatNumber(o.total_amount, displayFmt)}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(o)} aria-label={`View sales order ${o.id}`}>View</button>
                  {o.status === 'draft' && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() =>
                        act(
                          `/sales/orders/${o.id}/confirm`,
                          'Confirmed',
                          storeId.trim() || o.store_id
                            ? {
                                store_id: (storeId.trim() || o.store_id) as string,
                                delivery_date: deliveryDate.trim() || null,
                                // Omit blank delivery so Confirm does not 422 (AddressValue).
                                ...(deliveryAddress.trim()
                                  ? { delivery_address: deliveryAddress.trim() }
                                  : {}),
                              }
                            : {}
                        )
                      }
                      aria-label={`Confirm sales order ${o.id}`}
                    >
                      Confirm
                    </button>
                  )}
                  {o.can_process && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => act(`/sales/orders/${o.id}/process`, 'Processing')}
                      aria-label={`Process sales order ${o.id}`}
                    >
                      Process
                    </button>
                  )}
                  {o.can_ship && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => act(`/sales/orders/${o.id}/ship`, 'Shipped')}
                      aria-label={`Ship sales order ${o.id}`}
                    >
                      Ship
                    </button>
                  )}
                  {o.can_deliver && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => act(`/sales/orders/${o.id}/deliver`, 'Delivered')}
                      aria-label={`Deliver sales order ${o.id}`}
                    >
                      Deliver
                    </button>
                  )}
                  {o.can_invoice && (
                    <button
                      type="button"
                      className="btn-ok"
                      onClick={() => act(`/sales/orders/${o.id}/convert-invoice`, 'Invoice')}
                      aria-label={`Convert sales order to invoice ${o.id}`}
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
                <td colSpan={orderCols} className="muted">
                  {orders.length === 0
                    ? 'No orders yet'
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
          <details className="sales-more" style={{ marginBottom: 12 }}>
            <summary>Cancel, email, or sell over the limit</summary>
          <div className="card sales-more-body">
            <label>
              Credit override{' '}
              <input
                value={creditOverrideReason}
                onChange={(e) => setCreditOverrideReason(e.target.value)}
                placeholder="If posting over credit limit"
                aria-label="Credit override reason"
              />
            </label>
            <label style={{ display: 'block', marginTop: 8 }}>
              Cancel reason{' '}
              <input
                value={siCancelReason}
                onChange={(e) => setSiCancelReason(e.target.value)}
                placeholder="Required before Cancel"
                aria-label="Sales invoice cancel reason"
              />
            </label>
            <label style={{ display: 'block', marginTop: 8 }}>
              Email to{' '}
              <input
                type="email"
                value={docEmailTo}
                onChange={(e) => setDocEmailTo(e.target.value)}
                placeholder="Optional — uses customer email if blank"
                aria-label="Document email override to"
              />
            </label>
          </div>
          </details>
        <select
          className="list-toolbar"
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
        <div className="list-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Number</th>
              {showChannel ? <th>Channel</th> : null}
              <th>Status</th>
              {showStore ? <th>Store</th> : null}
              <th>Total</th>
              <th>Paid</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedInvoices.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.invoice_number}</td>
                {showChannel ? <td>{channelLabel(inv.sales_channel)}</td> : null}
                <td>{saleWords(inv.status)}</td>
                {showStore ? <td>{storeName(inv.store_id) || '—'}</td> : null}
                <td>{formatNumber(inv.total_amount, displayFmt)}</td>
                <td>{formatNumber(inv.paid_amount, displayFmt)}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(inv)} aria-label={`View sales invoice ${inv.id}`}>View</button>
                  {inv.status === 'draft' && (
                    <>
                      <button
                        type="button"
                        className="btn-ok"
                        onClick={() => postInvoice(inv)}
                        aria-label={`Post sales invoice ${inv.id}`}
                      >
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
                        aria-label="Print sales invoice A4"
                      >
                        Print
                      </button>
                      <button
                        onClick={() =>
                          downloadInvoicePdf(inv.id, inv.invoice_number, 'thermal', '80mm')
                            .then(() => setMessage(`Downloaded thermal ${inv.invoice_number}`))
                            .catch((err) => setError(err.message))
                        }
                        aria-label="Print sales invoice thermal"
                      >
                        Receipt
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
                      {inv.days_overdue} days overdue
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
                        aria-label={`Sales invoice pay amount ${inv.invoice_number || inv.id}`}
                      />
                      <button
                        onClick={() => {
                          setSelected(inv);
                          pay();
                        }}
                        aria-label={`Pay sales invoice ${inv.id}`}
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
                <td colSpan={invoiceCols} className="muted">
                  {invoices.length === 0
                    ? 'No invoices yet'
                    : 'No sales invoices for this filter'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
        </>
      )}

      {tab === 'coupons' && (
        <div className="card cat-panel">
          <h3>Coupons</h3>
          <div className="erp-form-grid" style={{ marginBottom: 12 }}>
            <input value={newCouponCode} onChange={(e) => setNewCouponCode(e.target.value.toUpperCase())} placeholder="Code" aria-label="New coupon code" />
            <input value={newCouponName} onChange={(e) => setNewCouponName(e.target.value)} placeholder="Name" aria-label="New coupon name" />
            <select value={newCouponType} onChange={(e) => setNewCouponType(e.target.value as 'fixed' | 'percent')} aria-label="New coupon type">
              <option value="percent">Percent</option>
              <option value="fixed">Fixed</option>
            </select>
            <input value={newCouponAmount} onChange={(e) => setNewCouponAmount(e.target.value)} placeholder="Amount" aria-label="New coupon amount" />
            <input value={newCouponMin} onChange={(e) => setNewCouponMin(e.target.value)} placeholder="Min spend" aria-label="New coupon min spend" />
            <button
              type="button"
              onClick={async () => {
                setError('');
                try {
                  await api('/sales/coupons', {
                    method: 'POST',
                    body: JSON.stringify({
                      code: newCouponCode.trim(),
                      name: newCouponName.trim(),
                      discount_type: newCouponType,
                      amount: Number(newCouponAmount),
                      min_spend: Number(newCouponMin) || 0,
                    }),
                  });
                  setNewCouponCode('');
                  setNewCouponName('');
                  await refresh();
                  setMessage('Coupon saved');
                } catch (err: any) {
                  setError(err.message);
                }
              }}
              aria-label="Save coupon"
            >
              Save coupon
            </button>
          </div>
          <div className="list-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Amount</th>
                  <th>Min spend</th>
                  <th>Active</th>
                  <th>Used</th>
                </tr>
              </thead>
              <tbody>
                {coupons.map((c) => (
                  <tr key={c.id}>
                    <td>{c.code}</td>
                    <td>{c.name}</td>
                    <td>{saleWords(c.discount_type)}</td>
                    <td>{formatNumber(c.amount, displayFmt)}</td>
                    <td>{formatNumber(c.min_spend, displayFmt)}</td>
                    <td>{c.is_active ? 'Yes' : 'No'}</td>
                    <td>{c.redemption_count ?? 0}</td>
                  </tr>
                ))}
                {coupons.length === 0 && (
                  <tr>
                    <td colSpan={7} className="muted">
                      No coupons yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'returns' && (
        <>
          <div style={{ marginBottom: 12 }}>
            <button type="button" className="btn-primary" onClick={() => setReturnCreateOpen(true)} aria-label="Create return">
              Create return
            </button>
          </div>
          {returnCreateOpen ? (
          <FormModal
            title="Create return"
            busy={saveBusy}
            dirty={Boolean(invoiceId || returnReason || returnCondition || returnNotes.trim())}
            onClose={() => setReturnCreateOpen(false)}
          >
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
                {saleWords(r)}
              </option>
            ))}
          </select>
          <select
            value={returnCondition}
            onChange={(e) => setReturnCondition(e.target.value)}
            aria-label="Return condition"
          >
            <option value="">Select condition</option>
            <option value="sellable">Good to sell again</option>
            <option value="discard">Do not restock</option>
          </select>
          <label>
            <input type="checkbox" checked={restock} onChange={(e) => setRestock(e.target.checked)} aria-label="Sales return restock" /> Restock
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
            disabled={!invoiceId || !productId || !returnReason || !returnCondition || saveBusy}
            aria-label="Create sales return"
          >
            {saveBusy ? 'Saving…' : 'Create return'}
          </button>
        </div>
            </div>
          </FormModal>
          ) : null}
          <details className="sales-more" style={{ marginBottom: 12 }}>
            <summary>Cancel a return</summary>
          <div className="card sales-more-body">
            <label>
              Cancel reason{' '}
              <input
                value={srCancelReason}
                onChange={(e) => setSrCancelReason(e.target.value)}
                placeholder="Required before Cancel"
                aria-label="Sales return cancel reason"
              />
            </label>
          </div>
          </details>
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
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedReturns.map((r) => (
              <tr key={r.id}>
                <td>{r.return_number}</td>
                <td>{r.credit_note_number || '—'}</td>
                <td>{saleWords(r.status)}</td>
                <td>
                  {r.settlement_method ? saleWords(r.settlement_method) : '—'}
                  {r.refunded_amount > 0 ? ` · ${formatNumber(r.refunded_amount, displayFmt)}` : ''}
                </td>
                <td>{saleWords(r.reason)}</td>
                <td>{formatNumber(r.total_amount, displayFmt)}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  <button onClick={() => setSelected(r)} aria-label={`View sales return ${r.id}`}>View</button>
                  {r.status === 'draft' && (
                    <>
                      <button
                        type="button"
                        className="btn-ok"
                        aria-label={`Post sales return credit ${r.id}`}
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
                        aria-label={`Post sales return refund ${r.id}`}
                        onClick={() =>
                          act(`/sales/returns/${r.id}/post`, 'Posted (refund)', {
                            settlement_method: 'refund',
                            payment_method: 'cash',
                          })
                        }
                      >
                        Post + refund
                      </button>
                      <button
                        className="btn-danger"
                        onClick={() => act(`/sales/returns/${r.id}/cancel`, 'Cancelled')}
                        aria-label={`Cancel sales return ${r.id}`}
                      >
                        Cancel
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
            {managedReturns.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
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
        <div className="sales-drawer-backdrop" onClick={() => setSelected(null)}>
        <div className="sales-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Document details">
          <div className="sales-drawer-head">
            <h2>
              {selected.invoice_number || selected.quotation_number || selected.order_number || selected.return_number || 'Document'} — {saleWords(selected.status)}
              {selected.invoice_number ? (
                <span style={{ display: 'inline-flex', gap: 8, marginLeft: 12 }}>
                  <button
                    type="button"
                    onClick={() => previewInvoicePdf(selected.id, 'a4').catch((err) => alert(err.message))}
                    aria-label="Preview invoice"
                  >
                    Preview
                  </button>
                  <button
                    type="button"
                    onClick={() => downloadInvoicePdf(selected.id, selected.invoice_number, 'a4')}
                    aria-label="Print invoice A4"
                  >
                    Print invoice
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      downloadInvoicePdf(selected.id, selected.invoice_number, 'thermal', '80mm')
                    }
                    aria-label="Print invoice thermal"
                  >
                    Thermal
                  </button>
                </span>
              ) : null}
            </h2>
            <button type="button" onClick={() => setSelected(null)}>Close</button>
          </div>
          {(error || message) ? (
            <p className={error ? 'sales-flash sales-flash-err' : 'sales-flash sales-flash-ok'} role={error ? 'alert' : undefined}>
              {error || message}
            </p>
          ) : null}
          {selected.emailed_to && (
            <p className="muted" style={{ marginBottom: 8 }}>
              Last emailed to {selected.emailed_to}
              {selected.emailed_at ? ` · ${formatWhen(selected.emailed_at, displayFmt)}` : ''}
            </p>
          )}
          {(selected.invoice_date || selected.due_date || selected.valid_until || selected.delivery_date) ? (
            <p className="muted" style={{ marginBottom: 8 }}>
              {[
                selected.invoice_date ? `Invoice ${formatWhen(selected.invoice_date, displayFmt)}` : '',
                selected.due_date ? `Due ${formatWhen(selected.due_date, displayFmt)}` : '',
                selected.valid_until ? `Valid until ${formatWhen(selected.valid_until, displayFmt)}` : '',
                selected.delivery_date ? `Delivery ${formatWhen(selected.delivery_date, displayFmt)}` : '',
              ].filter(Boolean).join(' · ')}
            </p>
          ) : null}
          {selected.notes ? <p style={{ marginBottom: 8 }}>{selected.notes}</p> : null}
          {selected.rejection_reason ? (
            <p className="muted" style={{ marginBottom: 8 }}>Rejected: {selected.rejection_reason}</p>
          ) : null}
          {showChannel && selected.sales_channel ? (
            <p className="muted" style={{ marginBottom: 8 }}>
              Channel {channelLabel(selected.sales_channel)}
              {selected.delivery_note_number ? ` · Delivery note ${selected.delivery_note_number}` : ''}
            </p>
          ) : null}
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th>SKU</th>
                <th>Qty</th>
                {showFilled ? <th>Filled</th> : null}
                <th>Price</th>
                <th>Tax</th>
                <th>Discount</th>
                {showCondition ? <th>Condition</th> : null}
                <th>Tax amount</th>
                <th>Line total</th>
              </tr>
            </thead>
            <tbody>
              {drawerLines.map((it) => {
                const prod = products.find((p) => p.id === it.product_id);
                return (
                <tr key={it.id}>
                  <td>
                    {prod?.name || 'Product'}
                    {it.is_reverse_charge ? ' · Reverse charge' : ''}
                  </td>
                  <td>{prod?.sku || '—'}</td>
                  <td>{formatNumber(it.quantity, displayFmt)}</td>
                  {showFilled ? <td>{it.qty_fulfilled != null ? formatNumber(it.qty_fulfilled, displayFmt) : '—'}</td> : null}
                  <td>{formatNumber(it.unit_price, displayFmt)}</td>
                  <td>{it.tax_rate != null ? `${formatNumber(it.tax_rate, displayFmt)}%` : '—'}</td>
                  <td>
                    {formatNumber(it.discount ?? 0, displayFmt)}
                    {it.discount_type === 'percent' ? ` (${formatNumber(it.discount_percent, displayFmt)}%)` : ''}
                  </td>
                  {showCondition ? <td>{it.condition ? saleWords(it.condition) : '—'}</td> : null}
                  <td>
                    {formatNumber(it.line_tax ?? 0, displayFmt)}
                    {(it.tax_components || []).length
                      ? ` (${(it.tax_components || [])
                          .map((c) => `${c.name || saleWords(c.code)} ${formatNumber(c.amount, displayFmt)}`)
                          .join(', ')})`
                      : ''}
                  </td>
                  <td>{formatNumber(it.line_total, displayFmt)}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
          {selected.order_number && selected.can_fulfill ? (
            <div style={{ marginTop: 12 }}>
              <h4 style={{ margin: '8px 0' }}>Partial fill</h4>
              <p className="muted">Record quantity shipped now. Stock still moves when the invoice posts.</p>
              {(selected.items || []).map((it: any) => {
                const prod = products.find((p) => p.id === it.product_id);
                const remaining = Math.max(Number(it.quantity || 0) - Number(it.qty_fulfilled || 0), 0);
                return (
                  <label key={it.id} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                    <span>{prod?.name || it.product_id}</span>
                    <span className="muted">remaining {remaining}</span>
                    <input
                      value={fulfillQty[it.product_id] || ''}
                      onChange={(e) =>
                        setFulfillQty((prev) => ({ ...prev, [it.product_id]: e.target.value }))
                      }
                      placeholder="Qty"
                      aria-label={`Fill quantity for ${prod?.name || it.product_id}`}
                      style={{ width: 80 }}
                    />
                  </label>
                );
              })}
              <button
                type="button"
                onClick={() => {
                  const items = (selected.items || [])
                    .map((it: any) => ({
                      product_id: it.product_id,
                      quantity: Number(fulfillQty[it.product_id] || 0),
                    }))
                    .filter((it: { quantity: number }) => it.quantity > 0);
                  if (!items.length) {
                    setError('Enter a fill quantity for at least one line');
                    return;
                  }
                  setFulfillQty({});
                  act(`/sales/orders/${selected.id}/fulfill`, 'Filled', { items });
                }}
                aria-label="Record partial fill"
              >
                Record fill
              </button>
            </div>
          ) : null}
          <div className="grid" style={{ marginTop: 12 }}>
            <div className="card">
              <div className="muted">Subtotal</div>
              <div className="kpi">{formatNumber(selected.subtotal ?? 0, displayFmt)}</div>
            </div>
            <div className="card">
              <div className="muted">Tax</div>
              <div className="kpi">{formatNumber(selected.tax_amount ?? 0, displayFmt)}</div>
            </div>
            <div className="card">
              <div className="muted">Discount</div>
              <div className="kpi">
                {formatNumber(selected.discount_amount ?? 0, displayFmt)}
                {selected.discount_type === 'percent' ? ` (${formatNumber(selected.discount_percent, displayFmt)}%)` : ''}
              </div>
            </div>
            <div className="card">
              <div className="muted">Total</div>
              <div className="kpi">{formatNumber(selected.total_amount ?? 0, displayFmt)}</div>
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
                      <td>{formatNumber(r.tax_rate, displayFmt)}%</td>
                      <td>{formatNumber(r.taxable, displayFmt)}</td>
                      <td>{formatNumber(r.tax, displayFmt)}</td>
                      <td>{r.is_reverse_charge ? 'Reverse charge' : 'Standard'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {selected.reverse_charge_tax > 0 && (
                <p className="muted">
                  Reverse-charge tax: {formatNumber(selected.reverse_charge_tax, displayFmt)}
                  {selected.is_reverse_charge ? ' · This document is reverse charge' : ''}
                </p>
              )}
            </div>
          )}
        </div>
        </div>
      )}
    </div>
  );
}
