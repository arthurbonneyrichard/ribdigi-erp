"""Tax rate helpers, calculation, and period reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

SUPPLY_CLASSES = frozenset({"standard", "zero_rated", "exempt"})
TAX_TYPES = frozenset({"vat", "gst", "sales_tax", "custom"})
PRICING_MODES = frozenset({"exclusive", "inclusive"})


def normalize_tax_type(value: str | None, *, default: str = "vat") -> str:
    # Defense in depth: TaxCreate/Update Literals reject blank/unknown with 422
    # before create/patch. Empty used to store as-is / omit → vat.
    text = (value or default).strip().lower().replace("-", "_").replace(" ", "_")
    if text not in TAX_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"tax_type must be one of: {', '.join(sorted(TAX_TYPES))}",
        )
    return text


def normalize_pricing_mode(value: str | None, *, default: str = "exclusive") -> str:
    # Defense in depth: schema Literal rejects blank/unknown with 422 first.
    # compute_tax_breakdown used to treat any non-inclusive string as exclusive.
    text = (value or default).strip().lower()
    if text not in PRICING_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"pricing_mode must be one of: {', '.join(sorted(PRICING_MODES))}",
        )
    return text


def normalize_supply_class(
    value: str | None,
    *,
    tax_exempt: bool | None = None,
) -> str:
    """Return standard | zero_rated | exempt."""
    text = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "zero": "zero_rated",
        "zerorated": "zero_rated",
        "zero_rate": "zero_rated",
        "exempted": "exempt",
        "non_taxable": "exempt",
        "nontaxable": "exempt",
    }
    text = aliases.get(text, text)
    if text in SUPPLY_CLASSES:
        return text
    if tax_exempt:
        return "exempt"
    return "standard"


def product_supply_class(product: m.Product) -> str:
    raw = getattr(product, "tax_supply_class", None)
    return normalize_supply_class(raw, tax_exempt=bool(getattr(product, "tax_exempt", False)))


def sync_product_tax_flags(product: m.Product, *, supply_class: str | None = None, tax_exempt: bool | None = None) -> str:
    """Keep tax_supply_class and tax_exempt aligned; return normalized class."""
    if supply_class is not None:
        cls = normalize_supply_class(supply_class, tax_exempt=tax_exempt)
    elif tax_exempt is not None:
        cls = "exempt" if tax_exempt else normalize_supply_class(
            getattr(product, "tax_supply_class", None), tax_exempt=False
        )
        if not tax_exempt and cls == "exempt":
            cls = "standard"
    else:
        cls = product_supply_class(product)
    product.tax_supply_class = cls
    product.tax_exempt = cls == "exempt"
    return cls


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
    mode = normalize_pricing_mode(pricing_mode)
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
    supply_class: str = "standard"

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


async def update_tax_rate(
    db: AsyncSession,
    *,
    tenant_id: str,
    rate_id: str,
    name: str | None = None,
    rate: float | None = None,
    tax_type: str | None = None,
    pricing_mode: str | None = None,
    components: list[dict] | None = None,
    clear_components: bool = False,
    is_reverse_charge: bool | None = None,
    is_active: bool | None = None,
) -> m.TaxRate:
    row = await get_tax_rate(db, tenant_id, rate_id)
    if name is not None:
        name = name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        row.name = name
    if rate is not None:
        row.rate = float(rate)
    if tax_type is not None:
        row.tax_type = normalize_tax_type(tax_type)
    if pricing_mode is not None:
        row.pricing_mode = normalize_pricing_mode(pricing_mode)
    if clear_components:
        row.components = None
    elif components is not None:
        comps = normalize_components(components)
        if comps:
            row.components = comps
            row.rate = effective_rate_from_components(comps, row.rate or 0)
        else:
            row.components = None
    if is_reverse_charge is not None:
        row.is_reverse_charge = bool(is_reverse_charge)
    if is_active is not None:
        row.is_active = bool(is_active)
        if not row.is_active:
            # Soft-deactivate clears default so resolution falls through to another active default.
            row.is_default = False
    await db.flush()
    return row


def tax_spec_from_rate(rate: m.TaxRate, *, supply_class: str = "standard") -> TaxSpec:
    comps = normalize_components(rate.components) if rate.components else None
    return TaxSpec(
        rate_pct=float(rate.rate),
        pricing_mode=rate.pricing_mode or "exclusive",
        components=tuple(comps) if comps else None,
        is_reverse_charge=bool(rate.is_reverse_charge),
        tax_rate_id=rate.id,
        supply_class=normalize_supply_class(supply_class),
    )


async def resolve_category_tax_rate(
    db: AsyncSession,
    tenant_id: str,
    category_id: str | None,
    *,
    max_depth: int = 16,
) -> m.TaxRate | None:
    """Walk category → parent until an active tax_rate_id is found (nearest wins)."""
    seen: set[str] = set()
    current_id = category_id
    depth = 0
    while current_id and depth < max_depth:
        if current_id in seen:
            break
        seen.add(current_id)
        cat = (
            await db.execute(
                select(m.ProductCategory).where(
                    m.ProductCategory.id == current_id,
                    m.ProductCategory.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not cat:
            break
        if cat.tax_rate_id:
            try:
                rate = await get_tax_rate(db, tenant_id, cat.tax_rate_id)
            except HTTPException:
                rate = None
            if rate is not None and rate.is_active:
                return rate
        current_id = cat.parent_id
        depth += 1
    return None


async def resolve_product_tax(
    db: AsyncSession,
    tenant_id: str,
    product: m.Product,
    explicit_rate: float | None = None,
) -> TaxSpec:
    """Resolve full tax spec for a product line.

    Order: supply class exempt/zero → explicit line rate → product.tax_rate_id →
    category (walk parents) → tenant default → 0%.
    """
    supply = product_supply_class(product)
    if supply in {"exempt", "zero_rated"}:
        return TaxSpec(rate_pct=0.0, pricing_mode="exclusive", supply_class=supply)
    if explicit_rate is not None:
        default = await get_default_tax_rate(db, tenant_id)
        mode = default.pricing_mode if default else "exclusive"
        # Explicit override uses single-rate path (no compound legs).
        return TaxSpec(
            rate_pct=float(explicit_rate),
            pricing_mode=mode,
            supply_class="standard",
        )
    if product.tax_rate_id:
        rate = await get_tax_rate(db, tenant_id, product.tax_rate_id)
        if rate.is_active:
            return tax_spec_from_rate(rate, supply_class="standard")
    category_rate = await resolve_category_tax_rate(
        db, tenant_id, getattr(product, "category_id", None)
    )
    if category_rate:
        return tax_spec_from_rate(category_rate, supply_class="standard")
    default = await get_default_tax_rate(db, tenant_id)
    if default:
        return tax_spec_from_rate(default, supply_class="standard")
    return TaxSpec(rate_pct=0.0, pricing_mode="exclusive", supply_class="standard")


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
    store_id: str | None = None,
) -> dict:
    """Summary VAT/GST output vs input tax for a period."""
    pack = await tax_filing_pack(
        db, tenant_id, from_date=from_date, to_date=to_date, store_id=store_id
    )
    return {
        "from_date": from_date,
        "to_date": to_date,
        "store_id": pack.get("store_id"),
        "store_name": pack.get("store_name"),
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
    store_id: str | None = None,
) -> dict:
    """Jurisdiction-neutral VAT/GST filing pack: boxes + detailed schedules for export.

    Optional ``store_id`` scopes:
    - output invoices by ``SalesInvoice.store_id``
    - POS by session store
    - input PIs/POs by PO/GRN warehouse → store
    """
    from fastapi import HTTPException

    store_name = None
    warehouse_ids: list[str] | None = None
    if store_id:
        store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.tenant_id == tenant_id,
                    m.Store.id == store_id,
                )
            )
        ).scalar_one_or_none()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found")
        store_id = store.id
        store_name = store.name
        warehouse_ids = [
            w.id
            for w in (
                await db.execute(
                    select(m.Warehouse).where(
                        m.Warehouse.tenant_id == tenant_id,
                        m.Warehouse.store_id == store_id,
                    )
                )
            ).scalars().all()
        ]

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.status.in_(["posted", "sent", "partial", "paid", "overdue"]),
    )
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    if store_id:
        inv_stmt = inv_stmt.where(m.SalesInvoice.store_id == store_id)
    invoices = (await db.execute(inv_stmt)).scalars().all()

    output_schedule = []
    output_invoices = 0.0
    reverse_charge_tax = 0.0
    standard_outputs = 0.0
    zero_rated_outputs = 0.0
    exempt_outputs = 0.0

    def _bump_supply(cls: str, net: float) -> None:
        nonlocal standard_outputs, zero_rated_outputs, exempt_outputs
        kind = normalize_supply_class(cls)
        if kind == "zero_rated":
            zero_rated_outputs += net
        elif kind == "exempt":
            exempt_outputs += net
        else:
            standard_outputs += net

    for inv in invoices:
        tax = float(inv.tax_amount or 0)
        rc = float(getattr(inv, "reverse_charge_tax", 0) or 0)
        net = float(inv.subtotal or 0)
        output_invoices += tax
        reverse_charge_tax += rc
        items = (
            await db.execute(
                select(m.SalesInvoiceItem).where(
                    m.SalesInvoiceItem.tenant_id == tenant_id,
                    m.SalesInvoiceItem.sales_invoice_id == inv.id,
                )
            )
        ).scalars().all()
        if items:
            for item in items:
                line_net = float(getattr(item, "line_subtotal", None) or 0)
                if line_net <= 0:
                    # Legacy rows: approximate net from qty * price - discount
                    line_net = max(
                        float(item.quantity or 0) * float(item.unit_price or 0)
                        - float(item.discount or 0),
                        0,
                    )
                _bump_supply(getattr(item, "tax_supply_class", None) or "standard", line_net)
        else:
            _bump_supply("standard", net)
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
                "store_id": inv.store_id,
            }
        )

    if store_id:
        pos_stmt = (
            select(m.Transaction)
            .join(m.PosSession, m.PosSession.id == m.Transaction.session_id)
            .where(
                m.Transaction.tenant_id == tenant_id,
                m.Transaction.tx_type == "pos_sale",
                m.PosSession.store_id == store_id,
            )
        )
    else:
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
        payload_items = list((tx.payload or {}).get("items") or [])
        if payload_items:
            for item in payload_items:
                if not isinstance(item, dict):
                    continue
                line_net = float(item.get("line_subtotal") or 0)
                _bump_supply(item.get("tax_supply_class") or "standard", line_net)
        else:
            _bump_supply("standard", net)
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
                "store_id": store_id,
            }
        )
    taxable_outputs = standard_outputs

    # Prefer approved purchase invoices for input tax; fall back to POs.
    pi_stmt = select(m.PurchaseInvoice).where(
        m.PurchaseInvoice.tenant_id == tenant_id,
        m.PurchaseInvoice.status.in_(["unpaid", "partial", "paid", "overdue"]),
    )
    if from_date:
        pi_stmt = pi_stmt.where(m.PurchaseInvoice.invoice_date >= from_date)
    if to_date:
        pi_stmt = pi_stmt.where(m.PurchaseInvoice.invoice_date <= to_date)
    if store_id is not None:
        if not warehouse_ids:
            pi_stmt = pi_stmt.where(m.PurchaseInvoice.id == None)  # noqa: E711
        else:
            pi_stmt = (
                pi_stmt.outerjoin(
                    m.PurchaseOrder,
                    m.PurchaseOrder.id == m.PurchaseInvoice.purchase_order_id,
                )
                .outerjoin(
                    m.GoodsReceipt,
                    m.GoodsReceipt.id == m.PurchaseInvoice.goods_receipt_id,
                )
                .where(
                    or_(
                        m.PurchaseOrder.warehouse_id.in_(warehouse_ids),
                        m.GoodsReceipt.warehouse_id.in_(warehouse_ids),
                    )
                )
            )
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
        if store_id is not None:
            if not warehouse_ids:
                po_stmt = po_stmt.where(m.PurchaseOrder.id == None)  # noqa: E711
            else:
                po_stmt = po_stmt.where(m.PurchaseOrder.warehouse_id.in_(warehouse_ids))
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
    zero_rated_outputs = round(zero_rated_outputs, 2)
    exempt_outputs = round(exempt_outputs, 2)
    taxable_inputs = round(taxable_inputs, 2)

    filing_boxes = [
        {
            "box": "1",
            "code": "taxable_outputs_net",
            "label": "Standard-rated taxable outputs (net)",
            "amount": taxable_outputs,
        },
        {
            "box": "1a",
            "code": "zero_rated_outputs_net",
            "label": "Zero-rated outputs (net)",
            "amount": zero_rated_outputs,
        },
        {
            "box": "1b",
            "code": "exempt_outputs_net",
            "label": "Exempt outputs (net)",
            "amount": exempt_outputs,
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
        "store_id": store_id,
        "store_name": store_name,
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
            "zero_rated_outputs_net": zero_rated_outputs,
            "exempt_outputs_net": exempt_outputs,
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
