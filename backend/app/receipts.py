"""POS thermal receipt builders (HTML + text + narrow PDF)."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json

WALK_IN_CUSTOMER = "Walk-in"

# Typical 80mm thermal width (~48 monospace chars); 58mm ~32
THERMAL_WIDTHS = {"80mm": 42, "58mm": 32}


def _money(value: float) -> str:
    return f"{money_json(value or 0):.2f}"


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


def _receipt_customer_name(
    *,
    tx: m.Transaction,
    payload: dict[str, Any],
    party: m.Party | None = None,
) -> str:
    """Name of the customer on this sale, or Walk-in.

    Checkout `party_id` is the source of truth. A leftover `customer_name` on
    the stored payload is ignored for walk-in sales and overridden by the
    selected party's name when `party_id` is set.
    """
    party_id = getattr(tx, "party_id", None)
    if not party_id:
        return WALK_IN_CUSTOMER
    if party is not None:
        named = _clean_text(getattr(party, "name", None))
        if named:
            return named
    stored = payload.get("customer_name")
    if isinstance(stored, str):
        named = stored.strip() or None
        if named:
            return named
    return WALK_IN_CUSTOMER


async def load_sale_party(
    db: AsyncSession, *, tenant_id: str, party_id: str | None
) -> m.Party | None:
    if not party_id:
        return None
    from sqlalchemy import select

    return (
        await db.execute(
            select(m.Party).where(
                m.Party.id == party_id,
                m.Party.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()


def _receipt_payments(raw: Any) -> list[dict[str, Any]]:
    """Tender method + amount only — never card/auth payment references."""
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for pay in raw:
        if not isinstance(pay, dict):
            continue
        out.append(
            {
                "payment_method": pay.get("payment_method") or "cash",
                "amount": money_json(pay.get("amount") or 0),
            }
        )
    return out


def build_receipt_payload(
    *,
    tx: m.Transaction,
    tenant: m.Tenant | None,
    cashier_name: str | None = None,
    store: m.Store | None = None,
    party: m.Party | None = None,
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
        qty = money_json(raw.get("quantity") or 0)
        unit = money_json(
            raw.get("unit_price")
            if raw.get("unit_price") is not None
            else raw.get("selling_price")
            or 0
        )
        line_total = money_json(
            raw.get("line_total") if raw.get("line_total") is not None else qty * unit
        )
        normalized_items.append(
            {
                "name": str(name),
                "sku": raw.get("sku"),
                "quantity": qty,
                "unit_price": unit,
                "discount": money_json(raw.get("discount") or 0),
                "discount_type": raw.get("discount_type") or "fixed",
                "discount_percent": money_json(raw.get("discount_percent") or 0),
                "line_total": line_total,
                "product_id": raw.get("product_id"),
                "variant_id": raw.get("variant_id"),
            }
        )
    customer_name = _receipt_customer_name(tx=tx, payload=payload, party=party)
    receipt_payments = _receipt_payments(payload.get("payments") or [])

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
    from app.pos import sale_settlement

    branding = branding_fields_for_payload(tenant)
    settle = sale_settlement(
        total=money_json(tx.total),
        payments=payload.get("payments") or None,
        payment_method=payload.get("payment_method"),
    )

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
        "subtotal": money_json(tx.subtotal),
        "tax": money_json(tx.tax),
        "discount_amount": money_json(payload.get("discount_amount") or 0),
        "discount_type": payload.get("discount_type") or "fixed",
        "discount_percent": money_json(payload.get("discount_percent") or 0),
        "line_discounts": money_json(payload.get("line_discounts") or 0),
        "total": money_json(tx.total),
        "items": normalized_items,
        "payment_method": payload.get("payment_method", "cash"),
        "payments": receipt_payments,
        "session_id": payload.get("session_id") or getattr(tx, "session_id", None),
        "created_at": tx.created_at,
        "format": "json",
        "paid_amount": settle["paid_amount"],
        "credit_amount": settle["credit_amount"],
        "balance_due": settle["balance_due"],
        "payment_status": settle["payment_status"],
        "invoice_number": payload.get("invoice_number"),
        "sales_invoice_id": payload.get("sales_invoice_id"),
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
    customer_label = str(receipt.get("customer_name") or WALK_IN_CUSTOMER).strip() or WALK_IN_CUSTOMER
    lines.append(_lr("Customer", customer_label[: width // 2], width))
    lines.append("-" * width)
    for item in receipt.get("items") or []:
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
    currency = receipt.get("currency") or ""
    lines.append(_lr("Subtotal", _money(receipt.get("subtotal") or 0), width))
    lines.append(_lr("Tax", _money(receipt.get("tax") or 0), width))
    discount_amount = money_json(receipt.get("discount_amount") or 0)
    if discount_amount > 0:
        lines.append(_lr("Discount", f"-{_money(discount_amount)}", width))
    lines.append(_lr(f"TOTAL {currency}".strip(), _money(receipt.get("total") or 0), width))
    payments = receipt.get("payments") or []
    if len(payments) > 1:
        lines.append(_center("Payments", width))
        for pay in payments:
            from app.pos import payment_method_label

            method = payment_method_label(pay.get("payment_method"))
            lines.append(_lr(method, _money(pay.get("amount") or 0), width))
            # Payment reference (card/auth) is till-only — never print it.
    else:
        from app.pos import payment_method_label

        lines.append(_lr("Payment", payment_method_label(receipt.get("payment_method")), width))
    paid_amount = money_json(receipt.get("paid_amount"))
    balance_due = money_json(receipt.get("balance_due"))
    status = str(receipt.get("payment_status") or "").replace("_", " ")
    if paid_amount > 0 or balance_due > 0 or status:
        lines.append(_lr("Paid", _money(paid_amount), width))
        if balance_due > 0:
            lines.append(_lr("Balance due", _money(balance_due), width))
        if status:
            lines.append(_lr("Status", status.upper(), width))
    if receipt.get("invoice_number"):
        lines.append(_lr("Invoice", str(receipt.get("invoice_number")), width))
    lines.append("-" * width)
    footer = receipt.get("print_footer") or "Thank you"
    for part in _wrap(str(footer), width):
        lines.append(_center(part, width))
    lines.append(_center("Powered by RIBDIGI", width))
    lines.append("")
    return "\n".join(lines)


def render_thermal_html(receipt: dict[str, Any], *, paper: str = "80mm") -> str:
    """Browser/email HTML for the same thermal receipt (no payment references)."""
    text = render_thermal_text(receipt, paper=paper)
    return (
        '<pre style="font-family:monospace;white-space:pre-wrap">'
        f"{html.escape(text)}</pre>"
    )


def escpos_drawer_kick() -> bytes:
    """Raw ESC/POS cash-drawer pulse (pin 0)."""
    from app.cash_drawer import kick_bytes

    return kick_bytes()


def to_thermal_pdf(receipt: dict[str, Any], *, paper: str = "80mm") -> bytes:
    """Narrow receipt PDF suitable for 58/80mm thermal printers (or browser print)."""
    from app.print_branding import build_text_pdf, load_logo_jpeg, style_powered_by_line

    text = render_thermal_text(receipt, paper=paper)
    lines = [style_powered_by_line(line, 8) for line in (text.splitlines() or [""])]
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

    party = await load_sale_party(db, tenant_id=tenant_id, party_id=tx.party_id)

    return build_receipt_payload(
        tx=tx, tenant=tenant, cashier_name=cashier_name, store=store, party=party
    )
