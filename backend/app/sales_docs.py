"""Sales quotations, orders, and returns."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import apply_stock_change
from app.sales import (
    INVOICE_PRINT_FORMATS,
    INVOICE_PRINT_TEMPLATES,
    create_sales_invoice,
    get_customer,
    get_invoice,
    list_invoice_items,
    render_branded_lines_pdf,
)
from app.tax import resolve_product_tax
from app.catalog import get_variant, resolve_sale_line

RETURN_REASONS = frozenset({"damaged", "wrong_item", "defective", "customer_change", "other"})

QUOTATION_PRINT_TEMPLATES = INVOICE_PRINT_TEMPLATES
QUOTATION_PRINT_FORMATS = INVOICE_PRINT_FORMATS


async def _prepare_lines(
    db: AsyncSession,
    tenant_id: str,
    items: list[dict],
    *,
    group_discount_percent: float = 0,
) -> tuple[float, float, list[tuple[dict, float]]]:
    if not items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    subtotal = 0.0
    tax_total = 0.0
    prepared: list[tuple[dict, float]] = []
    for item in items:
        product, variant, unit = await resolve_sale_line(
            db, tenant_id, item, group_discount_percent=group_discount_percent
        )
        qty = float(item["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")
        discount = float(item.get("discount") or 0)
        explicit = item.get("tax_rate")
        if explicit is not None:
            spec = await resolve_product_tax(
                db, tenant_id, product, explicit_rate=float(explicit)
            )
        else:
            spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=None)
        line_sub, line_tax, line_total = spec.compute_amounts(qty * unit)
        line_total = max(line_total - discount, 0)
        subtotal += line_sub
        if not spec.is_reverse_charge:
            tax_total += line_tax
        prepared.append(
            (
                {
                    "product_id": product.id,
                    "variant_id": variant.id if variant else None,
                    "quantity": qty,
                    "unit_price": unit,
                    "tax_rate": spec.rate_pct,
                    "discount": discount,
                    "line_total": line_total,
                },
                line_total,
            )
        )
    return round(subtotal, 2), round(tax_total, 2), prepared


async def _allocate(db: AsyncSession, tenant_id: str, doc_key: str) -> str:
    from app.document_numbering import allocate_document_number

    return await allocate_document_number(db, tenant_id=tenant_id, doc_key=doc_key)


# --- Quotations ---


async def get_quotation(db: AsyncSession, tenant_id: str, quotation_id: str) -> m.SalesQuotation:
    row = (
        await db.execute(
            select(m.SalesQuotation).where(
                m.SalesQuotation.id == quotation_id,
                m.SalesQuotation.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return row


async def list_quotation_items(db: AsyncSession, tenant_id: str, quotation_id: str) -> list[m.SalesQuotationItem]:
    return (
        await db.execute(
            select(m.SalesQuotationItem).where(
                m.SalesQuotationItem.tenant_id == tenant_id,
                m.SalesQuotationItem.quotation_id == quotation_id,
            )
        )
    ).scalars().all()


async def serialize_quotation(db: AsyncSession, quote: m.SalesQuotation) -> dict:
    items = await list_quotation_items(db, quote.tenant_id, quote.id)
    return {
        "id": quote.id,
        "quotation_number": quote.quotation_number,
        "customer_id": quote.customer_id,
        "status": quote.status,
        "subtotal": float(quote.subtotal),
        "tax_amount": float(quote.tax_amount),
        "discount_amount": float(quote.discount_amount),
        "total_amount": float(quote.total_amount),
        "valid_until": quote.valid_until,
        "notes": quote.notes,
        "converted_order_id": quote.converted_order_id,
        "converted_invoice_id": quote.converted_invoice_id,
        "emailed_at": quote.emailed_at,
        "emailed_to": quote.emailed_to,
        "created_at": quote.created_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount),
                "line_total": float(i.line_total),
            }
            for i in items
        ],
    }


def render_quotation_text(
    quotation_data: dict,
    *,
    company_name: str,
    customer_name: str,
    template: str = "a4",
    currency: str = "GHS",
    company_address: str | None = None,
    company_phone: str | None = None,
    company_email: str | None = None,
    tax_registration_number: str | None = None,
    customer_address: str | None = None,
    item_labels: dict[str, str] | None = None,
    logo_data_url: str | None = None,
    trading_name: str | None = None,
    legal_name: str | None = None,
    has_logo: bool = False,
    document_header: str | None = None,
    document_footer: str | None = None,
) -> str:
    from app.print_branding import header_footer_text_lines

    tpl = template if template in QUOTATION_PRINT_TEMPLATES else "a4"
    width = 48 if tpl == "thermal_80" else 32 if tpl == "thermal_58" else 72
    cur = currency or "GHS"
    labels = item_labels or {}
    lines = [company_name[:width]]
    if company_address:
        lines.append(str(company_address)[:width])
    if company_phone:
        lines.append(f"Tel: {company_phone}"[:width])
    if company_email:
        lines.append(str(company_email)[:width])
    if tax_registration_number:
        lines.append(f"Tax #: {tax_registration_number}"[:width])
    for part in header_footer_text_lines(document_header, width):
        lines.append(part[:width])
    lines.extend(
        [
            "",
            f"QUOTATION {quotation_data.get('quotation_number')}"[:width],
            f"Customer: {customer_name}"[:width],
        ]
    )
    if customer_address:
        lines.append(str(customer_address)[:width])
    lines.append(f"Status: {quotation_data.get('status')}"[:width])
    if quotation_data.get("valid_until"):
        lines.append(f"Valid until: {str(quotation_data['valid_until'])[:10]}"[:width])
    lines.extend(
        ["", f"{'Item':<{max(width - 28, 8)}} {'Qty':>6} {'Total':>10}"[:width], "-" * width]
    )
    for item in quotation_data.get("items") or []:
        pid = str(item.get("product_id") or "")
        desc = str(labels.get(pid) or pid or "Item")[: max(width - 28, 8)]
        lines.append(
            f"{desc:<{max(width - 28, 8)}} {float(item.get('quantity') or 0):>6.2f} "
            f"{float(item.get('line_total') or 0):>10.2f}"[:width]
        )
    lines.extend(
        [
            "-" * width,
            f"Subtotal: {cur} {float(quotation_data.get('subtotal') or 0):.2f}"[:width],
            f"Tax: {cur} {float(quotation_data.get('tax_amount') or 0):.2f}"[:width],
            f"Discount: {cur} {float(quotation_data.get('discount_amount') or 0):.2f}"[:width],
            f"TOTAL: {cur} {float(quotation_data.get('total_amount') or 0):.2f}"[:width],
        ]
    )
    if quotation_data.get("notes"):
        lines.extend(["", f"Notes: {quotation_data['notes']}"[:width]])
    footer_lines = header_footer_text_lines(document_footer, width)
    if footer_lines:
        lines.append("")
        lines.extend(part[:width] for part in footer_lines)
    elif tpl.startswith("thermal"):
        lines.extend(["", "Thank you!"[:width]])
    return "\n".join(lines)


def render_quotation_html(
    quotation_data: dict,
    *,
    company_name: str,
    customer_name: str,
    template: str = "a4",
    currency: str = "GHS",
    company_address: str | None = None,
    company_phone: str | None = None,
    company_email: str | None = None,
    tax_registration_number: str | None = None,
    customer_address: str | None = None,
    item_labels: dict[str, str] | None = None,
    logo_data_url: str | None = None,
    trading_name: str | None = None,
    legal_name: str | None = None,
    has_logo: bool = False,
    document_header: str | None = None,
    document_footer: str | None = None,
) -> str:
    from html import escape

    from app.print_branding import brand_html_block, header_footer_html

    tpl = template if template in QUOTATION_PRINT_TEMPLATES else "a4"
    cur = escape(currency or "GHS")
    labels = item_labels or {}
    max_width = "80mm" if tpl == "thermal_80" else "58mm" if tpl == "thermal_58" else "720px"
    font = "12px/1.4 monospace" if tpl.startswith("thermal") else "15px/1.45 Georgia, 'Times New Roman', serif"
    rows = []
    for item in quotation_data.get("items") or []:
        pid = str(item.get("product_id") or "")
        desc = escape(str(labels.get(pid) or pid or "Item"))
        rows.append(
            "<tr>"
            f"<td>{desc}</td>"
            f"<td style='text-align:right'>{float(item.get('quantity') or 0):.2f}</td>"
            f"<td style='text-align:right'>{float(item.get('unit_price') or 0):.2f}</td>"
            f"<td style='text-align:right'>{float(item.get('line_total') or 0):.2f}</td>"
            "</tr>"
        )
    meta = []
    if company_address:
        meta.append(escape(str(company_address)))
    if company_phone:
        meta.append(f"Tel: {escape(str(company_phone))}")
    if company_email:
        meta.append(escape(str(company_email)))
    if tax_registration_number:
        meta.append(f"Tax #: {escape(str(tax_registration_number))}")
    valid = str(quotation_data.get("valid_until") or "")[:10]
    valid_line = f" · Valid until {escape(valid)}" if valid else ""
    customer_addr_html = f"<br>{escape(str(customer_address))}" if customer_address else ""
    notes_html = (
        f"<p class='muted'>Notes: {escape(str(quotation_data.get('notes')))}</p>"
        if quotation_data.get("notes")
        else ""
    )
    header_html = header_footer_html(document_header, css_class="doc-header")
    footer_html = header_footer_html(document_footer, css_class="doc-footer") or (
        '<p class="muted" style="margin-top:28px">Thank you for considering us.</p>'
    )
    q_no = escape(str(quotation_data.get("quotation_number") or ""))
    status = escape(str(quotation_data.get("status") or ""))
    rows_html = "".join(rows) or "<tr><td colspan='4' class='muted'>No lines</td></tr>"
    meta_html = "<br>".join(meta)
    brand_block = brand_html_block(
        company_name=company_name,
        logo_data_url=logo_data_url,
        trading_name=trading_name,
        meta_html=meta_html,
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Quotation {q_no}</title>
<style>
  body {{ margin:0; background:#f3f0ea; color:#1c1917; font:{font}; }}
  .sheet {{ max-width:{max_width}; margin:0 auto; min-height:100vh; padding:28px 32px 40px;
    background:linear-gradient(180deg,#fffdf8 0%,#f7f1e8 100%); }}
  h1 {{ font-size:1.8rem; letter-spacing:.04em; margin:0 0 6px; font-weight:700; }}
  h2 {{ font-size:1.15rem; margin:24px 0 8px; font-weight:600; }}
  .muted {{ color:#57534e; }}
  .brand {{ border-bottom:2px solid #292524; padding-bottom:14px; margin-bottom:18px; }}
  .brand .logo {{ display:block; max-height:72px; max-width:220px; margin:0 0 10px; object-fit:contain; }}
  .doc-header {{ margin:8px 0 0; }}
  .doc-footer {{ margin-top:28px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
  th, td {{ padding:8px 4px; border-bottom:1px solid #d6d3d1; text-align:left; }}
  th {{ font-size:.85rem; text-transform:uppercase; letter-spacing:.06em; color:#44403c; }}
  .totals {{ margin-top:18px; width:100%; max-width:280px; margin-left:auto; }}
  .totals div {{ display:flex; justify-content:space-between; padding:4px 0; }}
  .totals .grand {{ font-weight:700; border-top:2px solid #292524; margin-top:6px; padding-top:8px; }}
  .toolbar {{ position:sticky; top:0; background:#fffdf8cc; padding:8px 0 12px; }}
  @media print {{ body {{ background:#fff; }} .toolbar {{ display:none; }} .sheet {{ max-width:none; background:#fff; }} }}
</style></head><body><div class="sheet">
  <div class="toolbar"><button onclick="window.print()">Print</button></div>
  {brand_block}
  {header_html}
  <h2>Quotation {q_no}</h2>
  <div class="muted">Status: {status}{valid_line}</div>
  <p><strong>Quote for</strong><br>{escape(customer_name)}{customer_addr_html}</p>
  <table>
    <thead><tr><th>Item</th><th style="text-align:right">Qty</th><th style="text-align:right">Price</th><th style="text-align:right">Total</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="totals">
    <div><span>Subtotal</span><span>{cur} {float(quotation_data.get("subtotal") or 0):.2f}</span></div>
    <div><span>Tax</span><span>{cur} {float(quotation_data.get("tax_amount") or 0):.2f}</span></div>
    <div><span>Discount</span><span>{cur} {float(quotation_data.get("discount_amount") or 0):.2f}</span></div>
    <div class="grand"><span>Total</span><span>{cur} {float(quotation_data.get("total_amount") or 0):.2f}</span></div>
  </div>
  {notes_html}
  {footer_html}
</div></body></html>"""


