"""Sales invoice print payloads (A4 + thermal), reusing thermal PDF helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.receipts import (
    THERMAL_WIDTHS,
    _center,
    _lr,
    _money,
    _wrap,
    _clean_text,
)
from app.report_export import _pdf_escape
from app.sales import get_customer, get_invoice, list_invoice_items

PRINTABLE_INVOICE_STATUSES = frozenset({"posted", "partial", "paid"})


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
                "quantity": float(item.quantity),
                "unit_price": float(item.unit_price),
                "tax_rate": float(item.tax_rate or 0),
                "discount": float(item.discount or 0),
                "line_total": float(item.line_total),
                "product_id": item.product_id,
                "variant_id": item.variant_id,
            }
        )

    company_name = _clean_text(tenant.company_name if tenant else None) or "RIBDIGI ERP"
    currency = (getattr(invoice, "currency", None) or "").strip() or (
        tenant.currency if tenant else "GHS"
    )
    paid = float(invoice.paid_amount or 0)
    total = float(invoice.total_amount or 0)
    balance = max(total - paid, 0)

    return {
        "document_type": "sales_invoice",
        "invoice_id": invoice.id,
        "reference": invoice.invoice_number,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status,
        "company_name": company_name,
        "store_name": _clean_text(store.name if store else None),
        "store_id": store.id if store else None,
        "company_phone": _clean_text(store.phone if store else None)
        or _clean_text(tenant.phone if tenant else None),
        "company_email": _clean_text(tenant.email if tenant else None),
        "company_website": _clean_text(tenant.website if tenant else None),
        "company_address": _clean_text(store.address if store else None)
        or _clean_text(tenant.address if tenant else None),
        "currency": currency,
        "customer_name": customer.name,
        "customer_email": _clean_text(customer.email),
        "customer_phone": _clean_text(getattr(customer, "phone", None)),
        "subtotal": float(invoice.subtotal or 0),
        "tax": float(invoice.tax_amount or 0),
        "tax_amount": float(invoice.tax_amount or 0),
        "discount_amount": float(invoice.discount_amount or 0),
        "total": total,
        "total_amount": total,
        "paid_amount": paid,
        "balance_due": balance,
        "payment_method": invoice.status,
        "payments": [],
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
        qty = float(item.get("quantity") or 0)
        unit = float(item.get("unit_price") or 0)
        total = float(item.get("line_total") or qty * unit)
        for i, part in enumerate(_wrap(name, width)):
            lines.append(part if i == 0 else ("  " + part)[:width])
        lines.append(_lr(f"  {qty:g} x {_money(unit)}", _money(total), width))
    lines.append("-" * width)
    currency = payload.get("currency") or ""
    lines.append(_lr("Subtotal", _money(payload.get("subtotal") or 0), width))
    lines.append(_lr("Tax", _money(payload.get("tax") or 0), width))
    discount_amount = float(payload.get("discount_amount") or 0)
    if discount_amount > 0:
        lines.append(_lr("Discount", f"-{_money(discount_amount)}", width))
    lines.append(_lr(f"TOTAL {currency}".strip(), _money(payload.get("total") or 0), width))
    lines.append(_lr("Paid", _money(payload.get("paid_amount") or 0), width))
    lines.append(_lr("Balance", _money(payload.get("balance_due") or 0), width))
    if payload.get("notes"):
        lines.append("-" * width)
        for part in _wrap(f"Notes: {payload['notes']}", width):
            lines.append(part)
    lines.append("-" * width)
    lines.append(_center("Thank you", width))
    lines.append(_center("Powered by RIBDIGI", width))
    lines.append("")
    return "\n".join(lines)


def to_invoice_thermal_pdf(payload: dict[str, Any], *, paper: str = "80mm") -> bytes:
    text = render_invoice_thermal_text(payload, paper=paper)
    lines = text.splitlines() or [""]
    page_width = 226 if paper == "80mm" else 164
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
    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        (
            f"3 0 obj<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {page_width} {page_height}] "
            f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
        ).encode("ascii")
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj\n")
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


def to_invoice_a4_pdf(payload: dict[str, Any]) -> bytes:
    """Simple A4 PDF invoice (Helvetica / Courier)."""
    page_width, page_height = 595, 842  # A4 points
    margin = 40
    lines: list[tuple[str, int]] = []  # text, font size

    def add(text: str, size: int = 10) -> None:
        lines.append((text, size))

    add(str(payload.get("company_name") or "RIBDIGI ERP"), 16)
    if payload.get("company_address"):
        add(str(payload["company_address"]), 9)
    if payload.get("company_phone"):
        add(f"Tel: {payload['company_phone']}", 9)
    if payload.get("company_email"):
        add(str(payload["company_email"]), 9)
    add("", 10)
    add("SALES INVOICE", 14)
    add(f"Invoice: {payload.get('invoice_number') or ''}", 11)
    add(f"Status: {str(payload.get('status') or '').upper()}", 10)
    posted = payload.get("posted_at") or payload.get("created_at")
    if isinstance(posted, datetime):
        add(f"Date: {posted.strftime('%Y-%m-%d %H:%M')}", 10)
    elif posted:
        add(f"Date: {str(posted)[:16]}", 10)
    if payload.get("due_date"):
        due = payload["due_date"]
        due_s = due.strftime("%Y-%m-%d") if isinstance(due, datetime) else str(due)[:10]
        add(f"Due date: {due_s}", 10)
    add("", 10)
    add(f"Bill to: {payload.get('customer_name') or '—'}", 11)
    if payload.get("customer_email"):
        add(str(payload["customer_email"]), 9)
    if payload.get("customer_phone"):
        add(str(payload["customer_phone"]), 9)
    add("", 10)
    add("Qty  Description                          Unit      Tax%      Line", 9)
    add("-" * 72, 9)
    for item in payload.get("items") or []:
        name = str(item.get("name") or "Item")[:34]
        qty = float(item.get("quantity") or 0)
        unit = float(item.get("unit_price") or 0)
        tax = float(item.get("tax_rate") or 0)
        line_total = float(item.get("line_total") or 0)
        add(
            f"{qty:>4g}  {name:<34} {_money(unit):>8} {_money(tax):>7} {_money(line_total):>9}",
            9,
        )
    add("-" * 72, 9)
    currency = payload.get("currency") or ""
    add(f"Subtotal: {currency} {_money(payload.get('subtotal') or 0)}", 10)
    add(f"Tax: {currency} {_money(payload.get('tax') or 0)}", 10)
    disc = float(payload.get("discount_amount") or 0)
    if disc > 0:
        add(f"Discount: -{currency} {_money(disc)}", 10)
    add(f"TOTAL: {currency} {_money(payload.get('total') or 0)}", 12)
    add(f"Paid: {currency} {_money(payload.get('paid_amount') or 0)}", 10)
    add(f"Balance due: {currency} {_money(payload.get('balance_due') or 0)}", 11)
    if payload.get("notes"):
        add("", 10)
        add(f"Notes: {payload['notes']}", 9)
    add("", 10)
    add("Thank you for your business.", 10)
    add("Powered by RIBDIGI", 8)

    content: list[str] = []
    y = page_height - margin
    for text, size in lines:
        font = "F2" if size >= 12 else "F1"
        content.append(f"BT /{font} {size} Tf {margin} {y} Td ({_pdf_escape(text[:110])}) Tj ET")
        y -= size + 4
        if y < margin:
            break
    stream = "\n".join(content).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        (
            f"3 0 obj<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {page_width} {page_height}] "
            f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>endobj\n"
        ).encode("ascii")
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream)} >>stream\n".encode("ascii")
        + stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj\n")
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
