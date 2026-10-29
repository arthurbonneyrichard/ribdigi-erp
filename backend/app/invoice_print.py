"""Sales invoice print payloads (A4 + thermal), reusing thermal PDF helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json
from app.receipts import (
    THERMAL_WIDTHS,
    _center,
    _lr,
    _money,
    _wrap,
    _clean_text,
)
from app.sales import get_customer, get_invoice, list_invoice_items

PRINTABLE_INVOICE_STATUSES = frozenset({"posted", "sent", "partial", "paid", "overdue"})


async def build_invoice_print_payload(
    db: AsyncSession,
    *,
    tenant_id: str,
    invoice_id: str,
) -> dict[str, Any]:
    invoice = await get_invoice(db, tenant_id, invoice_id)
    if invoice.status not in PRINTABLE_INVOICE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot print invoice in status {invoice.status}",
        )
    customer = await get_customer(db, tenant_id, invoice.customer_id)
    tenant = await db.get(m.Tenant, tenant_id)
    store = None
    if invoice.store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.id == invoice.store_id,
                    m.Store.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()

    items = await list_invoice_items(db, tenant_id, invoice.id)
    product_ids = {i.product_id for i in items}
    products: dict[str, m.Product] = {}
    if product_ids:
        rows = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id,
                    m.Product.id.in_(product_ids),
                )
            )
        ).scalars().all()
        products = {p.id: p for p in rows}

    normalized_items = []
    for item in items:
        product = products.get(item.product_id)
        name = (product.name if product else None) or item.product_id
        sku = product.sku if product else None
        normalized_items.append(
            {
                "name": str(name),
                "sku": sku,
                "quantity": money_json(item.quantity),
                "unit_price": money_json(item.unit_price),
                "tax_rate": money_json(item.tax_rate),
                "line_tax": money_json(getattr(item, "line_tax", None) or 0),
                "is_reverse_charge": bool(getattr(item, "is_reverse_charge", False)),
                "tax_components": getattr(item, "tax_components", None),
                "discount": money_json(item.discount),
                "line_subtotal": money_json(getattr(item, "line_subtotal", None) or 0),
                "line_total": money_json(item.line_total),
                "product_id": item.product_id,
                "variant_id": item.variant_id,
            }
        )

    company_name = _clean_text(tenant.company_name if tenant else None) or "RIBDIGI ERP"
    currency = (getattr(invoice, "currency", None) or "").strip() or (
        tenant.currency if tenant else "GHS"
    )
    paid = money_json(invoice.paid_amount)
    total = money_json(invoice.total_amount)
    balance = max(total - paid, 0)
    pay_rows = (
        await db.execute(
            select(m.CustomerPayment)
            .where(
                m.CustomerPayment.tenant_id == tenant_id,
                m.CustomerPayment.sales_invoice_id == invoice.id,
            )
            .order_by(m.CustomerPayment.created_at.asc())
        )
    ).scalars().all()
    payments = [
        {
            "payment_method": row.payment_method or "cash",
            "amount": money_json(row.amount),
            "reference": row.reference,
        }
        for row in pay_rows
    ]
    if balance <= 0.009:
        payment_status = "paid"
    elif paid > 0:
        payment_status = "partial"
    else:
        payment_status = "unpaid"
    method_label = ", ".join(
        dict.fromkeys(str(p["payment_method"]).replace("_", " ") for p in payments)
    ) or payment_status

    from app.print_branding import branding_fields_for_payload, company_identity_fields

    branding = branding_fields_for_payload(tenant)
    ident = company_identity_fields(tenant)
    ident["company_name"] = company_name
    store_name = _clean_text(store.name if store else None)
    if store_name:
        ident["store_name"] = store_name

    return {
        "document_type": "sales_invoice",
        "invoice_id": invoice.id,
        "reference": invoice.invoice_number,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status,
        "company_name": company_name,
        "legal_name": ident.get("legal_name"),
        "store_name": store_name,
        "store_id": store.id if store else None,
        "company_phone": ident.get("company_phone"),
        "company_email": ident.get("company_email"),
        "company_website": _clean_text(tenant.website if tenant else None),
        "company_address": ident.get("company_address"),
        "registration_number": ident.get("registration_number"),
        "tax_registration_number": ident.get("tax_registration_number"),
        "print_header": branding["print_header"],
        "print_footer": branding["print_footer"],
        "has_logo": branding["has_logo"],
        "default_invoice_template": branding["default_invoice_template"],
        "default_receipt_paper": branding["default_receipt_paper"],
        "tenant_id": tenant_id,
        "logo_key": getattr(tenant, "logo_url", None) if tenant else None,
        "currency": currency,
        "customer_name": customer.name,
        "customer_email": _clean_text(customer.email),
        "customer_phone": _clean_text(getattr(customer, "phone", None)),
        "subtotal": money_json(invoice.subtotal),
        "tax": money_json(invoice.tax_amount),
        "tax_amount": money_json(invoice.tax_amount),
        "reverse_charge_tax": money_json(getattr(invoice, "reverse_charge_tax", 0) or 0),
        "discount_amount": money_json(invoice.discount_amount),
        "discount_type": getattr(invoice, "discount_type", None) or "fixed",
        "discount_percent": money_json(getattr(invoice, "discount_percent", None) or 0),
        "total": total,
        "total_amount": total,
        "paid_amount": paid,
        "balance_due": balance,
        "payment_method": method_label,
        "payment_status": payment_status,
        "payments": payments,
        "items": normalized_items,
        "notes": invoice.notes,
        "posted_at": invoice.posted_at,
        "due_date": invoice.due_date,
        "created_at": invoice.created_at or invoice.posted_at,
        "format": "json",
    }


def render_invoice_thermal_text(payload: dict[str, Any], *, paper: str = "80mm") -> str:
    """Thermal receipt layout labeled as Invoice (reuses POS width helpers)."""
    width = THERMAL_WIDTHS.get(paper, THERMAL_WIDTHS["80mm"])
    lines: list[str] = []
    lines.append(_center(str(payload.get("company_name") or "RIBDIGI ERP"), width))
    if payload.get("store_name"):
        lines.append(_center(str(payload["store_name"]), width))
    if payload.get("company_address"):
        for part in _wrap(str(payload["company_address"]), width):
            lines.append(_center(part, width))
    if payload.get("company_phone"):
        lines.append(_center(f"Tel: {payload['company_phone']}", width))
    if payload.get("print_header"):
        for part in _wrap(str(payload["print_header"]), width):
            lines.append(_center(part, width))
    lines.append("-" * width)
    lines.append(_center("SALES INVOICE", width))
    lines.append(_lr("Invoice", str(payload.get("invoice_number") or ""), width))
    lines.append(_lr("Status", str(payload.get("status") or "").upper(), width))
    created = payload.get("posted_at") or payload.get("created_at")
    if isinstance(created, datetime):
        lines.append(_lr("Date", created.strftime("%Y-%m-%d %H:%M"), width))
    elif created:
        lines.append(_lr("Date", str(created)[:16], width))
    if payload.get("due_date"):
        due = payload["due_date"]
        due_s = due.strftime("%Y-%m-%d") if isinstance(due, datetime) else str(due)[:10]
        lines.append(_lr("Due", due_s, width))
    if payload.get("customer_name"):
        lines.append(_lr("Customer", str(payload["customer_name"])[: width // 2], width))
    lines.append("-" * width)
    for item in payload.get("items") or []:
        name = str(item.get("name") or "Item")
        qty = money_json(item.get("quantity") or 0)
        unit = money_json(item.get("unit_price") or 0)
        total = money_json(item.get("line_total") or qty * unit)
        for i, part in enumerate(_wrap(name, width)):
            lines.append(part if i == 0 else ("  " + part)[:width])
        lines.append(_lr(f"  {qty:g} x {_money(unit)}", _money(total), width))
        disc = money_json(item.get("discount") or 0)
        if disc > 0:
            lines.append(_lr("  Discount", f"-{_money(disc)}", width))
    lines.append("-" * width)
    currency = payload.get("currency") or ""
    lines.append(_lr("Subtotal", _money(payload.get("subtotal") or 0), width))
    lines.append(_lr("Tax", _money(payload.get("tax") or 0), width))
    discount_amount = money_json(payload.get("discount_amount") or 0)
    if discount_amount > 0:
        lines.append(_lr("Discount", f"-{_money(discount_amount)}", width))
    lines.append(_lr(f"TOTAL {currency}".strip(), _money(payload.get("total") or 0), width))
    lines.append(_lr("Paid", _money(payload.get("paid_amount") or 0), width))
    lines.append(_lr("Balance", _money(payload.get("balance_due") or 0), width))
    lines.append(_lr("Payment", str(payload.get("payment_method") or "unpaid")[: width // 2], width))
    lines.append(_lr("Pay status", str(payload.get("payment_status") or "").upper(), width))
    if payload.get("notes"):
        lines.append("-" * width)
        for part in _wrap(f"Notes: {payload['notes']}", width):
            lines.append(part)
    lines.append("-" * width)
    footer = payload.get("print_footer") or "Thank you"
    for part in _wrap(str(footer), width):
        lines.append(_center(part, width))
    lines.append(_center("Powered by RIBDIGI ERP", width))
    return "\n".join(lines)


def render_invoice_thermal_html(payload: dict[str, Any], *, paper: str = "80mm") -> str:
    """Browser thermal slip for sales invoices — same roll constraints as POS receipts."""
    import html as html_mod

    from app.receipts import render_thermal_html

    # Map invoice payload onto the POS receipt renderer shape.
    receipt = {
        **payload,
        "reference": payload.get("invoice_number") or payload.get("reference") or "",
        "customer_name": payload.get("customer_name") or "Walk-in",
    }
    html_doc = render_thermal_html(receipt, paper=paper)
    inv = html_mod.escape(str(payload.get("invoice_number") or ""))
    marker = f'<div class="mid">SALES INVOICE</div><div class="mid">{inv}</div>'
    # Insert title after the first brand rule (below company/header block).
    html_doc = html_doc.replace('<div class="rule"></div>', f'{marker}<div class="rule"></div>', 1)
    return html_doc


def render_invoice_a4_html(payload: dict[str, Any], tenant: m.Tenant | None = None) -> str:
    """Browser A4 invoice — same letterhead + line table as other commercial documents."""
    import html as html_mod

    from app.document_print import (
        _fmt_when,
        _money_line,
        document_body_html,
        render_document_print_html,
    )

    currency = str(payload.get("currency") or "GHS")
    number = str(payload.get("invoice_number") or "")
    date_s = _fmt_when(payload.get("posted_at") or payload.get("created_at"), tenant)
    due_s = _fmt_when(payload.get("due_date"), tenant)
    party_name = str(payload.get("customer_name") or "").strip()
    party_email = str(payload.get("customer_email") or "").strip()
    totals: list[tuple[str, str, bool]] = [
        ("Subtotal", _money_line(currency, payload.get("subtotal")), False),
        ("Tax", _money_line(currency, payload.get("tax") or payload.get("tax_amount")), False),
    ]
    rc = money_json(payload.get("reverse_charge_tax") or 0)
    if rc:
        totals.append(("Reverse-charge (memo)", _money_line(currency, rc), False))
    disc = money_json(payload.get("discount_amount") or 0)
    if disc:
        totals.append(("Discount", _money_line(currency, disc), False))
    totals.extend(
        [
            ("TOTAL", _money_line(currency, payload.get("total") or payload.get("total_amount")), True),
            ("Paid", _money_line(currency, payload.get("paid_amount")), False),
            ("Balance due", _money_line(currency, payload.get("balance_due")), True),
        ]
    )
    body = document_body_html(
        {
            "currency": currency,
            "table": "lines",
            "items": list(payload.get("items") or []),
            "notes": payload.get("notes"),
            "totals": totals,
            "meta_html_lines": [
                f"Invoice <strong>{html_mod.escape(number)}</strong> · Status {html_mod.escape(str(payload.get('status') or '').upper())}",
                f"Customer {html_mod.escape(party_name or '—')}"
                + (f"<br/>Customer email {html_mod.escape(party_email)}" if party_email else ""),
                f"Invoice date {html_mod.escape(date_s)}" if date_s else "",
                f"Payment due {html_mod.escape(due_s)}" if due_s else "",
                f"Payment {html_mod.escape(str(payload.get('payment_method') or payload.get('payment_status') or ''))}",
            ],
        }
    )
    return render_document_print_html(
        title=f"Invoice {number}".strip() or "Sales invoice",
        company_name=str(payload.get("company_name") or "RIBDIGI ERP"),
        body_html=body,
        tenant=tenant,
        store_name=str(payload.get("store_name") or ""),
        subtitle=f"Due {due_s}" if due_s else (f"Invoice date {date_s}" if date_s else None),
    )


def to_invoice_thermal_pdf(payload: dict[str, Any], *, paper: str = "80mm") -> bytes:
    from app.print_branding import build_text_pdf, load_logo_jpeg, style_powered_by_line

    text = render_invoice_thermal_text(payload, paper=paper)
    lines = [
        style_powered_by_line(line, 2 if line.strip() == "Powered by RIBDIGI ERP" else 8)
        for line in (text.splitlines() or [""])
    ]
    page_width = 226 if paper == "80mm" else 164
    line_height = 11
    top = 20
    bottom = 20
    page_height = max(top + bottom + line_height * (len(lines) + 8), 200)
    logo = None
    if payload.get("logo_key") and payload.get("tenant_id"):

        class _T:
            id = payload["tenant_id"]
            logo_url = payload["logo_key"]

        logo = load_logo_jpeg(_T(), max_width_px=240, max_height_px=80)
    return build_text_pdf(
        lines,
        page_width=page_width,
        page_height=page_height,
        margin=8 if paper == "58mm" else 10,
        mono=True,
        logo=logo,
        logo_max_pt=48 if paper == "58mm" else 64,
    )


def to_invoice_a4_pdf(payload: dict[str, Any]) -> bytes:
    """Modern A4 sales invoice PDF — forest header band, brand accent, Helvetica body."""
    from app.print_branding import (
        BRAND_GREEN_RGB,
        DEFAULT_FOOTER_INVOICE,
        FOREST_RGB,
        INK_RGB,
        POWERED_BY_RIBDIGI,
        append_a4_letterhead,
        assemble_a4_pdf,
        begin_a4_page,
        company_letterhead_detail_lines,
        load_logo_jpeg,
    )
    from app.report_export import _pdf_escape

    page_width, page_height = 595.0, 842.0
    margin = 40.0
    content: list[str] = []
    fr, fg, fb = FOREST_RGB
    br, bg, bb = BRAND_GREEN_RGB
    ir, ig, ib = INK_RGB

    company = str(payload.get("company_name") or "RIBDIGI ERP")
    logo = None
    if payload.get("logo_key") and payload.get("tenant_id"):

        class _T:
            id = payload["tenant_id"]
            logo_url = payload["logo_key"]

        logo = load_logo_jpeg(_T(), max_width_px=280, max_height_px=72)

    details = company_letterhead_detail_lines(
        {
            "company_name": company,
            "legal_name": payload.get("legal_name"),
            "store_name": payload.get("store_name"),
            "company_address": payload.get("company_address"),
            "company_phone": payload.get("company_phone"),
            "company_email": payload.get("company_email"),
            "registration_number": payload.get("registration_number"),
            "tax_registration_number": payload.get("tax_registration_number"),
        }
    )
    letterhead = {
        "company_name": company,
        "logo": logo,
        "print_header": str(payload["print_header"]) if payload.get("print_header") else None,
        "detail_lines": details,
        "page_width": page_width,
        "page_height": page_height,
        "margin": margin,
    }
    y = append_a4_letterhead(content, **letterhead)
    pages: list[list[str]] = []

    def draw_text(
        text: str,
        size: float,
        *,
        x: float | None = None,
        y_pos: float | None = None,
        bold: bool = False,
        rgb: tuple[float, float, float] | None = None,
    ) -> None:
        nonlocal y
        if y_pos is not None:
            y = y_pos
        if not text:
            return
        font = "/F2" if bold or size >= 12 else "/F1"
        r, g, b = rgb if rgb is not None else (ir, ig, ib)
        escaped = _pdf_escape(text)
        content.append(
            f"BT {font} {size:.0f} Tf {r:.3f} {g:.3f} {b:.3f} rg "
            f"{(x if x is not None else margin):.1f} {y - size:.1f} Td ({escaped}) Tj ET"
        )

    def break_page(label: str = "SALES INVOICE (continued)") -> None:
        nonlocal content, y
        pages.append(content)
        content, y = begin_a4_page(**letterhead, continuation_label=label)

    draw_text("SALES INVOICE", 18, bold=True, rgb=FOREST_RGB)
    y -= 22

    meta_left: list[str] = []
    meta_right: list[str] = []
    meta_left.append(f"Invoice  {payload.get('invoice_number') or ''}")
    meta_left.append(f"Status   {str(payload.get('status') or '').upper()}")
    posted = payload.get("posted_at") or payload.get("created_at")
    if isinstance(posted, datetime):
        meta_left.append(f"Date     {posted.strftime('%Y-%m-%d %H:%M')}")
    elif posted:
        meta_left.append(f"Date     {str(posted)[:16]}")
    if payload.get("due_date"):
        due = payload["due_date"]
        due_s = due.strftime("%Y-%m-%d") if isinstance(due, datetime) else str(due)[:10]
        meta_left.append(f"Pay by   {due_s}")

    meta_y = y
    for line in meta_left:
        draw_text(line, 10, y_pos=meta_y)
        meta_y -= 13
    meta_y_r = y
    for line in meta_right:
        draw_text(line, 9, x=320, y_pos=meta_y_r, rgb=(0.302, 0.365, 0.337))
        meta_y_r -= 12
    y = min(meta_y, meta_y_r) - 8

    # Bill-to panel background
    bill_h = 52.0
    content.append(
        f"0.961 0.969 0.925 rg {margin:.1f} {y - bill_h:.1f} "
        f"{page_width - 2 * margin:.1f} {bill_h:.1f} re f"
    )
    content.append(
        f"{br:.3f} {bg:.3f} {bb:.3f} rg {margin:.1f} {y - bill_h:.1f} 3 {bill_h:.1f} re f"
    )
    draw_text("Bill to", 8, y_pos=y - 12, bold=True, rgb=FOREST_RGB)
    draw_text(str(payload.get("customer_name") or "—"), 12, y_pos=y - 28, bold=True)
    contact_bits = [
        str(x)
        for x in (payload.get("customer_email"), payload.get("customer_phone"))
        if x
    ]
    if contact_bits:
        draw_text(" · ".join(contact_bits)[:70], 9, y_pos=y - 42, rgb=(0.302, 0.365, 0.337))
    y -= bill_h + 18

    # Table header bar
    def draw_col_header() -> None:
        nonlocal y
        col_y = y
        content.append(
            f"{fr:.3f} {fg:.3f} {fb:.3f} rg {margin:.1f} {col_y - 16:.1f} "
            f"{page_width - 2 * margin:.1f} 16 re f"
        )
        headers = [
            (margin + 4, "Qty"),
            (margin + 40, "Description"),
            (margin + 280, "Unit"),
            (margin + 340, "Tax%"),
            (margin + 390, "Tax"),
            (margin + 450, "Line"),
        ]
        for x, label in headers:
            draw_text(label, 8, x=x, y_pos=col_y - 2, bold=True, rgb=(1.0, 1.0, 1.0))
        y = col_y - 22

    draw_col_header()

    for item in payload.get("items") or []:
        if y < margin + 28:
            break_page()
            draw_col_header()
        name = str(item.get("name") or "Item")[:36]
        qty = money_json(item.get("quantity") or 0)
        unit = money_json(item.get("unit_price") or 0)
        tax = money_json(item.get("tax_rate") or 0)
        line_tax = money_json(item.get("line_tax") or 0)
        line_total = money_json(item.get("line_total") or 0)
        row_top = y
        draw_text(f"{qty:g}", 9, x=margin + 4, y_pos=row_top)
        draw_text(name, 9, x=margin + 40, y_pos=row_top)
        draw_text(_money(unit), 9, x=margin + 280, y_pos=row_top)
        draw_text(_money(tax), 9, x=margin + 340, y_pos=row_top)
        draw_text(_money(line_tax), 9, x=margin + 390, y_pos=row_top)
        draw_text(_money(line_total), 9, x=margin + 450, y_pos=row_top, bold=True)
        y = row_top - 14
        content.append(
            f"0.831 0.898 0.769 RG 0.5 w {margin:.1f} {y + 2:.1f} m "
            f"{page_width - margin:.1f} {y + 2:.1f} l S"
        )

    y -= 10
    currency = str(payload.get("currency") or "").strip()
    totals_x = 340.0
    totals: list[tuple[str, str, bool]] = [
        ("Subtotal", f"{currency} {_money(payload.get('subtotal') or 0)}".strip(), False),
        ("Tax", f"{currency} {_money(payload.get('tax') or 0)}".strip(), False),
    ]
    rc = money_json(payload.get("reverse_charge_tax") or 0)
    if rc > 0:
        totals.append(
            ("Reverse-charge (memo)", f"{currency} {_money(rc)}".strip(), False)
        )
    disc = money_json(payload.get("discount_amount") or 0)
    if disc > 0:
        totals.append(("Discount", f"-{currency} {_money(disc)}".strip(), False))
    totals.append(
        ("TOTAL", f"{currency} {_money(payload.get('total') or 0)}".strip(), True)
    )
    totals.append(
        ("Paid", f"{currency} {_money(payload.get('paid_amount') or 0)}".strip(), False)
    )
    totals.append(
        (
            "Balance due",
            f"{currency} {_money(payload.get('balance_due') or 0)}".strip(),
            True,
        )
    )

    box_h = 14 * len(totals) + 16
    if y < margin + box_h + 50:
        break_page()
    content.append(
        f"0.949 0.969 0.925 rg {totals_x - 8:.1f} {y - box_h:.1f} "
        f"{page_width - margin - totals_x + 8:.1f} {box_h:.1f} re f"
    )
    content.append(
        f"0.831 0.898 0.769 RG 0.8 w {totals_x - 8:.1f} {y - box_h:.1f} "
        f"{page_width - margin - totals_x + 8:.1f} {box_h:.1f} re S"
    )
    ty = y - 12
    for label, value, emph in totals:
        size = 12 if emph else 10
        draw_text(label, size, x=totals_x, y_pos=ty, bold=emph, rgb=FOREST_RGB if emph else INK_RGB)
        draw_text(value, size, x=totals_x + 110, y_pos=ty, bold=emph)
        ty -= 14
    y = y - box_h - 16

    if payload.get("notes"):
        if y < margin + 60:
            break_page()
        draw_text("Notes", 9, y_pos=y, bold=True, rgb=FOREST_RGB)
        y -= 12
        for part in _wrap(str(payload["notes"]), 78)[:4]:
            draw_text(part, 9, y_pos=y, rgb=(0.302, 0.365, 0.337))
            y -= 11

    if y < margin + 50:
        break_page()
    y = max(y - 8, margin + 36)
    draw_text(
        str(payload.get("print_footer") or DEFAULT_FOOTER_INVOICE),
        9,
        y_pos=y,
        rgb=(0.302, 0.365, 0.337),
    )
    y -= 14
    draw_text(POWERED_BY_RIBDIGI, 7, y_pos=y, bold=True, rgb=BRAND_GREEN_RGB)

    pages.append(content)
    return assemble_a4_pdf(
        pages, logo=logo, page_width=page_width, page_height=page_height
    )


def to_purchase_order_a4_pdf(payload: dict[str, Any]) -> bytes:
    """A4 purchase-order PDF — same forest letterhead as the sales invoice."""
    from app.print_branding import (
        BRAND_GREEN_RGB,
        FOREST_RGB,
        INK_RGB,
        POWERED_BY_RIBDIGI,
        append_a4_letterhead,
        assemble_a4_pdf,
        begin_a4_page,
        company_letterhead_detail_lines,
        load_logo_jpeg,
    )
    from app.report_export import _pdf_escape

    page_width, page_height = 595.0, 842.0
    margin = 40.0
    content: list[str] = []
    fr, fg, fb = FOREST_RGB
    ir, ig, ib = INK_RGB

    company = str(payload.get("company_name") or "RIBDIGI ERP")
    logo = None
    if payload.get("logo_key") and payload.get("tenant_id"):

        class _T:
            id = payload["tenant_id"]
            logo_url = payload["logo_key"]

        logo = load_logo_jpeg(_T(), max_width_px=280, max_height_px=72)

    ident = {
        "company_name": company,
        "legal_name": payload.get("legal_name"),
        "store_name": payload.get("store_name"),
        "company_address": payload.get("company_address"),
        "company_phone": payload.get("company_phone"),
        "company_email": payload.get("company_email"),
        "registration_number": payload.get("registration_number"),
        "tax_registration_number": payload.get("tax_registration_number"),
    }
    details = company_letterhead_detail_lines(ident)

    letterhead = {
        "company_name": company,
        "logo": logo,
        "print_header": str(payload["print_header"]) if payload.get("print_header") else None,
        "detail_lines": details,
        "page_width": page_width,
        "page_height": page_height,
        "margin": margin,
    }
    y = append_a4_letterhead(content, **letterhead)
    pages: list[list[str]] = []

    def draw_text(
        text: str,
        size: float,
        *,
        x: float | None = None,
        y_pos: float | None = None,
        bold: bool = False,
        rgb: tuple[float, float, float] | None = None,
    ) -> None:
        nonlocal y
        if y_pos is not None:
            y = y_pos
        if not text:
            return
        font = "/F2" if bold or size >= 12 else "/F1"
        r, g, b = rgb if rgb is not None else (ir, ig, ib)
        content.append(
            f"BT {font} {size:.0f} Tf {r:.3f} {g:.3f} {b:.3f} rg "
            f"{(x if x is not None else margin):.1f} {y - size:.1f} Td ({_pdf_escape(text)}) Tj ET"
        )

    def break_page(label: str = "PURCHASE ORDER (continued)") -> None:
        nonlocal content, y
        pages.append(content)
        content, y = begin_a4_page(**letterhead, continuation_label=label)

    draw_text("PURCHASE ORDER", 18, bold=True, rgb=FOREST_RGB)
    y -= 22

    meta_left: list[str] = []
    meta_right: list[str] = []
    meta_left.append(f"Order    {payload.get('po_number') or ''}")
    meta_left.append(f"Status   {str(payload.get('status') or '').upper()}")
    created = payload.get("created_at") or payload.get("order_date")
    if isinstance(created, datetime):
        meta_left.append(f"Date     {created.strftime('%Y-%m-%d')}")
    elif created:
        meta_left.append(f"Date     {str(created)[:10]}")
    if payload.get("due_date"):
        due = payload["due_date"]
        due_s = due.strftime("%Y-%m-%d") if isinstance(due, datetime) else str(due)[:10]
        meta_left.append(f"Needed   {due_s}")
    if payload.get("supplier_name"):
        meta_right.append(f"Supplier {str(payload['supplier_name'])[:40]}")
    if payload.get("supplier_email"):
        meta_right.append(str(payload["supplier_email"])[:48])
    if payload.get("delivery_address"):
        meta_right.append(f"Ship to {str(payload['delivery_address'])[:40]}")

    meta_y = y
    for line in meta_left:
        draw_text(line, 10, y_pos=meta_y)
        meta_y -= 13
    meta_y_r = y
    for line in meta_right:
        draw_text(line, 9, x=320, y_pos=meta_y_r, rgb=(0.302, 0.365, 0.337))
        meta_y_r -= 12
    y = min(meta_y, meta_y_r) - 8

    def draw_col_header() -> None:
        nonlocal y
        col_y = y
        content.append(
            f"{fr:.3f} {fg:.3f} {fb:.3f} rg {margin:.1f} {col_y - 16:.1f} "
            f"{page_width - 2 * margin:.1f} 16 re f"
        )
        headers = [
            (margin + 4, "Qty"),
            (margin + 40, "Description"),
            (margin + 280, "Unit"),
            (margin + 340, "Tax%"),
            (margin + 390, "Disc"),
            (margin + 450, "Line"),
        ]
        for x, label in headers:
            draw_text(label, 8, x=x, y_pos=col_y - 2, bold=True, rgb=(1.0, 1.0, 1.0))
        y = col_y - 22

    draw_col_header()

    for item in payload.get("items") or []:
        if y < margin + 28:
            break_page()
            draw_col_header()
        name = str(item.get("name") or "Item")[:36]
        qty = money_json(item.get("quantity") or 0)
        unit = money_json(item.get("unit_price") or 0)
        tax = money_json(item.get("tax_rate") or 0)
        disc = money_json(item.get("discount") or 0)
        line_total = money_json(item.get("line_total") or 0)
        row_top = y
        draw_text(f"{qty:g}", 9, x=margin + 4, y_pos=row_top)
        draw_text(name, 9, x=margin + 40, y_pos=row_top)
        draw_text(_money(unit), 9, x=margin + 280, y_pos=row_top)
        draw_text(_money(tax), 9, x=margin + 340, y_pos=row_top)
        draw_text(_money(disc), 9, x=margin + 390, y_pos=row_top)
        draw_text(_money(line_total), 9, x=margin + 450, y_pos=row_top, bold=True)
        y = row_top - 14
        content.append(
            f"0.831 0.898 0.769 RG 0.5 w {margin:.1f} {y + 2:.1f} m "
            f"{page_width - margin:.1f} {y + 2:.1f} l S"
        )

    y -= 10
    currency = str(payload.get("currency") or "").strip()
    totals_x = 340.0
    totals: list[tuple[str, str, bool]] = [
        ("Subtotal", f"{currency} {_money(payload.get('subtotal') or 0)}".strip(), False),
        ("Tax", f"{currency} {_money(payload.get('tax') or payload.get('tax_amount') or 0)}".strip(), False),
        (
            "TOTAL",
            f"{currency} {_money(payload.get('total') or payload.get('total_amount') or 0)}".strip(),
            True,
        ),
    ]
    box_h = 14 * len(totals) + 16
    if y < margin + box_h + 50:
        break_page()
    content.append(
        f"0.949 0.969 0.925 rg {totals_x - 8:.1f} {y - box_h:.1f} "
        f"{page_width - margin - totals_x + 8:.1f} {box_h:.1f} re f"
    )
    content.append(
        f"0.831 0.898 0.769 RG 0.8 w {totals_x - 8:.1f} {y - box_h:.1f} "
        f"{page_width - margin - totals_x + 8:.1f} {box_h:.1f} re S"
    )
    ty = y - 12
    for label, value, emph in totals:
        size = 12 if emph else 10
        draw_text(label, size, x=totals_x, y_pos=ty, bold=emph, rgb=FOREST_RGB if emph else INK_RGB)
        draw_text(value, size, x=totals_x + 110, y_pos=ty, bold=emph)
        ty -= 14
    y = y - box_h - 16

    if payload.get("notes"):
        if y < margin + 60:
            break_page()
        draw_text("Notes", 9, y_pos=y, bold=True, rgb=FOREST_RGB)
        y -= 12
        for part in _wrap(str(payload["notes"]), 78)[:4]:
            draw_text(part, 9, y_pos=y, rgb=(0.302, 0.365, 0.337))
            y -= 11

    if y < margin + 50:
        break_page()
    y = max(y - 8, margin + 36)
    if payload.get("print_footer"):
        draw_text(str(payload["print_footer"]), 9, y_pos=y, rgb=(0.302, 0.365, 0.337))
        y -= 14
    draw_text(POWERED_BY_RIBDIGI, 7, y_pos=y, bold=True, rgb=BRAND_GREEN_RGB)

    pages.append(content)
    return assemble_a4_pdf(
        pages, logo=logo, page_width=page_width, page_height=page_height
    )