def render_quotation_pdf(
    quotation_data: dict,
    *,
    company_name: str,
    customer_name: str,
    template: str = "a4",
    currency: str = "GHS",
    company_address: str | None = None,
    company_phone: str | None = None,
    company_email: str | None = None,
    tax_registration_number: str | None = None,
    customer_address: str | None = None,
    item_labels: dict[str, str] | None = None,
    logo_data_url: str | None = None,
    trading_name: str | None = None,
    legal_name: str | None = None,
    has_logo: bool = False,
    document_header: str | None = None,
    document_footer: str | None = None,
) -> bytes:
    tpl = template if template in QUOTATION_PRINT_TEMPLATES else "a4"
    text = render_quotation_text(
        quotation_data,
        company_name=company_name,
        customer_name=customer_name,
        template=tpl,
        currency=currency,
        company_address=company_address,
        company_phone=company_phone,
        company_email=company_email,
        tax_registration_number=tax_registration_number,
        customer_address=customer_address,
        item_labels=item_labels,
        logo_data_url=logo_data_url,
        trading_name=trading_name,
        legal_name=legal_name,
        has_logo=has_logo,
        document_header=document_header,
        document_footer=document_footer,
    )
    title = f"QUOTATION {quotation_data.get('quotation_number') or ''}"
    return render_branded_lines_pdf(
        text.splitlines() or [""],
        template=tpl,
        company_name=company_name,
        title=title,
    )


