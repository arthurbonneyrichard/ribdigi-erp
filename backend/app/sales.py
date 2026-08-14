"""Sales invoice and customer payment business logic."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.tax import resolve_product_tax
from app.credit import default_due_date
from app.catalog import resolve_sale_line, stock_out_with_batch


INVOICE_PRINT_TEMPLATES = frozenset({"a4", "thermal_80", "thermal_58"})
INVOICE_PRINT_FORMATS = frozenset({"text", "pdf", "html"})


def calc_sale_line_amounts(
    spec,
    quantity: float,
    unit_price: float,
    discount: float = 0,
) -> tuple[float, float, float, float]:
    """Return (line_sub, line_tax, line_total, discount) with tax on net after line discount.

    Stage 12 C1 — aligns quotations/orders/invoices with POS and Stage 11 PO math.
    """
    qty = float(quantity or 0)
    unit = float(unit_price or 0)
    disc = round(float(discount or 0), 2)
    if disc < 0:
        raise HTTPException(status_code=400, detail="Line discount must be >= 0")
    gross_before = round(qty * unit, 2)
    if disc > gross_before + 1e-9:
        raise HTTPException(status_code=400, detail="Line discount exceeds line amount")
    taxable = round(gross_before - disc, 2)
    line_sub, line_tax, line_total = spec.compute_amounts(taxable)
    return float(line_sub), float(line_tax), float(line_total), disc


def invoice_payment_status(total: float, paid: float, *, previous_status: str | None = None) -> str:
    total_f = float(total or 0)
    paid_f = float(paid or 0)
    if paid_f + 1e-9 >= total_f:
        return "paid"
    if paid_f > 0:
        return "partial"
    # Unpaid: preserve sent/overdue instead of collapsing back to posted
    if previous_status in {"sent", "overdue"}:
        return previous_status
    return "posted"


def refresh_invoice_overdue(invoice: m.SalesInvoice, *, now: datetime | None = None) -> bool:
    """Mark unpaid posted/sent invoices past due_date as overdue. Returns True if changed."""
    now = now or datetime.utcnow()
    balance = max(float(invoice.total_amount or 0) - float(invoice.paid_amount or 0), 0)
    if invoice.status not in {"posted", "sent", "overdue", "partial"}:
        return False
    if balance <= 1e-9:
        return False
    if not invoice.due_date or invoice.due_date.date() >= now.date():
        return False
    if invoice.status == "partial":
        # Keep partial for partially paid past-due; expose via is_overdue flag in serialize.
        return False
    if invoice.status != "overdue":
        invoice.status = "overdue"
        invoice.updated_at = now
        return True
    return False


async def get_customer(db: AsyncSession, tenant_id: str, customer_id: str) -> m.Party:
    customer = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == customer_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "customer",
            )
        )
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


async def get_invoice(db: AsyncSession, tenant_id: str, invoice_id: str) -> m.SalesInvoice:
    invoice = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.id == invoice_id,
                m.SalesInvoice.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Sales invoice not found")
    return invoice


async def list_invoice_items(db: AsyncSession, tenant_id: str, invoice_id: str) -> list[m.SalesInvoiceItem]:
    return (
        await db.execute(
            select(m.SalesInvoiceItem).where(
                m.SalesInvoiceItem.tenant_id == tenant_id,
                m.SalesInvoiceItem.sales_invoice_id == invoice_id,
            )
        )
    ).scalars().all()


async def serialize_invoice(db: AsyncSession, invoice: m.SalesInvoice) -> dict:
    refresh_invoice_overdue(invoice)
    items = await list_invoice_items(db, invoice.tenant_id, invoice.id)
    balance = max(float(invoice.total_amount) - float(invoice.paid_amount or 0), 0)
    now = datetime.utcnow()
    is_overdue = bool(
        balance > 1e-9
        and invoice.due_date
        and invoice.due_date.date() < now.date()
        and invoice.status not in {"draft", "cancelled", "paid"}
    )
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "store_id": invoice.store_id,
        "status": invoice.status,
        "is_overdue": is_overdue,
        "subtotal": float(invoice.subtotal),
        "tax_amount": float(invoice.tax_amount),
        "reverse_charge_tax": float(getattr(invoice, "reverse_charge_tax", 0) or 0),
        "discount_amount": float(invoice.discount_amount),
        "total_amount": float(invoice.total_amount),
        "paid_amount": float(invoice.paid_amount),
        "balance_due": balance,
        "currency": getattr(invoice, "currency", None) or "",
        "exchange_rate": float(getattr(invoice, "exchange_rate", None) or 1),
        "balance_due_base": round(
            balance * float(getattr(invoice, "exchange_rate", None) or 1),
            2,
        ),
        "notes": invoice.notes,
        "credit_limit_overridden": bool(getattr(invoice, "credit_limit_overridden", False)),
        "credit_override_reason": getattr(invoice, "credit_override_reason", None),
        "credit_override_by": getattr(invoice, "credit_override_by", None),
        "credit_override_at": getattr(invoice, "credit_override_at", None),
        "posted_at": invoice.posted_at,
        "due_date": invoice.due_date,
        "emailed_at": getattr(invoice, "emailed_at", None),
        "emailed_to": getattr(invoice, "emailed_to", None),
        "sales_order_id": invoice.sales_order_id,
        "quotation_id": invoice.quotation_id,
        "created_at": invoice.created_at,
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


def render_invoice_text(
    invoice_data: dict,
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

    tpl = template if template in INVOICE_PRINT_TEMPLATES else "a4"
    width = 48 if tpl == "thermal_80" else 32 if tpl == "thermal_58" else 72
    cur = currency or invoice_data.get("currency") or "GHS"
    labels = item_labels or {}
    lines = [
        company_name[:width],
    ]
    if trading_name:
        lines.append(f"Trading as {trading_name}"[:width])
    if has_logo or logo_data_url:
        lines.append("[Company logo on file]"[:width])
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
            f"INVOICE {invoice_data.get('invoice_number')}"[:width],
            f"Customer: {customer_name}"[:width],
        ]
    )
    if customer_address:
        lines.append(str(customer_address)[:width])
    lines.append(f"Status: {invoice_data.get('status')}"[:width])
    if invoice_data.get("due_date"):
        lines.append(f"Due: {str(invoice_data['due_date'])[:10]}"[:width])
    lines.extend(["", f"{'Item':<{max(width - 28, 8)}} {'Qty':>6} {'Total':>10}"[:width], "-" * width])
    for item in invoice_data.get("items") or []:
        pid = str(item.get("product_id") or "")
        desc = str(labels.get(pid) or pid or "Item")[: max(width - 28, 8)]
        lines.append(
            f"{desc:<{max(width - 28, 8)}} {float(item.get('quantity') or 0):>6.2f} "
            f"{float(item.get('line_total') or 0):>10.2f}"[:width]
        )
    lines.extend(
        [
            "-" * width,
            f"Subtotal: {cur} {float(invoice_data.get('subtotal') or 0):.2f}"[:width],
            f"Tax: {cur} {float(invoice_data.get('tax_amount') or 0):.2f}"[:width],
            f"Discount: {cur} {float(invoice_data.get('discount_amount') or 0):.2f}"[:width],
            f"TOTAL: {cur} {float(invoice_data.get('total_amount') or 0):.2f}"[:width],
            f"Paid: {cur} {float(invoice_data.get('paid_amount') or 0):.2f}"[:width],
            f"Balance: {cur} {float(invoice_data.get('balance_due') or 0):.2f}"[:width],
        ]
    )
    if invoice_data.get("notes"):
        lines.extend(["", f"Notes: {invoice_data['notes']}"[:width]])
    footer_lines = header_footer_text_lines(document_footer, width)
    if footer_lines:
        lines.append("")
        lines.extend(part[:width] for part in footer_lines)
    elif tpl.startswith("thermal"):
        lines.extend(["", "Thank you!"[:width]])
    from app.print_branding import platform_print_footer_text_lines

    lines.extend(platform_print_footer_text_lines(width=width, center=tpl.startswith("thermal")))
    return "\n".join(lines)


def render_invoice_html(
    invoice_data: dict,
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

    tpl = template if template in INVOICE_PRINT_TEMPLATES else "a4"
    cur = escape(currency or invoice_data.get("currency") or "GHS")
    labels = item_labels or {}
    max_width = "80mm" if tpl == "thermal_80" else "58mm" if tpl == "thermal_58" else "720px"
    font = "12px/1.4 monospace" if tpl.startswith("thermal") else "15px/1.45 Georgia, 'Times New Roman', serif"
    rows = []
    for item in invoice_data.get("items") or []:
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
    due = str(invoice_data.get("due_date") or "")[:10]
    due_line = f" · Due {escape(due)}" if due else ""
    customer_addr_html = f"<br>{escape(str(customer_address))}" if customer_address else ""
    notes_html = (
        f"<p class='muted'>Notes: {escape(str(invoice_data.get('notes')))}</p>"
        if invoice_data.get("notes")
        else ""
    )
    header_html = header_footer_html(document_header, css_class="doc-header")
    footer_html = header_footer_html(document_footer, css_class="doc-footer")
    if not footer_html:
        footer_html = (
            "<p>Thank you for your business.</p>"
            if tpl.startswith("thermal")
            else "<p class='muted' style='margin-top:28px'>Thank you for your business.</p>"
        )
    footer_html = f"{footer_html}{platform_print_footer_html()}"
    meta_html = "<br>".join(meta)
    rows_html = "".join(rows) or "<tr><td colspan='4' class='muted'>No lines</td></tr>"
    inv_no = escape(str(invoice_data.get("invoice_number") or ""))
    status = escape(str(invoice_data.get("status") or ""))
    brand_block = brand_html_block(
        company_name=company_name,
        logo_data_url=logo_data_url,
        trading_name=trading_name,
        meta_html=meta_html,
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Invoice {inv_no}</title>
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
  <h2>Invoice {inv_no}</h2>
  <div class="muted">Status: {status}{due_line}</div>
  <p><strong>Bill to</strong><br>{escape(customer_name)}{customer_addr_html}</p>
  <table>
    <thead><tr><th>Item</th><th style="text-align:right">Qty</th><th style="text-align:right">Price</th><th style="text-align:right">Total</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="totals">
    <div><span>Subtotal</span><span>{cur} {float(invoice_data.get("subtotal") or 0):.2f}</span></div>
    <div><span>Tax</span><span>{cur} {float(invoice_data.get("tax_amount") or 0):.2f}</span></div>
    <div><span>Discount</span><span>{cur} {float(invoice_data.get("discount_amount") or 0):.2f}</span></div>
    <div class="grand"><span>Total</span><span>{cur} {float(invoice_data.get("total_amount") or 0):.2f}</span></div>
    <div><span>Paid</span><span>{cur} {float(invoice_data.get("paid_amount") or 0):.2f}</span></div>
    <div><span>Balance</span><span>{cur} {float(invoice_data.get("balance_due") or 0):.2f}</span></div>
  </div>
  {notes_html}
  {footer_html}
</div></body></html>"""


