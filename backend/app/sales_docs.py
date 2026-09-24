"""Sales quotations, orders, and returns."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.inventory import apply_stock_change
from app.doc_numbers import (
    next_credit_note_number,
    next_quotation_number,
    next_sales_order_number,
    next_sales_return_number,
)
from app.sales import create_sales_invoice, get_customer, require_active_customer, get_invoice, list_invoice_items
from app.tax import resolve_product_tax
from app.catalog import get_variant, resolve_sale_line

RETURN_REASONS = frozenset({"damaged", "wrong_item", "defective", "customer_change", "other"})
RETURN_CONDITIONS = frozenset({"sellable", "discard"})
# Manage list statuses (full quotation lifecycle).
QT_MANAGE_STATUSES = frozenset(
    {"draft", "sent", "accepted", "rejected", "expired", "converted"}
)
# Manage list statuses (full sales order fulfillment lifecycle).
SO_MANAGE_STATUSES = frozenset(
    {
        "draft",
        "confirmed",
        "processing",
        "shipped",
        "delivered",
        "invoiced",
        "cancelled",
    }
)

QUOTATION_PRINT_TEMPLATES = INVOICE_PRINT_TEMPLATES
QUOTATION_PRINT_FORMATS = INVOICE_PRINT_FORMATS


async def _prepare_lines(
    db: AsyncSession,
    tenant_id: str,
    items: list[dict],
    *,
    customer_id: str | None = None,
) -> tuple[float, float, list[tuple[dict, float]]]:
    from app.uom import resolve_line_unit

    if not items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    from app.workspace import assert_fk_company

    subtotal = 0.0
    tax_total = 0.0
    prepared: list[tuple[dict, float]] = []
    for item in items:
        product, variant, unit = await resolve_sale_line(
            db, tenant_id, item, customer_id=customer_id
        )
        unit_id, qty, _qty_base = await resolve_line_unit(
            db,
            tenant_id=tenant_id,
            product=product,
            unit_id=item.get("unit_id"),
            quantity=money_json(item["quantity"]),
        )
        discount = money_json(item.get("discount") or 0)
        # Auto-apply best FMCG trade scheme when no explicit line discount.
        if discount <= 0 and item.get("apply_fmcg_scheme", True) is not False:
            try:
                from app import fmcg as fmcg_svc
                from app import packages as packages_svc
                from app import tenants as tenants_svc

                tenant = await tenants_svc.get_tenant(db, tenant_id)
                if packages_svc.module_allowed(tenant, "fmcg"):
                    gross = money_json(qty * unit)
                    scheme_disc, _meta = await fmcg_svc.best_line_scheme_discount(
                        db,
                        tenant_id=tenant_id,
                        product_id=product.id,
                        line_qty=float(qty),
                        line_amount=float(gross),
                    )
                    if scheme_disc > 0:
                        discount = money_json(min(scheme_disc, gross))
            except Exception:
                pass
        explicit = item.get("tax_rate")
        if explicit is not None:
            spec = await resolve_product_tax(
                db, tenant_id, product, explicit_rate=money_json(explicit)
            )
        else:
            spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=None)
        # Stage 12 C1 — tax on net after line discount (same as POS / invoices).
        line_sub, line_tax, line_total, discount = calc_sale_line_amounts(
            spec, qty, unit, discount
        )
        subtotal += line_sub
        if not spec.is_reverse_charge:
            tax_total += line_tax
        prepared.append(
            (
                {
                    "product_id": product.id,
                    "variant_id": variant.id if variant else None,
                    "quantity": qty,
                    "unit_id": unit_id,
                    "unit_price": unit,
                    "tax_rate": spec.rate_pct,
                    "discount": discount,
                    "line_total": line_total,
                },
                line_total,
            )
        )
    return money_json(round(subtotal, 2)), money_json(round(tax_total, 2)), prepared


async def _allocate(
    db: AsyncSession, tenant_id: str, doc_key: str, *, company_id: str | None = None
) -> str:
    from app.document_numbering import allocate_document_number

    return await allocate_document_number(
        db, tenant_id=tenant_id, doc_key=doc_key, company_id=company_id
    )


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
        "company_id": getattr(quote, "company_id", None),
        "quotation_number": quote.quotation_number,
        "customer_id": quote.customer_id,
        "status": quote.status,
        "subtotal": money_json(quote.subtotal),
        "tax_amount": money_json(quote.tax_amount),
        "discount_amount": money_json(quote.discount_amount),
        "total_amount": money_json(quote.total_amount),
        "valid_until": quote.valid_until,
        "notes": quote.notes,
        "rejection_reason": quote.rejection_reason,
        "converted_order_id": quote.converted_order_id,
        "converted_invoice_id": quote.converted_invoice_id,
        "emailed_at": quote.emailed_at,
        "emailed_to": quote.emailed_to,
        "created_at": quote.created_at,
        "items": [
            {
                "id": i.id,
                "company_id": getattr(i, "company_id", None),
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": money_json(i.quantity),
                "unit_id": i.unit_id,
                "unit_price": money_json(i.unit_price),
                "tax_rate": money_json(i.tax_rate),
                "discount": money_json(i.discount),
                "line_total": money_json(i.line_total),
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
    from app.print_branding import platform_print_footer_text_lines

    lines.extend(platform_print_footer_text_lines(width=width, center=tpl.startswith("thermal")))
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

    from app.print_branding import brand_html_block, header_footer_html, platform_print_footer_html

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
    footer_html = f"{footer_html}{platform_print_footer_html()}"
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
    company_id: str | None = None,
) -> m.SalesQuotation:
    await require_active_customer(db, tenant_id, customer_id)
    subtotal, tax_total, prepared = await _prepare_lines(
        db, tenant_id, items, customer_id=customer_id
    )
    discount_amount = money_json(discount_amount or 0)
    total = money_json(round(subtotal + tax_total - discount_amount, 2))
    if total < 0:
        raise HTTPException(status_code=400, detail="Total cannot be negative")
    quote = m.SalesQuotation(
        tenant_id=tenant_id,
        quotation_number=await next_quotation_number(db, tenant_id),
        customer_id=customer_id,
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        discount_amount=discount_amount,
        total_amount=total,
        valid_until=datetime.utcnow() + timedelta(days=max(valid_days, 1)),
        notes=optional_honest_narrative(notes, label="quotation notes"),
        created_by=user_id,
    )
    db.add(quote)
    await db.flush()
    for line, _ in prepared:
        db.add(m.SalesQuotationItem(tenant_id=tenant_id, company_id=company_id, quotation_id=quote.id, **line))
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
        tenant=tenant,
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


async def reject_quotation(
    db: AsyncSession,
    tenant_id: str,
    quotation_id: str,
    *,
    reason: str | None = None,
) -> m.SalesQuotation:
    quote = await get_quotation(db, tenant_id, quotation_id)
    if quote.status not in {"draft", "sent"}:
        raise HTTPException(status_code=409, detail=f"Cannot reject quotation in status {quote.status}")
    if quote.valid_until and quote.valid_until < datetime.utcnow():
        quote.status = "expired"
        await db.flush()
        raise HTTPException(status_code=409, detail="Quotation has expired")
    reason_s = require_honest_narrative(reason, label="rejection reason")
    quote.status = "rejected"
    quote.rejection_reason = reason_s
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
    from app.reservations import list_order_reservations

    reservations = await list_order_reservations(db, order.tenant_id, order.id, status=None)
    active = [r for r in reservations if r.status == "active"]
    reserved_by_item = {
        r.sales_order_item_id: money_json(r.quantity) for r in active if r.sales_order_item_id
    }
    return {
        "id": order.id,
        "company_id": getattr(order, "company_id", None),
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "quotation_id": order.quotation_id,
        "store_id": getattr(order, "store_id", None),
        "delivery_date": getattr(order, "delivery_date", None),
        "delivery_address": getattr(order, "delivery_address", None),
        "status": order.status,
        "subtotal": money_json(order.subtotal),
        "tax_amount": money_json(order.tax_amount),
        "discount_amount": money_json(order.discount_amount),
        "total_amount": money_json(order.total_amount),
        "notes": order.notes,
        "delivery_date": order.delivery_date,
        "delivery_address": order.delivery_address,
        "converted_invoice_id": order.converted_invoice_id,
        "confirmed_at": order.confirmed_at,
        "processing_at": getattr(order, "processing_at", None),
        "shipped_at": getattr(order, "shipped_at", None),
        "delivered_at": getattr(order, "delivered_at", None),
        "created_at": order.created_at,
        "reserved_qty": money_json(round(sum(money_json(r.quantity) for r in active), 3)),
        "reservation_status": (
            "active"
            if active
            else ("consumed" if any(r.status == "consumed" for r in reservations) else None)
        ),
        "can_process": order.status == "confirmed",
        "can_ship": order.status == "processing",
        "can_deliver": order.status == "shipped",
        "can_cancel": order.status in {"draft", "confirmed", "processing"},
        "can_invoice": order.status in {"draft", "confirmed", "processing", "shipped", "delivered"},
        "items": [
            {
                "id": i.id,
                "company_id": getattr(i, "company_id", None),
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": money_json(i.quantity),
                "unit_id": i.unit_id,
                "unit_price": money_json(i.unit_price),
                "tax_rate": money_json(i.tax_rate),
                "discount": money_json(i.discount),
                "line_total": money_json(i.line_total),
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
    company_id: str | None = None,
) -> tuple[str | None, str | None]:
    resolved_store = None
    resolved_wh = None
    if store_id:
        from app.stores import get_store, warehouse_for_store

        store = await get_store(db, tenant_id, store_id, company_id=company_id)
        resolved_store = store.id
        wh = await warehouse_for_store(
            db, tenant_id, store.id, company_id=company_id
        )
        resolved_wh = wh.id
    if warehouse_id:
        from app.inventory import get_warehouse

        wh = await get_warehouse(db, tenant_id, warehouse_id, company_id=company_id)
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
            company_id=getattr(order, "company_id", None),
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
    delivery_date: datetime | None = None,
    delivery_address: str | None = None,
) -> m.SalesOrder:
    await require_active_customer(db, tenant_id, customer_id)
    if quotation_id:
        from app.workspace import assert_fk_company

        quote = await get_quotation(db, tenant_id, quotation_id)
        assert_fk_company(quote, company_id, detail="Quotation not found")
        if quote.customer_id != customer_id:
            raise HTTPException(status_code=400, detail="Quotation customer mismatch")
    resolved_store_id = None
    if store_id:
        from app.stores import get_store

        store = await get_store(db, tenant_id, store_id)
        resolved_store_id = store.id
    subtotal, tax_total, prepared = await _prepare_lines(
        db, tenant_id, items, customer_id=customer_id
    )
    discount_amount = money_json(discount_amount or 0)
    total = money_json(round(subtotal + tax_total - discount_amount, 2))
    order = m.SalesOrder(
        tenant_id=tenant_id,
        order_number=await next_sales_order_number(db, tenant_id),
        customer_id=customer_id,
        quotation_id=quotation_id,
        store_id=resolved_store_id,
        delivery_date=delivery_date,
        delivery_address=optional_honest_narrative(
            delivery_address, label="sales order delivery address", max_length=500
        ),
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        discount_amount=discount_amount,
        total_amount=total,
        notes=optional_honest_narrative(notes, label="sales order notes"),
        created_by=user_id,
    )
    db.add(order)
    await db.flush()
    for line, _ in prepared:
        db.add(m.SalesOrderItem(tenant_id=tenant_id, company_id=company_id, sales_order_id=order.id, **line))
    await db.flush()

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="new_order",
        title="New sales order",
        message=(
            f"Order {order.order_number} created for {customer.name} "
            f"({float(order.total_amount):.2f})."
        ),
        entity_type="sales_order",
        entity_id=order.id,
        company_id=getattr(order, "company_id", None),
    )
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
            company_id=getattr(order, "company_id", None),
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
        company_id=getattr(order, "company_id", None),
    )
    await db.flush()

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="new_order",
        title="Sales order created",
        message=f"Order {order.order_number} created for {money_json(order.total_amount or 0):.2f}.",
        entity_type="sales_order",
        entity_id=order.id,
    )
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
                "quantity": money_json(i.quantity),
                "unit_id": i.unit_id,
                "unit_price": money_json(i.unit_price),
                "tax_rate": money_json(i.tax_rate),
                "discount": money_json(i.discount),
            }
            for i in items
        ],
        discount_amount=money_json(quote.discount_amount or 0),
        notes=quote.notes,
        quotation_id=quote.id,
        company_id=getattr(quote, "company_id", None),
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
    store_id: str | None = None,
    delivery_date: datetime | None = None,
    delivery_address: str | None = None,
) -> m.SalesOrder:
    order = await get_order(db, tenant_id, order_id)
    if order.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot confirm order in status {order.status}")
    if store_id:
        from app.stores import get_store

        store = await get_store(db, tenant_id, store_id)
        order.store_id = store.id
    if delivery_date is not None:
        order.delivery_date = delivery_date
    if delivery_address is not None:
        order.delivery_address = optional_honest_narrative(
            delivery_address, label="sales order delivery address", max_length=500
        )
    if not order.store_id:
        raise HTTPException(
            status_code=400,
            detail="store_id is required to confirm a sales order (soft inventory reservation)",
        )

    from app.stores import warehouse_for_store
    from app.reservations import reserve_order

    wh = await warehouse_for_store(db, tenant_id, order.store_id)
    items = await list_order_items(db, tenant_id, order.id)
    await reserve_order(db, tenant_id=tenant_id, order=order, items=items, warehouse_id=wh.id)

    order.status = "confirmed"
    order.confirmed_at = datetime.utcnow()
    order.updated_at = datetime.utcnow()
    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="new_order",
        title="Sales order confirmed",
        message=f"Order {order.order_number} confirmed; inventory reserved.",
        entity_type="sales_order",
        entity_id=order.id,
        company_id=getattr(order, "company_id", None),
    )
    await db.flush()
    return order


ORDER_CANCELABLE = frozenset({"draft", "confirmed", "processing"})
ORDER_INVOICEABLE = frozenset({"draft", "confirmed", "processing", "shipped", "delivered"})
# Soft holds remain active through fulfillment until cancel or invoice post.
ORDER_RESERVED_STATUSES = frozenset({"confirmed", "processing", "shipped", "delivered"})


async def _advance_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    order_id: str,
    from_status: str,
    to_status: str,
    stamp_field: str,
    notify_title: str,
    notify_message: str,
) -> m.SalesOrder:
    order = await get_order(db, tenant_id, order_id)
    if order.status != from_status:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot move order to {to_status} from status {order.status}",
        )
    order.status = to_status
    setattr(order, stamp_field, datetime.utcnow())
    order.updated_at = datetime.utcnow()
    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title=notify_title,
        message=notify_message.format(number=order.order_number),
        entity_type="sales_order",
        entity_id=order.id,
    )
    await db.flush()
    return order


async def start_processing_order(db: AsyncSession, tenant_id: str, order_id: str) -> m.SalesOrder:
    return await _advance_order(
        db,
        tenant_id=tenant_id,
        order_id=order_id,
        from_status="confirmed",
        to_status="processing",
        stamp_field="processing_at",
        notify_title="Sales order processing",
        notify_message="Order {number} is now processing.",
    )


async def ship_order(db: AsyncSession, tenant_id: str, order_id: str) -> m.SalesOrder:
    return await _advance_order(
        db,
        tenant_id=tenant_id,
        order_id=order_id,
        from_status="processing",
        to_status="shipped",
        stamp_field="shipped_at",
        notify_title="Sales order shipped",
        notify_message="Order {number} has been shipped.",
    )


async def deliver_order(db: AsyncSession, tenant_id: str, order_id: str) -> m.SalesOrder:
    return await _advance_order(
        db,
        tenant_id=tenant_id,
        order_id=order_id,
        from_status="shipped",
        to_status="delivered",
        stamp_field="delivered_at",
        notify_title="Sales order delivered",
        notify_message="Order {number} has been delivered.",
    )


async def cancel_order(
    db: AsyncSession,
    tenant_id: str,
    order_id: str,
    *,
    user_id: str | None = None,
    reason: str | None = None,
) -> m.SalesOrder:
    reason_s = require_honest_narrative(reason, label="cancel reason")
    order = await get_order(db, tenant_id, order_id)
    if order.status not in ORDER_CANCELABLE:
        raise HTTPException(status_code=409, detail=f"Cannot cancel order in status {order.status}")
    if order.status in ORDER_RESERVED_STATUSES:
        from app.reservations import release_order_reservations

        await release_order_reservations(db, tenant_id=tenant_id, order_id=order.id)
    order.status = "cancelled"
    order.notes = ((order.notes or "") + f"\nCancel: {reason_s}").strip()
    order.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="so_cancelled",
            entity="sales_order",
            entity_id=order.id,
            details={"order_number": order.order_number, "reason": reason_s},
        )
    )
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
    if order.status not in ORDER_INVOICEABLE:
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
                "quantity": money_json(i.quantity),
                "unit_id": i.unit_id,
                "unit_price": money_json(i.unit_price),
                "tax_rate": money_json(i.tax_rate),
                "discount": money_json(i.discount),
            }
            for i in items
        ],
        discount_amount=money_json(order.discount_amount or 0),
        notes=order.notes,
        company_id=getattr(order, "company_id", None),
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
        "company_id": getattr(ret, "company_id", None),
        "return_number": ret.return_number,
        "credit_note_number": getattr(ret, "credit_note_number", None),
        "customer_id": ret.customer_id,
        "sales_invoice_id": ret.sales_invoice_id,
        "status": ret.status,
        "reason": ret.reason,
        "restock": ret.restock,
        "subtotal": money_json(ret.subtotal),
        "tax_amount": money_json(ret.tax_amount),
        "total_amount": money_json(ret.total_amount),
        "settlement_method": getattr(ret, "settlement_method", None),
        "refund_payment_method": getattr(ret, "refund_payment_method", None),
        "refunded_amount": money_json(getattr(ret, "refunded_amount", None)),
        "notes": ret.notes,
        "posted_at": ret.posted_at,
        "created_at": ret.created_at,
        "can_cancel": ret.status == "draft",
        "items": [
            {
                "id": i.id,
                "company_id": getattr(i, "company_id", None),
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": money_json(i.quantity),
                "unit_price": money_json(i.unit_price),
                "tax_rate": money_json(i.tax_rate),
                "line_total": money_json(i.line_total),
                "condition": i.condition,
            }
            for i in items
        ],
    }


async def cancel_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    return_id: str,
    reason: str | None = None,
) -> m.SalesReturn:
    reason_s = require_honest_narrative(reason, label="cancel reason")
    ret = await get_return(db, tenant_id, return_id)
    if ret.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft sales returns can be cancelled")
    ret.status = "cancelled"
    ret.notes = ((ret.notes or "") + f"\nCancel: {reason_s}").strip()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="sales_return_cancelled",
            entity="sales_return",
            entity_id=ret.id,
            details={"return_number": ret.return_number, "reason": reason_s},
        )
    )
    return ret


async def create_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    sales_invoice_id: str,
    items: list[dict],
    reason: str,
    restock: bool = True,
    notes: str | None = None,
    company_id: str | None = None,
) -> m.SalesReturn:
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if reason not in RETURN_REASONS:
        raise HTTPException(status_code=400, detail=f"reason must be one of {sorted(RETURN_REASONS)}")
    invoice = await get_invoice(db, tenant_id, sales_invoice_id)
    if invoice.status not in {"posted", "sent", "partial", "paid", "overdue"}:
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
        qty = money_json(item["quantity"])
        if qty <= 0 or qty > money_json(src.quantity) + 1e-9:
            raise HTTPException(status_code=400, detail="Return quantity exceeds invoice quantity")
        unit = money_json(src.unit_price)
        rate = money_json(src.tax_rate or 0)
        line_net = money_json(round(qty * unit, 2))
        line_tax = money_json(round(line_net * (rate / 100.0), 2))
        line_total = money_json(round(line_net + line_tax, 2))
        subtotal += line_net
        tax_total += line_tax
        condition = (item.get("condition") or "").strip()
        if not condition:
            raise HTTPException(status_code=400, detail="items[].condition is required")
        if condition not in RETURN_CONDITIONS:
            raise HTTPException(
                status_code=400,
                detail=f"condition must be one of {sorted(RETURN_CONDITIONS)}",
            )
        prepared.append(
            {
                "product_id": pid,
                "variant_id": vid,
                "quantity": qty,
                "unit_price": unit,
                "tax_rate": rate,
                "line_total": line_total,
                "condition": condition,
            }
        )

    ret = m.SalesReturn(
        tenant_id=tenant_id,
        return_number=await next_sales_return_number(db, tenant_id),
        customer_id=invoice.customer_id,
        sales_invoice_id=invoice.id,
        status="draft",
        reason=reason,
        restock=restock,
        subtotal=money_json(round(subtotal, 2)),
        tax_amount=money_json(round(tax_total, 2)),
        total_amount=money_json(round(subtotal + tax_total, 2)),
        notes=optional_honest_narrative(notes, label="sales return notes"),
        created_by=user_id,
    )
    db.add(ret)
    await db.flush()
    for line in prepared:
        db.add(m.SalesReturnItem(tenant_id=tenant_id, company_id=ret.company_id, sales_return_id=ret.id, **line))
    await db.flush()
    return ret


async def post_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    return_id: str,
    settlement_method: str | None = None,
    payment_method: str = "cash",
    liquid_account_id: str | None = None,
) -> m.SalesReturn:
    ret = await get_return(db, tenant_id, return_id)
    if ret.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot post return in status {ret.status}")
    items = await list_return_items(db, tenant_id, ret.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot post empty return")

    invoice = await get_invoice(db, tenant_id, ret.sales_invoice_id)
    from app.fx import doc_rate, to_base

    warehouse_id = None
    if invoice.store_id:
        from app.stores import warehouse_for_store

        wh = await warehouse_for_store(
            db, tenant_id, invoice.store_id, company_id=getattr(invoice, "company_id", None)
        )
        warehouse_id = wh.id

    for item in items:
        if ret.restock and item.condition == "sellable":
            qty = money_json(item.quantity)
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
                warehouse_id=warehouse_id,
            )
            if item.variant_id:
                variant = await get_variant(db, tenant_id, item.variant_id)
                variant.stock_qty = money_json(variant.stock_qty or 0) + qty
        else:
            db.add(
                m.AuditLog(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="return_discarded",
                    entity="sales_return_item",
                    entity_id=item.id,
                    details={
                        "product_id": item.product_id,
                        "variant_id": item.variant_id,
                        "quantity": money_json(item.quantity),
                    },
                )
            )

    return_total = money_json(round(money_json(ret.total_amount), 2))
    invoice = await get_invoice(db, tenant_id, ret.sales_invoice_id)
    open_ar = max(money_json(invoice.total_amount) - money_json(invoice.paid_amount or 0), 0.0)
    apply_to_invoice = min(return_total, open_ar)
    excess = money_json(round(return_total - apply_to_invoice, 2))

    method = (settlement_method or "").strip().lower() or None
    # Defense in depth: SalesReturnPost Literal rejects blank/unknown with 422.
    # Invalid values used to persist as garbage when excess was 0 (method or "adjust").
    if method is not None and method not in {"adjust", "refund"}:
        raise HTTPException(
            status_code=400,
            detail="settlement_method must be adjust or refund",
        )
    if excess > 1e-9:
        if method not in {"adjust", "refund"}:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "SETTLEMENT_REQUIRED",
                    "message": (
                        "Return exceeds open invoice balance; "
                        "provide settlement_method=adjust (customer credit) or refund"
                    ),
                    "open_invoice_balance": open_ar,
                    "return_total": return_total,
                    "excess": excess,
                },
            )
    else:
        method = method or "adjust"

    invoice.paid_amount = min(
        money_json(invoice.total_amount),
        money_json(invoice.paid_amount or 0) + apply_to_invoice,
    )
    from app.sales import apply_invoice_status

    if invoice.status != "draft":
        apply_invoice_status(invoice)
        invoice.updated_at = datetime.utcnow()

    customer = await get_customer(db, tenant_id, ret.customer_id)
    # Negative balance = customer store credit after return
    customer.balance = money_json(round(money_json(customer.balance or 0) - return_total, 2))

    ret.credit_note_number = await next_credit_note_number(db, tenant_id)
    ret.settlement_method = method
    ret.refunded_amount = 0
    ret.status = "posted"
    ret.posted_at = datetime.utcnow()
    ret.credit_note_number = await _allocate(db, tenant_id, "sales_credit_note", company_id=getattr(ret, "company_id", None))

    from app.accounting import post_sales_return_journal, post_sales_return_refund_journal

    await post_sales_return_journal(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        sales_return=ret,
        invoice=invoice,
    )

    from app import audit as audit_svc

    restock_qty = round(
        sum(
            float(i.quantity or 0)
            for i in items
            if ret.restock and (getattr(i, "condition", None) or "sellable") == "sellable"
        ),
        3,
    )
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="sales_return_posted",
        entity="sales_return",
        entity_id=ret.id,
        details={
            "return_number": ret.return_number,
            "credit_note_number": ret.credit_note_number,
            "sales_invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "customer_id": ret.customer_id,
            "customer_balance": float(customer.balance or 0),
            "total": float(ret.total_amount),
            "total_base": ret_base,
            "tax_amount": float(ret.tax_amount or 0),
            "restock": bool(ret.restock),
            "restock_qty": restock_qty,
            "store_id": getattr(invoice, "store_id", None),
            "warehouse_id": warehouse_id,
            "line_count": len(items),
        },
        module="sales",
    )

    if method == "refund" and excess > 1e-9:
        pay_method = (payment_method or "cash").strip().lower() or "cash"
        await post_sales_return_refund_journal(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            sales_return=ret,
            amount=excess,
            payment_method=pay_method,
            liquid_account_id=liquid_account_id,
        )
        ret.refund_payment_method = pay_method
        ret.refund_liquid_account_id = liquid_account_id
        ret.refunded_amount = excess
        # Cash paid out instead of leaving store credit for the excess
        customer.balance = money_json(round(money_json(customer.balance or 0) + excess, 2))

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Sales return posted",
        message=(
            f"Return {ret.return_number} / {ret.credit_note_number} posted for "
            f"{return_total:.2f} ({method}"
            + (f", refunded {excess:.2f}" if method == "refund" and excess > 1e-9 else "")
            + ")."
        ),
        entity_type="sales_return",
        entity_id=ret.id,
        company_id=getattr(ret, "company_id", None),
    )
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="sales_return_posted",
            entity="sales_return",
            entity_id=ret.id,
            details={
                "return_number": ret.return_number,
                "credit_note_number": ret.credit_note_number,
                "total_amount": return_total,
                "settlement_method": method,
                "refunded_amount": money_json(ret.refunded_amount or 0),
                "applied_to_invoice": apply_to_invoice,
            },
        )
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
    from app.print_branding import platform_print_footer_text_lines

    lines.extend(platform_print_footer_text_lines(width=width, center=tpl.startswith("thermal")))
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

    from app.print_branding import brand_html_block, header_footer_html, platform_print_footer_html

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
    footer_html = f"{footer_html}{platform_print_footer_html()}"
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
