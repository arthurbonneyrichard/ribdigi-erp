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
from app.doc_numbers import next_sales_invoice_number


def invoice_payment_status(total: float, paid: float) -> str:
    if paid <= 0:
        return "posted"
    if paid + 1e-9 >= total:
        return "paid"
    return "partial"


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
    items = await list_invoice_items(db, invoice.tenant_id, invoice.id)
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "store_id": invoice.store_id,
        "status": invoice.status,
        "subtotal": float(invoice.subtotal),
        "tax_amount": float(invoice.tax_amount),
        "reverse_charge_tax": float(getattr(invoice, "reverse_charge_tax", 0) or 0),
        "discount_amount": float(invoice.discount_amount),
        "total_amount": float(invoice.total_amount),
        "paid_amount": float(invoice.paid_amount),
        "balance_due": max(float(invoice.total_amount) - float(invoice.paid_amount or 0), 0),
        "currency": getattr(invoice, "currency", None) or "",
        "exchange_rate": float(getattr(invoice, "exchange_rate", None) or 1),
        "balance_due_base": round(
            max(float(invoice.total_amount) - float(invoice.paid_amount or 0), 0)
            * float(getattr(invoice, "exchange_rate", None) or 1),
            2,
        ),
        "notes": invoice.notes,
        "posted_at": invoice.posted_at,
        "due_date": invoice.due_date,
        "emailed_at": invoice.emailed_at,
        "emailed_to": invoice.emailed_to,
        "created_at": invoice.created_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "tax_supply_class": getattr(i, "tax_supply_class", None) or "standard",
                "discount": float(i.discount),
                "line_subtotal": float(getattr(i, "line_subtotal", None) or 0),
                "line_total": float(i.line_total),
            }
            for i in items
        ],
    }


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

    subtotal = 0.0
    tax_total = 0.0
    reverse_charge_tax = 0.0
    prepared: list[tuple[dict, float]] = []
    for item in items:
        product, variant, unit_price = await resolve_sale_line(db, tenant_id, item)
        explicit = item.get("tax_rate")
        if explicit is not None:
            spec = await resolve_product_tax(
                db, tenant_id, product, explicit_rate=float(explicit)
            )
        else:
            spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=None)
        line_amount = float(item["quantity"]) * float(unit_price)
        line_sub, line_tax, line_total = spec.compute_amounts(line_amount)
        discount = float(item.get("discount") or 0)
        line_total = max(line_total - discount, 0)
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
                    "tax_supply_class": spec.supply_class,
                    "line_subtotal": line_sub,
                },
                line_total,
            )
        )

    discount_amount = float(discount_amount or 0)
    total = max(subtotal + tax_total - discount_amount, 0)

    invoice = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number=await next_sales_invoice_number(db, tenant_id),
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
                sales_invoice_id=invoice.id,
                product_id=item["product_id"],
                variant_id=item.get("variant_id"),
                quantity=item["quantity"],
                unit_price=item["unit_price"],
                tax_rate=item.get("tax_rate", 0),
                tax_supply_class=item.get("tax_supply_class") or "standard",
                discount=item.get("discount", 0),
                line_subtotal=item.get("line_subtotal") or 0,
                line_total=line_total,
            )
        )

    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="invoice_created",
            entity="sales_invoice",
            entity_id=invoice.id,
            details={"invoice_number": invoice.invoice_number, "total": float(invoice.total_amount)},
        )
    )
    return invoice


async def post_sales_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
) -> m.SalesInvoice:
    invoice = await get_invoice(db, tenant_id, invoice_id)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot post invoice in status {invoice.status}")

    items = await list_invoice_items(db, tenant_id, invoice.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot post empty invoice")

    customer = await get_customer(db, tenant_id, invoice.customer_id)
    from app.fx import doc_rate, to_base

    inv_base = to_base(float(invoice.total_amount), doc_rate(invoice))
    credit_limit = float(customer.credit_limit or 0)
    if credit_limit > 0:
        projected = float(customer.balance or 0) + inv_base
        if projected > credit_limit + 1e-9:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "CREDIT_LIMIT_EXCEEDED",
                    "message": "Posting this invoice would exceed the customer credit limit",
                    "credit_limit": credit_limit,
                    "current_balance": float(customer.balance or 0),
                    "invoice_total": float(invoice.total_amount),
                    "invoice_total_base": inv_base,
                    "currency": getattr(invoice, "currency", None) or "",
                },
            )

    warehouse_id = None
    if invoice.store_id:
        from app.stores import warehouse_for_store
        from app.inventory import allocate_unlocated_stock

        wh = await warehouse_for_store(db, tenant_id, invoice.store_id)
        warehouse_id = wh.id

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
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="invoice_posted",
            entity="sales_invoice",
            entity_id=invoice.id,
            details={"invoice_number": invoice.invoice_number, "total": float(invoice.total_amount)},
        )
    )
    return invoice


async def send_sales_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
    to: str | None = None,
) -> tuple[m.SalesInvoice, dict]:
    """Email posted/partial/paid invoice to customer. Status is unchanged."""
    from app import emailer

    invoice = await get_invoice(db, tenant_id, invoice_id)
    if invoice.status not in {"posted", "partial", "paid"}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot email invoice in status {invoice.status}",
        )
    items = await list_invoice_items(db, tenant_id, invoice.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot email empty invoice")

    customer = await get_customer(db, tenant_id, invoice.customer_id)
    recipient = (to or customer.email or "").strip()
    if not recipient:
        raise HTTPException(
            status_code=400,
            detail="Customer has no email; set customer email or pass to= override",
        )

    tenant = await db.get(m.Tenant, tenant_id)
    company_name = tenant.company_name if tenant else "RIBDIGI ERP"
    currency = (
        (getattr(invoice, "currency", None) or "").strip()
        or (tenant.currency if tenant else None)
        or "GHS"
    )
    payload = await serialize_invoice(db, invoice)

    result = await emailer.send_sales_invoice_email(
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
    invoice.emailed_at = now
    invoice.emailed_to = recipient
    invoice.updated_at = now
    await db.flush()
    delivery = {
        "sent": result.sent,
        "mode": result.mode,
        "to": recipient,
        "emailed_at": now.isoformat(),
        "invoice_number": invoice.invoice_number,
        "status": invoice.status,
    }
    return invoice, delivery


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
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="invoice_cancelled",
            entity="sales_invoice",
            entity_id=invoice.id,
            details={"invoice_number": invoice.invoice_number},
        )
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
) -> m.CustomerPayment:
    amount = float(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")

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
        invoice.status = invoice_payment_status(float(invoice.total_amount), float(invoice.paid_amount))
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

    db.add(
        m.AuditLog(
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
        )
    )
    return payment
