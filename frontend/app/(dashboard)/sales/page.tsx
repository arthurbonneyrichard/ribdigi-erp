'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import FormModal from '../../../components/FormModal';
import CustomerGroupsWindow from '../../../components/CustomerGroupsWindow';
import PageHeader from '../../../components/PageHeader';
import PartyContactsPanel from '../../../components/PartyContactsPanel';
import RowActions, { type RowActionItem } from '../../../components/RowActions';
import StatusChip from '../../../components/StatusChip';
import { api, apiFetch } from '../../../lib/api';
import { openDocumentPrint } from '../../../lib/documentPrint';
import { createPaintGet, peekPrefetch } from '../../../lib/prefetchCache';
import { openReceiptPrintWindow } from '../../../lib/posReceiptPrint';
import { formatMoney, formatNumber, formatWhen, plainLabel, type FormatPrefs } from '../../../lib/format';
import { AmountField } from '../../../components/AmountField';
import { useCompanyFormat } from '../../../lib/useCompanyFormat';
import { getMe } from '../../../lib/meCache';
import { usesWholesaleTrade } from '../../../lib/industries';
import { useStoreContext } from '../../../lib/storeContext';
import './sales-ui.css';

type Tab = 'customers' | 'quotations' | 'orders' | 'invoices' | 'returns' | 'coupons' | 'giftcards' | 'made';

const SALES_TABS: Tab[] = ['customers', 'quotations', 'orders', 'invoices', 'returns', 'coupons', 'giftcards', 'made'];

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

