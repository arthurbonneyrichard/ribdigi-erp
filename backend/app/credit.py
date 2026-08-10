"""Credit limits, AR/AP aging, and statements."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

DEFAULT_PAYMENT_TERMS_DAYS = 30
AGING_BUCKETS = ("current", "1_30", "31_60", "61_90", "90_plus")


def early_pay_settings(tenant: m.Tenant) -> dict:
    pct = float(getattr(tenant, "early_pay_discount_pct", None) or 0)
    days = int(getattr(tenant, "early_pay_discount_days", None) or 0)
    return {
        "early_pay_discount_pct": pct,
        "early_pay_discount_days": days,
        "enabled": pct > 0 and days > 0,
        "source": "tenant",
    }


def resolve_early_pay_settings(tenant: m.Tenant, party: m.Party | None = None) -> dict:
    """Prefer party early-pay override when either field is set; otherwise tenant defaults."""
    tenant_ep = early_pay_settings(tenant)
    if party is None:
        return tenant_ep
    pct_raw = getattr(party, "early_pay_discount_pct", None)
    days_raw = getattr(party, "early_pay_discount_days", None)
    if pct_raw is None and days_raw is None:
        return tenant_ep
    pct = float(pct_raw or 0)
    days = int(days_raw or 0)
    if pct < 0 or pct > 100:
        raise HTTPException(status_code=400, detail="early_pay_discount_pct must be between 0 and 100")
    if days < 0 or days > 365:
        raise HTTPException(status_code=400, detail="early_pay_discount_days must be between 0 and 365")
    return {
        "early_pay_discount_pct": pct,
        "early_pay_discount_days": days,
        "enabled": pct > 0 and days > 0,
        "source": "supplier" if party.kind == "supplier" else "party",
    }


def invoice_early_discount(
    invoice: m.SalesInvoice,
    *,
    pct: float,
    days: int,
    as_of: datetime | None = None,
) -> dict:
    """Return eligibility and discount amounts for settling an open invoice early."""
    as_of = as_of or datetime.utcnow()
    due = max(float(invoice.total_amount) - float(invoice.paid_amount or 0), 0)
    result = {
        "eligible": False,
        "discount_amount": 0.0,
        "cash_to_settle": round(due, 2),
        "balance_due": round(due, 2),
        "days_since_post": None,
        "window_days": days,
        "discount_pct": pct,
    }
    if due <= 0 or pct <= 0 or days <= 0:
        return result
    if invoice.status not in {"posted", "partial"}:
        return result
    anchor = invoice.posted_at or invoice.created_at or as_of
    age = (as_of.date() - anchor.date()).days
    result["days_since_post"] = age
    if age < 0 or age > days:
        return result
    discount = round(due * pct / 100.0, 2)
    result["eligible"] = discount > 0
    result["discount_amount"] = discount
    result["cash_to_settle"] = round(max(due - discount, 0), 2)
    return result


def purchase_invoice_early_discount(
    invoice: m.PurchaseInvoice,
    *,
    pct: float,
    days: int,
    as_of: datetime | None = None,
) -> dict:
    """Buyer take-discount quote for settling an open purchase invoice early."""
    as_of = as_of or datetime.utcnow()
    due = max(float(invoice.total_amount) - float(invoice.paid_amount or 0), 0)
    result = {
        "eligible": False,
        "discount_amount": 0.0,
        "cash_to_settle": round(due, 2),
        "balance_due": round(due, 2),
        "days_since_approve": None,
        "window_days": days,
        "discount_pct": pct,
    }
    if due <= 0 or pct <= 0 or days <= 0:
        return result
    if invoice.status not in {"unpaid", "partial", "overdue"}:
        return result
    anchor = invoice.approved_at or invoice.invoice_date or invoice.created_at or as_of
    age = (as_of.date() - anchor.date()).days
    result["days_since_approve"] = age
    if age < 0 or age > days:
        return result
    discount = round(due * pct / 100.0, 2)
    result["eligible"] = discount > 0
    result["discount_amount"] = discount
    result["cash_to_settle"] = round(max(due - discount, 0), 2)
    return result


def days_overdue(as_of: datetime, due_date: datetime | None, fallback: datetime | None = None) -> int:
    anchor = due_date or fallback or as_of
    delta = (as_of.date() - anchor.date()).days
    return max(delta, 0)


def age_bucket(days: int) -> str:
    if days <= 0:
        return "current"
    if days <= 30:
        return "1_30"
    if days <= 60:
        return "31_60"
    if days <= 90:
        return "61_90"
    return "90_plus"


def empty_buckets() -> dict[str, float]:
    return {k: 0.0 for k in AGING_BUCKETS}


def add_to_bucket(buckets: dict[str, float], days: int, amount: float) -> None:
    key = age_bucket(days)
    buckets[key] = round(buckets.get(key, 0.0) + float(amount), 2)


async def ar_aging(db: AsyncSession, tenant_id: str, as_of: datetime | None = None) -> dict:
    as_of = as_of or datetime.utcnow()
    invoices = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(["posted", "partial"]),
            )
        )
    ).scalars().all()
    customers = {
        p.id: p
        for p in (
            await db.execute(
                select(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer")
            )
        ).scalars().all()
    }

    by_customer: dict[str, dict] = {}
    totals = empty_buckets()
    documents = []

    for inv in invoices:
        due = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        days = days_overdue(as_of, inv.due_date, inv.posted_at or inv.created_at)
        bucket = age_bucket(days)
        add_to_bucket(totals, days, due)
        cust = customers.get(inv.customer_id)
        row = by_customer.setdefault(
            inv.customer_id,
            {
                "party_id": inv.customer_id,
                "name": cust.name if cust else inv.customer_id,
                "credit_limit": float(cust.credit_limit or 0) if cust else 0,
                "balance": float(cust.balance or 0) if cust else 0,
                "total_due": 0.0,
                **empty_buckets(),
            },
        )
        row["total_due"] = round(row["total_due"] + due, 2)
        row[bucket] = round(row[bucket] + due, 2)
        documents.append(
            {
                "id": inv.id,
                "document_number": inv.invoice_number,
                "party_id": inv.customer_id,
                "party_name": row["name"],
                "due_date": inv.due_date,
                "balance_due": due,
                "currency": getattr(inv, "currency", None) or "",
                "exchange_rate": float(getattr(inv, "exchange_rate", None) or 1),
                "balance_due_base": round(
                    due * float(getattr(inv, "exchange_rate", None) or 1), 2
                ),
                "days_overdue": days,
                "bucket": bucket,
            }
        )

    return {
        "as_of": as_of,
        "kind": "receivable",
        "totals": totals,
        "total_due": round(sum(totals.values()), 2),
        "parties": sorted(by_customer.values(), key=lambda x: x["total_due"], reverse=True),
        "documents": documents,
    }


async def ap_aging(db: AsyncSession, tenant_id: str, as_of: datetime | None = None) -> dict:
    as_of = as_of or datetime.utcnow()
    invoices = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.tenant_id == tenant_id,
                m.PurchaseInvoice.status.in_(["unpaid", "partial", "overdue"]),
            )
        )
    ).scalars().all()
    invoiced_po_ids = {i.purchase_order_id for i in invoices if i.purchase_order_id}

    orders = (
        await db.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == tenant_id,
                m.PurchaseOrder.status.in_(["sent", "partially_received", "received"]),
            )
        )
    ).scalars().all()
    suppliers = {
        p.id: p
        for p in (
            await db.execute(
                select(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "supplier")
            )
        ).scalars().all()
    }

    by_supplier: dict[str, dict] = {}
    totals = empty_buckets()
    documents = []

    def _party_row(supplier_id: str) -> dict:
        sup = suppliers.get(supplier_id)
        return by_supplier.setdefault(
            supplier_id,
            {
                "party_id": supplier_id,
                "name": sup.name if sup else supplier_id,
                "credit_limit": float(sup.credit_limit or 0) if sup else 0,
                "balance": float(sup.balance or 0) if sup else 0,
                "total_due": 0.0,
                **empty_buckets(),
            },
        )

    for inv in invoices:
        due = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        days = days_overdue(as_of, inv.due_date, inv.invoice_date or inv.created_at)
        bucket = age_bucket(days)
        add_to_bucket(totals, days, due)
        row = _party_row(inv.supplier_id)
        row["total_due"] = round(row["total_due"] + due, 2)
        row[bucket] = round(row[bucket] + due, 2)
        documents.append(
            {
                "id": inv.id,
                "document_number": inv.invoice_number,
                "document_type": "purchase_invoice",
                "party_id": inv.supplier_id,
                "party_name": row["name"],
                "due_date": inv.due_date,
                "balance_due": due,
                "currency": getattr(inv, "currency", None) or "",
                "exchange_rate": float(getattr(inv, "exchange_rate", None) or 1),
                "balance_due_base": round(
                    due * float(getattr(inv, "exchange_rate", None) or 1), 2
                ),
                "days_overdue": days,
                "bucket": bucket,
            }
        )

    # Stage 11 C1 — uninvoiced AP exposure = accepted GRN value (not full PO total).
    from app.purchasing import po_received_accepted_value

    for po in orders:
        if po.id in invoiced_po_ids:
            continue
        received_value = await po_received_accepted_value(db, tenant_id, po.id)
        due = max(float(received_value) - float(po.paid_amount or 0), 0)
        if due <= 0:
            continue
        days = days_overdue(as_of, po.due_date, po.created_at)
        bucket = age_bucket(days)
        add_to_bucket(totals, days, due)
        row = _party_row(po.supplier_id)
        row["total_due"] = round(row["total_due"] + due, 2)
        row[bucket] = round(row[bucket] + due, 2)
        documents.append(
            {
                "id": po.id,
                "document_number": po.po_number,
                "document_type": "purchase_order",
                "party_id": po.supplier_id,
                "party_name": row["name"],
                "due_date": po.due_date,
                "balance_due": due,
                "received_value": received_value,
                "days_overdue": days,
                "bucket": bucket,
            }
        )

    return {
        "as_of": as_of,
        "kind": "payable",
        "totals": totals,
        "total_due": round(sum(totals.values()), 2),
        "parties": sorted(by_supplier.values(), key=lambda x: x["total_due"], reverse=True),
        "documents": documents,
    }


async def customer_outstanding_bills(
    db: AsyncSession, tenant_id: str, customer_id: str
) -> list[dict]:
    """Open AR invoices for a customer (Stage 8 S2 / BR-11.1)."""
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

    invoices = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.customer_id == customer_id,
                m.SalesInvoice.status.in_(["posted", "partial", "sent", "overdue"]),
            )
        )
    ).scalars().all()
    rows: list[dict] = []
    for inv in invoices:
        due = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        rows.append(
            {
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": round(due, 2),
                "due_date": inv.due_date,
                "status": inv.status,
                "document_type": "sales_invoice",
            }
        )
    rows.sort(
        key=lambda r: (
            r["due_date"] is None,
            r["due_date"] or datetime.max,
            -float(r["amount"]),
        )
    )
    return rows


async def customer_statement(db: AsyncSession, tenant_id: str, customer_id: str) -> dict:
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

    invoices = (
        await db.execute(
            select(m.SalesInvoice)
            .where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.customer_id == customer_id,
            )
            .order_by(m.SalesInvoice.created_at.asc())
        )
    ).scalars().all()
    payments = (
        await db.execute(
            select(m.CustomerPayment)
            .where(
                m.CustomerPayment.tenant_id == tenant_id,
                m.CustomerPayment.customer_id == customer_id,
            )
            .order_by(m.CustomerPayment.created_at.asc())
        )
    ).scalars().all()

    lines = []
    for inv in invoices:
        lines.append(
            {
                "date": inv.posted_at or inv.created_at,
                "type": "invoice",
                "reference": inv.invoice_number,
                "debit": float(inv.total_amount) if inv.status != "cancelled" else 0,
                "credit": 0,
                "status": inv.status,
                "balance_due": max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
                if inv.status in {"posted", "partial"}
                else 0,
            }
        )
    for pay in payments:
        lines.append(
            {
                "date": pay.created_at,
                "type": "payment",
                "reference": pay.payment_number,
                "debit": 0,
                "credit": float(pay.amount),
                "status": "posted",
                "balance_due": None,
            }
        )
    lines.sort(key=lambda x: x["date"] or datetime.utcnow())
    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "credit_limit": float(customer.credit_limit or 0),
            "balance": float(customer.balance or 0),
        },
        "lines": lines,
    }


async def supplier_statement(db: AsyncSession, tenant_id: str, supplier_id: str) -> dict:
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

    orders = (
        await db.execute(
            select(m.PurchaseOrder)
            .where(
                m.PurchaseOrder.tenant_id == tenant_id,
                m.PurchaseOrder.supplier_id == supplier_id,
            )
            .order_by(m.PurchaseOrder.created_at.asc())
        )
    ).scalars().all()
    payments = (
        await db.execute(
            select(m.SupplierPayment)
            .where(
                m.SupplierPayment.tenant_id == tenant_id,
                m.SupplierPayment.supplier_id == supplier_id,
            )
            .order_by(m.SupplierPayment.created_at.asc())
        )
    ).scalars().all()

    lines = []
    for po in orders:
        if po.status == "cancelled":
            continue
        lines.append(
            {
                "date": po.created_at,
                "type": "purchase_order",
                "reference": po.po_number,
                "debit": 0,
                "credit": float(po.total_amount),
                "status": po.status,
                "balance_due": max(float(po.total_amount) - float(po.paid_amount or 0), 0),
            }
        )
    for pay in payments:
        lines.append(
            {
                "date": pay.created_at,
                "type": "payment",
                "reference": pay.payment_number,
                "debit": float(pay.amount),
                "credit": 0,
                "status": "posted",
                "balance_due": None,
            }
        )
    lines.sort(key=lambda x: x["date"] or datetime.utcnow())
    return {
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "balance": float(supplier.balance or 0),
        },
        "lines": lines,
    }


async def supplier_payment_schedule(
    db: AsyncSession,
    tenant_id: str,
    supplier_id: str,
    *,
    as_of: datetime | None = None,
) -> dict:
    """Upcoming/overdue AP schedule for a supplier (Stage 8 S1 / BR-11.2)."""
    as_of = as_of or datetime.utcnow()
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

    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    ep = resolve_early_pay_settings(tenant, supplier)

    invoices = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.tenant_id == tenant_id,
                m.PurchaseInvoice.supplier_id == supplier_id,
                m.PurchaseInvoice.status.in_(["unpaid", "partial", "overdue"]),
            )
        )
    ).scalars().all()
    orders = (
        await db.execute(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == tenant_id,
                m.PurchaseOrder.supplier_id == supplier_id,
                m.PurchaseOrder.status.in_(["sent", "partially_received", "received"]),
            )
        )
    ).scalars().all()

    items: list[dict] = []
    for inv in invoices:
        due_amt = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due_amt <= 0:
            continue
        due_dt = inv.due_date
        if due_dt is None:
            days_until = None
            is_overdue = False
            bucket = "unscheduled"
        else:
            days_until = (due_dt.date() - as_of.date()).days
            is_overdue = days_until < 0
            if is_overdue:
                bucket = "overdue"
            elif days_until == 0:
                bucket = "due_today"
            else:
                bucket = "upcoming"
        quote = purchase_invoice_early_discount(
            inv,
            pct=ep["early_pay_discount_pct"],
            days=ep["early_pay_discount_days"],
            as_of=as_of,
        )
        items.append(
            {
                "document_type": "purchase_invoice",
                "purchase_invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "purchase_order_id": inv.purchase_order_id,
                "amount": round(due_amt, 2),
                "due_date": due_dt,
                "status": inv.status,
                "days_until_due": days_until,
                "is_overdue": is_overdue,
                "schedule_bucket": bucket,
                "early_discount": quote,
            }
        )

    invoiced_pos = {i.purchase_order_id for i in invoices if i.purchase_order_id}
    for po in orders:
        if po.id in invoiced_pos:
            continue
        due_amt = max(float(po.total_amount) - float(po.paid_amount or 0), 0)
        if due_amt <= 0:
            continue
        due_dt = po.due_date
        if due_dt is None:
            days_until = None
            is_overdue = False
            bucket = "unscheduled"
        else:
            days_until = (due_dt.date() - as_of.date()).days
            is_overdue = days_until < 0
            if is_overdue:
                bucket = "overdue"
            elif days_until == 0:
                bucket = "due_today"
            else:
                bucket = "upcoming"
        items.append(
            {
                "document_type": "purchase_order",
                "purchase_order_id": po.id,
                "po_number": po.po_number,
                "amount": round(due_amt, 2),
                "due_date": due_dt,
                "status": po.status,
                "days_until_due": days_until,
                "is_overdue": is_overdue,
                "schedule_bucket": bucket,
                "early_discount": None,
            }
        )

    def _sort_key(row: dict):
        due = row.get("due_date")
        # Overdue first (most overdue), then due today, then upcoming, unscheduled last
        if due is None:
            return (3, datetime.max, -float(row["amount"]))
        days = row.get("days_until_due")
        if days is not None and days < 0:
            return (0, due, -float(row["amount"]))
        if days == 0:
            return (1, due, -float(row["amount"]))
        return (2, due, -float(row["amount"]))

    items.sort(key=_sort_key)
    total_due = round(sum(float(i["amount"]) for i in items), 2)
    overdue_total = round(
        sum(float(i["amount"]) for i in items if i["schedule_bucket"] == "overdue"), 2
    )
    upcoming_total = round(
        sum(
            float(i["amount"])
            for i in items
            if i["schedule_bucket"] in {"due_today", "upcoming"}
        ),
        2,
    )
    return {
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "as_of": as_of.date().isoformat(),
        "total_due": total_due,
        "overdue_total": overdue_total,
        "upcoming_total": upcoming_total,
        "early_pay": ep,
        "items": items,
    }


def default_due_date(from_dt: datetime | None = None, terms_days: int = DEFAULT_PAYMENT_TERMS_DAYS) -> datetime:
    return (from_dt or datetime.utcnow()) + timedelta(days=terms_days)


def credit_limit_projection(customer: m.Party, additional_amount: float) -> dict:
    """Return credit utilization projection for an additional AR amount (base currency)."""
    limit = float(customer.credit_limit or 0)
    balance = float(customer.balance or 0)
    add = round(float(additional_amount or 0), 2)
    projected = round(balance + add, 2)
    exceeded = limit > 0 and projected > limit + 1e-9
    return {
        "credit_limit": limit,
        "current_balance": balance,
        "additional_amount": add,
        "projected_balance": projected,
        "exceeded": exceeded,
        "available": round(max(limit - balance, 0), 2) if limit > 0 else None,
    }


async def enforce_credit_limit(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    role: str,
    permissions: dict | None,
    customer: m.Party,
    additional_amount: float,
    override: bool = False,
    override_reason: str | None = None,
    entity: str,
    entity_id: str | None,
    module: str = "credit",
    extra_details: dict | None = None,
    record_audit: bool = True,
) -> dict:
    """Block over-limit credit unless caller has credit:approve and supplies a reason.

    Returns projection dict. When override is applied, records an audit event
    (unless ``record_audit`` is False — caller will record with a final entity id).
    """
    from app.rbac import has_permission
    from app import audit as audit_svc

    projection = credit_limit_projection(customer, additional_amount)
    if not projection["exceeded"]:
        return {**projection, "overridden": False}

    detail = {
        "code": "CREDIT_LIMIT_EXCEEDED",
        "message": "This sale would exceed the customer credit limit",
        **projection,
        **(extra_details or {}),
    }

    if not override:
        raise HTTPException(status_code=409, detail=detail)

    reason = (override_reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "CREDIT_OVERRIDE_REASON_REQUIRED",
                "message": "credit_override_reason is required (min 3 characters) to override the credit limit",
            },
        )

    if not has_permission(role, "credit", "approve", overrides=permissions):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "CREDIT_OVERRIDE_FORBIDDEN",
                "message": "Missing permission: credit:approve",
            },
        )

    if record_audit:
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="credit_limit_override",
            entity=entity,
            entity_id=entity_id,
            module=module,
            details={
                "customer_id": customer.id,
                "customer_name": customer.name,
                "reason": reason,
                **projection,
                **(extra_details or {}),
            },
        )
    return {**projection, "overridden": True, "override_reason": reason}
