"""Purchase order and GRN business logic."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import apply_stock_change
from app.tax import resolve_product_tax
from app.credit import default_due_date, party_terms_days
from app.doc_numbers import (
    next_debit_note_number,
    next_grn_number,
    next_purchase_invoice_number,
    next_purchase_order_number,
    next_purchase_return_number,
    next_supplier_payment_number,
)


async def _purchase_line_tax(
    db: AsyncSession,
    tenant_id: str,
    product: m.Product,
    item: dict,
) -> tuple[float, float, float, float, list | None]:
    """Resolve purchase line tax (BR-12.2).

    Returns (line_subtotal, line_tax, line_total, rate_pct, tax_components).
    ``tax_rate`` omitted/None → product → category → tenant default;
    explicit value (including 0) wins.
    """
    explicit = item.get("tax_rate")
    if explicit is not None:
        spec = await resolve_product_tax(
            db, tenant_id, product, explicit_rate=float(explicit)
        )
    else:
        spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=None)
    qty = float(item.get("quantity") or 0)
    unit = float(item.get("unit_price") or 0)
    breakdown = spec.compute_breakdown(qty * unit)
    comps = list(breakdown.get("components") or []) or None
    return (
        float(breakdown["net"]),
        float(breakdown["tax"]),
        float(breakdown["gross"]),
        float(spec.rate_pct),
        comps,
    )

PO_EDITABLE = {"draft"}
PO_AMENDABLE = frozenset({"draft", "sent"})
PO_RECEIVABLE = {"sent", "partially_received"}
PURCHASE_RETURN_REASONS = frozenset({"damaged", "wrong_item", "expiry", "quality", "other"})
PURCHASE_INVOICE_OPEN = frozenset({"unpaid", "partial", "overdue"})


def purchase_invoice_status(
    total: float,
    paid: float,
    due_date: datetime | None = None,
    *,
    as_of: datetime | None = None,
) -> str:
    if paid + 1e-9 >= total:
        return "paid"
    base = "partial" if paid > 0 else "unpaid"
    now = as_of or datetime.utcnow()
    if due_date and now.date() > due_date.date():
        return "overdue"
    return base


async def refresh_overdue_purchase_invoices(
    db: AsyncSession, tenant_id: str, *, as_of: datetime | None = None
) -> int:
    """Flip open purchase invoices to overdue (and refresh unpaid/partial) when past due."""
    rows = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.tenant_id == tenant_id,
                m.PurchaseInvoice.status.in_(list(PURCHASE_INVOICE_OPEN)),
            )
        )
    ).scalars().all()
    changed = 0
    for inv in rows:
        before = inv.status
        new_status = purchase_invoice_status(
            float(inv.total_amount),
            float(inv.paid_amount or 0),
            inv.due_date,
            as_of=as_of,
        )
        if new_status != before:
            inv.status = new_status
            inv.updated_at = datetime.utcnow()
            changed += 1
    if changed:
        await db.flush()
    return changed


def derive_po_status(items: list[m.PurchaseOrderItem]) -> str:
    if not items:
        return "sent"
    fully = all(float(i.received_qty or 0) >= float(i.quantity or 0) for i in items)
    any_received = any(float(i.received_qty or 0) > 0 for i in items)
    if fully:
        return "received"
    if any_received:
        return "partially_received"
    return "sent"


async def get_supplier(db: AsyncSession, tenant_id: str, supplier_id: str) -> m.Party:
    supplier = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == supplier_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


async def require_active_supplier(db: AsyncSession, tenant_id: str, supplier_id: str) -> m.Party:
    """Resolve supplier for new purchasing documents; inactive suppliers cannot be newly assigned."""
    supplier = await get_supplier(db, tenant_id, supplier_id)
    status = (getattr(supplier, "status", None) or "active").strip().lower()
    if status != "active":
        raise HTTPException(status_code=400, detail="Supplier is inactive")
    return supplier


async def get_po(db: AsyncSession, tenant_id: str, po_id: str) -> m.PurchaseOrder:
    po = (
        await db.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.id == po_id,
                m.PurchaseOrder.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


async def list_po_items(db: AsyncSession, tenant_id: str, po_id: str) -> list[m.PurchaseOrderItem]:
    return (
        await db.execute(
            select(m.PurchaseOrderItem).where(
                m.PurchaseOrderItem.tenant_id == tenant_id,
                m.PurchaseOrderItem.purchase_order_id == po_id,
            )
        )
    ).scalars().all()


def _po_items_snapshot(items: list[m.PurchaseOrderItem]) -> list[dict]:
    return [
        {
            "product_id": i.product_id,
            "quantity": float(i.quantity),
            "unit_id": i.unit_id,
            "unit_price": float(i.unit_price),
            "tax_rate": float(i.tax_rate),
            "discount": float(getattr(i, "discount", 0) or 0),
            "line_total": float(i.line_total),
        }
        for i in items
    ]


def _po_line_discount(qty: float, unit_price: float, line_total: float, discount: float) -> tuple[float, float]:
    """Tax-before-discount (match PI). Returns (discount, discounted line_total)."""
    disc = float(discount or 0)
    if disc < 0:
        raise HTTPException(status_code=400, detail="discount must be >= 0")
    merch = float(qty) * float(unit_price)
    if disc > merch + 1e-9:
        raise HTTPException(
            status_code=400,
            detail="discount cannot exceed quantity × unit_price",
        )
    return disc, max(float(line_total) - disc, 0)


def _po_header_snapshot(po: m.PurchaseOrder) -> dict:
    return {
        "notes": po.notes,
        "delivery_address": getattr(po, "delivery_address", None),
        "due_date": po.due_date.isoformat() if po.due_date else None,
        "subtotal": float(po.subtotal),
        "tax_amount": float(po.tax_amount),
        "total_amount": float(po.total_amount),
        "revision_no": int(getattr(po, "revision_no", 0) or 0),
    }


async def list_po_amendments(
    db: AsyncSession, tenant_id: str, po_id: str
) -> list[m.PurchaseOrderAmendment]:
    return list(
        (
            await db.execute(
                select(m.PurchaseOrderAmendment)
                .where(
                    m.PurchaseOrderAmendment.tenant_id == tenant_id,
                    m.PurchaseOrderAmendment.purchase_order_id == po_id,
                )
                .order_by(m.PurchaseOrderAmendment.revision_no.asc())
            )
        )
        .scalars()
        .all()
    )


def serialize_po_amendment(row: m.PurchaseOrderAmendment) -> dict:
    return {
        "id": row.id,
        "purchase_order_id": row.purchase_order_id,
        "revision_no": int(row.revision_no),
        "reason": row.reason,
        "actor_id": row.actor_id,
        "changes": row.changes,
        "notified_supplier": bool(row.notified_supplier),
        "emailed_to": row.emailed_to,
        "created_at": row.created_at,
    }


async def serialize_po(db: AsyncSession, po: m.PurchaseOrder) -> dict:
    items = await list_po_items(db, po.tenant_id, po.id)
    amendments = await list_po_amendments(db, po.tenant_id, po.id)
    has_receipts = any(float(i.received_qty or 0) > 0 for i in items)
    can_amend = po.status in PO_AMENDABLE and not has_receipts
    can_cancel = po.status not in {"received", "cancelled"} and not has_receipts
    return {
        "id": po.id,
        "po_number": po.po_number,
        "supplier_id": po.supplier_id,
        "warehouse_id": po.warehouse_id,
        "status": po.status,
        "subtotal": float(po.subtotal),
        "tax_amount": float(po.tax_amount),
        "total_amount": float(po.total_amount),
        "paid_amount": float(po.paid_amount or 0),
        "balance_due": max(float(po.total_amount) - float(po.paid_amount or 0), 0),
        "due_date": po.due_date,
        "notes": po.notes,
        "delivery_address": getattr(po, "delivery_address", None),
        "emailed_at": po.emailed_at,
        "emailed_to": po.emailed_to,
        "revision_no": int(getattr(po, "revision_no", 0) or 0),
        "can_amend": can_amend,
        "can_cancel": can_cancel,
        "amendments": [serialize_po_amendment(a) for a in amendments],
        "created_at": po.created_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "quantity": float(i.quantity),
                "received_qty": float(i.received_qty),
                "unit_id": i.unit_id,
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(getattr(i, "discount", 0) or 0),
                "line_total": float(i.line_total),
                "outstanding_qty": max(float(i.quantity) - float(i.received_qty or 0), 0),
            }
            for i in items
        ],
    }


async def create_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    supplier_id: str,
    items: list[dict],
    warehouse_id: str | None = None,
    notes: str | None = None,
    delivery_address: str | None = None,
) -> m.PurchaseOrder:
    if not items:
        raise HTTPException(status_code=400, detail="Purchase order requires at least one line item")
    await require_active_supplier(db, tenant_id, supplier_id)
    if warehouse_id:
        from app.warehouses import require_active_warehouse

        await require_active_warehouse(db, tenant_id, warehouse_id)

    from app.uom import resolve_line_unit

    subtotal = 0.0
    tax_total = 0.0
    discount_total = 0.0
    prepared: list[tuple[dict, float]] = []
    for item in items:
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == item["product_id"],
                    m.Product.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {item['product_id']}")
        if not product.is_active:
            raise HTTPException(status_code=400, detail=f"Product is inactive: {product.sku}")
        unit_id, qty, _qty_base = await resolve_line_unit(
            db,
            tenant_id=tenant_id,
            product=product,
            unit_id=item.get("unit_id"),
            quantity=float(item["quantity"]),
        )
        unit_price = float(item.get("unit_price") or 0)
        line_item = {**item, "quantity": qty, "unit_price": unit_price}
        line_sub, line_tax, line_total, rate_pct, _comps = await _purchase_line_tax(
            db, tenant_id, product, line_item
        )
        disc, line_total = _po_line_discount(qty, unit_price, line_total, item.get("discount") or 0)
        subtotal += line_sub
        tax_total += line_tax
        discount_total += disc
        prepared.append(
            (
                {
                    **item,
                    "product_id": product.id,
                    "quantity": qty,
                    "unit_id": unit_id,
                    "unit_price": unit_price,
                    "tax_rate": rate_pct,
                    "discount": disc,
                },
                line_total,
            )
        )

    po = m.PurchaseOrder(
        tenant_id=tenant_id,
        po_number=await next_purchase_order_number(db, tenant_id),
        supplier_id=supplier_id,
        warehouse_id=warehouse_id,
        status="draft",
        subtotal=round(subtotal, 2),
        tax_amount=round(tax_total, 2),
        total_amount=round(max(subtotal + tax_total - discount_total, 0), 2),
        notes=notes,
        delivery_address=(delivery_address or "").strip() or None,
        created_by=user_id,
    )
    db.add(po)
    await db.flush()

    for item, line_total in prepared:
        db.add(
            m.PurchaseOrderItem(
                tenant_id=tenant_id,
                purchase_order_id=po.id,
                product_id=item["product_id"],
                quantity=item["quantity"],
                received_qty=0,
                unit_id=item.get("unit_id"),
                unit_price=item.get("unit_price", 0),
                tax_rate=item.get("tax_rate", 0),
                discount=item.get("discount", 0),
                line_total=line_total,
            )
        )

    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="po_created",
            entity="purchase_order",
            entity_id=po.id,
            details={"po_number": po.po_number, "total": float(po.total_amount)},
        )
    )
    return po


async def send_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    po_id: str,
    to: str | None = None,
) -> tuple[m.PurchaseOrder, dict]:
    """Email PO to supplier, then mark status=sent. Delivery must succeed first."""
    from app import emailer

    po = await get_po(db, tenant_id, po_id)
    if po.status not in {"draft", "sent"}:
        raise HTTPException(status_code=409, detail=f"Cannot send PO in status {po.status}")
    items = await list_po_items(db, tenant_id, po.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot send empty purchase order")

    supplier = await get_supplier(db, tenant_id, po.supplier_id)
    recipient = (to or supplier.email or "").strip()
    if not recipient:
        raise HTTPException(
            status_code=400,
            detail="Supplier has no email; set supplier email or pass to= override",
        )

    tenant = await db.get(m.Tenant, tenant_id)
    company_name = tenant.company_name if tenant else "RIBDIGI ERP"
    currency = (tenant.currency if tenant else None) or "GHS"
    payload = await serialize_po(db, po)

    result = await emailer.send_purchase_order_email(
        to=recipient,
        company_name=company_name,
        currency=currency,
        supplier_name=supplier.name,
        purchase_order=payload,
        tenant=tenant,
    )
    if not result.sent:
        if result.mode == "disabled":
            raise HTTPException(status_code=503, detail="Email delivery is disabled")
        raise HTTPException(status_code=502, detail=result.error or "Email send failed")

    now = datetime.utcnow()
    po.status = "sent"
    po.due_date = po.due_date or default_due_date(terms_days=party_terms_days(supplier))
    po.emailed_at = now
    po.emailed_to = recipient
    po.updated_at = now
    await db.flush()
    delivery = {
        "sent": result.sent,
        "mode": result.mode,
        "to": recipient,
        "emailed_at": now.isoformat(),
        "po_number": po.po_number,
    }
    return po, delivery


async def cancel_purchase_order(db: AsyncSession, *, tenant_id: str, user_id: str, po_id: str) -> m.PurchaseOrder:
    po = await get_po(db, tenant_id, po_id)
    if po.status in {"received", "cancelled"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel PO in status {po.status}")
    items = await list_po_items(db, tenant_id, po.id)
    if any(float(i.received_qty or 0) > 0 for i in items):
        raise HTTPException(status_code=409, detail="Cannot cancel PO after goods have been received")
    po.status = "cancelled"
    po.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="po_cancelled",
            entity="purchase_order",
            entity_id=po.id,
            details={"po_number": po.po_number},
        )
    )
    return po


async def amend_purchase_order(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    po_id: str,
    items: list[dict] | None = None,
    notes: str | None = None,
    delivery_address: str | None = None,
    due_date: datetime | None = None,
    clear_due_date: bool = False,
    reason: str | None = None,
    notify_supplier: bool = False,
    notify_to: str | None = None,
) -> tuple[m.PurchaseOrder, m.PurchaseOrderAmendment, dict | None]:
    """Amend draft/sent PO lines/notes/delivery_address/due_date; record revision history.

    Blocked after any receipt. Optional supplier notify fails closed (rollback amend).
    """
    from app import emailer

    po = await get_po(db, tenant_id, po_id)
    if po.status not in PO_AMENDABLE:
        raise HTTPException(status_code=409, detail=f"Cannot amend PO in status {po.status}")
    existing_items = await list_po_items(db, tenant_id, po.id)
    if any(float(i.received_qty or 0) > 0 for i in existing_items):
        raise HTTPException(status_code=409, detail="Cannot amend PO after goods have been received")

    before = {
        "header": _po_header_snapshot(po),
        "items": _po_items_snapshot(existing_items),
    }

    header_touched = (
        notes is not None
        or delivery_address is not None
        or due_date is not None
        or clear_due_date
    )
    items_touched = items is not None
    if not header_touched and not items_touched:
        raise HTTPException(
            status_code=400,
            detail="Amend requires items and/or notes/delivery_address/due_date changes",
        )

    if items_touched:
        if not items:
            raise HTTPException(status_code=400, detail="Amended purchase order requires at least one line")
        from app.uom import resolve_line_unit

        subtotal = 0.0
        tax_total = 0.0
        discount_total = 0.0
        prepared: list[tuple[dict, float]] = []
        for item in items:
            product = (
                await db.execute(
                    select(m.Product).where(
                        m.Product.id == item["product_id"],
                        m.Product.tenant_id == tenant_id,
                    )
                )
            ).scalar_one_or_none()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product not found: {item['product_id']}")
            if not product.is_active:
                raise HTTPException(status_code=400, detail=f"Product is inactive: {product.sku}")
            unit_id, qty, _qty_base = await resolve_line_unit(
                db,
                tenant_id=tenant_id,
                product=product,
                unit_id=item.get("unit_id"),
                quantity=float(item["quantity"]),
            )
            unit_price = float(item.get("unit_price") or 0)
            line_item = {
                **item,
                "quantity": qty,
                "unit_price": unit_price,
            }
            line_sub, line_tax, line_total, rate_pct, _comps = await _purchase_line_tax(
                db, tenant_id, product, line_item
            )
            disc, line_total = _po_line_discount(qty, unit_price, line_total, item.get("discount") or 0)
            subtotal += line_sub
            tax_total += line_tax
            discount_total += disc
            prepared.append(
                (
                    {
                        "product_id": product.id,
                        "quantity": qty,
                        "unit_id": unit_id,
                        "unit_price": unit_price,
                        "tax_rate": rate_pct,
                        "discount": disc,
                    },
                    line_total,
                )
            )
        for old in existing_items:
            await db.delete(old)
        await db.flush()
        for item, line_total in prepared:
            db.add(
                m.PurchaseOrderItem(
                    tenant_id=tenant_id,
                    purchase_order_id=po.id,
                    product_id=item["product_id"],
                    quantity=item["quantity"],
                    unit_id=item.get("unit_id"),
                    received_qty=0,
                    unit_price=item["unit_price"],
                    tax_rate=item["tax_rate"],
                    discount=item.get("discount", 0),
                    line_total=line_total,
                )
            )
        po.subtotal = round(subtotal, 2)
        po.tax_amount = round(tax_total, 2)
        po.total_amount = round(max(subtotal + tax_total - discount_total, 0), 2)

    if notes is not None:
        po.notes = notes
    if delivery_address is not None:
        po.delivery_address = delivery_address.strip() or None
    if clear_due_date:
        po.due_date = None
    elif due_date is not None:
        po.due_date = due_date

    new_items = await list_po_items(db, tenant_id, po.id)
    after = {
        "header": _po_header_snapshot(po),
        "items": _po_items_snapshot(new_items),
    }
    if before == after:
        raise HTTPException(status_code=400, detail="No changes detected for amendment")

    revision = int(getattr(po, "revision_no", 0) or 0) + 1
    po.revision_no = revision
    after["header"]["revision_no"] = revision
    po.updated_at = datetime.utcnow()

    delivery: dict | None = None
    emailed_to: str | None = None
    if notify_supplier:
        if po.status != "sent" and not po.emailed_at:
            raise HTTPException(
                status_code=400,
                detail="notify_supplier requires a sent/emailed purchase order",
            )
        if not new_items:
            raise HTTPException(status_code=400, detail="Cannot notify supplier for empty purchase order")
        supplier = await get_supplier(db, tenant_id, po.supplier_id)
        recipient = (notify_to or supplier.email or "").strip()
        if not recipient:
            raise HTTPException(
                status_code=400,
                detail="Supplier has no email; set supplier email or pass to= override",
            )
        tenant = await db.get(m.Tenant, tenant_id)
        company_name = tenant.company_name if tenant else "RIBDIGI ERP"
        currency = (tenant.currency if tenant else None) or "GHS"
        # Flush mutation before serializing for email body
        await db.flush()
        payload = await serialize_po(db, po)
        result = await emailer.send_purchase_order_email(
            to=recipient,
            company_name=company_name,
            currency=currency,
            supplier_name=supplier.name,
            purchase_order=payload,
            amended=True,
            tenant=tenant,
        )
        if not result.sent:
            if result.mode == "disabled":
                raise HTTPException(status_code=503, detail="Email delivery is disabled")
            raise HTTPException(status_code=502, detail=result.error or "Email send failed")
        now = datetime.utcnow()
        po.emailed_at = now
        po.emailed_to = recipient
        emailed_to = recipient
        delivery = {
            "sent": result.sent,
            "mode": result.mode,
            "to": recipient,
            "emailed_at": now.isoformat(),
            "po_number": po.po_number,
            "amended": True,
            "revision_no": revision,
        }

    amendment = m.PurchaseOrderAmendment(
        tenant_id=tenant_id,
        purchase_order_id=po.id,
        revision_no=revision,
        reason=(reason or "").strip() or None,
        actor_id=user_id,
        changes={"before": before, "after": after},
        notified_supplier=bool(notify_supplier),
        emailed_to=emailed_to,
    )
    db.add(amendment)
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="po_amended",
            entity="purchase_order",
            entity_id=po.id,
            details={
                "po_number": po.po_number,
                "revision_no": revision,
                "notified_supplier": bool(notify_supplier),
                "reason": amendment.reason,
            },
        )
    )
    await db.flush()
    return po, amendment, delivery


async def create_grn(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    purchase_order_id: str,
    items: list[dict],
    warehouse_id: str | None = None,
    notes: str | None = None,
    post_supplier_balance: bool = True,
) -> m.GoodsReceipt:
    if not items:
        raise HTTPException(status_code=400, detail="GRN requires at least one line item")

    po = await get_po(db, tenant_id, purchase_order_id)
    if po.status not in PO_RECEIVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot receive against PO in status {po.status}")

    po_items = {i.id: i for i in await list_po_items(db, tenant_id, po.id)}
    accepted_value = 0.0

    grn = m.GoodsReceipt(
        tenant_id=tenant_id,
        grn_number=await next_grn_number(db, tenant_id),
        purchase_order_id=po.id,
        supplier_id=po.supplier_id,
        warehouse_id=warehouse_id or po.warehouse_id,
        status="posted",
        notes=notes,
        created_by=user_id,
    )
    db.add(grn)
    await db.flush()

    for raw in items:
        po_item = po_items.get(raw["po_item_id"])
        if not po_item:
            raise HTTPException(status_code=400, detail=f"Invalid po_item_id: {raw['po_item_id']}")

        received_qty = float(raw.get("received_qty") or 0)
        accepted_qty = float(raw.get("accepted_qty") if raw.get("accepted_qty") is not None else received_qty)
        rejected_qty = float(raw.get("rejected_qty") or 0)
        if received_qty <= 0:
            raise HTTPException(status_code=400, detail="received_qty must be positive")
        if accepted_qty < 0 or rejected_qty < 0:
            raise HTTPException(status_code=400, detail="accepted/rejected qty cannot be negative")
        # If rejected omitted but accepted < received, treat remainder as rejected.
        if rejected_qty == 0 and accepted_qty < received_qty - 1e-9:
            rejected_qty = round(received_qty - accepted_qty, 3)
        if abs((accepted_qty + rejected_qty) - received_qty) > 1e-6:
            raise HTTPException(
                status_code=400,
                detail="accepted_qty + rejected_qty must equal received_qty",
            )
        reason = (raw.get("rejection_reason") or "").strip() or None
        if rejected_qty > 1e-9 and not reason:
            raise HTTPException(
                status_code=400,
                detail="rejection_reason is required when rejected_qty > 0",
            )
        if rejected_qty <= 1e-9:
            reason = None
            rejected_qty = 0.0

        outstanding = float(po_item.quantity) - float(po_item.received_qty or 0)
        if received_qty > outstanding + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OVER_RECEIPT",
                    "message": f"Received qty exceeds outstanding for PO item {po_item.id}",
                    "outstanding": outstanding,
                    "received_qty": received_qty,
                },
            )

        line_unit_id = po_item.unit_id
        db.add(
            m.GoodsReceiptItem(
                tenant_id=tenant_id,
                goods_receipt_id=grn.id,
                po_item_id=po_item.id,
                product_id=po_item.product_id,
                unit_id=line_unit_id,
                received_qty=received_qty,
                accepted_qty=accepted_qty,
                rejected_qty=rejected_qty,
                rejection_reason=reason,
            )
        )

        if accepted_qty > 0:
            from app.catalog import stock_in_with_batch

            batch_number = (raw.get("batch_number") or "").strip() or None
            await stock_in_with_batch(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                product_id=po_item.product_id,
                quantity=accepted_qty,
                unit_id=line_unit_id,
                notes=f"GRN {grn.grn_number}",
                warehouse_id=grn.warehouse_id,
                batch_number=batch_number,
                manufacturing_date=raw.get("manufacturing_date"),
                expiry_date=raw.get("expiry_date"),
                movement_type="stock_in",
                reference_type="grn",
                reference_id=grn.id,
            )
            line_gross = accepted_qty * float(po_item.unit_price) * (
                1 + float(po_item.tax_rate or 0) / 100.0
            )
            # Proportional share of PO line discount for partial receipts (BR-6.3)
            ordered = float(po_item.quantity or 0)
            line_disc = float(getattr(po_item, "discount", 0) or 0)
            if ordered > 1e-9 and line_disc > 0:
                line_gross -= line_disc * (accepted_qty / ordered)
            accepted_value += max(line_gross, 0)

        # Count full physical receipt (accepted + rejected) against PO outstanding;
        # only accepted qty is stocked above.
        po_item.received_qty = float(po_item.received_qty or 0) + received_qty

    updated_items = await list_po_items(db, tenant_id, po.id)
    po.status = derive_po_status(updated_items)
    po.updated_at = datetime.utcnow()

    if post_supplier_balance and accepted_value > 0:
        supplier = await get_supplier(db, tenant_id, po.supplier_id)
        supplier.balance = float(supplier.balance or 0) + accepted_value

    from app.accounting import post_grn_journal

    await post_grn_journal(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        grn=grn,
        accepted_value=accepted_value,
    )

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="purchase_received",
        title="Purchase received",
        message=f"GRN {grn.grn_number} posted against {po.po_number}. PO status: {po.status}.",
        entity_type="goods_receipt",
        entity_id=grn.id,
    )
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="grn_posted",
            entity="goods_receipt",
            entity_id=grn.id,
            details={
                "grn_number": grn.grn_number,
                "po_id": po.id,
                "po_status": po.status,
                "accepted_value": accepted_value,
            },
        )
    )
    return grn


async def serialize_grn(db: AsyncSession, grn: m.GoodsReceipt) -> dict:
    items = (
        await db.execute(
            select(m.GoodsReceiptItem).where(
                m.GoodsReceiptItem.tenant_id == grn.tenant_id,
                m.GoodsReceiptItem.goods_receipt_id == grn.id,
            )
        )
    ).scalars().all()
    movements = (
        await db.execute(
            select(m.StockMovement).where(
                m.StockMovement.tenant_id == grn.tenant_id,
                m.StockMovement.reference_type == "grn",
                m.StockMovement.reference_id == grn.id,
            )
        )
    ).scalars().all()
    batch_ids = {mv.batch_id for mv in movements if mv.batch_id}
    batches: dict[str, m.ProductBatch] = {}
    if batch_ids:
        rows = (
            await db.execute(select(m.ProductBatch).where(m.ProductBatch.id.in_(batch_ids)))
        ).scalars().all()
        batches = {b.id: b for b in rows}
    used_mv: set[str] = set()

    def _batch_fields_for(item: m.GoodsReceiptItem) -> dict:
        if float(item.accepted_qty or 0) <= 0:
            return {
                "batch_number": None,
                "manufacturing_date": None,
                "expiry_date": None,
            }
        for mv in movements:
            if mv.id in used_mv:
                continue
            if mv.product_id != item.product_id:
                continue
            used_mv.add(mv.id)
            batch = batches.get(mv.batch_id) if mv.batch_id else None
            if not batch:
                return {
                    "batch_number": None,
                    "manufacturing_date": None,
                    "expiry_date": None,
                }
            return {
                "batch_number": batch.batch_number,
                "manufacturing_date": batch.manufacturing_date,
                "expiry_date": batch.expiry_date,
            }
        return {
            "batch_number": None,
            "manufacturing_date": None,
            "expiry_date": None,
        }

    return {
        "id": grn.id,
        "grn_number": grn.grn_number,
        "purchase_order_id": grn.purchase_order_id,
        "supplier_id": grn.supplier_id,
        "warehouse_id": grn.warehouse_id,
        "status": grn.status,
        "notes": grn.notes,
        "created_at": grn.created_at,
        "items": [
            {
                "id": i.id,
                "po_item_id": i.po_item_id,
                "product_id": i.product_id,
                "unit_id": i.unit_id,
                "received_qty": float(i.received_qty),
                "accepted_qty": float(i.accepted_qty),
                "rejected_qty": float(i.rejected_qty),
                "rejection_reason": i.rejection_reason,
                **_batch_fields_for(i),
            }
            for i in items
        ],
    }


async def record_supplier_payment(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    supplier_id: str,
    amount: float,
    purchase_order_id: str | None = None,
    purchase_invoice_id: str | None = None,
    payment_method: str = "bank_transfer",
    reference: str | None = None,
    notes: str | None = None,
    cheque_number: str | None = None,
    bank_name: str | None = None,
    cheque_date: datetime | None = None,
    liquid_account_id: str | None = None,
    apply_early_discount: bool | None = None,
    currency: str | None = None,
    exchange_rate: float | None = None,
) -> m.SupplierPayment:
    amount = float(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

    supplier = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == supplier_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    tenant = (await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))).scalar_one()
    from app.credit import early_pay_settings, purchase_invoice_early_discount

    ep = early_pay_settings(tenant)
    use_discount = ep["enabled"] if apply_early_discount is None else bool(apply_early_discount)
    if use_discount and not ep["enabled"]:
        use_discount = False

    # (invoice, settlement_to_paid_amount, discount_portion) | PO-only handled separately
    invoice_allocations: list[tuple[m.PurchaseInvoice, float, float]] = []
    po_allocations: list[tuple[m.PurchaseOrder, float]] = []
    total_discount = 0.0

    if purchase_invoice_id:
        inv = await get_purchase_invoice(db, tenant_id, purchase_invoice_id)
        if inv.supplier_id != supplier_id:
            raise HTTPException(status_code=400, detail="Invoice does not belong to this supplier")
        if inv.status not in PURCHASE_INVOICE_OPEN and inv.status != "draft":
            raise HTTPException(status_code=409, detail=f"Cannot pay invoice in status {inv.status}")
        if inv.status == "draft":
            raise HTTPException(status_code=409, detail="Approve purchase invoice before payment")
        due = float(inv.total_amount) - float(inv.paid_amount or 0)
        quote = purchase_invoice_early_discount(
            inv, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
        )
        if use_discount and quote["eligible"] and amount + 1e-9 >= quote["cash_to_settle"]:
            if amount > due + 1e-9:
                raise HTTPException(status_code=409, detail="Payment exceeds invoice balance due")
            if amount + 1e-9 >= due:
                invoice_allocations.append((inv, min(amount, due), 0.0))
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
                invoice_allocations.append((inv, due, discount))
                total_discount = discount
        else:
            if amount > due + 1e-9:
                raise HTTPException(status_code=409, detail="Payment exceeds invoice balance due")
            invoice_allocations.append((inv, amount, 0.0))
        if inv.purchase_order_id:
            po = await get_po(db, tenant_id, inv.purchase_order_id)
            settlement = invoice_allocations[0][1]
            po_allocations.append((po, settlement))
    elif purchase_order_id:
        po = await get_po(db, tenant_id, purchase_order_id)
        if po.supplier_id != supplier_id:
            raise HTTPException(status_code=400, detail="PO does not belong to this supplier")
        open_invs = (
            await db.execute(
                select(m.PurchaseInvoice)
                .where(
                    m.PurchaseInvoice.tenant_id == tenant_id,
                    m.PurchaseInvoice.purchase_order_id == purchase_order_id,
                    m.PurchaseInvoice.status.in_(list(PURCHASE_INVOICE_OPEN)),
                )
                .order_by(m.PurchaseInvoice.due_date.asc(), m.PurchaseInvoice.created_at.asc())
            )
        ).scalars().all()
        remaining = amount
        for inv in open_invs:
            due = float(inv.total_amount) - float(inv.paid_amount or 0)
            if due <= 0:
                continue
            quote = purchase_invoice_early_discount(
                inv, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
            )
            if use_discount and quote["eligible"] and remaining + 1e-9 >= quote["cash_to_settle"]:
                settlement = due
                discount = quote["discount_amount"]
                cash_used = quote["cash_to_settle"]
                invoice_allocations.append((inv, settlement, discount))
                total_discount = round(total_discount + discount, 2)
                remaining = round(remaining - cash_used, 2)
            else:
                apply_amt = min(remaining, due)
                invoice_allocations.append((inv, apply_amt, 0.0))
                remaining = round(remaining - apply_amt, 2)
            if remaining <= 0:
                break
        due_po = float(po.total_amount) - float(po.paid_amount or 0)
        settlement_on_po = sum(s for _, s, _ in invoice_allocations) if invoice_allocations else amount
        if amount > due_po + 1e-9 and not invoice_allocations:
            raise HTTPException(status_code=409, detail="Payment exceeds PO balance due")
        po_allocations.append((po, min(settlement_on_po, due_po) if invoice_allocations else amount))
    else:
        remaining = amount
        open_invs = (
            await db.execute(
                select(m.PurchaseInvoice)
                .where(
                    m.PurchaseInvoice.tenant_id == tenant_id,
                    m.PurchaseInvoice.supplier_id == supplier_id,
                    m.PurchaseInvoice.status.in_(list(PURCHASE_INVOICE_OPEN)),
                )
                .order_by(m.PurchaseInvoice.due_date.asc(), m.PurchaseInvoice.created_at.asc())
            )
        ).scalars().all()
        for inv in open_invs:
            due = float(inv.total_amount) - float(inv.paid_amount or 0)
            if due <= 0:
                continue
            quote = purchase_invoice_early_discount(
                inv, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
            )
            if use_discount and quote["eligible"] and remaining + 1e-9 >= quote["cash_to_settle"]:
                settlement = due
                discount = quote["discount_amount"]
                cash_used = quote["cash_to_settle"]
                invoice_allocations.append((inv, settlement, discount))
                total_discount = round(total_discount + discount, 2)
                if inv.purchase_order_id:
                    po = await get_po(db, tenant_id, inv.purchase_order_id)
                    po_allocations.append((po, settlement))
                remaining = round(remaining - cash_used, 2)
            else:
                apply_amt = min(remaining, due)
                invoice_allocations.append((inv, apply_amt, 0.0))
                if inv.purchase_order_id:
                    po = await get_po(db, tenant_id, inv.purchase_order_id)
                    po_allocations.append((po, apply_amt))
                remaining = round(remaining - apply_amt, 2)
            if remaining <= 0:
                break
        if remaining > 1e-9:
            open_pos = (
                await db.execute(
                    select(m.PurchaseOrder)
                    .where(
                        m.PurchaseOrder.tenant_id == tenant_id,
                        m.PurchaseOrder.supplier_id == supplier_id,
                        m.PurchaseOrder.status.in_(["sent", "partially_received", "received"]),
                    )
                    .order_by(m.PurchaseOrder.due_date.asc(), m.PurchaseOrder.created_at.asc())
                )
            ).scalars().all()
            for po in open_pos:
                due = float(po.total_amount) - float(po.paid_amount or 0)
                if due <= 0:
                    continue
                apply_amt = min(remaining, due)
                po_allocations.append((po, apply_amt))
                remaining = round(remaining - apply_amt, 2)
                if remaining <= 0:
                    break
            if remaining > 1e-9 and (open_pos or open_invs):
                raise HTTPException(
                    status_code=409,
                    detail=f"Payment exceeds open balances by {remaining:.2f}",
                )

    primary_inv = invoice_allocations[0][0] if invoice_allocations else None
    primary_po_id = (
        purchase_order_id
        or (primary_inv.purchase_order_id if primary_inv else None)
        or (po_allocations[0][0].id if po_allocations else None)
    )

    from app.fx import doc_currency, doc_rate, resolve_rate, to_base

    if invoice_allocations:
        inv0 = invoice_allocations[0][0]
        default_cur = doc_currency(inv0, tenant.currency or "GHS")
        for inv, _s, _d in invoice_allocations[1:]:
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
        else:
            pay_cur, pay_rate = await resolve_rate(
                db, tenant_id, default_cur, explicit_rate=doc_rate(inv0)
            )
    else:
        pay_cur, pay_rate = await resolve_rate(db, tenant_id, currency, explicit_rate=exchange_rate)

    alloc_note = ", ".join(
        f"{inv.invoice_number}:{amt:.2f}" + (f"(disc {disc:.2f})" if disc else "")
        for inv, amt, disc in invoice_allocations
    )
    if invoice_allocations:
        settlement_base = round(
            sum(to_base(amt, doc_rate(inv)) for inv, amt, _ in invoice_allocations),
            2,
        )
    else:
        settlement_base = to_base(amount, pay_rate)

    payment = m.SupplierPayment(
        tenant_id=tenant_id,
        payment_number=await next_supplier_payment_number(db, tenant_id),
        supplier_id=supplier_id,
        purchase_order_id=primary_po_id,
        purchase_invoice_id=primary_inv.id if primary_inv else purchase_invoice_id,
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
            if alloc_note and not purchase_invoice_id
            else (f"Early discount {total_discount:.2f}" if total_discount else notes)
        ),
        created_by=user_id,
    )
    db.add(payment)
    supplier.balance = max(float(supplier.balance or 0) - settlement_base, 0)

    for inv, apply_amt, _disc in invoice_allocations:
        inv.paid_amount = float(inv.paid_amount or 0) + apply_amt
        inv.status = purchase_invoice_status(
            float(inv.total_amount), float(inv.paid_amount), inv.due_date
        )
        inv.updated_at = datetime.utcnow()

    # Aggregate PO applications (same PO may appear multiple times)
    po_applied: dict[str, float] = {}
    for po, apply_amt in po_allocations:
        po_applied[po.id] = po_applied.get(po.id, 0.0) + apply_amt
    for po_id, apply_amt in po_applied.items():
        po = await get_po(db, tenant_id, po_id)
        po.paid_amount = float(po.paid_amount or 0) + apply_amt
        po.updated_at = datetime.utcnow()

    from app.accounting import post_supplier_payment_journal

    await post_supplier_payment_journal(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payment=payment,
        allocations=invoice_allocations or None,
    )

    from app import cheques as cheques_svc

    await cheques_svc.create_from_supplier_payment(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        payment=payment,
        cheque_number=cheque_number,
        bank_name=bank_name,
        cheque_date=cheque_date,
    )
    return payment


# --- Purchase returns / debit notes ---


async def get_grn(db: AsyncSession, tenant_id: str, grn_id: str) -> m.GoodsReceipt:
    grn = (
        await db.execute(
            select(m.GoodsReceipt).where(
                m.GoodsReceipt.id == grn_id,
                m.GoodsReceipt.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not grn:
        raise HTTPException(status_code=404, detail="GRN not found")
    return grn


async def list_grn_items(db: AsyncSession, tenant_id: str, grn_id: str) -> list[m.GoodsReceiptItem]:
    return (
        await db.execute(
            select(m.GoodsReceiptItem).where(
                m.GoodsReceiptItem.tenant_id == tenant_id,
                m.GoodsReceiptItem.goods_receipt_id == grn_id,
            )
        )
    ).scalars().all()


async def get_purchase_return(db: AsyncSession, tenant_id: str, return_id: str) -> m.PurchaseReturn:
    row = (
        await db.execute(
            select(m.PurchaseReturn).where(
                m.PurchaseReturn.id == return_id,
                m.PurchaseReturn.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase return not found")
    return row


async def list_purchase_return_items(
    db: AsyncSession, tenant_id: str, return_id: str
) -> list[m.PurchaseReturnItem]:
    return (
        await db.execute(
            select(m.PurchaseReturnItem).where(
                m.PurchaseReturnItem.tenant_id == tenant_id,
                m.PurchaseReturnItem.purchase_return_id == return_id,
            )
        )
    ).scalars().all()


async def _returned_qty_by_grn_item(
    db: AsyncSession,
    *,
    tenant_id: str,
    goods_receipt_id: str,
    exclude_return_id: str | None = None,
) -> dict[str, float]:
    """Sum return qty for GRN lines across draft+posted returns (exclude cancelled)."""
    q = (
        select(m.PurchaseReturnItem.goods_receipt_item_id, m.PurchaseReturnItem.quantity)
        .join(m.PurchaseReturn, m.PurchaseReturn.id == m.PurchaseReturnItem.purchase_return_id)
        .where(
            m.PurchaseReturnItem.tenant_id == tenant_id,
            m.PurchaseReturn.goods_receipt_id == goods_receipt_id,
            m.PurchaseReturn.status.in_(["draft", "posted"]),
        )
    )
    if exclude_return_id:
        q = q.where(m.PurchaseReturn.id != exclude_return_id)
    rows = (await db.execute(q)).all()
    totals: dict[str, float] = {}
    for item_id, qty in rows:
        totals[item_id] = totals.get(item_id, 0.0) + float(qty or 0)
    return totals


async def serialize_purchase_return(db: AsyncSession, ret: m.PurchaseReturn) -> dict:
    items = await list_purchase_return_items(db, ret.tenant_id, ret.id)
    serialized_items = []
    discount_total = 0.0
    for i in items:
        qty = float(i.quantity)
        unit = float(i.unit_price)
        rate = float(i.tax_rate or 0)
        line_net = round(qty * unit, 2)
        line_tax = round(line_net * (rate / 100.0), 2)
        line_total = float(i.line_total)
        # Discount baked into line_total at create (no separate column)
        disc = max(round(line_net + line_tax - line_total, 2), 0.0)
        discount_total += disc
        serialized_items.append(
            {
                "id": i.id,
                "goods_receipt_item_id": i.goods_receipt_item_id,
                "product_id": i.product_id,
                "quantity": qty,
                "unit_price": unit,
                "tax_rate": rate,
                "discount": disc,
                "line_total": line_total,
            }
        )
    return {
        "id": ret.id,
        "return_number": ret.return_number,
        "debit_note_number": ret.debit_note_number,
        "supplier_id": ret.supplier_id,
        "purchase_order_id": ret.purchase_order_id,
        "goods_receipt_id": ret.goods_receipt_id,
        "warehouse_id": ret.warehouse_id,
        "status": ret.status,
        "reason": ret.reason,
        "subtotal": float(ret.subtotal),
        "tax_amount": float(ret.tax_amount),
        "discount_amount": round(discount_total, 2),
        "total_amount": float(ret.total_amount),
        "notes": ret.notes,
        "posted_at": ret.posted_at,
        "created_at": ret.created_at,
        "items": serialized_items,
    }


async def create_purchase_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    goods_receipt_id: str,
    items: list[dict],
    reason: str,
    notes: str | None = None,
) -> m.PurchaseReturn:
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required")
    if reason not in PURCHASE_RETURN_REASONS:
        raise HTTPException(
            status_code=400,
            detail=f"reason must be one of {sorted(PURCHASE_RETURN_REASONS)}",
        )
    if not items:
        raise HTTPException(status_code=400, detail="Return requires line items")

    grn = await get_grn(db, tenant_id, goods_receipt_id)
    if grn.status != "posted":
        raise HTTPException(status_code=409, detail="Returns require a posted GRN")

    grn_items = {i.id: i for i in await list_grn_items(db, tenant_id, grn.id)}
    already = await _returned_qty_by_grn_item(db, tenant_id=tenant_id, goods_receipt_id=grn.id)
    po = await get_po(db, tenant_id, grn.purchase_order_id)
    po_items = {i.id: i for i in await list_po_items(db, tenant_id, po.id)}

    subtotal = 0.0
    tax_total = 0.0
    discount_total = 0.0
    prepared: list[dict] = []
    for raw in items:
        grn_item_id = raw.get("goods_receipt_item_id")
        grn_item = grn_items.get(grn_item_id)
        if not grn_item:
            raise HTTPException(status_code=400, detail=f"Invalid goods_receipt_item_id: {grn_item_id}")
        qty = float(raw["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Return quantity must be positive")
        available = float(grn_item.accepted_qty or 0) - already.get(grn_item.id, 0.0)
        if qty > available + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "OVER_RETURN",
                    "message": f"Return qty exceeds remaining accepted qty for GRN line {grn_item.id}",
                    "available": available,
                    "requested": qty,
                },
            )
        po_item = po_items.get(grn_item.po_item_id)
        if not po_item:
            raise HTTPException(status_code=400, detail="GRN line missing PO item")
        unit = float(po_item.unit_price)
        rate = float(po_item.tax_rate or 0)
        ordered = float(po_item.quantity or 0)
        line_disc_po = float(getattr(po_item, "discount", 0) or 0)
        disc = 0.0
        if ordered > 1e-9 and line_disc_po > 0:
            disc = round(line_disc_po * (qty / ordered), 2)
            merch = qty * unit
            if disc > merch + 1e-9:
                disc = round(max(merch, 0), 2)
        line_net = round(qty * unit, 2)
        line_tax = round(line_net * (rate / 100.0), 2)
        # Tax before discount (match PO/PI); bake discount into line_total
        line_total = round(max(line_net + line_tax - disc, 0), 2)
        subtotal += line_net
        tax_total += line_tax
        discount_total += disc
        prepared.append(
            {
                "goods_receipt_item_id": grn_item.id,
                "product_id": grn_item.product_id,
                "quantity": qty,
                "unit_price": unit,
                "tax_rate": rate,
                "line_total": line_total,
            }
        )
        already[grn_item.id] = already.get(grn_item.id, 0.0) + qty

    ret = m.PurchaseReturn(
        tenant_id=tenant_id,
        return_number=await next_purchase_return_number(db, tenant_id),
        supplier_id=grn.supplier_id,
        purchase_order_id=grn.purchase_order_id,
        goods_receipt_id=grn.id,
        warehouse_id=grn.warehouse_id,
        status="draft",
        reason=reason,
        subtotal=round(subtotal, 2),
        tax_amount=round(tax_total, 2),
        total_amount=round(max(subtotal + tax_total - discount_total, 0), 2),
        notes=notes,
        created_by=user_id,
    )
    db.add(ret)
    await db.flush()
    for line in prepared:
        db.add(m.PurchaseReturnItem(tenant_id=tenant_id, purchase_return_id=ret.id, **line))
    await db.flush()
    return ret


async def post_purchase_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    return_id: str,
) -> m.PurchaseReturn:
    ret = await get_purchase_return(db, tenant_id, return_id)
    if ret.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot post return in status {ret.status}")
    items = await list_purchase_return_items(db, tenant_id, ret.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot post empty return")

    # Re-validate remaining accepted qty excluding this draft
    already = await _returned_qty_by_grn_item(
        db,
        tenant_id=tenant_id,
        goods_receipt_id=ret.goods_receipt_id,
        exclude_return_id=ret.id,
    )
    grn_items = {i.id: i for i in await list_grn_items(db, tenant_id, ret.goods_receipt_id)}
    po = await get_po(db, tenant_id, ret.purchase_order_id)
    po_items = {i.id: i for i in await list_po_items(db, tenant_id, po.id)}

    for item in items:
        grn_item = grn_items.get(item.goods_receipt_item_id)
        if not grn_item:
            raise HTTPException(status_code=400, detail="GRN line missing for return item")
        available = float(grn_item.accepted_qty or 0) - already.get(grn_item.id, 0.0)
        if float(item.quantity) > available + 1e-9:
            raise HTTPException(status_code=409, detail="Return quantity no longer available")
        already[grn_item.id] = already.get(grn_item.id, 0.0) + float(item.quantity)

        from app.uom import to_stock_qty

        product = await db.get(m.Product, item.product_id)
        if not product or product.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Product not found for return line")
        line_unit_id = grn_item.unit_id or (po_items.get(grn_item.po_item_id).unit_id if po_items.get(grn_item.po_item_id) else None)
        stock_qty, _u, _e = await to_stock_qty(
            db,
            tenant_id=tenant_id,
            quantity=float(item.quantity),
            from_unit_id=line_unit_id,
            product=product,
        )
        await apply_stock_change(
            db,
            tenant_id=tenant_id,
            product_id=item.product_id,
            quantity_delta=-stock_qty,
            movement_type="stock_out",
            user_id=user_id,
            reference_type="purchase_return",
            reference_id=ret.id,
            warehouse_id=ret.warehouse_id,
            notes=f"Purchase return {ret.return_number}",
        )

        po_item = po_items.get(grn_item.po_item_id)
        if po_item:
            # received_qty tracked in entered UoM
            po_item.received_qty = max(float(po_item.received_qty or 0) - float(item.quantity), 0)

    updated_items = await list_po_items(db, tenant_id, po.id)
    if po.status not in {"cancelled", "draft"}:
        po.status = derive_po_status(updated_items)
        po.updated_at = datetime.utcnow()

    # Credit against open AP (mirror sales return increasing invoice paid_amount)
    credit = float(ret.total_amount)
    po.paid_amount = min(float(po.total_amount), float(po.paid_amount or 0) + credit)
    po.updated_at = datetime.utcnow()

    supplier = await get_supplier(db, tenant_id, ret.supplier_id)
    supplier.balance = max(float(supplier.balance or 0) - credit, 0)

    ret.status = "posted"
    ret.posted_at = datetime.utcnow()
    ret.debit_note_number = await next_debit_note_number(db, tenant_id)

    from app.accounting import post_purchase_return_journal

    await post_purchase_return_journal(db, tenant_id=tenant_id, user_id=user_id, purchase_return=ret)

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Purchase return posted",
        message=f"Return {ret.return_number} / {ret.debit_note_number} for {credit:.2f}.",
        entity_type="purchase_return",
        entity_id=ret.id,
    )
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="purchase_return_posted",
            entity="purchase_return",
            entity_id=ret.id,
            details={
                "return_number": ret.return_number,
                "debit_note_number": ret.debit_note_number,
                "total_amount": credit,
                "reason": ret.reason,
            },
        )
    )
    await db.flush()
    return ret


# --- Purchase invoices ---


async def get_purchase_invoice(db: AsyncSession, tenant_id: str, invoice_id: str) -> m.PurchaseInvoice:
    row = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.id == invoice_id,
                m.PurchaseInvoice.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Purchase invoice not found")
    return row


async def list_purchase_invoice_items(
    db: AsyncSession, tenant_id: str, invoice_id: str
) -> list[m.PurchaseInvoiceItem]:
    return (
        await db.execute(
            select(m.PurchaseInvoiceItem).where(
                m.PurchaseInvoiceItem.tenant_id == tenant_id,
                m.PurchaseInvoiceItem.purchase_invoice_id == invoice_id,
            )
        )
    ).scalars().all()


async def serialize_purchase_invoice(db: AsyncSession, inv: m.PurchaseInvoice) -> dict:
    items = await list_purchase_invoice_items(db, inv.tenant_id, inv.id)
    status = inv.status
    if status in PURCHASE_INVOICE_OPEN:
        status = purchase_invoice_status(float(inv.total_amount), float(inv.paid_amount or 0), inv.due_date)
        if status != inv.status:
            inv.status = status
    paid = float(inv.paid_amount or 0)
    can_cancel = status in {"draft", "unpaid", "overdue"} and paid <= 0
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "supplier_id": inv.supplier_id,
        "purchase_order_id": inv.purchase_order_id,
        "goods_receipt_id": inv.goods_receipt_id,
        "supplier_invoice_number": inv.supplier_invoice_number,
        "status": status,
        "invoice_date": inv.invoice_date,
        "due_date": inv.due_date,
        "subtotal": float(inv.subtotal),
        "tax_amount": float(inv.tax_amount),
        "reverse_charge_tax": float(getattr(inv, "reverse_charge_tax", 0) or 0),
        "is_reverse_charge": bool(getattr(inv, "is_reverse_charge", False)),
        "discount_amount": float(inv.discount_amount or 0),
        "currency": getattr(inv, "currency", None) or "",
        "exchange_rate": float(getattr(inv, "exchange_rate", None) or 1),
        "balance_due_base": round(
            max(float(inv.total_amount) - paid, 0)
            * float(getattr(inv, "exchange_rate", None) or 1),
            2,
        ),
        "total_amount": float(inv.total_amount),
        "paid_amount": paid,
        "balance_due": max(float(inv.total_amount) - paid, 0),
        "ap_posted": bool(inv.ap_posted),
        "attachment_url": inv.attachment_url,
        "has_attachment": bool(inv.attachment_url),
        "notes": inv.notes,
        "approved_at": inv.approved_at,
        "created_at": inv.created_at,
        "can_cancel": can_cancel,
        "tax_breakdown": _purchase_invoice_tax_breakdown(items, inv),
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount or 0),
                "line_subtotal": float(getattr(i, "line_subtotal", None) or _pi_line_subtotal(i)),
                "line_tax": _pi_line_tax_value(i),
                "tax_components": getattr(i, "tax_components", None) or None,
                "line_total": float(i.line_total),
            }
            for i in items
        ],
    }


def _pi_line_subtotal(item: m.PurchaseInvoiceItem) -> float:
    stored = float(getattr(item, "line_subtotal", None) or 0)
    if stored > 0:
        return stored
    return round(float(item.quantity or 0) * float(item.unit_price or 0), 2)


def _pi_line_tax_value(item: m.PurchaseInvoiceItem) -> float:
    stored = float(getattr(item, "line_tax", None) or 0)
    if stored > 0 or getattr(item, "tax_components", None) is not None:
        return stored
    rate = float(item.tax_rate or 0)
    if rate <= 0:
        return 0.0
    sub = _pi_line_subtotal(item)
    total = float(item.line_total or 0)
    discount = float(item.discount or 0)
    derived = round(total - sub + discount, 2)
    if derived < 0:
        return round(sub * rate / 100.0, 2)
    return derived


def _purchase_invoice_tax_breakdown(
    items: list[m.PurchaseInvoiceItem], inv: m.PurchaseInvoice
) -> dict:
    by_rate: dict[str, dict] = {}
    component_totals: dict[str, dict] = {}
    line_rows: list[dict] = []
    for i in items:
        line_tax = _pi_line_tax_value(i)
        rate = float(i.tax_rate or 0)
        key = f"{rate:.4f}"
        bucket = by_rate.setdefault(
            key,
            {"tax_rate": rate, "taxable": 0.0, "tax": 0.0},
        )
        bucket["taxable"] = round(bucket["taxable"] + _pi_line_subtotal(i), 2)
        bucket["tax"] = round(bucket["tax"] + line_tax, 2)
        comps = getattr(i, "tax_components", None) or []
        for c in comps:
            cname = str(c.get("name") or c.get("code") or "component")
            cb = component_totals.setdefault(cname, {"name": cname, "tax": 0.0})
            cb["tax"] = round(cb["tax"] + float(c.get("amount") or 0), 2)
        line_rows.append(
            {
                "item_id": i.id,
                "product_id": i.product_id,
                "tax_rate": rate,
                "line_subtotal": _pi_line_subtotal(i),
                "line_tax": line_tax,
                "tax_components": comps or None,
            }
        )
    return {
        "lines": line_rows,
        "by_rate": sorted(by_rate.values(), key=lambda r: -r["tax_rate"]),
        "by_component": sorted(component_totals.values(), key=lambda r: r["name"]),
        "tax_amount": float(inv.tax_amount or 0),
        "reverse_charge_tax": float(getattr(inv, "reverse_charge_tax", 0) or 0),
        "is_reverse_charge": bool(getattr(inv, "is_reverse_charge", False)),
    }


async def _prepare_invoice_lines(
    db: AsyncSession, tenant_id: str, items: list[dict]
) -> tuple[float, float, float, list[dict]]:
    subtotal = 0.0
    tax_total = 0.0
    prepared: list[dict] = []
    for item in items:
        product = (
            await db.execute(
                select(m.Product).where(
                    m.Product.id == item["product_id"],
                    m.Product.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {item['product_id']}")
        if not product.is_active:
            raise HTTPException(status_code=400, detail=f"Product is inactive: {product.sku}")
        qty = float(item["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Line quantity must be positive")
        unit = float(item.get("unit_price") if item.get("unit_price") is not None else product.cost_price or 0)
        discount = float(item.get("discount") or 0)
        line_item = {**item, "quantity": qty, "unit_price": unit}
        line_sub, line_tax, line_total, rate_pct, comps = await _purchase_line_tax(
            db, tenant_id, product, line_item
        )
        line_total = max(line_total - discount, 0)
        subtotal += line_sub
        tax_total += line_tax
        prepared.append(
            {
                "product_id": product.id,
                "quantity": qty,
                "unit_price": unit,
                "tax_rate": rate_pct,
                "discount": discount,
                "line_subtotal": line_sub,
                "line_tax": line_tax,
                "tax_components": comps,
                "line_total": line_total,
            }
        )
    return subtotal, tax_total, subtotal + tax_total, prepared


async def create_purchase_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    supplier_id: str | None = None,
    goods_receipt_id: str | None = None,
    purchase_order_id: str | None = None,
    items: list[dict] | None = None,
    supplier_invoice_number: str | None = None,
    invoice_date: datetime | None = None,
    due_date: datetime | None = None,
    discount_amount: float = 0,
    attachment_url: str | None = None,
    notes: str | None = None,
    is_reverse_charge: bool = False,
    currency: str | None = None,
    exchange_rate: float | None = None,
) -> m.PurchaseInvoice:
    grn = None
    po = None
    from app.fx import resolve_rate

    cur, rate = await resolve_rate(db, tenant_id, currency, explicit_rate=exchange_rate)
    if goods_receipt_id:
        grn = await get_grn(db, tenant_id, goods_receipt_id)
        existing = (
            await db.execute(
                select(m.PurchaseInvoice).where(
                    m.PurchaseInvoice.tenant_id == tenant_id,
                    m.PurchaseInvoice.goods_receipt_id == grn.id,
                    m.PurchaseInvoice.status != "cancelled",
                )
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="GRN already has a purchase invoice")
        po = await get_po(db, tenant_id, grn.purchase_order_id)
        supplier_id = grn.supplier_id
        purchase_order_id = po.id
        if not items:
            po_items = {i.id: i for i in await list_po_items(db, tenant_id, po.id)}
            items = []
            for gi in await list_grn_items(db, tenant_id, grn.id):
                qty = float(gi.accepted_qty or 0)
                if qty <= 0:
                    continue
                poi = po_items.get(gi.po_item_id)
                unit_price = float(poi.unit_price) if poi else 0.0
                tax_rate = float(poi.tax_rate or 0) if poi else 0.0
                # Carry proportional PO line discount (BR-6.3 → BR-6.5)
                disc = 0.0
                if poi is not None:
                    ordered = float(poi.quantity or 0)
                    line_disc = float(getattr(poi, "discount", 0) or 0)
                    if ordered > 1e-9 and line_disc > 0:
                        disc = round(line_disc * (qty / ordered), 2)
                        merch = qty * unit_price
                        if disc > merch + 1e-9:
                            disc = round(max(merch, 0), 2)
                items.append(
                    {
                        "product_id": gi.product_id,
                        "quantity": qty,
                        "unit_price": unit_price,
                        "tax_rate": tax_rate,
                        "discount": disc,
                    }
                )
            # When client leaves header discount at 0, mirror sum of carried line discounts
            # so invoice total_amount matches negotiated PO economics (PI totals use header).
            if float(discount_amount or 0) <= 0:
                discount_amount = round(
                    sum(float(i.get("discount") or 0) for i in items),
                    2,
                )
    elif purchase_order_id:
        po = await get_po(db, tenant_id, purchase_order_id)
        supplier_id = supplier_id or po.supplier_id

    if not supplier_id:
        raise HTTPException(status_code=400, detail="supplier_id is required")
    # New standalone invoices cannot use inactive suppliers; GRN/PO-linked may settle existing ones.
    if not goods_receipt_id and not purchase_order_id:
        supplier = await require_active_supplier(db, tenant_id, supplier_id)
    else:
        supplier = await get_supplier(db, tenant_id, supplier_id)
    if not items:
        raise HTTPException(status_code=400, detail="Invoice requires line items")

    subtotal, tax_total, gross, prepared = await _prepare_invoice_lines(db, tenant_id, items)
    discount_amount = float(discount_amount or 0)
    is_rc = bool(is_reverse_charge)
    if is_rc:
        # Supplier invoice is net; tax is self-assessed and excluded from AP.
        total = max(subtotal - discount_amount, 0)
        charged_tax = 0.0
        rc_tax = round(tax_total, 2)
    else:
        total = max(gross - discount_amount, 0)
        charged_tax = round(tax_total, 2)
        rc_tax = 0.0
    inv_date = invoice_date or datetime.utcnow()
    if due_date is None:
        if po is not None and po.due_date is not None:
            due_date = po.due_date
        else:
            due_date = default_due_date(inv_date, party_terms_days(supplier))

    inv = m.PurchaseInvoice(
        tenant_id=tenant_id,
        invoice_number=await next_purchase_invoice_number(db, tenant_id),
        supplier_id=supplier_id,
        purchase_order_id=purchase_order_id or (po.id if po else None),
        goods_receipt_id=grn.id if grn else None,
        supplier_invoice_number=supplier_invoice_number,
        status="draft",
        invoice_date=inv_date,
        due_date=due_date,
        subtotal=round(subtotal, 2),
        tax_amount=charged_tax,
        reverse_charge_tax=rc_tax,
        is_reverse_charge=is_rc,
        discount_amount=round(discount_amount, 2),
        total_amount=round(total, 2),
        paid_amount=0,
        currency=cur,
        exchange_rate=rate,
        ap_posted=False,
        attachment_url=attachment_url,
        notes=notes,
        created_by=user_id,
    )
    db.add(inv)
    await db.flush()
    for line in prepared:
        db.add(m.PurchaseInvoiceItem(tenant_id=tenant_id, purchase_invoice_id=inv.id, **line))
    await db.flush()
    return inv


async def approve_purchase_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
) -> m.PurchaseInvoice:
    inv = await get_purchase_invoice(db, tenant_id, invoice_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot approve invoice in status {inv.status}")
    items = await list_purchase_invoice_items(db, tenant_id, inv.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot approve empty invoice")

    # GRN path already posted inventory + AP; manual bills post AP now.
    if inv.goods_receipt_id:
        inv.ap_posted = False
    else:
        from app.fx import doc_rate, to_base

        supplier = await get_supplier(db, tenant_id, inv.supplier_id)
        supplier.balance = float(supplier.balance or 0) + to_base(
            float(inv.total_amount), doc_rate(inv)
        )
        from app.accounting import post_purchase_invoice_journal

        await post_purchase_invoice_journal(
            db, tenant_id=tenant_id, user_id=user_id, purchase_invoice=inv
        )
        inv.ap_posted = True

    inv.status = purchase_invoice_status(float(inv.total_amount), float(inv.paid_amount or 0), inv.due_date)
    inv.approved_at = datetime.utcnow()
    inv.updated_at = datetime.utcnow()

    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="system",
        title="Purchase invoice approved",
        message=f"Invoice {inv.invoice_number} approved for {float(inv.total_amount):.2f}.",
        entity_type="purchase_invoice",
        entity_id=inv.id,
    )
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="purchase_invoice_approved",
            entity="purchase_invoice",
            entity_id=inv.id,
            details={
                "invoice_number": inv.invoice_number,
                "total": float(inv.total_amount),
                "ap_posted": inv.ap_posted,
                "goods_receipt_id": inv.goods_receipt_id,
                "is_reverse_charge": bool(getattr(inv, "is_reverse_charge", False)),
                "reverse_charge_tax": float(getattr(inv, "reverse_charge_tax", 0) or 0),
            },
        )
    )
    await db.flush()
    return inv


async def cancel_purchase_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
) -> m.PurchaseInvoice:
    inv = await get_purchase_invoice(db, tenant_id, invoice_id)
    if inv.status == "cancelled":
        return inv
    if float(inv.paid_amount or 0) > 0:
        raise HTTPException(status_code=409, detail="Cannot cancel invoice with payments")
    if inv.status not in {"draft", "unpaid", "overdue"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel invoice in status {inv.status}")
    if inv.ap_posted and inv.status != "draft":
        supplier = await get_supplier(db, tenant_id, inv.supplier_id)
        supplier.balance = max(float(supplier.balance or 0) - float(inv.total_amount), 0)
        from app.accounting import post_purchase_invoice_reversal_journal

        await post_purchase_invoice_reversal_journal(
            db, tenant_id=tenant_id, user_id=user_id, purchase_invoice=inv
        )
    inv.status = "cancelled"
    inv.updated_at = datetime.utcnow()
    await db.flush()
    return inv
