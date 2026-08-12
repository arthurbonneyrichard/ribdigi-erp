"""Sales quotations, orders, and returns."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import apply_stock_change
from app.sales import create_sales_invoice, get_customer, get_invoice, list_invoice_items
from app.tax import resolve_product_tax
from app.catalog import get_variant, resolve_sale_line

RETURN_REASONS = frozenset({"damaged", "wrong_item", "defective", "customer_change", "other"})


async def _prepare_lines(
    db: AsyncSession,
    tenant_id: str,
    items: list[dict],
) -> tuple[float, float, list[tuple[dict, float]]]:
    if not items:
        raise HTTPException(status_code=400, detail="At least one line item is required")
    subtotal = 0.0
    tax_total = 0.0
    prepared: list[tuple[dict, float]] = []
    for item in items:
        product, variant, unit = await resolve_sale_line(db, tenant_id, item)
        qty = float(item["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")
        discount = float(item.get("discount") or 0)
        explicit = item.get("tax_rate")
        if explicit is not None:
            spec = await resolve_product_tax(
                db, tenant_id, product, explicit_rate=float(explicit)
            )
        else:
            spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=None)
        line_sub, line_tax, line_total = spec.compute_amounts(qty * unit)
        line_total = max(line_total - discount, 0)
        subtotal += line_sub
        if not spec.is_reverse_charge:
            tax_total += line_tax
        prepared.append(
            (
                {
                    "product_id": product.id,
                    "variant_id": variant.id if variant else None,
                    "quantity": qty,
                    "unit_price": unit,
                    "tax_rate": spec.rate_pct,
                    "discount": discount,
                    "line_total": line_total,
                },
                line_total,
            )
        )
    return round(subtotal, 2), round(tax_total, 2), prepared


def _stamp(prefix: str) -> str:
    return f"{prefix}-{datetime.utcnow():%Y%m%d%H%M%S%f}"


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
        "quotation_number": quote.quotation_number,
        "customer_id": quote.customer_id,
        "status": quote.status,
        "subtotal": float(quote.subtotal),
        "tax_amount": float(quote.tax_amount),
        "discount_amount": float(quote.discount_amount),
        "total_amount": float(quote.total_amount),
        "valid_until": quote.valid_until,
        "notes": quote.notes,
        "converted_order_id": quote.converted_order_id,
        "converted_invoice_id": quote.converted_invoice_id,
        "emailed_at": quote.emailed_at,
        "emailed_to": quote.emailed_to,
        "created_at": quote.created_at,
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
) -> m.SalesQuotation:
    await get_customer(db, tenant_id, customer_id)
    subtotal, tax_total, prepared = await _prepare_lines(db, tenant_id, items)
    discount_amount = float(discount_amount or 0)
    total = round(subtotal + tax_total - discount_amount, 2)
    if total < 0:
        raise HTTPException(status_code=400, detail="Total cannot be negative")
    quote = m.SalesQuotation(
        tenant_id=tenant_id,
        quotation_number=_stamp("QT"),
        customer_id=customer_id,
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        discount_amount=discount_amount,
        total_amount=total,
        valid_until=datetime.utcnow() + timedelta(days=max(valid_days, 1)),
        notes=notes,
        created_by=user_id,
    )
    db.add(quote)
    await db.flush()
    for line, _ in prepared:
        db.add(m.SalesQuotationItem(tenant_id=tenant_id, quotation_id=quote.id, **line))
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


async def reject_quotation(db: AsyncSession, tenant_id: str, quotation_id: str) -> m.SalesQuotation:
    quote = await get_quotation(db, tenant_id, quotation_id)
    if quote.status not in {"draft", "sent"}:
        raise HTTPException(status_code=409, detail=f"Cannot reject quotation in status {quote.status}")
    quote.status = "rejected"
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


async def serialize_order(db: AsyncSession, order: m.SalesOrder) -> dict:
    items = await list_order_items(db, order.tenant_id, order.id)
    from app.reservations import list_order_reservations

    reservations = await list_order_reservations(db, order.tenant_id, order.id, status=None)
    active = [r for r in reservations if r.status == "active"]
    reserved_by_item = {r.sales_order_item_id: float(r.quantity) for r in active if r.sales_order_item_id}
    return {
        "id": order.id,
        "order_number": order.order_number,
        "customer_id": order.customer_id,
        "quotation_id": order.quotation_id,
        "store_id": getattr(order, "store_id", None),
        "delivery_date": getattr(order, "delivery_date", None),
        "delivery_address": getattr(order, "delivery_address", None),
        "status": order.status,
        "subtotal": float(order.subtotal),
        "tax_amount": float(order.tax_amount),
        "discount_amount": float(order.discount_amount),
        "total_amount": float(order.total_amount),
        "notes": order.notes,
        "converted_invoice_id": order.converted_invoice_id,
        "confirmed_at": order.confirmed_at,
        "processing_at": getattr(order, "processing_at", None),
        "shipped_at": getattr(order, "shipped_at", None),
        "delivered_at": getattr(order, "delivered_at", None),
        "created_at": order.created_at,
        "reserved_qty": round(sum(float(r.quantity) for r in active), 3),
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
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount),
                "line_total": float(i.line_total),
                "reserved_qty": reserved_by_item.get(i.id, 0.0),
            }
            for i in items
        ],
    }


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
    await get_customer(db, tenant_id, customer_id)
    if quotation_id:
        quote = await get_quotation(db, tenant_id, quotation_id)
        if quote.customer_id != customer_id:
            raise HTTPException(status_code=400, detail="Quotation customer mismatch")
    resolved_store_id = None
    if store_id:
        from app.stores import get_store

        store = await get_store(db, tenant_id, store_id)
        resolved_store_id = store.id
    subtotal, tax_total, prepared = await _prepare_lines(db, tenant_id, items)
    discount_amount = float(discount_amount or 0)
    total = round(subtotal + tax_total - discount_amount, 2)
    order = m.SalesOrder(
        tenant_id=tenant_id,
        order_number=_stamp("SO"),
        customer_id=customer_id,
        quotation_id=quotation_id,
        store_id=resolved_store_id,
        delivery_date=delivery_date,
        delivery_address=(delivery_address or "").strip() or None,
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        discount_amount=discount_amount,
        total_amount=total,
        notes=notes,
        created_by=user_id,
    )
    db.add(order)
    await db.flush()
    for line, _ in prepared:
        db.add(m.SalesOrderItem(tenant_id=tenant_id, sales_order_id=order.id, **line))
    await db.flush()
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
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount),
            }
            for i in items
        ],
        discount_amount=float(quote.discount_amount or 0),
        notes=quote.notes,
        quotation_id=quote.id,
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
        order.delivery_address = delivery_address.strip() or None
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
        category="system",
        title="Sales order confirmed",
        message=f"Order {order.order_number} confirmed; inventory reserved.",
        entity_type="sales_order",
        entity_id=order.id,
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


async def cancel_order(db: AsyncSession, tenant_id: str, order_id: str) -> m.SalesOrder:
    order = await get_order(db, tenant_id, order_id)
    if order.status not in ORDER_CANCELABLE:
        raise HTTPException(status_code=409, detail=f"Cannot cancel order in status {order.status}")
    if order.status in ORDER_RESERVED_STATUSES:
        from app.reservations import release_order_reservations

        await release_order_reservations(db, tenant_id=tenant_id, order_id=order.id)
    order.status = "cancelled"
    order.updated_at = datetime.utcnow()
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
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "discount": float(i.discount),
            }
            for i in items
        ],
        discount_amount=float(order.discount_amount or 0),
        notes=order.notes,
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
        "return_number": ret.return_number,
        "credit_note_number": getattr(ret, "credit_note_number", None),
        "customer_id": ret.customer_id,
        "sales_invoice_id": ret.sales_invoice_id,
        "status": ret.status,
        "reason": ret.reason,
        "restock": ret.restock,
        "subtotal": float(ret.subtotal),
        "tax_amount": float(ret.tax_amount),
        "total_amount": float(ret.total_amount),
        "settlement_method": getattr(ret, "settlement_method", None),
        "refund_payment_method": getattr(ret, "refund_payment_method", None),
        "refunded_amount": float(getattr(ret, "refunded_amount", 0) or 0),
        "notes": ret.notes,
        "posted_at": ret.posted_at,
        "created_at": ret.created_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "line_total": float(i.line_total),
                "condition": i.condition,
            }
            for i in items
        ],
    }


async def create_return(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    sales_invoice_id: str,
    items: list[dict],
    reason: str = "other",
    restock: bool = True,
    notes: str | None = None,
) -> m.SalesReturn:
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
        qty = float(item["quantity"])
        if qty <= 0 or qty > float(src.quantity) + 1e-9:
            raise HTTPException(status_code=400, detail="Return quantity exceeds invoice quantity")
        unit = float(src.unit_price)
        rate = float(src.tax_rate or 0)
        line_net = round(qty * unit, 2)
        line_tax = round(line_net * (rate / 100.0), 2)
        line_total = round(line_net + line_tax, 2)
        subtotal += line_net
        tax_total += line_tax
        prepared.append(
            {
                "product_id": pid,
                "variant_id": vid,
                "quantity": qty,
                "unit_price": unit,
                "tax_rate": rate,
                "line_total": line_total,
                "condition": item.get("condition") or ("sellable" if restock else "discard"),
            }
        )

    ret = m.SalesReturn(
        tenant_id=tenant_id,
        return_number=_stamp("SR"),
        customer_id=invoice.customer_id,
        sales_invoice_id=invoice.id,
        status="draft",
        reason=reason,
        restock=restock,
        subtotal=round(subtotal, 2),
        tax_amount=round(tax_total, 2),
        total_amount=round(subtotal + tax_total, 2),
        notes=notes,
        created_by=user_id,
    )
    db.add(ret)
    await db.flush()
    for line in prepared:
        db.add(m.SalesReturnItem(tenant_id=tenant_id, sales_return_id=ret.id, **line))
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

    for item in items:
        if ret.restock and item.condition == "sellable":
            qty = float(item.quantity)
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
            )
            if item.variant_id:
                variant = await get_variant(db, tenant_id, item.variant_id)
                variant.stock_qty = float(variant.stock_qty or 0) + qty
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
                        "quantity": float(item.quantity),
                    },
                )
            )

    return_total = round(float(ret.total_amount), 2)
    invoice = await get_invoice(db, tenant_id, ret.sales_invoice_id)
    open_ar = max(float(invoice.total_amount) - float(invoice.paid_amount or 0), 0.0)
    apply_to_invoice = min(return_total, open_ar)
    excess = round(return_total - apply_to_invoice, 2)

    method = (settlement_method or "").strip().lower() or None
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
        float(invoice.total_amount),
        float(invoice.paid_amount or 0) + apply_to_invoice,
    )
    from app.sales import apply_invoice_status

    if invoice.status != "draft":
        apply_invoice_status(invoice)
        invoice.updated_at = datetime.utcnow()

    customer = await get_customer(db, tenant_id, ret.customer_id)
    # Negative balance = customer store credit after return
    customer.balance = round(float(customer.balance or 0) - return_total, 2)

    ret.credit_note_number = f"CN-{datetime.utcnow():%Y%m%d%H%M%S%f}"
    ret.settlement_method = method
    ret.refunded_amount = 0
    ret.status = "posted"
    ret.posted_at = datetime.utcnow()

    from app.accounting import post_sales_return_journal, post_sales_return_refund_journal

    await post_sales_return_journal(db, tenant_id=tenant_id, user_id=user_id, sales_return=ret)

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
        customer.balance = round(float(customer.balance or 0) + excess, 2)

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
                "refunded_amount": float(ret.refunded_amount or 0),
                "applied_to_invoice": apply_to_invoice,
            },
        )
    )
    await db.flush()
    return ret