async function downloadInvoicePdf(
  invoiceId: string,
  invoiceNumber: string,
  template: 'a4' | 'thermal',
  paper = '80mm'
) {
  const qs =
    template === 'thermal'
      ? `template=thermal&format=pdf&paper=${encodeURIComponent(paper)}`
      : 'template=a4&format=pdf';
  const res = await apiFetch(`/sales/invoices/${invoiceId}/print?${qs}`);
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

async function previewInvoicePdf(invoiceId: string, template: 'a4' | 'thermal', paper = '80mm') {
  const qs =
    template === 'thermal'
      ? `template=thermal&format=pdf&paper=${encodeURIComponent(paper)}`
      : 'template=a4&format=pdf';
  const res = await apiFetch(`/sales/invoices/${invoiceId}/print?${qs}`);
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
  const [tab, setTab] = useState<Tab>('invoices');
  const [madeSales, setMadeSales] = useState<any[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [invoiceManageFilter, setInvoiceManageFilter] = useState<
    'all' | 'draft' | 'posted' | 'sent' | 'partial' | 'paid' | 'overdue' | 'cancelled'
  >('all');
  const [invoicePaper, setInvoicePaper] = useState<'a4' | '80mm' | '58mm'>('a4');
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
  const [useGroupPrice, setUseGroupPrice] = useState(true);
  const [productId, setProductId] = useState('');
  const [variantId, setVariantId] = useState('');
  const [unitId, setUnitId] = useState('');
  const [units, setUnits] = useState<any[]>([]);
  const [qty, setQty] = useState('1');
  const [unitPrice, setUnitPrice] = useState('0');
  const [addedLines, setAddedLines] = useState<{ label: string; qty: number; price: number; item: any }[]>([]);
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
  const [payAmounts, setPayAmounts] = useState<Record<string, string>>({});
  const [composerKind, setComposerKind] = useState<'invoice' | 'quotation' | 'order'>('invoice');
  const [customerFormOpen, setCustomerFormOpen] = useState(false);
  const [groupsOpen, setGroupsOpen] = useState(false);
  const [couponFormOpen, setCouponFormOpen] = useState(false);
  const [giftAmount, setGiftAmount] = useState('');
  const [giftLookup, setGiftLookup] = useState('');
  const [giftIssued, setGiftIssued] = useState<{ code: string; balance: number; status: string } | null>(null);
  const [giftFound, setGiftFound] = useState<{ code: string; balance: number; status: string } | null>(null);
  const [deliveryDate, setDeliveryDate] = useState('');
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [reprintingId, setReprintingId] = useState('');
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

  const paintGet = useMemo(() => createPaintGet(), []);

  async function refresh() {
    const get = paintGet.get;
    const peekInv = peekPrefetch('/sales/invoices');
    if (peekInv?.data) setInvoices(peekInv.data || []);
    const peekCust = peekPrefetch('/customers');
    if (peekCust?.data) setCustomers(peekCust.data || []);
    const peekProd = peekPrefetch('/products');
    if (peekProd?.data) setProducts(peekProd.data || []);
    const [madeRes, invRes, custRes, prodRes, unitRes, qRes, oRes, rRes, storeRes, settingsRes, groupRes, tenantRes, couponRes] =
      await Promise.all([
        get('/sales/made').catch(() => ({ data: [] })),
        get('/sales/invoices'),
        get('/customers'),
        get('/products'),
        get('/catalog/units').catch(() => ({ data: [] })),
        get('/sales/quotations'),
        get('/sales/orders'),
        get('/sales/returns'),
        get('/stores').catch(() => ({ data: [] })),
        get('/sales/settings').catch(() => ({ data: null })),
        get('/customers/groups').catch(() => ({ data: [] })),
        get('/tenants/me').catch(() => ({ data: null })),
        get('/sales/coupons').catch(() => ({ data: [] })),
      ]);
    paintGet.done();
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
    if (!composerOpen) setAddedLines([]);
  }, [composerOpen]);

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
  const currentLine = {
    product_id: productId.trim(),
    variant_id: variantId.trim() || null,
    unit_id: unitId.trim() || null,
    quantity: Number(qty),
    ...(useGroupPrice ? {} : { unit_price: Number(unitPrice) }),
    tax_rate: taxRate === '' ? null : Number(taxRate),
    discount: lineDiscountType === 'percent' ? 0 : lineDisc,
    discount_type: lineDiscountType,
    discount_percent: lineDiscountType === 'percent' ? Math.max(0, Math.min(100, lineDisc)) : 0,
  };
  // Lines already added with "Add line", plus the line being typed (when a product is chosen).
  const lineItems = [...addedLines.map((l) => l.item), ...(productId.trim() || !addedLines.length ? [currentLine] : [])];

  function addLine() {
    if (!productId.trim() || !(Number(qty) > 0)) {
      setError('Choose a product and a quantity first');
      return;
    }
    setError('');
    const prod = products.find((p) => p.id === productId);
    const variant = variants.find((v) => v.id === variantId);
    const label = [prod?.name || 'Product', variant?.name].filter(Boolean).join(' · ');
    setAddedLines((prev) => [...prev, { label, qty: Number(qty), price: Number(unitPrice) || 0, item: currentLine }]);
    setProductId('');
    setVariantId('');
    setUnitId('');
    setQty('1');
    setUnitPrice('0');
    setTaxRate('');
    setLineDiscount('');
  }

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

  /** Load one customer's details into the form, or clear it for a new customer. */
  function fillCustomerForm(c: any | null) {
    setCustomerId(c?.id || '');
    setCustomerName(c?.name || '');
    setCustomerCode(c?.code || '');
    setCustomerEmail(c?.email || '');
    setCustomerPhone(c?.phone || '');
    setCustomerAddress(c?.address || '');
    setCustomerProfileType(c?.profile_type || 'registered');
    setCustomerCategory(c?.category || '');
    setCustomerStatus(c?.status || 'active');
    setCustomerLat(c?.latitude == null ? '' : String(c.latitude));
    setCustomerLng(c?.longitude == null ? '' : String(c.longitude));
    setCustomerGroupId(c?.customer_group_id || '');
    setCreditLimit(String(c?.credit_limit ?? 0));
    setPaymentTermsDays(String(c?.payment_terms_days ?? 30));
  }

  function openCustomerForm(c: any | null) {
    fillCustomerForm(c);
    setError('');
    setMessage('');
    setComposerOpen(false);
    setCustomerFormOpen(true);
  }

  async function saveCustomer() {
    if (saveBusy || !customerId) return;
    setError('');
    setSaveBusy(true);
    try {
      const r = await api(`/customers/${customerId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: customerName.trim(),
          code: customerCode.trim() || undefined,
          profile_type: customerProfileType || 'registered',
          category: customerCategory.trim() || undefined,
          status: customerStatus || 'active',
          email: customerEmail.trim() || undefined,
          phone: customerPhone.trim() || undefined,
          address: customerAddress.trim() || undefined,
          latitude: customerLat === '' ? undefined : Number(customerLat),
          longitude: customerLng === '' ? undefined : Number(customerLng),
          credit_limit: Number(creditLimit) || 0,
          payment_terms_days: Number(paymentTermsDays) || 0,
          customer_group_id: customerGroupId.trim() || null,
        }),
      });
      await refresh();
      setCustomerFormOpen(false);
      setMessage(`${r.data?.name || 'Customer'} saved`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaveBusy(false);
    }
  }

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
      setCustomerFormOpen(false);
      setMessage(`${r.data?.name || 'Customer'} added`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaveBusy(false);
    }
  }

  async function setCustomerActive(isActive: boolean, id = customerId) {
    if (!id) {
      setError('Select a customer first');
      return;
    }
    setError('');
    try {
      const r = await api(`/customers/${id}`, {
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

  function applyReturnLine(line: { product_id?: string; variant_id?: string | null; quantity?: number } | undefined) {
    if (!line?.product_id) return;
    setProductId(String(line.product_id));
    setVariantId(line.variant_id ? String(line.variant_id) : '');
    setQty(String(line.quantity ?? 1));
  }

  function openReturnForInvoice(inv: { id: string; items?: any[] }) {
    setInvoiceId(inv.id);
    applyReturnLine(inv.items?.[0]);
    setTab('returns');
    setReturnCreateOpen(true);
  }

  async function reprintSale(row: {
    id: string;
    source?: string;
    invoice_id?: string | null;
    number?: string;
  }) {
    if (reprintingId) return;
    setError('');
    setMessage('');
    setReprintingId(row.id);
    const isRegister = row.source === 'register';
    const sourceId = isRegister ? row.id : row.invoice_id || row.id;
    try {
      let printed = false;
      try {
        const queued = await api('/printers/reprint', {
          method: 'POST',
          body: JSON.stringify({
            source_type: isRegister ? 'pos_sale' : 'sales_invoice',
            source_id: sourceId,
            purposes: isRegister ? ['customer_receipt'] : ['invoice'],
          }),
        });
        const jobs = Array.isArray(queued.data) ? queued.data : [];
        if (
          jobs.some(
            (job: { purpose?: string; status?: string }) =>
              (job.purpose === 'customer_receipt' || job.purpose === 'invoice') &&
              job.status === 'printed'
          )
        ) {
          printed = true;
        }
        const browser = printed
          ? undefined
          : jobs.find(
              (job: { id?: string; purpose?: string; status?: string }) =>
                (job.purpose === 'customer_receipt' || job.purpose === 'invoice') &&
                job.status === 'browser_pending' &&
                job.id
            );
        if (browser?.id) {
          const detail = await api(`/printers/jobs/${browser.id}`);
          const payload = detail.data?.payload || {};
          printed = openReceiptPrintWindow(payload.html, payload.text || '');
          if (printed) {
            await api(`/printers/jobs/${browser.id}/browser-ack`, {
              method: 'POST',
              body: JSON.stringify({ status: 'printed' }),
            });
          }
        }
      } catch {
        printed = false;
      }
      if (!printed) {
        if (isRegister) {
          const receipt = await api(`/pos/sales/${row.id}/receipt`);
          printed = openReceiptPrintWindow(receipt.data?.html, receipt.data?.text || '');
        } else if (invoicePaper === 'a4') {
          await previewInvoicePdf(sourceId, 'a4');
          printed = true;
        } else {
          const paper = invoicePaper === '58mm' ? '58mm' : '80mm';
          const printedDoc = await api(
            `/sales/invoices/${sourceId}/print?template=thermal&format=json&paper=${encodeURIComponent(paper)}`
          );
          printed = openReceiptPrintWindow(
            printedDoc.data?.html,
            String(printedDoc.data?.text || '')
          );
        }
      }
      if (!printed) throw new Error('Reprint could not open the print dialog.');
      setMessage(`Reprinted ${row.number || ''}`.trim());
    } catch (err: any) {
      setError(err?.message || 'Reprint could not open the print dialog.');
    } finally {
      setReprintingId('');
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
        (path.includes('/quotations/')
          || path.includes('/invoices/')
          || path.includes('/orders/')
          || path.includes('/returns/')) &&
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

  async function pay(inv: { id: string; customer_id?: string | null }, amountRaw: string) {
    if (!inv?.id || !inv.customer_id) {
      setError('This invoice has no customer to record a payment against');
      return;
    }
    const amountText = String(amountRaw ?? '').trim();
    const amount = Number(amountText);
    if (!amountText || !Number.isFinite(amount) || amount <= 0) {
      setError('Enter a pay amount');
      return;
    }
    setError('');
    try {
      const r = await api('/sales/payments', {
        method: 'POST',
        body: JSON.stringify({
          customer_id: inv.customer_id,
          sales_invoice_id: inv.id,
          amount,
        }),
      });
      setMessage(r.message || 'Payment recorded');
      setPayAmounts((prev) => {
        const next = { ...prev };
        delete next[inv.id];
        return next;
      });
      await refresh();
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function issueGiftCard() {
    const amountText = giftAmount.trim();
    const amount = Number(amountText);
    if (!amountText || !Number.isFinite(amount) || amount <= 0) {
      setError('Enter a gift card amount');
      return;
    }
    setError('');
    setGiftIssued(null);
    try {
      const res = await api('/gift-cards', {
        method: 'POST',
        body: JSON.stringify({ amount }),
      });
      setGiftIssued(res.data);
      setGiftAmount('');
      setMessage('Gift card issued. The balance stays a liability until the code is spent at the register.');
    } catch (err: any) {
      setError(err.message || 'Could not issue the gift card');
    }
  }

  async function lookupGiftCard() {
    const code = giftLookup.trim();
    if (!code) {
      setError('Enter the gift card code');
      setGiftFound(null);
      return;
    }
    setError('');
    setGiftFound(null);
    try {
      const res = await api(`/gift-cards/${encodeURIComponent(code)}`);
      setGiftFound(res.data);
    } catch (err: any) {
      setError(err.message || 'Gift card not found');
    }
  }

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
  const customerNameOf = (id?: string | null) => customers.find((c) => c.id === id)?.name || '—';
  const quoteCols = 6 + (showChannel ? 1 : 0) + (showQuoteReject ? 1 : 0);
  const orderCols = 6 + (showChannel ? 1 : 0) + (showStore ? 1 : 0) + (showReserved ? 1 : 0);
  const invoiceCols = 6 + (showChannel ? 1 : 0) + (showStore ? 1 : 0);
  function printInvoice(invoiceId: string, invoiceNumber: string, variant: 'list' | 'drawer' = 'list') {
    const paper = invoicePaper;
    const fail = (err: { message?: string }) => {
      const text = err?.message || 'Print failed';
      if (variant === 'drawer') alert(text);
      else setError(text);
    };
    const task =
      paper === 'a4'
        ? downloadInvoicePdf(invoiceId, invoiceNumber, 'a4')
        : downloadInvoicePdf(invoiceId, invoiceNumber, 'thermal', paper);
    task
      .then(() =>
        setMessage(
          paper === 'a4' ? `Downloaded A4 ${invoiceNumber}` : `Downloaded ${paper} receipt ${invoiceNumber}`
        )
      )
      .catch(fail);
  }

  function previewInvoice(invoiceId: string, variant: 'list' | 'drawer' = 'list') {
    const paper = invoicePaper;
    const fail = (err: { message?: string }) => {
      const text = err?.message || 'Print failed';
      if (variant === 'drawer') alert(text);
      else setError(text);
    };
    previewInvoicePdf(invoiceId, paper === 'a4' ? 'a4' : 'thermal', paper === '58mm' ? '58mm' : '80mm').catch(fail);
  }

  function invoicePaperBar() {
    return (
      <div className="sales-paper-bar">
        <label className="print-ui-paper">
          Paper
          <select
            value={invoicePaper}
            onChange={(e) => {
              const next = e.target.value;
              setInvoicePaper(next === '58mm' || next === '80mm' ? next : 'a4');
            }}
            aria-label="Sales invoice paper size"
          >
            <option value="a4">A4 invoice</option>
            <option value="80mm">80mm receipt</option>
            <option value="58mm">58mm receipt</option>
          </select>
        </label>
        <p className="print-ui-help">
          Choose A4 for a full invoice, or 58mm or 80mm for a receipt slip. Print from the row menu uses this size.
        </p>
      </div>
    );
  }

  function invoicePrintControls(invoiceId: string, invoiceNumber: string, variant: 'list' | 'drawer') {
    if (variant === 'list') {
      return (
        <div className="print-ui-actions">
          <button
            type="button"
            className="btn-ok"
            aria-label={invoicePaper === 'a4' ? 'Print sales invoice A4' : 'Print sales invoice thermal'}
            onClick={() => printInvoice(invoiceId, invoiceNumber, 'list')}
          >
            {invoicePaper === 'a4' ? 'Print A4' : `Print ${invoicePaper}`}
          </button>
          <button type="button" onClick={() => previewInvoice(invoiceId, 'list')} aria-label={`Preview sales invoice ${invoiceId}`}>
            Preview
          </button>
        </div>
      );
    }
    return (
      <div className="print-ui-row">
        <label className="print-ui-paper">
          Paper
          <select
            value={invoicePaper}
            onChange={(e) => {
              const next = e.target.value;
              setInvoicePaper(next === '58mm' || next === '80mm' ? next : 'a4');
            }}
            aria-label="Invoice paper size"
          >
            <option value="a4">A4 invoice</option>
            <option value="80mm">80mm receipt</option>
            <option value="58mm">58mm receipt</option>
          </select>
        </label>
        <div className="print-ui-actions">
          <button
            type="button"
            className="btn-ok"
            aria-label={invoicePaper === 'a4' ? 'Print invoice A4' : 'Print invoice thermal'}
            onClick={() => printInvoice(invoiceId, invoiceNumber, 'drawer')}
          >
            {invoicePaper === 'a4' ? 'Print A4 invoice' : `Print ${invoicePaper} receipt`}
          </button>
          <button type="button" onClick={() => previewInvoice(invoiceId, 'drawer')} aria-label="Preview invoice">
            Preview
          </button>
        </div>
      </div>
    );
  }

  const drawerLines: any[] = selected?.items || [];
  const showFilled = drawerLines.some((it) => it.qty_fulfilled != null && it.qty_fulfilled !== '');
  const showCondition = drawerLines.some((it) => Boolean(it.condition));

  const numberingPanel = (
    <details className="sales-ui-settings">
            <summary>Numbering</summary>
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
  );

  function openComposer(kind: 'invoice' | 'quotation' | 'order') {
    setComposerKind(kind);
    setCustomerFormOpen(false);
    setComposerOpen(true);
  }

  return (
    <div className="sales-desk work sales-ui-page">
      <PageHeader className="sales-desk-head" title="Sales">
        <p className="sales-ui-path">
          <span>1 Customers</span>
          <span>2 Quotes</span>
          <span>3 Orders</span>
          <span>4 Invoices</span>
          <span>5 Returns</span>
        </p>
        <p className="sales-ui-note">
          {wholesaleOps
            ? 'Quotes and orders are not sales until they are invoiced. Coupons and gift cards are codes, not a card charge.'
            : 'Coupons and gift cards are codes, not a card charge.'}
        </p>
      </PageHeader>

      <nav className="sales-toolbar sales-ui-nav" aria-label="Sales workflow">
        {(
          [
            ['customers', 'Customers'],
            ['quotations', 'Quotes'],
            ['orders', 'Orders'],
            ['invoices', 'Invoices'],
            ['returns', 'Returns'],
            ['coupons', 'Coupons'],
            ['giftcards', 'Gift cards'],
            ['made', 'All sales'],
          ] as [Tab, string][]
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? 'sales-tab is-on' : 'sales-tab'}
            onClick={() => setTab(id)}
            disabled={tab === id}
            aria-label={`Show sales ${id} tab`}
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
      </nav>
      {(error || message) && !composerOpen && !selected ? (
        <p className={error ? 'sales-flash sales-flash-err' : 'sales-flash sales-flash-ok'} role={error ? 'alert' : undefined}>
          {error || message}
        </p>
      ) : null}

      {(composerOpen || customerFormOpen) ? (
      <FormModal
        title={composerOpen ? 'New document' : customerId ? 'Edit customer' : 'New customer'}
        busy={saveBusy}
        dirty={Boolean(customerName.trim() || customerId || productId || docNotes.trim() || qty !== '1')}
        onClose={() => {
          setComposerOpen(false);
          setCustomerFormOpen(false);
        }}
      >
        {(error || message) ? (
          <p className={error ? 'sales-flash sales-flash-err' : 'sales-flash sales-flash-ok'} role={error ? 'alert' : undefined}>
            {error || message}
          </p>
        ) : null}
      <div className="erp-split">
        {customerFormOpen && !composerOpen ? (
        <div className="card cust-form">
          <div className="form-grid">
            <div className="field span-2">
              <label htmlFor="cust-name">Name</label>
              <input
                id="cust-name"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="e.g. Kofi Mensah or Adom Traders"
                aria-label="Customer name"
              />
            </div>
            <div className="field">
              <label htmlFor="cust-phone">Phone</label>
              <input
                id="cust-phone"
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                placeholder="+233 24 000 0000"
                aria-label="Customer phone"
              />
            </div>
            <div className="field">
              <label htmlFor="cust-email">Email</label>
              <input
                id="cust-email"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                placeholder="name@example.com"
                aria-label="Customer email"
              />
            </div>
            <div className="field span-2">
              <label htmlFor="cust-address">Address</label>
              <input
                id="cust-address"
                value={customerAddress}
                onChange={(e) => setCustomerAddress(e.target.value)}
                placeholder="Street, town"
                aria-label="Customer address"
              />
            </div>
            <div className="field span-2">
              <label htmlFor="cust-group">Customer group</label>
              <select
                id="cust-group"
                value={customerGroupId}
                onChange={(e) => setCustomerGroupId(e.target.value)}
                aria-label="Customer group"
              >
                <option value="">No group (normal prices)</option>
                {groups
                  .filter((g) => g.is_active !== false || g.id === customerGroupId)
                  .map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name} · {Number(g.discount_percent || 0)}% off{g.is_active === false ? ' [inactive]' : ''}
                    </option>
                  ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="cust-credit">Credit limit</label>
              <input
                id="cust-credit"
                value={creditLimit}
                onChange={(e) => setCreditLimit(e.target.value)}
                inputMode="decimal"
                placeholder="0 = pays now"
                aria-label="Customer credit limit"
              />
            </div>
            <div className="field">
              <label htmlFor="cust-terms">Days to pay</label>
              <input
                id="cust-terms"
                value={paymentTermsDays}
                onChange={(e) => setPaymentTermsDays(e.target.value)}
                inputMode="numeric"
                title="Payment terms (days)"
                aria-label="Customer payment terms days"
              />
            </div>
          </div>
          <details className="sales-more cust-more">
            <summary>More details</summary>
            <div className="form-grid">
            <div className="field">
              <label htmlFor="cust-code">Customer code</label>
              <input
                id="cust-code"
                value={customerCode}
                onChange={(e) => setCustomerCode(e.target.value)}
                placeholder="Optional"
                aria-label="Customer code"
              />
            </div>
            <div className="field">
              <label htmlFor="cust-type">Type</label>
              <select
                id="cust-type"
                value={customerProfileType}
                onChange={(e) => setCustomerProfileType(e.target.value)}
                aria-label="Customer profile type"
              >
                <option value="registered">Registered</option>
                <option value="walk_in">Walk-in</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="cust-category">Category</label>
              <input
                id="cust-category"
                value={customerCategory}
                onChange={(e) => setCustomerCategory(e.target.value)}
                placeholder="Optional"
                aria-label="Customer category"
              />
            </div>
            <div className="field">
              <label htmlFor="cust-status">Status</label>
              <select
                id="cust-status"
                value={customerStatus}
                onChange={(e) => setCustomerStatus(e.target.value)}
                aria-label="Customer status"
              >
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </select>
            </div>
            <div className="field">
              <label htmlFor="cust-lat">Latitude</label>
              <input
                id="cust-lat"
                value={customerLat}
                onChange={(e) => setCustomerLat(e.target.value)}
                inputMode="decimal"
                placeholder="Optional"
                aria-label="Customer latitude"
              />
            </div>
            <div className="field">
              <label htmlFor="cust-lng">Longitude</label>
              <input
                id="cust-lng"
                value={customerLng}
                onChange={(e) => setCustomerLng(e.target.value)}
                inputMode="decimal"
                placeholder="Optional"
                aria-label="Customer longitude"
              />
            </div>
            <div className="field">
              <label htmlFor="cust-currency">Invoice currency</label>
              <input
                id="cust-currency"
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                placeholder="Company currency"
                aria-label="Sales invoice currency"
                pattern="[A-Z]{3}"
                maxLength={3}
              />
            </div>
            <div className="field">
              <label htmlFor="cust-fx">Exchange rate</label>
              <input
                id="cust-fx"
                value={exchangeRate}
                onChange={(e) => setExchangeRate(e.target.value)}
                placeholder="Optional"
                aria-label="Sales invoice FX rate"
              />
            </div>
            </div>
          </details>
          {customerId && customerStatus === 'inactive' ? (
            <p className="muted" style={{ margin: 0 }}>
              Inactive customers are not offered on new sales. Their open invoices can still be paid.
            </p>
          ) : null}
          <div className="cust-actions">
            {customerId ? (
              <>
                <button type="button" className="btn-primary" onClick={saveCustomer} disabled={saveBusy || !customerName.trim()} aria-label="Save customer">
                  Save customer
                </button>
                <button type="button" className="sr-only" onClick={assignCustomerGroup} aria-label="Assign customer group" tabIndex={-1}>
                  Assign group
                </button>
                <button
                  type="button"
                  className={customerStatus === 'inactive' ? 'btn-ok' : 'btn-danger'}
                  aria-label="Toggle customer active status"
                  onClick={async () => {
                    const next = customerStatus === 'inactive';
                    await setCustomerActive(next);
                    setCustomerStatus(next ? 'active' : 'inactive');
                  }}
                >
                  {customerStatus === 'inactive' ? 'Activate customer' : 'Deactivate customer'}
                </button>
              </>
            ) : (
              <button type="button" className="btn-primary" onClick={createCustomer} disabled={saveBusy || !customerName.trim()} aria-label="Add customer">
                Add customer
              </button>
            )}
          </div>
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
        ) : null}
        {composerOpen ? (
        <div className="card sale-form">
          <div className="erp-stack" style={{ marginBottom: 0 }}>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="sale-customer">Customer</label>
            <select
              id="sale-customer"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              aria-label="Sale customer"
            >
              <option value="">Choose a customer</option>
              {customers
                .filter((c) => c.is_active !== false && (c.status || 'active') === 'active')
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
            </select>
          </div>
          {showStore && composerKind !== 'quotation' ? (
          <div className="field">
            <label htmlFor="sale-store">Store</label>
            <select
              id="sale-store"
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
          </div>
          ) : null}
          {composerKind === 'order' ? (
            <>
              <div className="field">
                <label htmlFor="sale-deliver-on">Deliver on</label>
                <input
                  id="sale-deliver-on"
                  type="date"
                  value={deliveryDate}
                  onChange={(e) => setDeliveryDate(e.target.value)}
                  aria-label="SO delivery date"
                  title="Promised delivery date for a sales order"
                />
              </div>
              <div className="field">
                <label htmlFor="sale-deliver-to">Deliver to</label>
                <input
                  id="sale-deliver-to"
                  value={deliveryAddress}
                  onChange={(e) => setDeliveryAddress(e.target.value)}
                  placeholder="Delivery address"
                  aria-label="SO delivery address"
                  title="Ship-to address for a sales order"
                />
              </div>
            </>
          ) : null}
        </div>

        <h4 className="sale-form-sub">Products</h4>
        {addedLines.length ? (
          <table className="table sale-form-lines">
            <thead>
              <tr>
                <th>Product</th>
                <th className="num">Qty</th>
                <th className="num">Price each</th>
                <th aria-label="Remove" />
              </tr>
            </thead>
            <tbody>
              {addedLines.map((l, i) => (
                <tr key={i}>
                  <td>{l.label}</td>
                  <td className="num">{l.qty}</td>
                  <td className="num">{l.price.toFixed(2)}</td>
                  <td className="num">
                    <button
                      type="button"
                      className="btn-danger"
                      aria-label={`Remove sale line ${i + 1}`}
                      onClick={() => setAddedLines((prev) => prev.filter((_, k) => k !== i))}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        <div className="form-grid sale-form-line">
          <div className="field span-2">
            <label htmlFor="sale-product">{addedLines.length ? 'Another product (optional)' : 'Product'}</label>
            <select
              id="sale-product"
              value={productId}
              onChange={(e) => setProductId(e.target.value)}
              aria-label="Sales product"
            >
              <option value="">Choose a product</option>
              {products
                .filter((p) => p.is_active !== false)
                .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} — {p.sku}
                </option>
              ))}
            </select>
          </div>
          {variants.length > 0 && (
            <div className="field">
              <label htmlFor="sale-variant">Size or colour</label>
              <select
                id="sale-variant"
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
            </div>
          )}
          <div className="field">
            <label htmlFor="sale-unit">Unit</label>
            <select
              id="sale-unit"
              value={unitId}
              onChange={(e) => setUnitId(e.target.value)}
              aria-label="Sales unit"
            >
              <option value="">Product&apos;s unit</option>
              {units.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.code}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="sale-qty">Quantity</label>
            <input
              id="sale-qty"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              placeholder="Qty"
              inputMode="decimal"
              aria-label="Line quantity"
            />
            {wholesaleOps && Number(products.find((p) => p.id === productId)?.min_order_qty || 0) > 0 ? (
              <span className="muted">
                Wholesale minimum {products.find((p) => p.id === productId)?.min_order_qty}
              </span>
            ) : null}
          </div>
          <div className="field">
            <label htmlFor="sale-price">Price each</label>
            <AmountField
              id="sale-price"
              currency={currency}
              value={unitPrice}
              onChange={(e) => {
                setUseGroupPrice(false);
                setUnitPrice(e.target.value);
              }}
              placeholder="Price"
              aria-label="Line unit price"
            />
            <label className="sale-form-check">
              <input
                type="checkbox"
                aria-label="Use customer group price"
                checked={useGroupPrice}
                onChange={(e) => setUseGroupPrice(e.target.checked)}
              />
              {wholesaleOps ? 'Use quantity price' : 'Use the customer group price'}
            </label>
          </div>
          <div className="field">
            <label htmlFor="sale-tax">Tax %</label>
            <input
              id="sale-tax"
              value={taxRate}
              onChange={(e) => setTaxRate(e.target.value)}
              placeholder="Product tax"
              inputMode="decimal"
              aria-label="Line tax percent"
            />
          </div>
          <div className="field sale-form-add">
            <button type="button" onClick={addLine} aria-label="Add sale line">
              + Add line
            </button>
          </div>
        </div>

        <details className="sales-more sale-form-more">
          <summary>Discounts and more</summary>
          <div className="form-grid">
            <div className="field">
              <label htmlFor="sale-line-disc">Discount on this line</label>
              <div className="sale-form-pair">
                <select
                  value={lineDiscountType}
                  onChange={(e) => setLineDiscountType(e.target.value === 'percent' ? 'percent' : 'fixed')}
                  aria-label="Line discount type"
                >
                  <option value="fixed">Amount</option>
                  <option value="percent">%</option>
                </select>
                {lineDiscountType === 'fixed' ? (
                  <AmountField
                    id="sale-line-disc"
                    inline
                    currency={currency}
                    value={lineDiscount}
                    onChange={(e) => setLineDiscount(e.target.value)}
                    placeholder="0"
                    aria-label="Line discount"
                    title="Line discount amount (tax before discount)"
                  />
                ) : (
                  <input
                    id="sale-line-disc"
                    value={lineDiscount}
                    onChange={(e) => setLineDiscount(e.target.value)}
                    placeholder="0"
                    aria-label="Line discount"
                    title="Line discount percent"
                  />
                )}
              </div>
            </div>
            <div className="field">
              <label htmlFor="sale-hdr-disc">Discount on the whole sale</label>
              <div className="sale-form-pair">
                <select
                  value={headerDiscountType}
                  onChange={(e) => setHeaderDiscountType(e.target.value === 'percent' ? 'percent' : 'fixed')}
                  aria-label="Header discount type"
                >
                  <option value="fixed">Amount</option>
                  <option value="percent">%</option>
                </select>
                {headerDiscountType === 'fixed' ? (
                  <AmountField
                    id="sale-hdr-disc"
                    inline
                    currency={currency}
                    value={headerDiscount}
                    onChange={(e) => setHeaderDiscount(e.target.value)}
                    placeholder="0"
                    aria-label="Header discount"
                    title="Document-level discount amount"
                  />
                ) : (
                  <input
                    id="sale-hdr-disc"
                    value={headerDiscount}
                    onChange={(e) => setHeaderDiscount(e.target.value)}
                    placeholder="0"
                    aria-label="Header discount"
                    title="Document-level discount percent"
                  />
                )}
              </div>
            </div>
            {composerKind === 'invoice' ? (
              <div className="field">
                <label htmlFor="sale-coupon">Coupon code</label>
                <input
                  id="sale-coupon"
                  value={couponCode}
                  onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                  placeholder="Optional"
                  aria-label="Invoice coupon code"
                />
              </div>
            ) : null}
            <div className="field span-2">
              <label htmlFor="sale-notes">Notes</label>
              <input
                id="sale-notes"
                value={docNotes}
                onChange={(e) => setDocNotes(e.target.value)}
                placeholder="Optional, e.g. Price valid for bulk order only"
                aria-label="Sales document notes"
                title="Optional notes"
              />
            </div>
          </div>
          {composerKind === 'invoice' ? (
            <label className="sale-form-check">
              <input
                type="checkbox"
                checked={invoiceReverseCharge}
                onChange={(e) => setInvoiceReverseCharge(e.target.checked)}
                aria-label="Sales invoice reverse charge"
              />
              Reverse charge (tax memo only — not charged to customer)
            </label>
          ) : null}
        </details>
        <div className="sale-form-actions">
          {(composerKind === 'quotation'
            ? (['quotation', 'order', 'invoice'] as const)
            : composerKind === 'order'
              ? (['order', 'quotation', 'invoice'] as const)
              : (['invoice', 'quotation', 'order'] as const)
          ).map((kind) =>
            kind === 'quotation' ? (
              <button key={kind} className={composerKind === kind ? 'btn-primary' : undefined} onClick={createQuotation} disabled={saveBusy} aria-label="Create quotation">
                {saveBusy ? 'Saving…' : 'Save quote'}
              </button>
            ) : kind === 'order' ? (
              <button key={kind} className={composerKind === kind ? 'btn-primary' : undefined} onClick={createOrder} disabled={saveBusy} aria-label="Create order">
                {saveBusy ? 'Saving…' : 'Save order'}
              </button>
            ) : (
              <button key={kind} className={composerKind === kind ? 'btn-primary' : undefined} onClick={createInvoice} disabled={saveBusy} aria-label="Create invoice">
                {saveBusy ? 'Saving…' : 'Save invoice'}
              </button>
            ),
          )}
        </div>
        {(error || message) ? (
          <p className={error ? 'sales-flash sales-flash-err' : 'sales-flash sales-flash-ok'} role={error ? 'alert' : undefined}>
            {error || message}
          </p>
        ) : null}
          </div>
        </div>
        ) : null}
      </div>
      </FormModal>
      ) : null}

      {groupsOpen ? (
        <CustomerGroupsWindow
          groups={groups}
          customers={customers}
          onClose={() => setGroupsOpen(false)}
          onChanged={refresh}
        />
      ) : null}

      {tab === 'customers' && (
        <>
          <div className="sales-ui-actions">
            <button
              type="button"
              className="btn-primary"
              aria-label="Add customer"
              onClick={() => openCustomerForm(null)}
            >
              Add customer
            </button>
            <button
              type="button"
              aria-label="Open customer groups"
              onClick={() => {
                setError('');
                setMessage('');
                setGroupsOpen(true);
              }}
            >
              Customer groups
            </button>
            <select
              value={customerManageFilter}
              onChange={(e) => setCustomerManageFilter(e.target.value as 'all' | 'active' | 'inactive')}
              aria-label="Customer status filter"
              className="cust-filter"
            >
              <option value="all">All customers</option>
              <option value="active">Active only</option>
              <option value="inactive">Inactive only</option>
            </select>
          </div>
          <p className="sales-ui-note">Add a customer, then use that name on a quote, order, or invoice. A group gives its customers a set discount.</p>
          <div className="list-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th className="col-id">Phone</th>
                  <th>Group</th>
                  <th className="col-status">Status</th>
                  <th className="col-actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {customers
                  .filter((c) => {
                    if (customerManageFilter === 'all') return true;
                    return customerManageFilter === 'inactive' ? c.status === 'inactive' : c.status !== 'inactive';
                  })
                  .map((c) => (
                  <tr key={c.id}>
                    <td>{c.name}</td>
                    <td className="col-id">{c.phone || '—'}</td>
                    <td>{groups.find((g) => g.id === c.customer_group_id)?.name || '—'}</td>
                    <td className="col-status"><StatusChip value={c.status || 'active'} /></td>
                    <td className="col-actions">
                      <RowActions
                        label={`More actions for ${c.name}`}
                        primaryMax={1}
                        items={[
                          {
                            key: 'open',
                            label: 'Open',
                            onClick: () => openCustomerForm(c),
                          },
                          {
                            key: 'toggle',
                            label: (c.status || 'active') === 'inactive' ? 'Activate' : 'Deactivate',
                            variant: (c.status || 'active') === 'inactive' ? 'ok' : 'danger',
                            ariaLabel: 'Toggle customer active status',
                            onClick: () => setCustomerActive((c.status || 'active') === 'inactive', c.id),
                          },
                        ]}
                      />
                    </td>
                  </tr>
                ))}
                {customers.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">No customers yet. Add a customer to use them on a quote, order, or invoice.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'made' && (
        <div className="list-table-wrap">
          {invoicePaperBar()}
          <table className="table">
            <thead>
              <tr>
                <th className="col-date">When</th>
                <th className="col-id">Number</th>
                <th>Customer</th>
                <th>Where</th>
                <th className="col-status">Status</th>
                <th className="col-num">Total</th>
                <th className="col-actions">Actions</th>
              </tr>
            </thead>
            <tbody>
              {managedMade.map((row) => {
                const inv = row.invoice_id
                  ? invoices.find((item) => item.id === row.invoice_id)
                  : undefined;
                const invoiceStatus = inv?.status || (row.source === 'invoice' ? row.status : '');
                const invoiceId = inv?.id || row.invoice_id || '';
                const invoiceNumber = inv?.invoice_number || row.number || '';
                const canPrint = inv ? Boolean(inv.can_print) : ['posted', 'sent', 'partial', 'paid', 'overdue'].includes(invoiceStatus);
                const canEmail = inv ? Boolean(inv.can_email) : canPrint;
                const canPay = Boolean(
                  inv && ['posted', 'sent', 'partial', 'overdue'].includes(inv.status)
                );
                const canReturn = Boolean(
                  inv && ['posted', 'sent', 'partial', 'paid', 'overdue'].includes(inv.status)
                );
                const madeActions: RowActionItem[] = [
                  {
                    key: 'view',
                    label: 'View',
                    hidden: !invoiceId,
                    ariaLabel: `View sales invoice ${invoiceId}`,
                    onClick: () => {
                      if (inv) {
                        setSelected(inv);
                        return;
                      }
                      api(`/sales/invoices/${invoiceId}`)
                        .then((r) => setSelected(r.data))
                        .catch((err) => setError(err.message));
                    },
                  },
                  {
                    key: 'print',
                    label: invoicePaper === 'a4' ? 'Print A4' : `Print ${invoicePaper}`,
                    variant: 'ok',
                    hidden: !(canPrint && invoiceId),
                    ariaLabel: invoicePaper === 'a4' ? 'Print sales invoice A4' : 'Print sales invoice thermal',
                    onClick: () => printInvoice(invoiceId, invoiceNumber, 'list'),
                  },
                  {
                    key: 'preview',
                    label: 'Preview',
                    hidden: !(canPrint && invoiceId),
                    ariaLabel: `Preview sales invoice ${invoiceId}`,
                    onClick: () => previewInvoice(invoiceId, 'list'),
                  },
                  {
                    key: 'reprint',
                    label: reprintingId === row.id ? 'Reprint…' : 'Reprint',
                    disabled: reprintingId === row.id,
                    ariaLabel: `Reprint sale ${row.number || row.id}`,
                    onClick: () => reprintSale(row),
                  },
                  {
                    key: 'email',
                    label: inv?.emailed_at ? 'Resend email' : 'Email',
                    hidden: !(canEmail && invoiceId),
                    ariaLabel: inv?.emailed_at ? 'Resend invoice email' : 'Email invoice',
                    onClick: () => act(`/sales/invoices/${invoiceId}/send`, 'Invoice emailed'),
                  },
                  {
                    key: 'pay',
                    hidden: !canPay || !inv,
                    node: inv ? (
                      <>
                        <AmountField
                          inline
                          currency={inv.currency}
                          value={payAmounts[inv.id] || ''}
                          onChange={(e) => {
                            const next = e.target.value;
                            setPayAmounts((prev) => ({ ...prev, [inv.id]: next }));
                          }}
                          placeholder="Pay"
                          aria-label={`Sales invoice pay amount ${inv.invoice_number || inv.id}`}
                        />
                        <button
                          type="button"
                          onClick={() => pay(inv, payAmounts[inv.id] || '')}
                          aria-label={`Pay sales invoice ${inv.id}`}
                        >
                          Pay
                        </button>
                      </>
                    ) : null,
                  },
                  {
                    key: 'return',
                    label: 'Return',
                    hidden: !canReturn || !inv,
                    ariaLabel: `Create sales return ${inv?.id || ''}`,
                    onClick: () => inv && openReturnForInvoice(inv),
                  },
                ];
                return (
                <tr key={`${row.source}-${row.id}`}>
                  <td className="col-date">{formatWhen(row.when, fmt)}</td>
                  <td className="col-id">{row.number}</td>
                  <td>{row.customer || 'Walk-in'}</td>
                  <td>{saleWords(row.source)}</td>
                  <td className="col-status"><StatusChip value={row.status} label={saleWords(row.status)} /></td>
                  <td className="col-num">{formatMoney(row.total, fmt, row.currency)}</td>
                  <td className="col-actions">
                    <RowActions label={`More actions for ${row.number || row.id}`} primaryMax={1} items={madeActions} />
                  </td>
                </tr>
                );
              })}
              {!managedMade.length && (
                <tr>
                  <td colSpan={7} className="muted">
                    {listSearch.trim()
                      ? 'No sales for this search. Clear the search to see every completed sale.'
                      : 'No sales yet. Completed invoices and register sales show here.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'quotations' && (
        <>
          <div className="sales-ui-actions">
            <button type="button" className="btn-primary" onClick={() => openComposer('quotation')} aria-label="Create quotation">
              Create quotation
            </button>
          </div>
          {numberingPanel}
          <details className="sales-more sales-ui-settings">
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
        <div className="list-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th className="col-id">Number</th>
              <th className="col-text">Customer</th>
              {showChannel ? <th>Channel</th> : null}
              <th className="col-status">Status</th>
              <th className="col-num">Total</th>
              <th className="col-date">Valid until</th>
              {showQuoteReject ? <th className="col-text">Reject reason</th> : null}
              <th className="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedQuotations.map((q) => {
              const quoteActions: RowActionItem[] = [
                {
                  key: 'view',
                  label: 'View',
                  ariaLabel: `View quotation ${q.id}`,
                  onClick: () => setSelected(q),
                },
                {
                  key: 'print',
                  label: 'Print',
                  ariaLabel: 'Print quotation',
                  onClick: () => {
                    openDocumentPrint(`/sales/quotations/${q.id}/print?format=pdf`).catch((err) =>
                      setError(String(err)),
                    );
                  },
                },
                {
                  key: 'email',
                  label: 'Email',
                  hidden: q.status !== 'draft',
                  ariaLabel: 'Email quotation',
                  onClick: () => act(`/sales/quotations/${q.id}/send`, 'Quotation emailed'),
                },
                {
                  key: 'resend',
                  label: 'Resend',
                  hidden: q.status !== 'sent',
                  ariaLabel: 'Resend quotation email',
                  onClick: () => act(`/sales/quotations/${q.id}/send`, 'Quotation re-emailed'),
                },
                {
                  key: 'accept',
                  label: 'Accept',
                  variant: 'ok',
                  hidden: !['draft', 'sent'].includes(q.status),
                  ariaLabel: `Accept quotation ${q.id}`,
                  onClick: () => act(`/sales/quotations/${q.id}/accept`, 'Accepted'),
                },
                {
                  key: 'reject',
                  label: 'Reject',
                  variant: 'danger',
                  hidden: !['draft', 'sent'].includes(q.status),
                  disabled: !quoteRejectReason.trim(),
                  title: quoteRejectReason.trim()
                    ? 'Reject quotation'
                    : 'Enter a reject reason before rejecting',
                  ariaLabel: `Reject quotation ${q.id}`,
                  onClick: () => act(`/sales/quotations/${q.id}/reject`, 'Rejected'),
                },
                {
                  key: 'to-order',
                  label: '→ Order',
                  variant: 'ok',
                  hidden: !['draft', 'sent', 'accepted'].includes(q.status),
                  ariaLabel: `Convert quotation to order ${q.id}`,
                  onClick: () => act(`/sales/quotations/${q.id}/convert-order`, 'Order'),
                },
                {
                  key: 'to-invoice',
                  label: '→ Invoice',
                  variant: 'ok',
                  hidden: !['draft', 'sent', 'accepted'].includes(q.status),
                  ariaLabel: `Convert quotation to invoice ${q.id}`,
                  onClick: () => act(`/sales/quotations/${q.id}/convert-invoice`, 'Invoice'),
                },
              ];
              return (
              <tr key={q.id}>
                <td className="col-id">{q.quotation_number}</td>
                <td className="col-text">{q.customer_name || customerNameOf(q.customer_id)}</td>
                {showChannel ? <td>{channelLabel(q.sales_channel)}</td> : null}
                <td className="col-status"><StatusChip value={q.status} label={saleWords(q.status)} /></td>
                <td className="col-num">{formatMoney(q.total_amount, fmt, q.currency)}</td>
                <td className="col-date">{q.valid_until ? formatWhen(q.valid_until, fmt) : '—'}</td>
                {showQuoteReject ? <td className="col-text">{q.rejection_reason || '—'}</td> : null}
                <td className="col-actions">
                  <RowActions label={`More actions for ${q.quotation_number || q.id}`} primaryMax={1} items={quoteActions} />
                </td>
              </tr>
              );
            })}
            {managedQuotations.length === 0 && (
              <tr>
                <td colSpan={quoteCols} className="muted">
                  {quotations.length === 0
                    ? 'No quotes yet. Create a quotation to send a price before you invoice.'
                    : 'No quotations for this filter. Choose All statuses to see every quote.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
        </>
      )}

      {tab === 'orders' && (
        <>
          <div className="sales-ui-actions">
            <button type="button" className="btn-primary" onClick={() => openComposer('order')} aria-label="Create order">
              Create order
            </button>
          </div>
          {numberingPanel}
          <details className="sales-more sales-ui-settings">
            <summary>Cancel or email an order</summary>
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
          <div className="list-table-wrap">
          <table className="table">
          <thead>
            <tr>
              <th className="col-id">Number</th>
              <th className="col-text">Customer</th>
              {showChannel ? <th>Channel</th> : null}
              <th className="col-status">Status</th>
              {showStore ? <th>Store</th> : null}
              {showReserved ? <th className="col-num">Reserved</th> : null}
              <th className="col-text">Delivery</th>
              <th className="col-num">Total</th>
              <th className="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedOrders.map((o) => {
              const orderActions: RowActionItem[] = [
                {
                  key: 'view',
                  label: 'View',
                  ariaLabel: `View sales order ${o.id}`,
                  onClick: () => setSelected(o),
                },
                {
                  key: 'print',
                  label: 'Print',
                  ariaLabel: 'Print sales order',
                  onClick: () => {
                    openDocumentPrint(`/sales/orders/${o.id}/print?format=pdf`).catch((err) =>
                      setError(String(err)),
                    );
                  },
                },
                {
                  key: 'email',
                  label: 'Email',
                  ariaLabel: 'Email sales order',
                  onClick: () => act(`/sales/orders/${o.id}/send`, 'Sales order emailed'),
                },
                {
                  key: 'confirm',
                  label: 'Confirm',
                  variant: 'ok',
                  hidden: o.status !== 'draft',
                  ariaLabel: `Confirm sales order ${o.id}`,
                  onClick: () =>
                    act(
                      `/sales/orders/${o.id}/confirm`,
                      'Confirmed',
                      storeId.trim() || o.store_id
                        ? {
                            store_id: (storeId.trim() || o.store_id) as string,
                            delivery_date: deliveryDate.trim() || null,
                            ...(deliveryAddress.trim()
                              ? { delivery_address: deliveryAddress.trim() }
                              : {}),
                          }
                        : {}
                    ),
                },
                {
                  key: 'process',
                  label: 'Process',
                  variant: 'ok',
                  hidden: !o.can_process,
                  ariaLabel: `Process sales order ${o.id}`,
                  onClick: () => act(`/sales/orders/${o.id}/process`, 'Processing'),
                },
                {
                  key: 'ship',
                  label: 'Ship',
                  variant: 'ok',
                  hidden: !o.can_ship,
                  ariaLabel: `Ship sales order ${o.id}`,
                  onClick: () => act(`/sales/orders/${o.id}/ship`, 'Shipped'),
                },
                {
                  key: 'deliver',
                  label: 'Deliver',
                  variant: 'ok',
                  hidden: !o.can_deliver,
                  ariaLabel: `Deliver sales order ${o.id}`,
                  onClick: () => act(`/sales/orders/${o.id}/deliver`, 'Delivered'),
                },
                {
                  key: 'to-invoice',
                  label: '→ Invoice',
                  variant: 'ok',
                  hidden: !o.can_invoice,
                  ariaLabel: `Convert sales order to invoice ${o.id}`,
                  onClick: () => act(`/sales/orders/${o.id}/convert-invoice`, 'Invoice'),
                },
                {
                  key: 'cancel',
                  label: 'Cancel',
                  variant: 'danger',
                  hidden: !o.can_cancel,
                  ariaLabel: `Cancel sales order ${o.id}`,
                  onClick: () => act(`/sales/orders/${o.id}/cancel`, 'Cancelled'),
                },
              ];
              return (
              <tr key={o.id}>
                <td className="col-id">{o.order_number}</td>
                <td className="col-text">{o.customer_name || customerNameOf(o.customer_id)}</td>
                {showChannel ? <td>{channelLabel(o.sales_channel)}</td> : null}
                <td className="col-status"><StatusChip value={o.status} label={saleWords(o.status)} /></td>
                {showStore ? <td>{storeName(o.store_id) || '—'}</td> : null}
                {showReserved ? (
                <td className="col-num">
                  {o.reservation_status
                    ? `${formatNumber(o.reserved_qty ?? 0, fmt)} ${saleWords(o.reservation_status)}`
                    : '—'}
                </td>
                ) : null}
                <td className="col-text">
                  {o.delivery_date ? formatWhen(o.delivery_date, fmt) : '—'}
                  {o.delivery_address ? ` · ${o.delivery_address}` : ''}
                </td>
                <td className="col-num">{formatMoney(o.total_amount, fmt, o.currency)}</td>
                <td className="col-actions">
                  <RowActions label={`More actions for ${o.order_number || o.id}`} primaryMax={1} items={orderActions} />
                </td>
              </tr>
              );
            })}
            {managedOrders.length === 0 && (
              <tr>
                <td colSpan={orderCols} className="muted">
                  {orders.length === 0
                    ? 'No orders yet. Create an order when the customer has agreed to buy.'
                    : 'No sales orders for this filter. Choose All statuses to see every order.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
          </div>
        </>
      )}

      {tab === 'invoices' && (
        <>
          <div className="sales-ui-actions">
            <button type="button" className="btn-primary" onClick={() => openComposer('invoice')} aria-label="Create invoice">
              Create invoice
            </button>
          </div>
          {numberingPanel}
          <details className="sales-more sales-ui-settings">
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
        {invoicePaperBar()}
        <table className="table">
          <thead>
            <tr>
              <th className="col-id">Number</th>
              <th className="col-text">Customer</th>
              {showChannel ? <th>Channel</th> : null}
              <th className="col-status">Status</th>
              {showStore ? <th>Store</th> : null}
              <th className="col-num">Total</th>
              <th className="col-num">Paid</th>
              <th className="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedInvoices.map((inv) => {
              const invoiceActions: RowActionItem[] = [
                {
                  key: 'view',
                  label: 'View',
                  ariaLabel: `View sales invoice ${inv.id}`,
                  onClick: () => setSelected(inv),
                },
                {
                  key: 'post',
                  label: 'Post',
                  variant: 'ok',
                  hidden: inv.status !== 'draft',
                  ariaLabel: `Post sales invoice ${inv.id}`,
                  onClick: () => postInvoice(inv),
                },
                {
                  key: 'cancel',
                  label: 'Cancel',
                  variant: 'danger',
                  hidden: inv.status !== 'draft',
                  ariaLabel: `Cancel sales invoice ${inv.id}`,
                  onClick: () => act(`/sales/invoices/${inv.id}/cancel`, 'Cancelled'),
                },
                {
                  key: 'print',
                  label: invoicePaper === 'a4' ? 'Print A4' : `Print ${invoicePaper}`,
                  variant: 'ok',
                  hidden: !inv.can_print,
                  ariaLabel: invoicePaper === 'a4' ? 'Print sales invoice A4' : 'Print sales invoice thermal',
                  onClick: () => printInvoice(inv.id, inv.invoice_number, 'list'),
                },
                {
                  key: 'preview',
                  label: 'Preview',
                  hidden: !inv.can_print,
                  ariaLabel: `Preview sales invoice ${inv.id}`,
                  onClick: () => previewInvoice(inv.id, 'list'),
                },
                {
                  key: 'reprint',
                  label: reprintingId === inv.id ? 'Reprint…' : 'Reprint',
                  hidden: !inv.can_print,
                  disabled: reprintingId === inv.id,
                  ariaLabel: `Reprint sales invoice ${inv.id}`,
                  onClick: () =>
                    reprintSale({
                      id: inv.id,
                      source: 'invoice',
                      invoice_id: inv.id,
                      number: inv.invoice_number,
                    }),
                },
                {
                  key: 'email',
                  label: inv.emailed_at ? 'Resend email' : 'Email',
                  hidden: !inv.can_email,
                  ariaLabel: inv.emailed_at ? 'Resend invoice email' : 'Email invoice',
                  onClick: () => act(`/sales/invoices/${inv.id}/send`, 'Invoice emailed'),
                },
                {
                  key: 'overdue',
                  hidden: inv.status !== 'overdue',
                  node: <span className="muted">{inv.days_overdue} days overdue</span>,
                },
                {
                  key: 'pay',
                  hidden: !['posted', 'sent', 'partial', 'overdue'].includes(inv.status),
                  node: (
                    <>
                      <AmountField
                        inline
                        currency={inv.currency}
                        value={payAmounts[inv.id] || ''}
                        onChange={(e) => {
                          const next = e.target.value;
                          setPayAmounts((prev) => ({ ...prev, [inv.id]: next }));
                        }}
                        placeholder="Pay"
                        aria-label={`Sales invoice pay amount ${inv.invoice_number || inv.id}`}
                      />
                      <button
                        type="button"
                        onClick={() => pay(inv, payAmounts[inv.id] || '')}
                        aria-label={`Pay sales invoice ${inv.id}`}
                      >
                        Pay
                      </button>
                    </>
                  ),
                },
                {
                  key: 'return',
                  label: 'Return',
                  hidden: !['posted', 'sent', 'partial', 'paid', 'overdue'].includes(inv.status),
                  ariaLabel: `Create sales return ${inv.id}`,
                  onClick: () => openReturnForInvoice(inv),
                },
              ];
              return (
              <tr key={inv.id}>
                <td className="col-id">{inv.invoice_number}</td>
                <td className="col-text">{inv.customer_name || customerNameOf(inv.customer_id)}</td>
                {showChannel ? <td>{channelLabel(inv.sales_channel)}</td> : null}
                <td className="col-status"><StatusChip value={inv.status} label={saleWords(inv.status)} /></td>
                {showStore ? <td>{storeName(inv.store_id) || '—'}</td> : null}
                <td className="col-num">{formatMoney(inv.total_amount, fmt, inv.currency)}</td>
                <td className="col-num">{formatMoney(inv.paid_amount, fmt, inv.currency)}</td>
                <td className="col-actions">
                  <RowActions label={`More actions for ${inv.invoice_number || inv.id}`} primaryMax={1} items={invoiceActions} />
                </td>
              </tr>
              );
            })}
            {managedInvoices.length === 0 && (
              <tr>
                <td colSpan={invoiceCols} className="muted">
                  {invoices.length === 0
                    ? 'No invoices yet. Create an invoice when you are ready to bill the customer.'
                    : 'No sales invoices for this filter. Choose All statuses to see every invoice.'}
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
          <div className="coupon-head">
            <div>
              <h3>Coupons</h3>
              <p className="sales-ui-note">
                A coupon code takes a percent or a set amount off. Type it on a quote, order or invoice, or under Discount at the till. It is not a payment.
              </p>
            </div>
            <button
              type="button"
              className="btn-primary"
              onClick={() => {
                setError('');
                setMessage('');
                setCouponFormOpen(true);
              }}
              aria-label="Add coupon"
            >
              Add coupon
            </button>
          </div>
          {couponFormOpen ? (
            <FormModal
              title="Add coupon"
              busy={saveBusy}
              dirty={Boolean(newCouponCode.trim() || newCouponName.trim())}
              onClose={() => setCouponFormOpen(false)}
            >
              {error ? (
                <p className="sales-flash sales-flash-err" role="alert">
                  {error}
                </p>
              ) : null}
              <div className="form-grid">
                <div className="field">
                  <label htmlFor="coupon-code">Code customers type</label>
                  <input
                    id="coupon-code"
                    value={newCouponCode}
                    onChange={(e) => setNewCouponCode(e.target.value.toUpperCase())}
                    placeholder="e.g. SAVE10"
                    aria-label="New coupon code"
                  />
                </div>
                <div className="field">
                  <label htmlFor="coupon-name">Name</label>
                  <input
                    id="coupon-name"
                    value={newCouponName}
                    onChange={(e) => setNewCouponName(e.target.value)}
                    placeholder="e.g. Ten percent off"
                    aria-label="New coupon name"
                  />
                </div>
                <div className="field">
                  <label htmlFor="coupon-type">Discount</label>
                  <select
                    id="coupon-type"
                    value={newCouponType}
                    onChange={(e) => setNewCouponType(e.target.value as 'fixed' | 'percent')}
                    aria-label="New coupon type"
                  >
                    <option value="percent">Percent off</option>
                    <option value="fixed">Amount off</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="coupon-amount">{newCouponType === 'fixed' ? 'Amount off' : 'Percent off'}</label>
                  {newCouponType === 'fixed' ? (
                    <AmountField id="coupon-amount" value={newCouponAmount} onChange={(e) => setNewCouponAmount(e.target.value)} aria-label="New coupon amount" />
                  ) : (
                    <input id="coupon-amount" value={newCouponAmount} onChange={(e) => setNewCouponAmount(e.target.value)} inputMode="decimal" aria-label="New coupon amount" />
                  )}
                </div>
                <div className="field span-2">
                  <label htmlFor="coupon-min">Lowest bill it works on</label>
                  <AmountField
                    id="coupon-min"
                    value={newCouponMin}
                    onChange={(e) => setNewCouponMin(e.target.value)}
                    placeholder="0 = any bill"
                    aria-label="New coupon min spend"
                  />
                </div>
              </div>
              <div className="cust-actions" style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={saveBusy || !newCouponCode.trim() || !newCouponName.trim() || !(Number(newCouponAmount) > 0)}
                  onClick={async () => {
                    setError('');
                    setSaveBusy(true);
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
                      const code = newCouponCode.trim();
                      setNewCouponCode('');
                      setNewCouponName('');
                      await refresh();
                      setCouponFormOpen(false);
                      setMessage(`Coupon ${code} saved`);
                    } catch (err: any) {
                      setError(err.message);
                    } finally {
                      setSaveBusy(false);
                    }
                  }}
                  aria-label="Save coupon"
                >
                  Save coupon
                </button>
              </div>
            </FormModal>
          ) : null}
          <div className="list-table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th className="col-id">Code</th>
                  <th>Name</th>
                  <th className="col-num">Takes off</th>
                  <th className="col-num">Lowest bill</th>
                  <th className="col-num">Used</th>
                  <th className="col-status">Status</th>
                  <th className="col-actions">Actions</th>
                </tr>
              </thead>
              <tbody>
                {coupons.map((c) => (
                  <tr key={c.id}>
                    <td className="col-id">{c.code}</td>
                    <td>{c.name}</td>
                    <td className="col-num">{c.discount_type === 'percent' ? `${formatNumber(c.amount, fmt)}%` : formatMoney(c.amount, fmt)}</td>
                    <td className="col-num">{Number(c.min_spend || 0) > 0 ? formatMoney(c.min_spend, fmt) : 'Any'}</td>
                    <td className="col-num">{c.redemption_count ?? 0}</td>
                    <td className="col-status"><StatusChip value={c.is_active ? 'active' : 'inactive'} label={c.is_active ? 'On' : 'Off'} /></td>
                    <td className="col-actions">
                      <button
                        type="button"
                        className={c.is_active ? 'btn-danger' : 'btn-ok'}
                        aria-label={c.is_active ? `Switch off coupon ${c.code}` : `Switch on coupon ${c.code}`}
                        onClick={async () => {
                          setError('');
                          try {
                            await api(`/sales/coupons/${c.id}`, {
                              method: 'PATCH',
                              body: JSON.stringify({ is_active: !c.is_active }),
                            });
                            await refresh();
                            setMessage(c.is_active ? `Coupon ${c.code} switched off` : `Coupon ${c.code} switched on`);
                          } catch (err: any) {
                            setError(err.message);
                          }
                        }}
                      >
                        {c.is_active ? 'Switch off' : 'Switch on'}
                      </button>
                    </td>
                  </tr>
                ))}
                {coupons.length === 0 && (
                  <tr>
                    <td colSpan={7} className="muted">
                      No coupons yet. Press Add coupon to make a code that takes a percent or a set amount off.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'giftcards' && (
        <div className="card cat-panel">
          <h3>Gift cards</h3>
          <p className="sales-ui-note">
            Issue a card, then enter that code in Gift card code at the register. The balance stays a liability until the card is spent. This screen does not take till cash and does not charge a bank card. One loyalty point equals one currency unit. A named customer earns 1% of the sale.
          </p>
          <div className="sales-ui-actions">
            <AmountField
              value={giftAmount}
              onChange={(e) => setGiftAmount(e.target.value)}
              placeholder="Amount"
              aria-label="Gift card amount"
            />
            <button type="button" className="btn-primary" onClick={issueGiftCard}>
              Issue gift card
            </button>
          </div>
          {giftIssued ? (
            <p>
              Code <strong>{giftIssued.code}</strong> · balance {formatMoney(giftIssued.balance, fmt)} · {giftIssued.status}
            </p>
          ) : null}
          <div className="sales-ui-actions">
            <input
              value={giftLookup}
              onChange={(e) => setGiftLookup(e.target.value)}
              placeholder="Gift card code"
              aria-label="Gift card lookup code"
            />
            <button type="button" onClick={lookupGiftCard}>
              Look up gift card
            </button>
          </div>
          {giftFound ? (
            <p>
              {giftFound.code} · balance {formatMoney(giftFound.balance, fmt)} · {giftFound.status}
            </p>
          ) : null}
        </div>
      )}

      {tab === 'returns' && (
        <>
          <div className="sales-ui-actions">
            <button type="button" className="btn-primary" onClick={() => setReturnCreateOpen(true)} aria-label="Create return">
              Create return
            </button>
          </div>
          {numberingPanel}
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
            onChange={(e) => {
              const nextId = e.target.value;
              setInvoiceId(nextId);
              const next = invoices.find((item) => item.id === nextId);
              applyReturnLine(next?.items?.[0]);
            }}
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
          {(invoices.find((item) => item.id === invoiceId)?.items || []).length > 0 && (
            <select
              value={productId}
              onChange={(e) => {
                const lines = invoices.find((item) => item.id === invoiceId)?.items || [];
                applyReturnLine(lines.find((line: { product_id?: string }) => String(line.product_id) === e.target.value));
              }}
              aria-label="Sales return product"
            >
              <option value="">Product on invoice</option>
              {(invoices.find((item) => item.id === invoiceId)?.items || []).map((line: any) => {
                const prod = products.find((p) => p.id === line.product_id);
                return (
                  <option key={line.id || line.product_id} value={line.product_id}>
                    {line.product_name || prod?.name || 'Product'} · {line.quantity}
                  </option>
                );
              })}
            </select>
          )}
          <input
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            placeholder="Qty"
            aria-label="Sales return quantity"
            style={{ width: 80 }}
          />
          <label>
            <input type="checkbox" checked={restock} onChange={(e) => setRestock(e.target.checked)} aria-label="Sales return restock" /> Restock
          </label>
          <input
            value={returnNotes}
            onChange={(e) => setReturnNotes(e.target.value)}
            placeholder="Return notes (optional)"
            aria-label="Sales return notes"
            title="Optional notes"
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
            <summary>Cancel or email a return</summary>
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
        <div className="list-table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th className="col-id">Number</th>
              <th className="col-id">Credit note</th>
              <th className="col-status">Status</th>
              <th>Settlement</th>
              <th className="col-status">Reason</th>
              <th className="col-num">Total</th>
              <th className="col-actions">Actions</th>
            </tr>
          </thead>
          <tbody>
            {managedReturns.map((r) => {
              const returnActions: RowActionItem[] = [
                {
                  key: 'view',
                  label: 'View',
                  ariaLabel: `View sales return ${r.id}`,
                  onClick: () => setSelected(r),
                },
                {
                  key: 'print',
                  label: 'Print',
                  ariaLabel: 'Print sales return',
                  onClick: () => {
                    openDocumentPrint(`/sales/returns/${r.id}/print?format=pdf`).catch((err) =>
                      setError(String(err)),
                    );
                  },
                },
                {
                  key: 'email',
                  label: 'Email',
                  ariaLabel: 'Email sales return',
                  onClick: () => act(`/sales/returns/${r.id}/send`, 'Credit note emailed'),
                },
                {
                  key: 'post-credit',
                  label: 'Post credit',
                  variant: 'ok',
                  hidden: r.status !== 'draft',
                  ariaLabel: `Post sales return credit ${r.id}`,
                  onClick: () =>
                    act(`/sales/returns/${r.id}/post`, 'Posted (credit)', {
                      settlement_method: 'adjust',
                    }),
                },
                {
                  key: 'post-refund',
                  label: 'Post + refund',
                  variant: 'ok',
                  hidden: r.status !== 'draft',
                  ariaLabel: `Post sales return refund ${r.id}`,
                  onClick: () =>
                    act(`/sales/returns/${r.id}/post`, 'Posted (refund)', {
                      settlement_method: 'refund',
                      payment_method: 'cash',
                    }),
                },
                {
                  key: 'cancel',
                  label: 'Cancel',
                  variant: 'danger',
                  hidden: r.status !== 'draft',
                  ariaLabel: `Cancel sales return ${r.id}`,
                  onClick: () => act(`/sales/returns/${r.id}/cancel`, 'Cancelled'),
                },
              ];
              return (
              <tr key={r.id}>
                <td className="col-id">{r.return_number}</td>
                <td className="col-id">{r.credit_note_number || '—'}</td>
                <td className="col-status"><StatusChip value={r.status} label={saleWords(r.status)} /></td>
                <td>
                  {r.settlement_method ? saleWords(r.settlement_method) : '—'}
                  {r.refunded_amount > 0 ? ` · ${formatMoney(r.refunded_amount, fmt, r.currency)}` : ''}
                </td>
                <td className="col-status">{saleWords(r.reason)}</td>
                <td className="col-num">{formatMoney(r.total_amount, fmt, r.currency)}</td>
                <td className="col-actions">
                  <RowActions label={`More actions for ${r.return_number || r.id}`} primaryMax={1} items={returnActions} />
                </td>
              </tr>
              );
            })}
            {managedReturns.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  {returns.length === 0
                    ? 'No returns yet. Create a return from a posted invoice.'
                    : 'No sales returns for this filter. Choose All statuses to see every return.'}

                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
        </>
      )}

      {selected && (
        <div className="sales-drawer-backdrop" onClick={() => setSelected(null)}>
        <div className="sales-drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Document details">
          <div className="sales-drawer-head">
            <h2>
              {selected.invoice_number || selected.quotation_number || selected.order_number || selected.return_number || 'Document'} — {saleWords(selected.status)}
              {selected.invoice_number ? (
                <span className="print-ui-row" style={{ marginLeft: 12 }}>
                  {invoicePrintControls(selected.id, selected.invoice_number, 'drawer')}
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
              {selected.emailed_at ? ` · ${formatWhen(selected.emailed_at, fmt)}` : ''}
            </p>
          )}
          {(selected.invoice_date || selected.due_date || selected.valid_until || selected.delivery_date) ? (
            <p className="muted" style={{ marginBottom: 8 }}>
              {[
                selected.invoice_date ? `Invoice ${formatWhen(selected.invoice_date, fmt)}` : '',
                selected.due_date ? `Due ${formatWhen(selected.due_date, fmt)}` : '',
                selected.valid_until ? `Valid until ${formatWhen(selected.valid_until, fmt)}` : '',
                selected.delivery_date ? `Delivery ${formatWhen(selected.delivery_date, fmt)}` : '',
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
          <div className="list-table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Product</th>
                <th className="col-id">SKU</th>
                <th className="col-num">Qty</th>
                {showFilled ? <th className="col-num">Filled</th> : null}
                <th className="col-num">Price</th>
                <th className="col-num">Tax</th>
                <th className="col-num">Discount</th>
                {showCondition ? <th className="col-status">Condition</th> : null}
                <th className="col-num">Tax amount</th>
                <th className="col-num">Line total</th>
              </tr>
            </thead>
            <tbody>
              {drawerLines.map((it) => {
                const prod = products.find((p) => p.id === it.product_id);
                return (
                <tr key={it.id}>
                  <td className="col-text">
                    {it.product_name || prod?.name || 'Product'}
                    {it.is_reverse_charge ? ' · Reverse charge' : ''}
                  </td>
                  <td className="col-id">{prod?.sku || '—'}</td>
                  <td className="col-num">{formatNumber(it.quantity, fmt)}</td>
                  {showFilled ? <td className="col-num">{it.qty_fulfilled != null ? formatNumber(it.qty_fulfilled, fmt) : '—'}</td> : null}
                  <td className="col-num">{formatMoney(it.unit_price, fmt, selected?.currency)}</td>
                  <td className="col-num">{it.tax_rate != null ? `${formatNumber(it.tax_rate, fmt)}%` : '—'}</td>
                  <td className="col-num">
                    {it.discount_type === 'percent' ? formatNumber(it.discount ?? 0, fmt) : formatMoney(it.discount ?? 0, fmt, selected?.currency)}
                    {it.discount_type === 'percent' ? ` (${formatNumber(it.discount_percent, fmt)}%)` : ''}
                  </td>
                  {showCondition ? <td className="col-status">{it.condition ? saleWords(it.condition) : '—'}</td> : null}
                  <td className="col-num">
                    {formatMoney(it.line_tax ?? 0, fmt, selected?.currency)}
                    {(it.tax_components || []).length
                      ? ` (${(it.tax_components || [])
                          .map((c: any) => `${c.name || saleWords(c.code)} ${formatMoney(c.amount, fmt, selected?.currency)}`)
                          .join(', ')})`
                      : ''}
                  </td>
                  <td className="col-num">{formatMoney(it.line_total, fmt, selected?.currency)}</td>
                </tr>
                );
              })}
            </tbody>
          </table>
          </div>
          {selected.order_number && selected.can_fulfill ? (
            <div style={{ marginTop: 12 }}>
              <h4 style={{ margin: '8px 0' }}>Partial fill</h4>
              <p className="muted">Record quantity shipped now. Stock still moves when the invoice posts.</p>
              {(selected.items || []).map((it: any) => {
                const prod = products.find((p) => p.id === it.product_id);
                const remaining = Math.max(Number(it.quantity || 0) - Number(it.qty_fulfilled || 0), 0);
                return (
                  <label key={it.id} style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
                    <span>{it.product_name || prod?.name || 'Item'}</span>
                    <span className="muted">remaining {remaining}</span>
                    <input
                      value={fulfillQty[it.product_id] || ''}
                      onChange={(e) =>
                        setFulfillQty((prev) => ({ ...prev, [it.product_id]: e.target.value }))
                      }
                      placeholder="Qty"
                      aria-label={`Fill quantity for ${it.product_name || prod?.name || 'Item'}`}
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
              <div className="kpi">{formatMoney(selected.subtotal ?? 0, fmt, selected.currency)}</div>
            </div>
            <div className="card">
              <div className="muted">Tax</div>
              <div className="kpi">{formatMoney(selected.tax_amount ?? 0, fmt, selected.currency)}</div>
            </div>
            <div className="card">
              <div className="muted">Discount</div>
              <div className="kpi">
                {selected.discount_type === 'percent' ? formatNumber(selected.discount_amount ?? 0, fmt) : formatMoney(selected.discount_amount ?? 0, fmt, selected.currency)}
                {selected.discount_type === 'percent' ? ` (${formatNumber(selected.discount_percent, fmt)}%)` : ''}
              </div>
            </div>
            <div className="card">
              <div className="muted">Total</div>
              <div className="kpi">{formatMoney(selected.total_amount ?? 0, fmt, selected.currency)}</div>
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
                      <td>{formatNumber(r.tax_rate, fmt)}%</td>
                      <td>{formatMoney(r.taxable, fmt, selected.currency)}</td>
                      <td>{formatMoney(r.tax, fmt, selected.currency)}</td>
                      <td>{r.is_reverse_charge ? 'Reverse charge' : 'Standard'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {selected.reverse_charge_tax > 0 && (
                <p className="muted">
                  Reverse-charge tax: {formatMoney(selected.reverse_charge_tax, fmt, selected.currency)}
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
