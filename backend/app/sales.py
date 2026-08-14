"""Sales invoice and customer payment business logic."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.tax import resolve_product_tax
from app.credit import default_due_date, party_terms_days
from app.catalog import resolve_sale_line, stock_out_with_batch
from app.doc_numbers import next_customer_payment_number, next_sales_invoice_number


SALES_INVOICE_OPEN = frozenset({"posted", "sent", "partial", "overdue"})
SALES_INVOICE_BILLED = frozenset({"posted", "sent", "partial", "paid", "overdue"})


def invoice_payment_status(
    total: float,
    paid: float,
    due_date: datetime | None = None,
    *,
    emailed_at: datetime | None = None,
    as_of: datetime | None = None,
) -> str:
    """Derive sales invoice payment/lifecycle status.

    Open unpaid: posted (approved) → sent (emailed) → overdue (past due).
    Partial payments stay partial unless past due (then overdue).
    """
    if paid + 1e-9 >= float(total):
        return "paid"
    now = as_of or datetime.utcnow()
    if due_date and now.date() > due_date.date():
        return "overdue"
    if paid > 0:
        return "partial"
    if emailed_at:
        return "sent"
    return "posted"


def apply_invoice_status(
    invoice: m.SalesInvoice,
    *,
    as_of: datetime | None = None,
    leave_draft: bool = False,
) -> str:
    """Recompute open/billed status from balances. Cancelled is never changed.

    Draft invoices stay draft unless ``leave_draft=True`` (used when posting).
    """
    if invoice.status == "cancelled":
        return invoice.status
    if invoice.status == "draft" and not leave_draft:
        return invoice.status
    invoice.status = invoice_payment_status(
        float(invoice.total_amount),
        float(invoice.paid_amount or 0),
        invoice.due_date,
        emailed_at=invoice.emailed_at,
        as_of=as_of,
    )
    return invoice.status


async def refresh_overdue_sales_invoices(
    db: AsyncSession, tenant_id: str, *, as_of: datetime | None = None
) -> int:
    """Flip open invoices to overdue (and refresh sent/partial) when past due."""
    rows = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(list(SALES_INVOICE_OPEN)),
            )
        )
    ).scalars().all()
    changed = 0
    for inv in rows:
        before = inv.status
        if apply_invoice_status(inv, as_of=as_of) != before:
            inv.updated_at = datetime.utcnow()
            changed += 1
    if changed:
        await db.flush()
    return changed


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
    status = invoice.status
    if status not in {"draft", "cancelled"}:
        status = invoice_payment_status(
            float(invoice.total_amount),
            float(invoice.paid_amount or 0),
            invoice.due_date,
            emailed_at=invoice.emailed_at,
        )
    from app.credit import days_overdue

    overdue_days = 0
    if status == "overdue" or (
        invoice.due_date
        and status in SALES_INVOICE_OPEN
        and float(invoice.paid_amount or 0) + 1e-9 < float(invoice.total_amount)
    ):
        overdue_days = days_overdue(datetime.utcnow(), invoice.due_date, invoice.posted_at or invoice.created_at)
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "store_id": invoice.store_id,
        "status": status,
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
        "days_overdue": overdue_days if status == "overdue" else 0,
        "can_print": status in SALES_INVOICE_BILLED,
        "can_email": status in SALES_INVOICE_BILLED,
        "tax_breakdown": _invoice_tax_breakdown(items, invoice),
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "variant_id": i.variant_id,
                "quantity": float(i.quantity),
                "unit_id": i.unit_id,
                "unit_price": float(i.unit_price),
                "tax_rate": float(i.tax_rate),
                "tax_supply_class": getattr(i, "tax_supply_class", None) or "standard",
                "discount": float(i.discount),
                "line_subtotal": float(getattr(i, "line_subtotal", None) or 0),
                "line_tax": _line_tax_value(i),
                "is_reverse_charge": bool(getattr(i, "is_reverse_charge", False)),
                "tax_components": getattr(i, "tax_components", None) or None,
                "line_total": float(i.line_total),
            }
            for i in items
        ],
    }


def _line_tax_value(item: m.SalesInvoiceItem) -> float:
    """Persisted line_tax, with legacy backfill when column is still 0 but rate > 0."""
    stored = float(getattr(item, "line_tax", None) or 0)
    if stored > 0 or bool(getattr(item, "is_reverse_charge", False)):
        return stored
    if getattr(item, "tax_components", None) is not None:
        return stored
    rate = float(item.tax_rate or 0)
    if rate <= 0:
        return 0.0
    sub = float(getattr(item, "line_subtotal", None) or 0)
    total = float(item.line_total or 0)
    discount = float(item.discount or 0)
    derived = round(total - sub + discount, 2)
    if derived < 0:
        return round(sub * rate / 100.0, 2)
    return derived


def _invoice_tax_breakdown(items: list[m.SalesInvoiceItem], invoice: m.SalesInvoice) -> dict:
    by_rate: dict[str, dict] = {}
    component_totals: dict[str, dict] = {}
    line_rows: list[dict] = []
    for i in items:
        line_tax = _line_tax_value(i)
        is_rc = bool(getattr(i, "is_reverse_charge", False))
        rate = float(i.tax_rate or 0)
        key = f"{rate:.4f}|{'rc' if is_rc else 'std'}"
        bucket = by_rate.setdefault(
            key,
            {
                "tax_rate": rate,
                "is_reverse_charge": is_rc,
                "taxable": 0.0,
                "tax": 0.0,
            },
        )
        bucket["taxable"] = round(bucket["taxable"] + float(getattr(i, "line_subtotal", None) or 0), 2)
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
                "line_subtotal": float(getattr(i, "line_subtotal", None) or 0),
                "line_tax": line_tax,
                "is_reverse_charge": is_rc,
                "tax_components": comps or None,
            }
        )
    return {
        "lines": line_rows,
        "by_rate": sorted(by_rate.values(), key=lambda r: (-r["tax_rate"], r["is_reverse_charge"])),
        "by_component": sorted(component_totals.values(), key=lambda r: r["name"]),
        "tax_amount": float(invoice.tax_amount or 0),
        "reverse_charge_tax": float(getattr(invoice, "reverse_charge_tax", 0) or 0),
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

    from app.uom import resolve_line_unit

    subtotal = 0.0
    tax_total = 0.0
    reverse_charge_tax = 0.0
    prepared: list[tuple[dict, float]] = []
    for item in items:
        product, variant, unit_price = await resolve_sale_line(
            db, tenant_id, item, customer_id=customer_id
        )
        unit_id, qty, _qty_base = await resolve_line_unit(
            db,
            tenant_id=tenant_id,
            product=product,
            unit_id=item.get("unit_id"),
            quantity=float(item["quantity"]),
        )
        explicit = item.get("tax_rate")
        if explicit is not None:
            spec = await resolve_product_tax(
                db, tenant_id, product, explicit_rate=float(explicit)
            )
        else:
            spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=None)
        line_amount = qty * float(unit_price)
        breakdown = spec.compute_breakdown(line_amount)
        line_sub = float(breakdown["net"])
        line_tax = float(breakdown["tax"])
        line_total = float(breakdown["gross"])
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
                    "quantity": qty,
                    "unit_id": unit_id,
                    "unit_price": unit_price,
                    "discount": discount,
                    "tax_rate": spec.rate_pct,
                    "tax_supply_class": spec.supply_class,
                    "line_subtotal": line_sub,
                    "line_tax": line_tax,
                    "is_reverse_charge": bool(spec.is_reverse_charge),
                    "tax_components": list(breakdown.get("components") or []) or None,
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
                unit_id=item.get("unit_id"),
                unit_price=item["unit_price"],
                tax_rate=item.get("tax_rate", 0),
                tax_supply_class=item.get("tax_supply_class") or "standard",
                discount=item.get("discount", 0),
                line_subtotal=item.get("line_subtotal") or 0,
                line_tax=item.get("line_tax") or 0,
                is_reverse_charge=bool(item.get("is_reverse_charge")),
                tax_components=item.get("tax_components"),
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
    override_credit_limit: bool = False,
    override_reason: str | None = None,
    credit_override_allowed: bool = False,
) -> m.SalesInvoice:
    invoice = await get_invoice(db, tenant_id, invoice_id)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail=f"Cannot post invoice in status {invoice.status}")

    items = await list_invoice_items(db, tenant_id, invoice.id)
    if not items:
        raise HTTPException(status_code=400, detail="Cannot post empty invoice")

    customer = await get_customer(db, tenant_id, invoice.customer_id)
    from app.fx import doc_rate, to_base
    from app.credit import enforce_customer_credit_limit

    inv_base = to_base(float(invoice.total_amount), doc_rate(invoice))
    credit_limit = float(customer.credit_limit or 0)
    override_info = enforce_customer_credit_limit(
        customer,
        amount=inv_base,
        override=override_credit_limit,
        override_allowed=credit_override_allowed,
        override_reason=override_reason,
        extra={
            "message": "Posting this invoice would exceed the customer credit limit",
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
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

    if invoice.sales_order_id:
        from app.reservations import consume_order_reservations

        await consume_order_reservations(
            db, tenant_id=tenant_id, order_id=invoice.sales_order_id
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
            unit_id=item.unit_id,
            notes=f"Invoice {invoice.invoice_number}",
            variant_id=item.variant_id,
            warehouse_id=warehouse_id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
        )

    customer.balance = float(customer.balance or 0) + inv_base
    invoice.posted_at = datetime.utcnow()
    invoice.due_date = invoice.due_date or default_due_date(
        invoice.posted_at, party_terms_days(customer)
    )
    apply_invoice_status(invoice, leave_draft=True)
    invoice.updated_at = datetime.utcnow()

    from app.accounting import post_sales_invoice_journal

    await post_sales_invoice_journal(
        db, tenant_id=tenant_id, user_id=user_id, invoice=invoice
    )

    if credit_limit > 0:
        utilization = float(customer.balance or 0) / credit_limit
        if utilization >= 0.8 or override_info:
            from app.notifications import create_notification

            title = "Credit Limit Exceeded" if override_info else "Credit Limit Warning"
            await create_notification(
                db,
                tenant_id=tenant_id,
                category="credit_limit",
                title=title,
                message=(
                    f"{customer.name} credit utilization is {utilization:.0%} "
                    f"({float(customer.balance or 0):.2f} / {credit_limit:.2f})."
                    + (
                        f" Overridden by user on invoice {invoice.invoice_number}."
                        if override_info
                        else ""
                    )
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
    if override_info:
        db.add(
            m.AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                action="credit_limit_override",
                entity="customer",
                entity_id=customer.id,
                details={
                    **override_info,
                    "source": "sales_invoice",
                    "invoice_id": invoice.id,
                    "invoice_number": invoice.invoice_number,
                },
            )
        )
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="invoice_posted",
            entity="sales_invoice",
            entity_id=invoice.id,
            details={
                "invoice_number": invoice.invoice_number,
                "total": float(invoice.total_amount),
                "credit_limit_overridden": bool(override_info),
            },
        )
    )
    # Transient flag for API response (not persisted)
    invoice.credit_limit_overridden = bool(override_info)  # type: ignore[attr-defined]
    return invoice


async def send_sales_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    invoice_id: str,
    to: str | None = None,
) -> tuple[m.SalesInvoice, dict]:
    """Email billed invoice to customer. Marks unpaid invoices as sent when emailed."""
    from app import emailer

    invoice = await get_invoice(db, tenant_id, invoice_id)
    if invoice.status not in SALES_INVOICE_BILLED:
        # Allow status refresh for overdue/sent drift before rejecting
        apply_invoice_status(invoice)
    if invoice.status not in SALES_INVOICE_BILLED:
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
    apply_invoice_status(invoice, as_of=now)
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
        if invoice.status not in SALES_INVOICE_OPEN:
            apply_invoice_status(invoice)
        if invoice.status not in SALES_INVOICE_OPEN:
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
                    m.SalesInvoice.status.in_(list(SALES_INVOICE_OPEN)),
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
        payment_number=await next_customer_payment_number(db, tenant_id),
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
        apply_invoice_status(invoice)
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