async def create_quotation(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    customer_id: str,
    items: list[dict],
    discount_amount: float = 0,
    notes: str | None = None,
    valid_days: int = 14,
) -> m.SalesQuotation:
    await get_customer(db, tenant_id, customer_id)
    from app.customers import customer_group_discount_percent

    group_discount = await customer_group_discount_percent(db, tenant_id, customer_id)
    subtotal, tax_total, prepared = await _prepare_lines(
        db, tenant_id, items, group_discount_percent=group_discount
    )
    discount_amount = float(discount_amount or 0)
    total = round(subtotal + tax_total - discount_amount, 2)
    if total < 0:
        raise HTTPException(status_code=400, detail="Total cannot be negative")
    quote = m.SalesQuotation(
        tenant_id=tenant_id,
        quotation_number=await _allocate(db, tenant_id, "sales_quotation"),
        customer_id=customer_id,
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        discount_amount=discount_amount,
        total_amount=total,
        valid_until=datetime.utcnow() + timedelta(days=max(valid_days, 1)),
        notes=notes,
        created_by=user_id,
    )
    db.add(quote)
    await db.flush()
    for line, _ in prepared:
        db.add(m.SalesQuotationItem(tenant_id=tenant_id, quotation_id=quote.id, **line))
    await db.flush()
    return quote


async def send_quotation(
    db: AsyncSession,
    tenant_id: str,
    quotation_id: str,
    *,
    to: str | None = None,
) -> tuple[m.SalesQuotation, dict]:
    """Email quotation to customer, then mark status=sent. Delivery must succeed first."""
    from app import emailer

    quote = await get_quotation(db, tenant_id, quotation_id)
    if quote.status not in {"draft", "sent"}:
        raise HTTPException(status_code=409, detail=f"Cannot send quotation in status {quote.status}")
    if quote.valid_until and quote.valid_until < datetime.utcnow() and quote.status == "draft":
        quote.status = "expired"
        await db.flush()
        raise HTTPException(status_code=409, detail="Quotation has expired")

    customer = await get_customer(db, tenant_id, quote.customer_id)
    recipient = (to or customer.email or "").strip()
    if not recipient:
        raise HTTPException(
            status_code=400,
            detail="Customer has no email; set customer email or pass to= override",
        )

    tenant = await db.get(m.Tenant, tenant_id)
    company_name = tenant.company_name if tenant else "RIBDIGI ERP"
    currency = (tenant.currency if tenant else None) or "GHS"
    payload = await serialize_quotation(db, quote)

    result = await emailer.send_quotation_email(
        to=recipient,
        company_name=company_name,
        currency=currency,
        customer_name=customer.name,
        quotation=payload,
    )
    if not result.sent:
        if result.mode == "disabled":
            raise HTTPException(status_code=503, detail="Email delivery is disabled")
        raise HTTPException(status_code=502, detail=result.error or "Email send failed")

    now = datetime.utcnow()
    quote.status = "sent"
    quote.emailed_at = now
    quote.emailed_to = recipient
    quote.updated_at = now
    await db.flush()
    delivery = {
        "sent": result.sent,
        "mode": result.mode,
        "to": recipient,
        "emailed_at": quote.emailed_at,
    }
    return quote, delivery


async def accept_quotation(db: AsyncSession, tenant_id: str, quotation_id: str) -> m.SalesQuotation:
    quote = await get_quotation(db, tenant_id, quotation_id)
    if quote.status not in {"draft", "sent"}:
        raise HTTPException(status_code=409, detail=f"Cannot accept quotation in status {quote.status}")
    if quote.valid_until and quote.valid_until < datetime.utcnow():
        quote.status = "expired"
        await db.flush()
        raise HTTPException(status_code=409, detail="Quotation has expired")
    quote.status = "accepted"
    quote.updated_at = datetime.utcnow()
    await db.flush()
    return quote