def render_invoice_pdf(
    invoice_data: dict,
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
    """Branded invoice PDF: A4 letter page or narrow thermal page."""
    tpl = template if template in INVOICE_PRINT_TEMPLATES else "a4"
    text = render_invoice_text(
        invoice_data,
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
    title = f"INVOICE {invoice_data.get('invoice_number') or ''}"
    return render_branded_lines_pdf(
        text.splitlines() or [""],
        template=tpl,
        company_name=company_name,
        title=title,
    )


def render_branded_lines_pdf(
    lines: list[str],
    *,
    template: str = "a4",
    company_name: str,
    title: str,
) -> bytes:
    """Build a simple branded multi-line PDF (A4 or thermal)."""
    from app.report_export import _pdf_escape

    tpl = template if template in INVOICE_PRINT_TEMPLATES else "a4"
    if tpl.startswith("thermal"):
        page_width = 226 if tpl == "thermal_80" else 164
        line_height = 11
        top = 20
        bottom = 20
        page_height = max(top + bottom + line_height * (len(lines) + 2), 200)
        content: list[str] = []
        y = page_height - top
        for line in lines:
            content.append(f"BT /F1 8 Tf 8 {y} Td ({_pdf_escape(line[:80])}) Tj ET")
            y -= line_height
            if y < bottom:
                break
        stream = "\n".join(content).encode("latin-1", errors="replace")
        media = f"[0 0 {page_width} {page_height}]"
    else:
        page_width, page_height = 612, 792
        content = []
        y = 760
        content.append(
            f"BT /F2 18 Tf 50 {y} Td ({_pdf_escape(company_name[:60])}) Tj ET"
        )
        y -= 22
        content.append(
            f"BT /F2 14 Tf 50 {y} Td ({_pdf_escape(str(title)[:50])}) Tj ET"
        )
        y -= 28
        for line in lines[1:]:
            if y < 48:
                content.append(
                    f"BT /F1 9 Tf 50 {y} Td ({_pdf_escape('… continued on request …')}) Tj ET"
                )
                break
            content.append(f"BT /F1 10 Tf 50 {y} Td ({_pdf_escape(line[:95])}) Tj ET")
            y -= 13
        stream = "\n".join(content).encode("latin-1", errors="replace")
        media = f"[0 0 {page_width} {page_height}]"

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    if tpl.startswith("thermal"):
        objects.append(
            (
                f"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox {media} "
                f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
            ).encode("ascii")
        )
    else:
        objects.append(
            (
                f"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox {media} "
                f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>endobj\n"
            ).encode("ascii")
        )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    if tpl.startswith("thermal"):
        objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj\n")
    else:
        objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
        objects.append(b"6 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>endobj\n")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(out)


async def send_sales_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
    to: str | None = None,
) -> tuple[m.SalesInvoice, dict]:
    from app import emailer

    invoice = await get_invoice(db, tenant_id, invoice_id)
    refresh_invoice_overdue(invoice)
    if invoice.status not in {"posted", "sent", "partial", "overdue", "paid"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot email invoice in status {invoice.status}",
        )
    customer = await get_customer(db, tenant_id, invoice.customer_id)
    recipient = (to or customer.email or "").strip()
    if not recipient:
        raise HTTPException(
            status_code=400,
            detail="Customer has no email; set customer email or pass to= override",
        )
    tenant = await db.get(m.Tenant, tenant_id)
    company_name = tenant.company_name if tenant else "RIBDIGI ERP"
    currency = (getattr(invoice, "currency", None) or (tenant.currency if tenant else None) or "GHS")
    payload = await serialize_invoice(db, invoice)
    result = await emailer.send_invoice_email(
        to=recipient,
        company_name=company_name,
        currency=currency,
        customer_name=customer.name,
        invoice=payload,
    )
    if not result.sent:
        if result.mode == "disabled":
            raise HTTPException(status_code=503, detail="Email delivery is disabled")
        raise HTTPException(status_code=502, detail=result.error or "Email send failed")

    now = datetime.utcnow()
    if invoice.status == "posted":
        invoice.status = "sent"
    invoice.emailed_at = now
    invoice.emailed_to = recipient
    invoice.updated_at = now
    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="sales",
        action="invoice_sent",
        entity="sales_invoice",
        entity_id=invoice.id,
        details={
            "invoice_number": invoice.invoice_number,
            "to": recipient,
            "mode": result.mode,
        },
    )
    await db.flush()
    delivery = {
        "sent": result.sent,
        "mode": result.mode,
        "to": recipient,
        "emailed_at": invoice.emailed_at,
    }
    return invoice, delivery


