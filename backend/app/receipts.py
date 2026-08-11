"""POS thermal receipt builders (text + narrow PDF)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.report_export import _pdf_escape

# Typical 80mm thermal width (~48 monospace chars); 58mm ~32
THERMAL_WIDTHS = {"80mm": 42, "58mm": 32}
RECEIPT_PRINT_TEMPLATES = frozenset({"thermal_80", "thermal_58"})
RECEIPT_TEMPLATE_TO_PAPER = {"thermal_80": "80mm", "thermal_58": "58mm"}
PAPER_TO_RECEIPT_TEMPLATE = {"80mm": "thermal_80", "58mm": "thermal_58"}


def resolve_receipt_paper(tenant: m.Tenant | None, paper: str | None = None) -> str:
    """Resolve POS receipt paper width from explicit paper or tenant default template."""
    if paper in THERMAL_WIDTHS:
        return paper  # type: ignore[return-value]
    tpl = (getattr(tenant, "receipt_print_template", None) or "thermal_80").strip().lower()
    if tpl not in RECEIPT_PRINT_TEMPLATES:
        tpl = "thermal_80"
    return RECEIPT_TEMPLATE_TO_PAPER[tpl]


def _money(value: float) -> str:
    return f"{float(value):.2f}"


def _wrap(text: str, width: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return [""]
    lines: list[str] = []
    while len(text) > width:
        cut = text.rfind(" ", 0, width + 1)
        if cut <= 0:
            cut = width
        lines.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    if text:
        lines.append(text)
    return lines


def _center(text: str, width: int) -> str:
    text = text[:width]
    pad = max(width - len(text), 0)
    left = pad // 2
    return (" " * left) + text


def _lr(left: str, right: str, width: int) -> str:
    left = (left or "")[: width - 1]
    right = (right or "")[:width]
    gap = width - len(left) - len(right)
    if gap < 1:
        return (left + right)[:width]
    return left + (" " * gap) + right


def build_receipt_payload(
    *,
    tx: m.Transaction,
    tenant: m.Tenant | None,
    cashier_name: str | None = None,
) -> dict[str, Any]:
    from app.print_branding import tenant_document_brand

    payload = tx.payload or {}
    items = payload.get("items") or []
    normalized_items = []
    for raw in items:
        name = (
            raw.get("name")
            or raw.get("product_name")
            or raw.get("sku")
            or raw.get("product_id")
            or "Item"
        )
        qty = float(raw.get("quantity") or 0)
        unit = float(
            raw.get("unit_price")
            if raw.get("unit_price") is not None
            else raw.get("selling_price")
            or 0
        )
        line_total = float(raw.get("line_total") if raw.get("line_total") is not None else qty * unit)
        normalized_items.append(
            {
                "name": str(name),
                "sku": raw.get("sku"),
                "quantity": qty,
                "unit_price": unit,
                "line_total": line_total,
                "product_id": raw.get("product_id"),
                "variant_id": raw.get("variant_id"),
            }
        )
    brand = tenant_document_brand(tenant)
    default_paper = resolve_receipt_paper(tenant)
    return {
        "sale_id": tx.id,
        "reference": tx.reference,
        "company_name": brand["company_name"],
        "legal_name": brand["legal_name"],
        "trading_name": brand["trading_name"],
        "has_logo": brand["has_logo"],
        "logo_data_url": brand["logo_data_url"],
        "document_header": brand["document_header"],
        "document_footer": brand["document_footer"],
        "receipt_print_template": PAPER_TO_RECEIPT_TEMPLATE.get(default_paper, "thermal_80"),
        "default_paper": default_paper,
        "company_phone": brand["company_phone"] or (tenant.phone if tenant else None),
        "company_address": brand["company_address"] or (tenant.address if tenant else None),
        "currency": tenant.currency if tenant else "GHS",
        "cashier_name": cashier_name,
        "customer_name": payload.get("customer_name"),
        "subtotal": float(tx.subtotal or 0),
        "tax": float(tx.tax or 0),
        "discount_amount": float(payload.get("discount_amount") or 0),
        "total": float(tx.total or 0),
        "items": normalized_items,
        "payment_method": payload.get("payment_method", "cash"),
        "payments": payload.get("payments") or [],
        "session_id": payload.get("session_id"),
        "created_at": tx.created_at,
        "format": "json",
    }


def render_thermal_text(receipt: dict[str, Any], *, paper: str = "80mm") -> str:
    from app.print_branding import header_footer_text_lines

    width = THERMAL_WIDTHS.get(paper, THERMAL_WIDTHS["80mm"])
    lines: list[str] = []
    lines.append(_center(str(receipt.get("company_name") or "RIBDIGI ERP"), width))
    if receipt.get("trading_name"):
        lines.append(_center(f"T/A {receipt['trading_name']}", width))
    if receipt.get("has_logo") or receipt.get("logo_data_url"):
        lines.append(_center("[Company logo on file]", width))
    if receipt.get("company_address"):
        lines.extend(_wrap(str(receipt["company_address"]), width))
    if receipt.get("company_phone"):
        lines.append(_center(str(receipt["company_phone"]), width))
    for part in header_footer_text_lines(receipt.get("document_header"), width):
        lines.append(_center(part, width))
    lines.append("-" * width)
    lines.append(_lr("Sale", str(receipt.get("reference") or ""), width))
    created = receipt.get("created_at")
    if isinstance(created, datetime):
        lines.append(_lr("Date", created.strftime("%Y-%m-%d %H:%M"), width))
    elif created:
        lines.append(_lr("Date", str(created)[:16], width))
    if receipt.get("cashier_name"):
        lines.append(_lr("Cashier", str(receipt["cashier_name"])[: width // 2], width))
    if receipt.get("customer_name"):
        lines.append(_lr("Customer", str(receipt["customer_name"])[: width // 2], width))
    lines.append("-" * width)
    for item in receipt.get("items") or []:
        name = str(item.get("name") or "Item")
        qty = float(item.get("quantity") or 0)
        unit = float(item.get("unit_price") or 0)
        total = float(item.get("line_total") or qty * unit)
        for i, part in enumerate(_wrap(name, width)):
            lines.append(part if i == 0 else ("  " + part)[:width])
        lines.append(_lr(f"  {qty:g} x {_money(unit)}", _money(total), width))
    lines.append("-" * width)
    currency = receipt.get("currency") or ""
    lines.append(_lr("Subtotal", _money(receipt.get("subtotal") or 0), width))
    lines.append(_lr("Tax", _money(receipt.get("tax") or 0), width))
    discount = float(receipt.get("discount_amount") or 0)
    if discount > 0:
        lines.append(_lr("Discount", _money(discount), width))
    lines.append(_lr(f"TOTAL {currency}".strip(), _money(receipt.get("total") or 0), width))
    payments = receipt.get("payments") or []
    if len(payments) > 1:
        lines.append(_center("Payments", width))
        for pay in payments:
            method = str(pay.get("payment_method") or "cash").upper()
            lines.append(_lr(method, _money(pay.get("amount") or 0), width))
    else:
        lines.append(_lr("Payment", str(receipt.get("payment_method") or "cash").upper(), width))
    lines.append("-" * width)
    footer_lines = header_footer_text_lines(receipt.get("document_footer"), width)
    if footer_lines:
        for part in footer_lines:
            lines.append(_center(part, width))
    else:
        lines.append(_center("Thank you", width))
    from app.print_branding import platform_print_footer_text_lines

    for part in platform_print_footer_text_lines(width=width, center=True):
        if part:
            lines.append(part)
    lines.append("")
    return "\n".join(lines)


def escpos_drawer_kick() -> bytes:
    """Raw ESC/POS cash-drawer pulse (pin 0)."""
    from app.cash_drawer import kick_bytes

    return kick_bytes()


def to_thermal_pdf(receipt: dict[str, Any], *, paper: str = "80mm") -> bytes:
    """Narrow receipt PDF suitable for 58/80mm thermal printers (or browser print)."""
    text = render_thermal_text(receipt, paper=paper)
    lines = text.splitlines() or [""]
    page_width = 226 if paper == "80mm" else 164  # ~80mm / ~58mm at 72dpi
    line_height = 11
    top = 20
    bottom = 20
    page_height = max(top + bottom + line_height * (len(lines) + 2), 200)

    content: list[str] = []
    y = page_height - top
    for line in lines:
        content.append(
            f"BT /F1 8 Tf 8 {y} Td ({_pdf_escape(line[:80])}) Tj ET"
        )
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


async def build_sale_receipt(
    db: AsyncSession,
    *,
    tenant_id: str,
    sale_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    from sqlalchemy import select

    tx = (
        await db.execute(
            select(m.Transaction).where(
                m.Transaction.id == sale_id,
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
            )
        )
    ).scalar_one_or_none()
    if not tx:
        raise HTTPException(status_code=404, detail="POS sale not found")
    tenant = await db.get(m.Tenant, tenant_id)
    cashier_name = None
    if user_id:
        user = await db.get(m.User, user_id)
        cashier_name = user.full_name if user else None
    return build_receipt_payload(tx=tx, tenant=tenant, cashier_name=cashier_name)
