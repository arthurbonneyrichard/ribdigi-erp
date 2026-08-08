"""Tax rate helpers, calculation, and period reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


def normalize_components(raw: list | None) -> list[dict[str, Any]] | None:
    if not raw:
        return None
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        rate = float(item.get("rate") or 0)
        if rate < 0:
            raise HTTPException(status_code=400, detail="Component rate must be >= 0")
        basis = (item.get("basis") or "net").lower()
        if basis not in {"net", "compound"}:
            raise HTTPException(status_code=400, detail="Component basis must be net or compound")
        code = (item.get("code") or item.get("name") or f"c{len(out)+1}").strip()[:40]
        name = (item.get("name") or code).strip()[:80]
        out.append({"code": code, "name": name, "rate": rate, "basis": basis})
    return out or None


def effective_rate_from_components(components: list[dict] | None, fallback: float) -> float:
    if not components:
        return float(fallback or 0)
    # Approximate header rate: sum of net-basis rates (compound legs not additive).
    total = 0.0
    for c in components:
        if c.get("basis", "net") == "net":
            total += float(c.get("rate") or 0)
    if total <= 0:
        total = sum(float(c.get("rate") or 0) for c in components)
    return round(total, 4)


def compute_tax_amounts(
    amount: float,
    rate_pct: float,
    pricing_mode: str = "exclusive",
    *,
    components: list[dict] | None = None,
    is_reverse_charge: bool = False,
) -> tuple[float, float, float]:
    """Return (net, tax, gross) for a taxable amount."""
    detail = compute_tax_breakdown(
        amount,
        rate_pct,
        pricing_mode,
        components=components,
        is_reverse_charge=is_reverse_charge,
    )
    return detail["net"], detail["tax"], detail["gross"]


def compute_tax_breakdown(
    amount: float,
    rate_pct: float,
    pricing_mode: str = "exclusive",
    *,
    components: list[dict] | None = None,
    is_reverse_charge: bool = False,
) -> dict[str, Any]:
    """Detailed tax calc including optional compound component lines."""
    amount = float(amount or 0)
    mode = (pricing_mode or "exclusive").lower()
    comps = normalize_components(components) if components else None
    rate = effective_rate_from_components(comps, rate_pct) if comps else float(rate_pct or 0)

    if amount <= 0:
        return {
            "net": round(amount, 2),
            "tax": 0.0,
            "gross": round(amount, 2),
            "effective_rate": rate,
            "is_reverse_charge": bool(is_reverse_charge),
            "components": [],
        }

    component_lines: list[dict[str, Any]] = []

    if comps:
        if mode == "inclusive":
            eff = effective_rate_from_components(comps, rate)
            if eff <= 0:
                net = round(amount, 2)
                return {
                    "net": net,
                    "tax": 0.0,
                    "gross": net,
                    "effective_rate": 0.0,
                    "is_reverse_charge": bool(is_reverse_charge),
                    "components": [],
                }
            gross = round(amount, 2)
            tax = round(gross * eff / (100.0 + eff), 2)
            net = round(gross - tax, 2)
            net_comps = [c for c in comps if c["basis"] == "net"] or list(comps)
            denom = sum(float(c["rate"]) for c in net_comps) or eff
            allocated = 0.0
            for i, c in enumerate(net_comps):
                if i == len(net_comps) - 1:
                    share = round(tax - allocated, 2)
                else:
                    share = round(tax * (float(c["rate"]) / denom), 2)
                    allocated += share
                component_lines.append({**c, "amount": share})
        else:
            net = round(amount, 2)
            running = net
            tax = 0.0
            for c in comps:
                if c["basis"] == "compound":
                    part = round(running * float(c["rate"]) / 100.0, 2)
                else:
                    part = round(net * float(c["rate"]) / 100.0, 2)
                running += part
                tax += part
                component_lines.append({**c, "amount": part})
            tax = round(tax, 2)
            gross = round(net + tax, 2)
    else:
        if rate <= 0:
            net = round(amount, 2)
            return {
                "net": net,
                "tax": 0.0,
                "gross": net,
                "effective_rate": 0.0,
                "is_reverse_charge": bool(is_reverse_charge),
                "components": [],
            }
        if mode == "inclusive":
            gross = round(amount, 2)
            tax = round(gross * rate / (100.0 + rate), 2)
            net = round(gross - tax, 2)
        else:
            net = round(amount, 2)
            tax = round(net * rate / 100.0, 2)
            gross = round(net + tax, 2)

    if is_reverse_charge:
        # Chargeable document total excludes tax; tax kept for memo / self-assessment.
        gross = net

    return {
        "net": net,
        "tax": tax,
        "gross": gross,
        "effective_rate": rate,
        "is_reverse_charge": bool(is_reverse_charge),
        "components": component_lines,
    }


def compute_line_total(
    quantity: float,
    unit_price: float,
    tax_rate: float,
    pricing_mode: str = "exclusive",
    *,
    components: list[dict] | None = None,
    is_reverse_charge: bool = False,
) -> tuple[float, float, float]:
    qty = float(quantity or 0)
    price = float(unit_price or 0)
    line_amount = qty * price
    return compute_tax_amounts(
        line_amount,
        tax_rate,
        pricing_mode,
        components=components,
        is_reverse_charge=is_reverse_charge,
    )


@dataclass(frozen=True)
class TaxSpec:
    rate_pct: float
    pricing_mode: str = "exclusive"
    components: tuple[dict, ...] | None = None
    is_reverse_charge: bool = False
    tax_rate_id: str | None = None

    def compute_amounts(self, amount: float) -> tuple[float, float, float]:
        return compute_tax_amounts(
            amount,
            self.rate_pct,
            self.pricing_mode,
            components=list(self.components) if self.components else None,
            is_reverse_charge=self.is_reverse_charge,
        )

    def compute_breakdown(self, amount: float) -> dict[str, Any]:
        return compute_tax_breakdown(
            amount,
            self.rate_pct,
            self.pricing_mode,
            components=list(self.components) if self.components else None,
            is_reverse_charge=self.is_reverse_charge,
        )


async def get_default_tax_rate(db: AsyncSession, tenant_id: str) -> m.TaxRate | None:
    return (
        await db.execute(
            select(m.TaxRate).where(
                m.TaxRate.tenant_id == tenant_id,
                m.TaxRate.is_active == True,  # noqa: E712
                m.TaxRate.is_default == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()


async def get_tax_rate(db: AsyncSession, tenant_id: str, tax_rate_id: str) -> m.TaxRate:
    row = (
        await db.execute(
            select(m.TaxRate).where(m.TaxRate.id == tax_rate_id, m.TaxRate.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Tax rate not found")
    return row


async def clear_default_flags(db: AsyncSession, tenant_id: str) -> None:
    rows = (
        await db.execute(
            select(m.TaxRate).where(m.TaxRate.tenant_id == tenant_id, m.TaxRate.is_default == True)  # noqa: E712
        )
    ).scalars().all()
    for row in rows:
        row.is_default = False


def tax_spec_from_rate(rate: m.TaxRate) -> TaxSpec:
    comps = normalize_components(rate.components) if rate.components else None
    return TaxSpec(
        rate_pct=float(rate.rate),
        pricing_mode=rate.pricing_mode or "exclusive",
        components=tuple(comps) if comps else None,
        is_reverse_charge=bool(rate.is_reverse_charge),
        tax_rate_id=rate.id,
    )


async def resolve_product_tax(
    db: AsyncSession,
    tenant_id: str,
    product: m.Product,
    explicit_rate: float | None = None,
) -> TaxSpec:
    """Resolve full tax spec for a product line."""
    if product.tax_exempt:
        return TaxSpec(rate_pct=0.0, pricing_mode="exclusive")
    if explicit_rate is not None:
        default = await get_default_tax_rate(db, tenant_id)
        mode = default.pricing_mode if default else "exclusive"
        # Explicit override uses single-rate path (no compound legs).
        return TaxSpec(rate_pct=float(explicit_rate), pricing_mode=mode)
    if product.tax_rate_id:
        rate = await get_tax_rate(db, tenant_id, product.tax_rate_id)
        if rate.is_active:
            return tax_spec_from_rate(rate)
    default = await get_default_tax_rate(db, tenant_id)
    if default:
        return tax_spec_from_rate(default)
    return TaxSpec(rate_pct=0.0, pricing_mode="exclusive")


async def resolve_product_tax_rate(
    db: AsyncSession,
    tenant_id: str,
    product: m.Product,
    explicit_rate: float | None = None,
) -> tuple[float, str]:
    """Return (rate_pct, pricing_mode). Back-compat wrapper."""
    spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=explicit_rate)
    return spec.rate_pct, spec.pricing_mode


def serialize_tax_rate(rate: m.TaxRate) -> dict:
    comps = normalize_components(rate.components) if rate.components else None
    return {
        "id": rate.id,
        "name": rate.name,
        "rate": float(rate.rate),
        "tax_type": rate.tax_type,
        "pricing_mode": rate.pricing_mode,
        "components": comps,
        "is_reverse_charge": bool(rate.is_reverse_charge),
        "is_default": rate.is_default,
        "is_active": rate.is_active,
    }


async def tax_report(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    """Summary VAT/GST output vs input tax for a period."""
    pack = await tax_filing_pack(db, tenant_id, from_date=from_date, to_date=to_date)
    return {
        "from_date": from_date,
        "to_date": to_date,
        "output_tax": pack["output_tax"],
        "output_tax_invoices": pack["output_tax_invoices"],
        "output_tax_pos": pack["output_tax_pos"],
        "reverse_charge_tax": pack["reverse_charge_tax"],
        "input_tax": pack["input_tax"],
        "input_tax_source": pack["input_tax_source"],
        "net_tax_payable": pack["net_tax_payable"],
        "invoice_count": pack["invoice_count"],
        "pos_sale_count": pack["pos_sale_count"],
        "purchase_count": pack["purchase_count"],
        "purchase_order_count": pack["purchase_order_count"],
        "taxable_outputs_net": pack["filing_boxes"]["taxable_outputs_net"],
        "taxable_inputs_net": pack["filing_boxes"]["taxable_inputs_net"],
    }


async def tax_filing_pack(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    """Jurisdiction-neutral VAT/GST filing pack: boxes + detailed schedules for export."""
    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid"]),
    )
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    invoices = (await db.execute(inv_stmt)).scalars().all()

    output_schedule = []
    output_invoices = 0.0
    reverse_charge_tax = 0.0
    taxable_outputs = 0.0
    for inv in invoices:
        tax = float(inv.tax_amount or 0)
        rc = float(getattr(inv, "reverse_charge_tax", 0) or 0)
        net = float(inv.subtotal or 0)
        output_invoices += tax
        reverse_charge_tax += rc
        taxable_outputs += net
        output_schedule.append(
            {
                "schedule": "output_sales_invoices",
                "document_type": "sales_invoice",
                "document_number": inv.invoice_number,
                "document_id": inv.id,
                "document_date": inv.posted_at or inv.created_at,
                "net_amount": round(net, 2),
                "tax_amount": round(tax, 2),
                "reverse_charge_tax": round(rc, 2),
                "gross_amount": round(float(inv.total_amount or 0), 2),
                "party_id": inv.customer_id,
            }
        )

    pos_stmt = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
    )
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    pos_sales = (await db.execute(pos_stmt)).scalars().all()
    output_pos = 0.0
    for tx in pos_sales:
        tax = float(tx.tax or 0)
        net = float(tx.subtotal or 0)
        output_pos += tax
        taxable_outputs += net
        output_schedule.append(
            {
                "schedule": "output_pos",
                "document_type": "pos_sale",
                "document_number": tx.reference,
                "document_id": tx.id,
                "document_date": tx.created_at,
                "net_amount": round(net, 2),
                "tax_amount": round(tax, 2),
                "reverse_charge_tax": 0.0,
                "gross_amount": round(float(tx.total or 0), 2),
                "party_id": tx.party_id,
            }
        )

    # Prefer approved purchase invoices for input tax; fall back to POs.
    pi_stmt = select(m.PurchaseInvoice).where(
        m.PurchaseInvoice.tenant_id == tenant_id,
        m.PurchaseInvoice.status.in_(["unpaid", "partial", "paid", "overdue"]),
    )
    if from_date:
        pi_stmt = pi_stmt.where(m.PurchaseInvoice.invoice_date >= from_date)
    if to_date:
        pi_stmt = pi_stmt.where(m.PurchaseInvoice.invoice_date <= to_date)
    purchase_invoices = (await db.execute(pi_stmt)).scalars().all()

    input_schedule = []
    input_tax = 0.0
    taxable_inputs = 0.0
    purchase_reverse_charge = 0.0
    input_source = "purchase_invoices"
    if purchase_invoices:
        for inv in purchase_invoices:
            tax = float(inv.tax_amount or 0)
            rc = float(getattr(inv, "reverse_charge_tax", 0) or 0)
            net = float(inv.subtotal or 0)
            # Supplier-charged input + self-assessed RC input (claimable).
            input_tax += tax + rc
            purchase_reverse_charge += rc
            taxable_inputs += net
            input_schedule.append(
                {
                    "schedule": "input_purchase_invoices",
                    "document_type": "purchase_invoice",
                    "document_number": inv.invoice_number,
                    "document_id": inv.id,
                    "document_date": inv.invoice_date or inv.created_at,
                    "supplier_invoice_number": inv.supplier_invoice_number,
                    "net_amount": round(net, 2),
                    "tax_amount": round(tax, 2),
                    "reverse_charge_tax": round(rc, 2),
                    "is_reverse_charge": bool(getattr(inv, "is_reverse_charge", False)),
                    "gross_amount": round(float(inv.total_amount or 0), 2),
                    "party_id": inv.supplier_id,
                }
            )
    else:
        input_source = "purchase_orders"
        po_stmt = select(m.PurchaseOrder).where(
            m.PurchaseOrder.tenant_id == tenant_id,
            m.PurchaseOrder.status.in_(["received", "partial", "sent", "closed"]),
        )
        if from_date:
            po_stmt = po_stmt.where(m.PurchaseOrder.created_at >= from_date)
        if to_date:
            po_stmt = po_stmt.where(m.PurchaseOrder.created_at <= to_date)
        orders = (await db.execute(po_stmt)).scalars().all()
        for po in orders:
            tax = float(po.tax_amount or 0)
            net = float(po.subtotal or 0)
            input_tax += tax
            taxable_inputs += net
            input_schedule.append(
                {
                    "schedule": "input_purchase_orders",
                    "document_type": "purchase_order",
                    "document_number": po.po_number,
                    "document_id": po.id,
                    "document_date": po.created_at,
                    "net_amount": round(net, 2),
                    "tax_amount": round(tax, 2),
                    "gross_amount": round(float(po.total_amount or 0), 2),
                    "party_id": po.supplier_id,
                }
            )

    purchase_reverse_charge = round(purchase_reverse_charge, 2)
    # Sales RC is seller memo; purchase RC is buyer self-assess (also claimable input).
    reverse_charge_tax = round(reverse_charge_tax + purchase_reverse_charge, 2)
    # Include purchase RC in output tax so self-assess + matching input nets to zero.
    output_tax = round(output_invoices + output_pos + purchase_reverse_charge, 2)
    input_tax = round(input_tax, 2)
    net = round(output_tax - input_tax, 2)
    taxable_outputs = round(taxable_outputs, 2)
    taxable_inputs = round(taxable_inputs, 2)

    filing_boxes = [
        {
            "box": "1",
            "code": "taxable_outputs_net",
            "label": "Taxable outputs (net)",
            "amount": taxable_outputs,
        },
        {
            "box": "2",
            "code": "output_tax",
            "label": "Output tax due",
            "amount": output_tax,
        },
        {
            "box": "2a",
            "code": "reverse_charge_tax",
            "label": "Reverse charge (memo / self-assess)",
            "amount": reverse_charge_tax,
        },
        {
            "box": "3",
            "code": "taxable_inputs_net",
            "label": "Taxable inputs (net)",
            "amount": taxable_inputs,
        },
        {
            "box": "4",
            "code": "input_tax",
            "label": "Input tax claimable",
            "amount": input_tax,
        },
        {
            "box": "5",
            "code": "net_tax_payable",
            "label": "Net tax payable/(refundable)",
            "amount": net,
        },
    ]

    period = {
        "from_date": from_date.isoformat() if isinstance(from_date, datetime) else from_date,
        "to_date": to_date.isoformat() if isinstance(to_date, datetime) else to_date,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    return {
        "period": period,
        "from_date": from_date,
        "to_date": to_date,
        "output_tax": output_tax,
        "output_tax_invoices": round(output_invoices, 2),
        "output_tax_pos": round(output_pos, 2),
        "reverse_charge_tax": reverse_charge_tax,
        "input_tax": input_tax,
        "input_tax_source": input_source,
        "net_tax_payable": net,
        "invoice_count": len(invoices),
        "pos_sale_count": len(pos_sales),
        "purchase_count": len(input_schedule),
        "purchase_order_count": len(input_schedule) if input_source == "purchase_orders" else 0,
        "filing_boxes": {
            "taxable_outputs_net": taxable_outputs,
            "output_tax": output_tax,
            "reverse_charge_tax": reverse_charge_tax,
            "taxable_inputs_net": taxable_inputs,
            "input_tax": input_tax,
            "net_tax_payable": net,
            "boxes": filing_boxes,
        },
        "schedules": {
            "output": output_schedule,
            "input": input_schedule,
        },
        "lines": [
            *[
                {
                    "section": "filing_box",
                    "box": b["box"],
                    "code": b["code"],
                    "label": b["label"],
                    "amount": b["amount"],
                }
                for b in filing_boxes
            ],
            *output_schedule,
            *input_schedule,
        ],
    }