async def reject_quotation(db: AsyncSession, tenant_id: str, quotation_id: str) -> m.SalesQuotation:
    quote = await get_quotation(db, tenant_id, quotation_id)
    if quote.status not in {"draft", "sent"}:
        raise HTTPException(status_code=409, detail=f"Cannot reject quotation in status {quote.status}")
    quote.status = "rejected"
    quote.updated_at = datetime.utcnow()
    await db.flush()
    return quote


# --- Orders ---


async def get_order(db: AsyncSession, tenant_id: str, order_id: str) -> m.SalesOrder:
    row = (
        await db.execute(
            select(m.SalesOrder).where(m.SalesOrder.id == order_id, m.SalesOrder.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Sales order not found")
    return row


async def list_order_items(db: AsyncSession, tenant_id: str, order_id: str) -> list[m.SalesOrderItem]:
    return (
        await db.execute(
            select(m.SalesOrderItem).where(
                m.SalesOrderItem.tenant_id == tenant_id,
                m.SalesOrderItem.sales_order_id == order_id,
            )
        )
    ).scalars().all()


async def list_order_reservations(
    db: AsyncSession, tenant_id: str, order_id: str
) -> list[m.StockReservation]:
    return (
        await db.execute(
            select(m.StockReservation).where(
                m.StockReservation.tenant_id == tenant_id,
                m.StockReservation.sales_order_id == order_id,
            )
        )
    ).scalars().all()


async def serialize_order(db: AsyncSession, order: m.SalesOrder) -> dict:
    items = await list_order_items(db, order.tenant_id, order.id)
    reservations = await list_order_reservations(db, order.tenant_id, order.id)
    reserved_by_item = {
        r.sales_order_item_id: float(r.quantity or 0)
        for r in reservations
        if r.status == "active"
    }
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "quotation_id": order.quotation_id,
        "store_id": order.store_id,
        "warehouse_id": order.warehouse_id,
        "status": order.status,
        "subtotal": float(order.subtotal),
        "tax_amount": float(order.tax_amount),
        "discount_amount": float(order.discount_amount),
        "total_amount": float(order.total_amount),
        "notes": order.notes,
        "delivery_date": order.delivery_date,
        "delivery_address": order.delivery_address,
        "converted_invoice_id": order.converted_invoice_id,
        "confirmed_at": order.confirmed_at,
        "processing_at": order.processing_at,
        "shipped_at": order.shipped_at,
        "delivered_at": order.delivered_at,
        "created_at": order.created_at,
        "reserved_qty_total": sum(reserved_by_item.values()),
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount),
                "line_total": float(i.line_total),
                "reserved_qty": reserved_by_item.get(i.id, 0.0),
            }
            for i in items
        ],
        "reservations": [
            {
                "id": r.id,
                "product_id": r.product_id,
                "variant_id": r.variant_id,
                "warehouse_id": r.warehouse_id,
                "sales_order_item_id": r.sales_order_item_id,
                "quantity": float(r.quantity or 0),
                "status": r.status,
            }
            for r in reservations
        ],
    }


async def _resolve_order_warehouse(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str | None,
    warehouse_id: str | None,
) -> tuple[str | None, str | None]:
    resolved_store = None
    resolved_wh = None
    if store_id:
        from app.stores import get_store, warehouse_for_store

        store = await get_store(db, tenant_id, store_id)
        resolved_store = store.id
        wh = await warehouse_for_store(db, tenant_id, store.id)
        resolved_wh = wh.id
    if warehouse_id:
        from app.inventory import get_warehouse

        wh = await get_warehouse(db, tenant_id, warehouse_id)
        if resolved_wh and resolved_wh != wh.id:
            raise HTTPException(
                status_code=400,
                detail="warehouse_id does not match the selected store warehouse",
            )
        resolved_wh = wh.id
    return resolved_store, resolved_wh


async def reserve_order_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    order: m.SalesOrder,
    user_id: str | None = None,
) -> None:
    from app.inventory import reserve_product_stock

    existing = (
        await db.execute(
            select(m.StockReservation.id).where(
                m.StockReservation.tenant_id == tenant_id,
                m.StockReservation.sales_order_id == order.id,
                m.StockReservation.status == "active",
            )
        )
    ).scalars().all()
    if existing:
        return
    items = await list_order_items(db, tenant_id, order.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot reserve an empty order")
    for item in items:
        await reserve_product_stock(
            db,
            tenant_id=tenant_id,
            product_id=item.product_id,
            quantity=float(item.quantity),
            sales_order_id=order.id,
            sales_order_item_id=item.id,
            warehouse_id=order.warehouse_id,
            variant_id=item.variant_id,
            user_id=user_id,
        )


async def create_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    customer_id: str,
    items: list[dict],
    discount_amount: float = 0,
    notes: str | None = None,
    quotation_id: str | None = None,
    store_id: str | None = None,
    warehouse_id: str | None = None,
    delivery_date: datetime | None = None,
    delivery_address: str | None = None,
) -> m.SalesOrder:
    customer = await get_customer(db, tenant_id, customer_id)
    if quotation_id:
        quote = await get_quotation(db, tenant_id, quotation_id)
        if quote.customer_id != customer_id:
            raise HTTPException(status_code=400, detail="Quotation customer mismatch")
    resolved_store, resolved_wh = await _resolve_order_warehouse(
        db, tenant_id=tenant_id, store_id=store_id, warehouse_id=warehouse_id
    )
    from app.customers import customer_group_discount_percent

    group_discount = await customer_group_discount_percent(db, tenant_id, customer_id)
    subtotal, tax_total, prepared = await _prepare_lines(
        db, tenant_id, items, group_discount_percent=group_discount
    )
    discount_amount = float(discount_amount or 0)
    total = round(subtotal + tax_total - discount_amount, 2)
    address = (delivery_address or "").strip() or (customer.address or None)
    order = m.SalesOrder(
        tenant_id=tenant_id,
        order_number=await _allocate(db, tenant_id, "sales_order"),
        customer_id=customer_id,
        quotation_id=quotation_id,
        store_id=resolved_store,
        warehouse_id=resolved_wh,
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        discount_amount=discount_amount,
        total_amount=total,
        notes=notes,
        delivery_date=delivery_date,
        delivery_address=address,
        created_by=user_id,
    )
    db.add(order)
    await db.flush()
    for line, _ in prepared:
        db.add(m.SalesOrderItem(tenant_id=tenant_id, sales_order_id=order.id, **line))
    await db.flush()
    return order