async def create_sales_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    customer_id: str,
    items: list[dict],
    discount_amount: float = 0,
    notes: str | None = None,
    store_id: str | None = None,
    currency: str | None = None,
    exchange_rate: float | None = None,
    company_id: str | None = None,
) -> m.SalesInvoice:
    if not items:
        raise HTTPException(status_code=400, detail="Invoice requires at least one line item")
    await get_customer(db, tenant_id, customer_id)

    from app.fx import resolve_rate

    cur, rate = await resolve_rate(db, tenant_id, currency, explicit_rate=exchange_rate)

    resolved_store_id = None
    if store_id:
        from app import stores as stores_svc

        store = await stores_svc.get_store(db, tenant_id, store_id)
        resolved_store_id = store.id

    from app.customers import customer_group_discount_percent

    group_discount = await customer_group_discount_percent(db, tenant_id, customer_id)
    subtotal = 0.0
    tax_total = 0.0
    reverse_charge_tax = 0.0
    prepared: list[tuple[dict, float]] = []
    for item in items:
        product, variant, unit_price = await resolve_sale_line(
            db, tenant_id, item, group_discount_percent=group_discount
        )
        explicit = item.get("tax_rate")
        if explicit is not None:
            spec = await resolve_product_tax(
                db, tenant_id, product, explicit_rate=float(explicit)
            )
        else:
            spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=None)
        line_sub, line_tax, line_total, discount = calc_sale_line_amounts(
            spec,
            item["quantity"],
            unit_price,
            item.get("discount") or 0,
        )
        subtotal += line_sub
        if spec.is_reverse_charge:
            reverse_charge_tax += line_tax
        else:
            tax_total += line_tax
        prepared.append(
            (
                {
                    "product_id": product.id,
                    "variant_id": variant.id if variant else None,
                    "quantity": item["quantity"],
                    "unit_price": unit_price,
                    "discount": discount,
                    "tax_rate": spec.rate_pct,
                    "supply_category": spec.supply_category,
                },
                line_total,
            )
        )

    discount_amount = float(discount_amount or 0)
    total = max(subtotal + tax_total - discount_amount, 0)

    from app.document_numbering import allocate_document_number

    invoice_number = await allocate_document_number(
        db, tenant_id=tenant_id, doc_key="sales_invoice", company_id=company_id
    )
    invoice = m.SalesInvoice(
        tenant_id=tenant_id,
        company_id=company_id,
        invoice_number=invoice_number,
        customer_id=customer_id,
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        reverse_charge_tax=round(reverse_charge_tax, 2),
        discount_amount=discount_amount,
        total_amount=total,
        paid_amount=0,
        currency=cur,
        exchange_rate=rate,
        notes=notes,
        created_by=user_id,
        store_id=resolved_store_id,
    )
    db.add(invoice)
    await db.flush()

    for item, line_total in prepared:
        db.add(
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                company_id=company_id,
                sales_invoice_id=invoice.id,
                product_id=item["product_id"],
                variant_id=item.get("variant_id"),
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                tax_rate=item.get("tax_rate", 0),
                discount=item.get("discount", 0),
                line_total=line_total,
                supply_category=item.get("supply_category") or "standard",
            )
        )

    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="invoice_created",
        entity="sales_invoice",
        entity_id=invoice.id,
        details={"invoice_number": invoice.invoice_number, "total": float(invoice.total_amount)},
        module='sales',
    )
    return invoice


