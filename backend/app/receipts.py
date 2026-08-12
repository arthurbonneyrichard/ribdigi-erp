"""POS thermal receipt builders (text + narrow PDF)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

# Typical 80mm thermal width (~48 monospace chars); 58mm ~32
THERMAL_WIDTHS = {"80mm": 42, "58mm": 32}


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


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_receipt_payload(
    *,
    tx: m.Transaction,
    tenant: m.Tenant | None,
    cashier_name: str | None = None,
    store: m.Store | None = None,
) -> dict[str, Any]:
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
    customer_name = payload.get("customer_name")
    if isinstance(customer_name, str):
        customer_name = customer_name.strip() or None
    else:
        customer_name = None

    company_name = _clean_text(tenant.company_name if tenant else None) or "RIBDIGI ERP"
    store_name = _clean_text(store.name if store else None)
    # Prefer the selling store's contact/location; fall back to company profile.
    company_phone = _clean_text(store.phone if store else None) or _clean_text(
        tenant.phone if tenant else None
    )
    company_email = _clean_text(tenant.email if tenant else None)
    company_website = _clean_text(tenant.website if tenant else None)
    company_address = _clean_text(store.address if store else None) or _clean_text(
        tenant.address if tenant else None
    )

    from app.print_branding import branding_fields_for_payload

    branding = branding_fields_for_payload(tenant)

    return {
        "sale_id": tx.id,
        "reference": tx.reference,
        "company_name": company_name,
        "store_name": store_name,
        "store_id": store.id if store else None,
        "company_phone": company_phone,
        "company_email": company_email,
        "company_website": company_website,
        "company_address": company_address,
        "print_header": branding["print_header"],
        "print_footer": branding["print_footer"],
        "has_logo": branding["has_logo"],
        "default_invoice_template": branding["default_invoice_template"],
        "default_receipt_paper": branding["default_receipt_paper"],
        "tenant_id": getattr(tx, "tenant_id", None) or getattr(tenant, "id", None),
        "logo_key": getattr(tenant, "logo_url", None) if tenant else None,
        "currency": tenant.currency if tenant else "GHS",
        "cashier_name": cashier_name,
        "customer_name": customer_name,
        "subtotal": float(tx.subtotal or 0),
        "tax": float(tx.tax or 0),
        "discount_amount": float(payload.get("discount_amount") or 0),
        "line_discounts": float(payload.get("line_discounts") or 0),
        "total": float(tx.total or 0),
        "items": normalized_items,
        "payment_method": payload.get("payment_method", "cash"),
        "payments": payload.get("payments") or [],
        "session_id": payload.get("session_id") or getattr(tx, "session_id", None),
        "created_at": tx.created_at,
        "format": "json",
    }


def render_thermal_text(receipt: dict[str, Any], *, paper: str = "80mm") -> str:
    width = THERMAL_WIDTHS.get(paper, THERMAL_WIDTHS["80mm"])
    lines: list[str] = []
    lines.append(_center(str(receipt.get("company_name") or "RIBDIGI ERP"), width))
    if receipt.get("store_name"):
        lines.append(_center(str(receipt["store_name"]), width))
    if receipt.get("company_address"):
        for part in _wrap(str(receipt["company_address"]), width):
            lines.append(_center(part, width))
    if receipt.get("company_phone"):
        lines.append(_center(f"Tel: {receipt['company_phone']}", width))
    if receipt.get("company_email"):
        lines.append(_center(str(receipt["company_email"]), width))
    if receipt.get("company_website"):
        lines.append(_center(str(receipt["company_website"]), width))
    if receipt.get("print_header"):
        for part in _wrap(str(receipt["print_header"]), width):
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
    discount_amount = float(receipt.get("discount_amount") or 0)
    if discount_amount > 0:
        lines.append(_lr("Discount", f"-{_money(discount_amount)}", width))
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
    footer = receipt.get("print_footer") or "Thank you"
    for part in _wrap(str(footer), width):
        lines.append(_center(part, width))
    lines.append(_center("Powered by RIBDIGI", width))
    lines.append("")
    return "\n".join(lines)


def escpos_drawer_kick() -> bytes:
    """Raw ESC/POS cash-drawer pulse (pin 0)."""
    from app.cash_drawer import kick_bytes

    return kick_bytes()


def to_thermal_pdf(receipt: dict[str, Any], *, paper: str = "80mm") -> bytes:
    """Narrow receipt PDF suitable for 58/80mm thermal printers (or browser print)."""
    from app.print_branding import build_text_pdf, load_logo_jpeg

    text = render_thermal_text(receipt, paper=paper)
    lines = [(line, 8) for line in (text.splitlines() or [""])]
    page_width = 226 if paper == "80mm" else 164
    line_height = 11
    top = 20
    bottom = 20
    page_height = max(top + bottom + line_height * (len(lines) + 8), 200)
    logo = None
    if receipt.get("logo_key") and receipt.get("tenant_id"):

        class _T:
            id = receipt["tenant_id"]
            logo_url = receipt["logo_key"]

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

    store = None
    session_id = tx.session_id or (tx.payload or {}).get("session_id")
    if session_id:
        session = await db.get(m.PosSession, session_id)
        if session and session.tenant_id == tenant_id and session.store_id:
            store = (
                await db.execute(
                    select(m.Store).where(
                        m.Store.id == session.store_id,
                        m.Store.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()

    return build_receipt_payload(
        tx=tx, tenant=tenant, cashier_name=cashier_name, store=store
    )