async def update_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    order_id: str,
    notes: str | None = None,
    delivery_date: datetime | None = None,
    delivery_address: str | None = None,
    store_id: str | None = None,
    warehouse_id: str | None = None,
    clear_delivery_date: bool = False,
) -> m.SalesOrder:
    order = await get_order(db, tenant_id, order_id)
    if order.status not in {"draft", "confirmed", "processing"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot update order in status {order.status}",
        )
    if notes is not None:
        order.notes = notes
    if clear_delivery_date:
        order.delivery_date = None
    elif delivery_date is not None:
        order.delivery_date = delivery_date
    if delivery_address is not None:
        order.delivery_address = delivery_address.strip() or None
    if store_id is not None or warehouse_id is not None:
        if order.status != "draft":
            raise HTTPException(
                status_code=409,
                detail="Store/warehouse can only be changed while the order is draft",
            )
        resolved_store, resolved_wh = await _resolve_order_warehouse(
            db,
            tenant_id=tenant_id,
            store_id=store_id if store_id is not None else order.store_id,
            warehouse_id=warehouse_id if warehouse_id is not None else order.warehouse_id,
        )
        order.store_id = resolved_store
        order.warehouse_id = resolved_wh
    order.updated_at = datetime.utcnow()
    await db.flush()
    return order


ORDER_LOGISTICS_TRANSITIONS = {
    "processing": {"from": {"confirmed"}, "ts_field": "processing_at"},
    "shipped": {"from": {"processing"}, "ts_field": "shipped_at"},
    "delivered": {"from": {"shipped"}, "ts_field": "delivered_at"},
}


async def advance_order_status(
    db: AsyncSession,
    *,
    tenant_id: str,
    order_id: str,
    target_status: str,
    user_id: str | None = None,
) -> m.SalesOrder:
    meta = ORDER_LOGISTICS_TRANSITIONS.get(target_status)
    if not meta:
        raise HTTPException(status_code=400, detail=f"Unsupported status transition to {target_status}")
    order = await get_order(db, tenant_id, order_id)
    if order.status not in meta["from"]:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot mark order {target_status} from status {order.status}",
        )
    now = datetime.utcnow()
    order.status = target_status
    setattr(order, meta["ts_field"], now)
    order.updated_at = now
    from app import audit as audit_svc
    from app.notifications import create_notification

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="sales",
        action=f"order_{target_status}",
        entity="sales_order",
        entity_id=order.id,
        details={"order_number": order.order_number, "status": target_status},
    )
    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title=f"Sales order {target_status}",
        message=f"Order {order.order_number} marked {target_status}.",
        entity_type="sales_order",
        entity_id=order.id,
    )
    await db.flush()
    return order


async def convert_quotation_to_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    quotation_id: str,
) -> m.SalesOrder:
    quote = await get_quotation(db, tenant_id, quotation_id)
    if quote.status not in {"draft", "sent", "accepted"}:
        raise HTTPException(status_code=409, detail=f"Cannot convert quotation in status {quote.status}")
    if quote.valid_until and quote.valid_until < datetime.utcnow() and quote.status != "accepted":
        quote.status = "expired"
        await db.flush()
        raise HTTPException(status_code=409, detail="Quotation has expired")
    items = await list_quotation_items(db, tenant_id, quote.id)
    order = await create_order(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=quote.customer_id,
        items=[
            {
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount),
            }
            for i in items
        ],
        discount_amount=float(quote.discount_amount or 0),
        notes=quote.notes,
        quotation_id=quote.id,
    )
    quote.status = "converted"
    quote.converted_order_id = order.id
    quote.updated_at = datetime.utcnow()
    await db.flush()
    return order


async def confirm_order(
    db: AsyncSession,
    tenant_id: str,
    order_id: str,
    *,
    user_id: str | None = None,
) -> m.SalesOrder:
    order = await get_order(db, tenant_id, order_id)
    if order.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot confirm order in status {order.status}")
    await reserve_order_stock(db, tenant_id=tenant_id, order=order, user_id=user_id)
    order.status = "confirmed"
    order.confirmed_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Sales order confirmed",
        message=f"Order {order.order_number} confirmed; inventory reserved.",
        entity_type="sales_order",
        entity_id=order.id,
    )
    await db.flush()
    return order


async def cancel_order(
    db: AsyncSession,
    tenant_id: str,
    order_id: str,
    *,
    user_id: str | None = None,
) -> m.SalesOrder:
    order = await get_order(db, tenant_id, order_id)
    if order.status not in {"draft", "confirmed", "processing"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel order in status {order.status}")
    from app.inventory import release_reservations_for_order

    await release_reservations_for_order(
        db, tenant_id=tenant_id, sales_order_id=order.id, user_id=user_id
    )
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
    await db.flush()
    return order


async def convert_order_to_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    order_id: str,
) -> m.SalesInvoice:
    order = await get_order(db, tenant_id, order_id)
    if order.status not in {"draft", "confirmed", "processing", "shipped", "delivered"}:
        raise HTTPException(status_code=409, detail=f"Cannot invoice order in status {order.status}")
    if order.status == "draft":
        await reserve_order_stock(db, tenant_id=tenant_id, order=order, user_id=user_id)
        order.confirmed_at = order.confirmed_at or datetime.utcnow()
    items = await list_order_items(db, tenant_id, order.id)
    invoice = await create_sales_invoice(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        customer_id=order.customer_id,
        store_id=order.store_id,
        items=[
            {
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount),
            }
            for i in items
        ],
        discount_amount=float(order.discount_amount or 0),
        notes=order.notes,
    )
    invoice.sales_order_id = order.id
    invoice.quotation_id = order.quotation_id
    order.status = "invoiced"
    order.converted_invoice_id = invoice.id
    order.updated_at = datetime.utcnow()
    if order.quotation_id:
        quote = await get_quotation(db, tenant_id, order.quotation_id)
        quote.converted_invoice_id = invoice.id
        quote.status = "converted"
        quote.updated_at = datetime.utcnow()
    await db.flush()
    return invoice