async def post_sales_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
    role: str = "",
    permissions: dict | None = None,
    credit_limit_override: bool = False,
    credit_override_reason: str | None = None,
) -> m.SalesInvoice:
    invoice = await get_invoice(db, tenant_id, invoice_id)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot post invoice in status {invoice.status}")

    items = await list_invoice_items(db, tenant_id, invoice.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot post empty invoice")

    customer = await get_customer(db, tenant_id, invoice.customer_id)
    from app.fx import doc_rate, to_base
    from app.credit import enforce_credit_limit

    inv_base = to_base(float(invoice.total_amount), doc_rate(invoice))
    credit_gate = await enforce_credit_limit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        permissions=permissions,
        customer=customer,
        additional_amount=inv_base,
        override=credit_limit_override,
        override_reason=credit_override_reason,
        entity="sales_invoice",
        entity_id=invoice.id,
        module="sales",
        extra_details={
            "invoice_total": float(invoice.total_amount),
            "invoice_total_base": inv_base,
            "currency": getattr(invoice, "currency", None) or "",
            "invoice_number": invoice.invoice_number,
        },
    )
    credit_limit = float(credit_gate["credit_limit"] or 0)

    warehouse_id = None
    if invoice.store_id:
        from app.stores import warehouse_for_store
        from app.inventory import allocate_unlocated_stock

        wh = await warehouse_for_store(db, tenant_id, invoice.store_id)
        warehouse_id = wh.id

    # Soft allocations from the source sales order must be consumed before stock-out
    # so available qty includes this order's reserved quantity.
    if invoice.sales_order_id:
        from app.inventory import consume_reservations_for_order

        await consume_reservations_for_order(
            db,
            tenant_id=tenant_id,
            sales_order_id=invoice.sales_order_id,
            user_id=user_id,
        )

    # Stage 15 H1 — aggregated fail-fast before stock-out / AR / journal.
    # On 409 the request session rolls back (no commit), so reservation consume
    # and any prior work in this post are undone.
    from app.inventory import assert_outbound_lines_stock_available

    await assert_outbound_lines_stock_available(
        db,
        tenant_id=tenant_id,
        items=[
            {
                "product_id": item.product_id,
                "quantity": float(item.quantity),
                "variant_id": item.variant_id,
            }
            for item in items
        ],
    )

    for item in items:
        if warehouse_id:
            await allocate_unlocated_stock(
                db,
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
                product_id=item.product_id,
            )
        await stock_out_with_batch(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            product_id=item.product_id,
            quantity=float(item.quantity),
            notes=f"Invoice {invoice.invoice_number}",
            variant_id=item.variant_id,
            warehouse_id=warehouse_id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
        )

    customer.balance = float(customer.balance or 0) + inv_base
    invoice.status = "posted"
    invoice.posted_at = datetime.utcnow()
    invoice.due_date = invoice.due_date or default_due_date(invoice.posted_at)
    invoice.updated_at = datetime.utcnow()
    if credit_gate.get("overridden"):
        invoice.credit_limit_overridden = True
        invoice.credit_override_reason = credit_gate.get("override_reason")
        invoice.credit_override_by = user_id
        invoice.credit_override_at = datetime.utcnow()

    from app.accounting import post_sales_invoice_journal

    await post_sales_invoice_journal(
        db, tenant_id=tenant_id, user_id=user_id, invoice=invoice
    )

    if credit_limit > 0:
        utilization = float(customer.balance or 0) / credit_limit
        if utilization >= 0.8:
            from app.notifications import create_notification

            await create_notification(
                db,
                tenant_id=tenant_id,
                category="credit_limit",
                title="Credit Limit Warning",
                message=(
                    f"{customer.name} credit utilization is {utilization:.0%} "
                    f"({float(customer.balance or 0):.2f} / {credit_limit:.2f})."
                ),
                entity_type="customer",
                entity_id=customer.id,
            )

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Sales invoice posted",
        message=f"Invoice {invoice.invoice_number} posted for {float(invoice.total_amount):.2f}.",
        entity_type="sales_invoice",
        entity_id=invoice.id,
    )
    from app import audit as audit_svc
    from app.fx import doc_rate, to_base

    stock_qty = round(sum(float(i.quantity or 0) for i in items), 3)
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="invoice_posted",
        entity="sales_invoice",
        entity_id=invoice.id,
        details={
            "invoice_number": invoice.invoice_number,
            "total": float(invoice.total_amount),
            "total_base": to_base(float(invoice.total_amount), doc_rate(invoice)),
            "subtotal": float(invoice.subtotal or 0),
            "tax_amount": float(invoice.tax_amount or 0),
            "reverse_charge_tax": float(getattr(invoice, "reverse_charge_tax", 0) or 0),
            "currency": getattr(invoice, "currency", None) or "",
            "exchange_rate": float(getattr(invoice, "exchange_rate", None) or 1),
            "customer_id": invoice.customer_id,
            "customer_balance": float(customer.balance or 0),
            "store_id": getattr(invoice, "store_id", None),
            "stock_qty_out": stock_qty,
            "line_count": len(items),
            "warehouse_id": warehouse_id,
        },
        module="sales",
    )
    return invoice


