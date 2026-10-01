"""Sales invoice and customer payment business logic."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.tax import resolve_product_tax
from app.credit import default_due_date, party_terms_days
from app.catalog import resolve_sale_line, stock_out_with_batch
from app.doc_numbers import next_customer_payment_number, next_sales_invoice_number


SALES_INVOICE_OPEN = frozenset({"posted", "sent", "partial", "overdue"})
SALES_INVOICE_BILLED = frozenset({"posted", "sent", "partial", "paid", "overdue"})
# Manage list statuses (draft + billed + cancelled).
SI_MANAGE_STATUSES = frozenset(
    {"draft", "posted", "sent", "partial", "paid", "overdue", "cancelled"}
)


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
    if paid + 1e-9 >= money_json(total):
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
        money_json(invoice.total_amount),
        money_json(invoice.paid_amount or 0),
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


async def require_active_customer(db: AsyncSession, tenant_id: str, customer_id: str) -> m.Party:
    """Resolve customer for new sales documents; inactive customers cannot be newly assigned."""
    customer = await get_customer(db, tenant_id, customer_id)
    status = (getattr(customer, "status", None) or "active").strip().lower()
    if status != "active":
        raise HTTPException(status_code=400, detail="Customer is inactive")
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
            money_json(invoice.total_amount),
            money_json(invoice.paid_amount),
            invoice.due_date,
            emailed_at=invoice.emailed_at,
        )
    from app.credit import days_overdue

    overdue_days = 0
    if status == "overdue" or (
        invoice.due_date
        and status in SALES_INVOICE_OPEN
        and money_json(invoice.paid_amount) + 1e-9 < money_json(invoice.total_amount)
    ):
        overdue_days = days_overdue(datetime.utcnow(), invoice.due_date, invoice.posted_at or invoice.created_at)
    balance_due = max(money_json(invoice.total_amount) - money_json(invoice.paid_amount), 0)
    fx = money_json(getattr(invoice, "exchange_rate", None), default=1.0)
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "store_id": invoice.store_id,
        "status": status,
        "subtotal": money_json(invoice.subtotal),
        "tax_amount": money_json(invoice.tax_amount),
        "reverse_charge_tax": money_json(getattr(invoice, "reverse_charge_tax", 0) or 0),
        "is_reverse_charge": bool(getattr(invoice, "is_reverse_charge", False)),
        "discount_amount": money_json(invoice.discount_amount),
        "discount_type": getattr(invoice, "discount_type", None) or "fixed",
        "discount_percent": money_json(getattr(invoice, "discount_percent", None) or 0),
        "coupon_id": getattr(invoice, "coupon_id", None),
        "total_amount": money_json(invoice.total_amount),
        "paid_amount": money_json(invoice.paid_amount),
        "balance_due": balance_due,
        "currency": getattr(invoice, "currency", None) or "",
        "exchange_rate": fx,
        "balance_due_base": money_json(round(balance_due * fx, 2)),
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
                "quantity": money_json(i.quantity),
                "unit_id": i.unit_id,
                "unit_price": money_json(i.unit_price),
                "tax_rate": money_json(i.tax_rate),
                "tax_supply_class": getattr(i, "tax_supply_class", None) or "standard",
                "discount": money_json(i.discount),
                "discount_type": getattr(i, "discount_type", None) or "fixed",
                "discount_percent": money_json(getattr(i, "discount_percent", None) or 0),
                "line_subtotal": money_json(getattr(i, "line_subtotal", None) or 0),
                "line_tax": money_json(_line_tax_value(i)),
                "is_reverse_charge": bool(getattr(i, "is_reverse_charge", False)),
                "tax_components": getattr(i, "tax_components", None) or None,
                "line_total": money_json(i.line_total),
            }
            for i in items
        ],
    }


def _line_tax_value(item: m.SalesInvoiceItem) -> float:
    """Persisted line_tax, with legacy backfill when column is still 0 but rate > 0."""
    stored = money_json(getattr(item, "line_tax", None))
    if stored > 0 or bool(getattr(item, "is_reverse_charge", False)):
        return stored
    if getattr(item, "tax_components", None) is not None:
        return stored
    rate = money_json(item.tax_rate)
    if rate <= 0:
        return money_json(0)
    sub = money_json(getattr(item, "line_subtotal", None))
    total = money_json(item.line_total)
    discount = money_json(item.discount)
    derived = money_json(round(total - sub + discount, 2))
    if derived < 0:
        return money_json(round(sub * rate / 100.0, 2))
    return derived


def _invoice_tax_breakdown(items: list[m.SalesInvoiceItem], invoice: m.SalesInvoice) -> dict:
    by_rate: dict[str, dict] = {}
    component_totals: dict[str, dict] = {}
    line_rows: list[dict] = []
    for i in items:
        line_tax = _line_tax_value(i)
        is_rc = bool(getattr(i, "is_reverse_charge", False))
        rate = money_json(i.tax_rate or 0)
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
        bucket["taxable"] = money_json(
            round(
                bucket["taxable"] + money_json(getattr(i, "line_subtotal", None) or 0), 2
            )
        )
        bucket["tax"] = money_json(round(bucket["tax"] + money_json(line_tax), 2))
        comps = getattr(i, "tax_components", None) or []
        for c in comps:
            cname = str(c.get("name") or c.get("code") or "component")
            cb = component_totals.setdefault(cname, {"name": cname, "tax": 0.0})
            cb["tax"] = money_json(round(cb["tax"] + money_json(c.get("amount") or 0), 2))
        line_rows.append(
            {
                "item_id": i.id,
                "product_id": i.product_id,
                "tax_rate": rate,
                "line_subtotal": money_json(getattr(i, "line_subtotal", None) or 0),
                "line_tax": money_json(line_tax),
                "is_reverse_charge": is_rc,
                "tax_components": comps or None,
            }
        )
    return {
        "lines": line_rows,
        "by_rate": sorted(by_rate.values(), key=lambda r: (-r["tax_rate"], r["is_reverse_charge"])),
        "by_component": sorted(component_totals.values(), key=lambda r: r["name"]),
        "tax_amount": money_json(invoice.tax_amount or 0),
        "reverse_charge_tax": money_json(getattr(invoice, "reverse_charge_tax", 0) or 0),
    }


async def create_sales_invoice(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    customer_id: str,
    items: list[dict],
    discount_amount: float = 0,
    discount_type: str | None = "fixed",
    discount_percent: float = 0,
    notes: str | None = None,
    store_id: str | None = None,
    currency: str | None = None,
    exchange_rate: float | None = None,
    is_reverse_charge: bool = False,
    coupon_code: str | None = None,
) -> m.SalesInvoice:
    if not items:
        raise HTTPException(status_code=400, detail="Invoice requires at least one line item")
    await require_active_customer(db, tenant_id, customer_id)

    from app.fx import resolve_rate

    cur, rate = await resolve_rate(db, tenant_id, currency, explicit_rate=exchange_rate)

    resolved_store_id = None
    if store_id:
        from app import stores as stores_svc

        store = await stores_svc.require_active_store(db, tenant_id, store_id)
        from app import store_access as store_access_svc

        await store_access_svc.assert_store_access(
            db, tenant_id=tenant_id, user_id=user_id, store_id=store.id
        )
        resolved_store_id = store.id

    from app.uom import resolve_line_unit
    from app.sale_discounts import resolve_discount

    header_rc = bool(is_reverse_charge)
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
            quantity=money_json(item["quantity"]),
        )
        explicit = item.get("tax_rate")
        if explicit is not None:
            spec = await resolve_product_tax(
                db, tenant_id, product, explicit_rate=money_json(explicit)
            )
        else:
            spec = await resolve_product_tax(db, tenant_id, product, explicit_rate=None)
        line_amount = money_json(round(qty * money_json(unit_price), 2))
        discount, line_disc_type, line_disc_pct = resolve_discount(
            base_amount=line_amount,
            discount=item.get("discount") or 0,
            discount_type=item.get("discount_type") or "fixed",
            discount_percent=item.get("discount_percent") or 0,
            label="Line discount",
        )
        if discount <= 0:
            try:
                from app import fmcg as fmcg_svc
                from app import packages as packages_svc
                from app import tenants as tenants_svc

                tenant = await tenants_svc.get_tenant(db, tenant_id)
                if packages_svc.module_allowed(tenant, "fmcg"):
                    scheme_disc, _meta = await fmcg_svc.best_line_scheme_discount(
                        db,
                        tenant_id=tenant_id,
                        product_id=product.id,
                        line_qty=float(qty),
                        line_amount=float(line_amount),
                    )
                    if scheme_disc > 0:
                        discount = money_json(min(scheme_disc, line_amount))
                        line_disc_type = "fixed"
                        line_disc_pct = 0
            except Exception:
                pass
        taxable_base = money_json(round(line_amount - discount, 2))
        breakdown = spec.compute_breakdown(taxable_base)
        line_sub = money_json(breakdown["net"])
        line_tax = money_json(breakdown["tax"])
        line_is_rc = header_rc or bool(spec.is_reverse_charge)
        if line_is_rc:
            line_total = line_sub
        else:
            line_total = money_json(breakdown["gross"])
        subtotal += line_sub
        if line_is_rc:
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
                    "discount_type": line_disc_type,
                    "discount_percent": line_disc_pct,
                    "tax_rate": spec.rate_pct,
                    "tax_supply_class": spec.supply_class,
                    "line_subtotal": line_sub,
                    "line_tax": line_tax,
                    "is_reverse_charge": line_is_rc,
                    "tax_components": list(breakdown.get("components") or []) or None,
                },
                line_total,
            )
        )

    header_base = money_json(round(subtotal + tax_total, 2))
    coupon_id = None
    coupon_meta = None
    if coupon_code and str(coupon_code).strip():
        from app import coupons as coupons_svc

        product_ids = [p[0]["product_id"] for p in prepared]
        cat_ids = []
        for p, _lt in prepared:
            prod = await db.get(m.Product, p["product_id"])
            if prod and prod.category_id:
                cat_ids.append(prod.category_id)
        coupon_meta = await coupons_svc.apply_coupon(
            db,
            tenant_id=tenant_id,
            code=coupon_code,
            header_base=header_base,
            product_ids=product_ids,
            category_ids=cat_ids,
            customer_id=customer_id,
        )
        discount_amount = coupon_meta["discount_amount"]
        discount_type = coupon_meta["discount_type"]
        discount_percent = coupon_meta["discount_percent"]
        coupon_id = coupon_meta["coupon_id"]
    discount_amount, header_disc_type, header_disc_pct = resolve_discount(
        base_amount=header_base,
        discount=discount_amount or 0,
        discount_type=discount_type,
        discount_percent=discount_percent or 0,
        label="Sale discount",
    )
    total = max(header_base - discount_amount, 0)

    invoice = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number=await next_sales_invoice_number(db, tenant_id),
        customer_id=customer_id,
        status="draft",
        subtotal=subtotal,
        tax_amount=tax_total,
        reverse_charge_tax=money_json(round(reverse_charge_tax, 2)),
        is_reverse_charge=header_rc,
        discount_amount=discount_amount,
        discount_type=header_disc_type,
        discount_percent=header_disc_pct,
        total_amount=total,
        paid_amount=0,
        currency=cur,
        exchange_rate=rate,
        notes=optional_honest_narrative(notes, label="sales invoice notes"),
        created_by=user_id,
        store_id=resolved_store_id,
        coupon_id=coupon_id,
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
                discount_type=item.get("discount_type") or "fixed",
                discount_percent=item.get("discount_percent") or 0,
                line_subtotal=item.get("line_subtotal") or 0,
                line_tax=item.get("line_tax") or 0,
                is_reverse_charge=bool(item.get("is_reverse_charge")),
                tax_components=item.get("tax_components"),
                line_total=line_total,
            )
        )

    if coupon_meta:
        from app import coupons as coupons_svc

        await coupons_svc.record_redemption(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            coupon_id=coupon_meta["coupon_id"],
            amount=discount_amount,
            customer_id=customer_id,
            source_type="sales_invoice",
            source_id=invoice.id,
        )

    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="invoice_created",
            entity="sales_invoice",
            entity_id=invoice.id,
            details={
                "invoice_number": invoice.invoice_number,
                "total": money_json(invoice.total_amount),
                "is_reverse_charge": header_rc,
            },
        )
    )
    return invoice


async def open_ar_from_pos_sale(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    customer: m.Party,
    tx: m.Transaction,
    priced_items: list[dict],
    subtotal: float,
    tax_amount: float,
    total: float,
    paid_amount: float,
    cart_discount: float = 0,
    cart_disc_type: str = "fixed",
    cart_disc_pct: float = 0,
    coupon_id: str | None = None,
    store_id: str | None = None,
) -> m.SalesInvoice:
    """Open the existing AR invoice for a POS on-account tender.

    Does not post a second sales journal or move stock — POS already did both.
    Does not change ``customer.balance``; the POS path increments it by the credit tender.
    """
    from app.credit import default_due_date, party_terms_days
    from app.doc_numbers import next_sales_invoice_number
    from app.fx import resolve_rate

    invoice_total = money_json(round(money_json(total or 0), 2))
    collected = money_json(round(min(money_json(paid_amount or 0), invoice_total), 2))
    if invoice_total <= 0 or collected + 1e-9 >= invoice_total:
        raise HTTPException(status_code=400, detail="POS credit invoice requires an outstanding balance")
    lines = [row for row in (priced_items or []) if row.get("product_id")]
    if not lines:
        raise HTTPException(status_code=400, detail="POS credit invoice requires at least one product line")

    tenant = await db.get(m.Tenant, tenant_id)
    cur, rate = await resolve_rate(
        db, tenant_id, getattr(tenant, "currency", None) if tenant else None
    )
    now = datetime.utcnow()
    invoice = m.SalesInvoice(
        tenant_id=tenant_id,
        invoice_number=await next_sales_invoice_number(db, tenant_id),
        customer_id=customer.id,
        status="posted",
        subtotal=money_json(subtotal),
        tax_amount=money_json(tax_amount),
        discount_amount=money_json(cart_discount),
        discount_type=cart_disc_type or "fixed",
        discount_percent=money_json(cart_disc_pct or 0),
        total_amount=invoice_total,
        paid_amount=collected,
        currency=cur,
        exchange_rate=rate,
        notes=optional_honest_narrative(
            f"POS {tx.reference}", label="sales invoice notes"
        ),
        created_by=user_id,
        store_id=store_id,
        posted_at=now,
        due_date=default_due_date(now, party_terms_days(customer)),
        coupon_id=coupon_id,
    )
    db.add(invoice)
    await db.flush()
    for item in lines:
        db.add(
            m.SalesInvoiceItem(
                tenant_id=tenant_id,
                sales_invoice_id=invoice.id,
                product_id=item["product_id"],
                variant_id=item.get("variant_id"),
                quantity=money_json(item.get("quantity") or 0),
                unit_id=item.get("unit_id"),
                unit_price=money_json(item.get("unit_price") or 0),
                tax_rate=money_json(item.get("tax_rate") or 0),
                tax_supply_class=item.get("tax_supply_class") or "standard",
                discount=money_json(item.get("discount") or 0),
                discount_type=item.get("discount_type") or "fixed",
                discount_percent=money_json(item.get("discount_percent") or 0),
                line_subtotal=money_json(item.get("line_subtotal") or 0),
                line_tax=money_json(item.get("line_tax") or 0),
                is_reverse_charge=bool(item.get("is_reverse_charge")),
                tax_components=item.get("tax_components"),
                line_total=money_json(item.get("line_total") or 0),
            )
        )
    apply_invoice_status(invoice, leave_draft=True, as_of=now)
    invoice.updated_at = now
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="invoice_created",
            entity="sales_invoice",
            entity_id=invoice.id,
            details={
                "invoice_number": invoice.invoice_number,
                "total": money_json(invoice.total_amount),
                "paid_amount": money_json(invoice.paid_amount),
                "source": "pos_sale",
                "transaction_id": tx.id,
                "reference": tx.reference,
            },
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

    inv_base = to_base(money_json(invoice.total_amount), doc_rate(invoice))
    credit_limit = money_json(customer.credit_limit or 0)
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
            "invoice_total": money_json(invoice.total_amount),
            "invoice_total_base": money_json(inv_base),
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
            quantity=money_json(item.quantity),
            unit_id=item.unit_id,
            notes=f"Invoice {invoice.invoice_number}",
            variant_id=item.variant_id,
            warehouse_id=warehouse_id,
            reference_type="sales_invoice",
            reference_id=invoice.id,
        )

    customer.balance = money_json(customer.balance or 0) + inv_base
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
        utilization = money_json(customer.balance or 0) / credit_limit
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
                    f"({money_json(customer.balance or 0):.2f} / {credit_limit:.2f})."
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
        message=f"Invoice {invoice.invoice_number} posted for {money_json(invoice.total_amount):.2f}.",
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
                "total": money_json(invoice.total_amount),
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
        tenant=tenant,
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
    reason: str | None = None,
) -> m.SalesInvoice:
    reason_s = require_honest_narrative(reason, label="cancel reason")
    invoice = await get_invoice(db, tenant_id, invoice_id)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft invoices can be cancelled")
    invoice.status = "cancelled"
    invoice.notes = ((invoice.notes or "") + f"\nCancel: {reason_s}").strip()
    invoice.updated_at = datetime.utcnow()
    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="invoice_cancelled",
            entity="sales_invoice",
            entity_id=invoice.id,
            details={"invoice_number": invoice.invoice_number, "reason": reason_s},
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
    from app.expenses import normalize_expense_payment_method

    amount = money_json(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be positive")
    payment_method = normalize_expense_payment_method(payment_method, default="cash")

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
        due = money_json(invoice.total_amount) - money_json(invoice.paid_amount or 0)
        quote = invoice_early_discount(
            invoice, pct=ep["early_pay_discount_pct"], days=ep["early_pay_discount_days"]
        )
        if use_discount and quote["eligible"] and amount + 1e-9 >= quote["cash_to_settle"]:
            if amount > due + 1e-9:
                raise HTTPException(status_code=409, detail="Payment exceeds invoice balance due")
            if amount + 1e-9 >= due:
                allocations.append((invoice, min(amount, due), 0.0))
            else:
                discount = money_json(round(due - amount, 2))
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
            due = money_json(invoice.total_amount) - money_json(invoice.paid_amount or 0)
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
                total_discount = money_json(round(total_discount + discount, 2))
                remaining = money_json(round(remaining - cash_used, 2))
            else:
                apply_amt = min(remaining, due)
                allocations.append((invoice, apply_amt, 0.0))
                remaining = money_json(round(remaining - apply_amt, 2))
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
            pay_rate = money_json(exchange_rate)
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
    settlement_base = money_json(round(
        sum(to_base(amt, doc_rate(inv)) for inv, amt, _ in allocations),
        2,
    ))
    payment = m.CustomerPayment(
        tenant_id=tenant_id,
        payment_number=await next_customer_payment_number(db, tenant_id),
        customer_id=customer_id,
        sales_invoice_id=sales_invoice_id or primary_invoice_id,
        amount=amount,
        payment_method=payment_method,
        early_payment_discount=money_json(round(total_discount, 2)),
        currency=pay_cur,
        exchange_rate=pay_rate,
        liquid_account_id=liquid_account_id,
        reference=optional_honest_narrative(
            reference, label="payment reference", max_length=100
        ),
        notes=optional_honest_narrative(notes, label="payment notes")
        or (
            f"Auto-allocated: {alloc_note}"
            if alloc_note and not sales_invoice_id
            else (f"Early discount {total_discount:.2f}" if total_discount else None)
        ),
        created_by=user_id,
    )
    db.add(payment)

    # AR balance reduced by base settlement (invoice rates)
    customer.balance = max(money_json(customer.balance or 0) - settlement_base, 0)
    for invoice, apply_amt, _disc in allocations:
        invoice.paid_amount = money_json(invoice.paid_amount or 0) + apply_amt
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
                "amount": money_json(amount),
                "early_payment_discount": money_json(total_discount),
                "currency": pay_cur,
                "exchange_rate": money_json(pay_rate),
                "fx_gain_loss": money_json(getattr(payment, "fx_gain_loss", 0) or 0),
                "customer_id": customer_id,
                "invoice_id": sales_invoice_id,
                "allocations": [
                    {
                        "invoice_id": inv.id,
                        "amount": money_json(amt),
                        "discount": money_json(disc),
                    }
                    for inv, amt, disc in allocations
                ],
            },
        )
    )
    from app import webhooks as webhooks_svc

    await webhooks_svc.emit_event(
        db,
        tenant_id=tenant_id,
        event="sale.paid",
        data={
            "payment_id": payment.id,
            "payment_number": payment.payment_number,
            "amount": money_json(payment.amount or 0),
            "customer_id": customer_id,
            "sales_invoice_id": payment.sales_invoice_id,
            "currency": pay_cur,
            "invoice_statuses": [
                {
                    "invoice_id": inv.id,
                    "status": inv.status,
                    "amount_applied": money_json(amt),
                }
                for inv, amt, _disc in allocations
            ],
        },
    )
    return payment