async def convert_quotation_to_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    quotation_id: str,
) -> m.SalesInvoice:
    order = await convert_quotation_to_order(
        db, tenant_id=tenant_id, user_id=user_id, quotation_id=quotation_id
    )
    return await convert_order_to_invoice(db, tenant_id=tenant_id, user_id=user_id, order_id=order.id)


# --- Returns ---


async def get_return(db: AsyncSession, tenant_id: str, return_id: str) -> m.SalesReturn:
    row = (
        await db.execute(
            select(m.SalesReturn).where(m.SalesReturn.id == return_id, m.SalesReturn.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Sales return not found")
    return row


async def list_return_items(db: AsyncSession, tenant_id: str, return_id: str) -> list[m.SalesReturnItem]:
    return (
        await db.execute(
            select(m.SalesReturnItem).where(
                m.SalesReturnItem.tenant_id == tenant_id,
                m.SalesReturnItem.sales_return_id == return_id,
            )
        )
    ).scalars().all()


async def serialize_return(db: AsyncSession, ret: m.SalesReturn) -> dict:
    items = await list_return_items(db, ret.tenant_id, ret.id)
    return {
        "id": ret.id,
        "return_number": ret.return_number,
        "credit_note_number": ret.credit_note_number,
        "customer_id": ret.customer_id,
        "sales_invoice_id": ret.sales_invoice_id,
        "status": ret.status,
        "reason": ret.reason,
        "restock": ret.restock,
        "subtotal": float(ret.subtotal),
        "tax_amount": float(ret.tax_amount),
        "total_amount": float(ret.total_amount),
        "notes": ret.notes,
        "posted_at": ret.posted_at,
        "created_at": ret.created_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "line_total": float(i.line_total),
                "condition": i.condition,
            }
            for i in items
        ],
    }


async def create_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    sales_invoice_id: str,
    items: list[dict],
    reason: str = "other",
    restock: bool = True,
    notes: str | None = None,
) -> m.SalesReturn:
    if reason not in RETURN_REASONS:
        raise HTTPException(status_code=400, detail=f"reason must be one of {sorted(RETURN_REASONS)}")
    invoice = await get_invoice(db, tenant_id, sales_invoice_id)
    if invoice.status not in {"posted", "partial", "paid"}:
        raise HTTPException(status_code=409, detail="Returns require a posted invoice")
    inv_items = {
        (i.product_id, i.variant_id): i for i in await list_invoice_items(db, tenant_id, invoice.id)
    }
    if not items:
        raise HTTPException(status_code=400, detail="Return requires line items")

    subtotal = 0.0
    tax_total = 0.0
    prepared: list[dict] = []
    for item in items:
        pid = item["product_id"]
        vid = item.get("variant_id")
        src = inv_items.get((pid, vid))
        if not src and vid is None:
            # Allow omitting variant_id when the invoice has a single matching product line
            matches = [v for (p, _), v in inv_items.items() if p == pid]
            if len(matches) == 1:
                src = matches[0]
                vid = src.variant_id
        if not src:
            raise HTTPException(status_code=400, detail=f"Product {pid} not on original invoice")
        qty = float(item["quantity"])
        if qty <= 0 or qty > float(src.quantity) + 1e-9:
            raise HTTPException(status_code=400, detail="Return quantity exceeds invoice quantity")
        unit = float(src.unit_price)
        rate = float(src.tax_rate or 0)
        line_net = round(qty * unit, 2)
        line_tax = round(line_net * (rate / 100.0), 2)
        line_total = round(line_net + line_tax, 2)
        subtotal += line_net
        tax_total += line_tax
        prepared.append(
            {
                "product_id": pid,
                "variant_id": vid,
                "quantity": qty,
                "unit_price": unit,
                "tax_rate": rate,
                "line_total": line_total,
                "condition": item.get("condition") or ("sellable" if restock else "discard"),
            }
        )

    ret = m.SalesReturn(
        tenant_id=tenant_id,
        return_number=await _allocate(db, tenant_id, "sales_return"),
        customer_id=invoice.customer_id,
        sales_invoice_id=invoice.id,
        status="draft",
        reason=reason,
        restock=restock,
        subtotal=round(subtotal, 2),
        tax_amount=round(tax_total, 2),
        total_amount=round(subtotal + tax_total, 2),
        notes=notes,
        created_by=user_id,
    )
    db.add(ret)
    await db.flush()
    for line in prepared:
        db.add(m.SalesReturnItem(tenant_id=tenant_id, sales_return_id=ret.id, **line))
    await db.flush()
    return ret