async def cancel_sales_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
) -> m.SalesInvoice:
    invoice = await get_invoice(db, tenant_id, invoice_id)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft invoices can be cancelled")
    invoice.status = "cancelled"
    invoice.updated_at = datetime.utcnow()
    if invoice.sales_order_id:
        # Keep soft allocations; reopen the order so it can be re-invoiced.
        order = (
            await db.execute(
                select(m.SalesOrder).where(
                    m.SalesOrder.id == invoice.sales_order_id,
                    m.SalesOrder.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if order and order.status == "invoiced":
            order.status = "confirmed" if order.confirmed_at else "draft"
            order.converted_invoice_id = None
            order.updated_at = datetime.utcnow()
    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="invoice_cancelled",
        entity="sales_invoice",
        entity_id=invoice.id,
        details={"invoice_number": invoice.invoice_number},
        module='sales',
    )
    return invoice


async def record_customer_payment(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    customer_id: str,
    amount: float,
    sales_invoice_id: str | None = None,
    payment_method: str = "cash",
    reference: str | None = None,
    notes: str | None = None,
    cheque_number: str | None = None,
    bank_name: str | None = None,
    cheque_date: datetime | None = None,
    apply_early_discount: bool | None = None,
    liquid_account_id: str | None = None,
    currency: str | None = None,
    exchange_rate: float | None = None,
    company_id: str | None = None,
) -> m.CustomerPayment:
    amount = float(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

    if liquid_account_id:
        from app.accounting import resolve_settlement_gl

        await resolve_settlement_gl(
            db,
            tenant_id,
            payment_method or "cash",
            liquid_account_id=liquid_account_id,
            outflow=False,
        )

    customer = await get_customer(db, tenant_id, customer_id)
    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one()
    from app.credit import early_pay_settings, invoice_early_discount
    from app.fx import doc_currency, doc_rate, resolve_rate, to_base

    ep = early_pay_settings(tenant)
    use_discount = ep["enabled"] if apply_early_discount is None else bool(apply_early_discount)
    if use_discount and not ep["enabled"]:
        use_discount = False

    # allocations: (invoice, settlement_to_paid_amount, discount_portion)
    allocations: list[tuple[m.SalesInvoice, float, float]] = []
    total_discount = 0.0

    if sales_invoice_id:
        invoice = await get_invoice(db, tenant_id, sales_invoice_id)
        if invoice.customer_id != customer_id:
            raise HTTPException(status_code=400, detail="Invoice does not belong to this customer")
        if invoice.status not in {"posted", "partial"}:
            raise HTTPException(status_code=409, detail=f"Cannot pay invoice in status {invoice.status}")
        due = float(invoice.total_amount) - float(invoice.paid_amount or 0)
        quote = invoice_early_discount(
            invoice, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
        )
        if use_discount and quote["eligible"] and amount + 1e-9 >= quote["cash_to_settle"]:
            if amount > due + 1e-9:
                raise HTTPException(status_code=409, detail="Payment exceeds invoice balance due")
            if amount + 1e-9 >= due:
                allocations.append((invoice, min(amount, due), 0.0))
            else:
                discount = round(due - amount, 2)
                if discount > quote["discount_amount"] + 1e-9:
                    raise HTTPException(
                        status_code=409,
                        detail=(
                            f"Payment too low for early discount; "
                            f"need at least {quote['cash_to_settle']:.2f}"
                        ),
                    )
                allocations.append((invoice, due, discount))
                total_discount = discount
        else:
            if amount > due + 1e-9:
                raise HTTPException(status_code=409, detail="Payment exceeds invoice balance due")
            allocations.append((invoice, amount, 0.0))
    else:
        open_invoices = (
            await db.execute(
                select(m.SalesInvoice)
                .where(
                    m.SalesInvoice.tenant_id == tenant_id,
                    m.SalesInvoice.customer_id == customer_id,
                    m.SalesInvoice.status.in_(["posted", "partial"]),
                )
                .order_by(m.SalesInvoice.due_date.asc(), m.SalesInvoice.posted_at.asc())
            )
        ).scalars().all()
        remaining = amount
        for invoice in open_invoices:
            due = float(invoice.total_amount) - float(invoice.paid_amount or 0)
            if due <= 0:
                continue
            quote = invoice_early_discount(
                invoice, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
            )
            if use_discount and quote["eligible"] and remaining + 1e-9 >= quote["cash_to_settle"]:
                settlement = due
                discount = quote["discount_amount"]
                cash_used = quote["cash_to_settle"]
                allocations.append((invoice, settlement, discount))
                total_discount = round(total_discount + discount, 2)
                remaining = round(remaining - cash_used, 2)
            else:
                apply_amt = min(remaining, due)
                allocations.append((invoice, apply_amt, 0.0))
                remaining = round(remaining - apply_amt, 2)
            if remaining <= 0:
                break
        if remaining > 1e-9 and open_invoices:
            raise HTTPException(
                status_code=409,
                detail=f"Payment exceeds open invoice balances by {remaining:.2f}",
            )

    # Payment currency defaults to first allocated invoice (or base).
    if allocations:
        inv0 = allocations[0][0]
        default_cur = doc_currency(inv0, tenant.currency or "GHS")
        for inv, _s, _d in allocations[1:]:
            if doc_currency(inv, tenant.currency or "GHS") != default_cur:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot auto-allocate across mixed invoice currencies; pay per invoice",
                )
        pay_cur = (currency or default_cur).strip().upper()
        if pay_cur != default_cur:
            raise HTTPException(
                status_code=400,
                detail=f"Payment currency {pay_cur} must match invoice currency {default_cur}",
            )
        if exchange_rate is not None:
            pay_rate = float(exchange_rate)
            if pay_rate <= 0:
                raise HTTPException(status_code=400, detail="exchange_rate must be positive")
            pay_cur = default_cur
        else:
            pay_cur, pay_rate = await resolve_rate(db, tenant_id, default_cur, explicit_rate=doc_rate(inv0))
    else:
        pay_cur, pay_rate = await resolve_rate(db, tenant_id, currency, explicit_rate=exchange_rate)

    primary_invoice_id = allocations[0][0].id if allocations else None
    alloc_note = ", ".join(
        f"{inv.invoice_number}:{amt:.2f}" + (f"(disc {disc:.2f})" if disc else "")
        for inv, amt, disc in allocations
    )
    settlement_base = round(
        sum(to_base(amt, doc_rate(inv)) for inv, amt, _ in allocations),
        2,
    )
    payment = m.CustomerPayment(
        tenant_id=tenant_id,
        company_id=company_id or getattr(customer, "company_id", None),
        payment_number=f"RCP-{datetime.utcnow():%Y%m%d%H%M%S%f}",
        customer_id=customer_id,
        sales_invoice_id=sales_invoice_id or primary_invoice_id,
        amount=amount,
        payment_method=payment_method,
        early_payment_discount=round(total_discount, 2),
        currency=pay_cur,
        exchange_rate=pay_rate,
        liquid_account_id=liquid_account_id,
        reference=reference,
        notes=notes
        or (
            f"Auto-allocated: {alloc_note}"
            if alloc_note and not sales_invoice_id
            else (f"Early discount {total_discount:.2f}" if total_discount else notes)
        ),
        created_by=user_id,
    )
    db.add(payment)

    # AR balance reduced by base settlement (invoice rates)
    customer.balance = max(float(customer.balance or 0) - settlement_base, 0)
    for invoice, apply_amt, _disc in allocations:
        invoice.paid_amount = float(invoice.paid_amount or 0) + apply_amt
        invoice.status = invoice_payment_status(
            float(invoice.total_amount),
            float(invoice.paid_amount),
            previous_status=invoice.status,
        )
        invoice.updated_at = datetime.utcnow()

    from app.accounting import post_customer_payment_journal

    await post_customer_payment_journal(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payment=payment,
        allocations=allocations or None,
    )

    from app import cheques as cheques_svc

    await cheques_svc.create_from_customer_payment(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payment=payment,
        cheque_number=cheque_number,
        bank_name=bank_name,
        cheque_date=cheque_date,
    )

    from app import audit as audit_svc
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="customer_payment",
        entity="customer_payment",
        entity_id=payment.id,
        details={
        "amount": amount,
        "early_payment_discount": total_discount,
        "currency": pay_cur,
        "exchange_rate": pay_rate,
        "fx_gain_loss": float(getattr(payment, "fx_gain_loss", 0) or 0),
        "customer_id": customer_id,
        "invoice_id": sales_invoice_id,
        "allocations": [
        {"invoice_id": inv.id, "amount": amt, "discount": disc}
        for inv, amt, disc in allocations
        ],
        },
        module='sales',
    )
    return payment