async def post_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    return_id: str,
) -> m.SalesReturn:
    ret = await get_return(db, tenant_id, return_id)
    if ret.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot post return in status {ret.status}")
    items = await list_return_items(db, tenant_id, ret.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot post empty return")

    for item in items:
        if ret.restock and item.condition == "sellable":
            qty = float(item.quantity)
            await apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=item.product_id,
                quantity_delta=qty,
                movement_type="stock_in",
                user_id=user_id,
                reference_type="sales_return",
                reference_id=ret.id,
                notes=f"Return {ret.return_number}",
                variant_id=item.variant_id,
            )
            if item.variant_id:
                variant = await get_variant(db, tenant_id, item.variant_id)
                variant.stock_qty = float(variant.stock_qty or 0) + qty
        else:
            # Discarded: still log movement as adjust out of sold goods without increasing sellable stock
            from app import audit as audit_svc
            await audit_svc.record_event(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                action="return_discarded",
                entity="sales_return_item",
                entity_id=item.id,
                details={
                "product_id": item.product_id,
                "variant_id": item.variant_id,
                "quantity": float(item.quantity),
                },
                module='sales',
            )

    customer = await get_customer(db, tenant_id, ret.customer_id)
    customer.balance = max(float(customer.balance or 0) - float(ret.total_amount), 0)

    invoice = await get_invoice(db, tenant_id, ret.sales_invoice_id)
    invoice.paid_amount = min(
        float(invoice.total_amount),
        float(invoice.paid_amount or 0) + float(ret.total_amount),
    )
    from app.sales import invoice_payment_status

    if invoice.status in {"posted", "partial", "paid"}:
        invoice.status = invoice_payment_status(float(invoice.total_amount), float(invoice.paid_amount))
        # credit note style: treat return as reducing open balance
        if float(invoice.paid_amount) + 1e-9 >= float(invoice.total_amount):
            invoice.status = "paid"
        elif float(invoice.paid_amount) > 0:
            invoice.status = "partial"
        invoice.updated_at = datetime.utcnow()

    ret.status = "posted"
    ret.posted_at = datetime.utcnow()
    ret.credit_note_number = await _allocate(db, tenant_id, "sales_credit_note")

    from app.accounting import post_sales_return_journal

    await post_sales_return_journal(db, tenant_id=tenant_id, user_id=user_id, sales_return=ret)

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Sales return posted",
        message=(
            f"Return {ret.return_number} / {ret.credit_note_number} posted for "
            f"{float(ret.total_amount):.2f}."
        ),
        entity_type="sales_return",
        entity_id=ret.id,
    )
    await db.flush()
    return ret


CREDIT_NOTE_PRINT_TEMPLATES = QUOTATION_PRINT_TEMPLATES
CREDIT_NOTE_PRINT_FORMATS = QUOTATION_PRINT_FORMATS


def render_credit_note_text(
    return_data: dict,
    *,
    company_name: str,
    customer_name: str,
    template: str = "a4",
    currency: str = "GHS",
    company_address: str | None = None,
    company_phone: str | None = None,
    company_email: str | None = None,
    tax_registration_number: str | None = None,
    customer_address: str | None = None,
    invoice_number: str | None = None,
    item_labels: dict[str, str] | None = None,
    logo_data_url: str | None = None,
    trading_name: str | None = None,
    legal_name: str | None = None,
    has_logo: bool = False,
    document_header: str | None = None,
    document_footer: str | None = None,
) -> str:
    from app.print_branding import header_footer_text_lines

    tpl = template if template in CREDIT_NOTE_PRINT_TEMPLATES else "a4"
    width = 48 if tpl == "thermal_80" else 32 if tpl == "thermal_58" else 72
    cur = currency or "GHS"
    labels = item_labels or {}
    cn = return_data.get("credit_note_number") or "—"
    lines = [company_name[:width]]
    if company_address:
        lines.append(str(company_address)[:width])
    if company_phone:
        lines.append(f"Tel: {company_phone}"[:width])
    if company_email:
        lines.append(str(company_email)[:width])
    if tax_registration_number:
        lines.append(f"Tax #: {tax_registration_number}"[:width])
    for part in header_footer_text_lines(document_header, width):
        lines.append(part[:width])
    lines.extend(
        [
            "",
            f"CREDIT NOTE {cn}"[:width],
            f"Return: {return_data.get('return_number')}"[:width],
            f"Customer: {customer_name}"[:width],
        ]
    )
    if customer_address:
        lines.append(str(customer_address)[:width])
    if invoice_number:
        lines.append(f"Invoice: {invoice_number}"[:width])
    lines.append(f"Status: {return_data.get('status')}"[:width])
    lines.append(f"Reason: {return_data.get('reason')}"[:width])
    if return_data.get("posted_at"):
        lines.append(f"Posted: {str(return_data['posted_at'])[:19]}"[:width])
    lines.extend(
        ["", f"{'Item':<{max(width - 28, 8)}} {'Qty':>6} {'Total':>10}"[:width], "-" * width]
    )
    for item in return_data.get("items") or []:
        pid = str(item.get("product_id") or "")
        desc = str(labels.get(pid) or pid or "Item")[: max(width - 28, 8)]
        lines.append(
            f"{desc:<{max(width - 28, 8)}} {float(item.get('quantity') or 0):>6.2f} "
            f"{float(item.get('line_total') or 0):>10.2f}"[:width]
        )
    lines.extend(
        [
            "-" * width,
            f"Subtotal: {cur} {float(return_data.get('subtotal') or 0):.2f}"[:width],
            f"Tax: {cur} {float(return_data.get('tax_amount') or 0):.2f}"[:width],
            f"TOTAL CREDIT: {cur} {float(return_data.get('total_amount') or 0):.2f}"[:width],
        ]
    )
    if return_data.get("notes"):
        lines.extend(["", f"Notes: {return_data['notes']}"[:width]])
    footer_lines = header_footer_text_lines(document_footer, width)
    if footer_lines:
        lines.append("")
        lines.extend(part[:width] for part in footer_lines)
    elif tpl.startswith("thermal"):
        lines.extend(["", "Thank you!"[:width]])
    return "\n".join(lines)


def render_credit_note_html(
    return_data: dict,
    *,
    company_name: str,
    customer_name: str,
    template: str = "a4",
    currency: str = "GHS",
    company_address: str | None = None,
    company_phone: str | None = None,
    company_email: str | None = None,
    tax_registration_number: str | None = None,
    customer_address: str | None = None,
    invoice_number: str | None = None,
    item_labels: dict[str, str] | None = None,
    logo_data_url: str | None = None,
    trading_name: str | None = None,
    legal_name: str | None = None,
    has_logo: bool = False,
    document_header: str | None = None,
    document_footer: str | None = None,
) -> str:
    from html import escape

    from app.print_branding import brand_html_block, header_footer_html

    tpl = template if template in CREDIT_NOTE_PRINT_TEMPLATES else "a4"
    cur = escape(currency or "GHS")
    labels = item_labels or {}
    max_width = "80mm" if tpl == "thermal_80" else "58mm" if tpl == "thermal_58" else "720px"
    font = "12px/1.4 monospace" if tpl.startswith("thermal") else "15px/1.45 Georgia, 'Times New Roman', serif"
    rows = []
    for item in return_data.get("items") or []:
        pid = str(item.get("product_id") or "")
        desc = escape(str(labels.get(pid) or pid or "Item"))
        rows.append(
            "<tr>"
            f"<td>{desc}</td>"
            f"<td style='text-align:right'>{float(item.get('quantity') or 0):.2f}</td>"
            f"<td style='text-align:right'>{float(item.get('unit_price') or 0):.2f}</td>"
            f"<td style='text-align:right'>{float(item.get('line_total') or 0):.2f}</td>"
            "</tr>"
        )
    meta = []
    if company_address:
        meta.append(escape(str(company_address)))
    if company_phone:
        meta.append(f"Tel: {escape(str(company_phone))}")
    if company_email:
        meta.append(escape(str(company_email)))
    if tax_registration_number:
        meta.append(f"Tax #: {escape(str(tax_registration_number))}")
    cn = escape(str(return_data.get("credit_note_number") or "—"))
    rn = escape(str(return_data.get("return_number") or ""))
    status = escape(str(return_data.get("status") or ""))
    reason = escape(str(return_data.get("reason") or ""))
    customer_addr_html = f"<br>{escape(str(customer_address))}" if customer_address else ""
    inv_html = f"<br>Invoice: {escape(str(invoice_number))}" if invoice_number else ""
    notes_html = (
        f"<p class='muted'>Notes: {escape(str(return_data.get('notes')))}</p>"
        if return_data.get("notes")
        else ""
    )
    header_html = header_footer_html(document_header, css_class="doc-header")
    footer_html = header_footer_html(document_footer, css_class="doc-footer")
    rows_html = "".join(rows) or "<tr><td colspan='4' class='muted'>No lines</td></tr>"
    meta_html = "<br>".join(meta)
    brand_block = brand_html_block(
        company_name=company_name,
        logo_data_url=logo_data_url,
        trading_name=trading_name,
        meta_html=meta_html,
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Credit Note {cn}</title>
<style>
  body {{ margin:0; background:#f3f0ea; color:#1c1917; font:{font}; }}
  .sheet {{ max-width:{max_width}; margin:0 auto; min-height:100vh; padding:28px 32px 40px;
    background:linear-gradient(180deg,#fffdf8 0%,#f7f1e8 100%); }}
  h1 {{ font-size:1.8rem; letter-spacing:.04em; margin:0 0 6px; font-weight:700; }}
  h2 {{ font-size:1.15rem; margin:24px 0 8px; font-weight:600; }}
  .muted {{ color:#57534e; }}
  .brand {{ border-bottom:2px solid #292524; padding-bottom:14px; margin-bottom:18px; }}
  .brand .logo {{ display:block; max-height:72px; max-width:220px; margin:0 0 10px; object-fit:contain; }}
  .doc-header {{ margin:8px 0 0; }}
  .doc-footer {{ margin-top:28px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:12px; }}
  th, td {{ padding:8px 4px; border-bottom:1px solid #d6d3d1; text-align:left; }}
  th {{ font-size:.85rem; text-transform:uppercase; letter-spacing:.06em; color:#44403c; }}
  .totals {{ margin-top:18px; width:100%; max-width:280px; margin-left:auto; }}
  .totals div {{ display:flex; justify-content:space-between; padding:4px 0; }}
  .totals .grand {{ font-weight:700; border-top:2px solid #292524; margin-top:6px; padding-top:8px; }}
  .toolbar {{ position:sticky; top:0; background:#fffdf8cc; padding:8px 0 12px; }}
  @media print {{ body {{ background:#fff; }} .toolbar {{ display:none; }} .sheet {{ max-width:none; background:#fff; }} }}
</style></head><body><div class="sheet">
  <div class="toolbar"><button onclick="window.print()">Print</button></div>
  {brand_block}
  {header_html}
  <h2>Credit Note {cn}</h2>
  <div class="muted">Return {rn} · Status: {status} · Reason: {reason}</div>
  <p><strong>Credit to</strong><br>{escape(customer_name)}{customer_addr_html}{inv_html}</p>
  <table>
    <thead><tr><th>Item</th><th style="text-align:right">Qty</th><th style="text-align:right">Price</th><th style="text-align:right">Total</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="totals">
    <div><span>Subtotal</span><span>{cur} {float(return_data.get("subtotal") or 0):.2f}</span></div>
    <div><span>Tax</span><span>{cur} {float(return_data.get("tax_amount") or 0):.2f}</span></div>
    <div class="grand"><span>Total credit</span><span>{cur} {float(return_data.get("total_amount") or 0):.2f}</span></div>
  </div>
  {notes_html}
  {footer_html}
</div></body></html>"""


def render_credit_note_pdf(
    return_data: dict,
    *,
    company_name: str,
    customer_name: str,
    template: str = "a4",
    currency: str = "GHS",
    company_address: str | None = None,
    company_phone: str | None = None,
    company_email: str | None = None,
    tax_registration_number: str | None = None,
    customer_address: str | None = None,
    invoice_number: str | None = None,
    item_labels: dict[str, str] | None = None,
    logo_data_url: str | None = None,
    trading_name: str | None = None,
    legal_name: str | None = None,
    has_logo: bool = False,
    document_header: str | None = None,
    document_footer: str | None = None,
) -> bytes:
    tpl = template if template in CREDIT_NOTE_PRINT_TEMPLATES else "a4"
    text = render_credit_note_text(
        return_data,
        company_name=company_name,
        customer_name=customer_name,
        template=tpl,
        currency=currency,
        company_address=company_address,
        company_phone=company_phone,
        company_email=company_email,
        tax_registration_number=tax_registration_number,
        customer_address=customer_address,
        invoice_number=invoice_number,
        item_labels=item_labels,
        logo_data_url=logo_data_url,
        trading_name=trading_name,
        legal_name=legal_name,
        has_logo=has_logo,
        document_header=document_header,
        document_footer=document_footer,
    )
    title = f"CREDIT NOTE {return_data.get('credit_note_number') or ''}"
    return render_branded_lines_pdf(
        text.splitlines() or [""],
        template=tpl,
        company_name=company_name,
        title=title,
    )
