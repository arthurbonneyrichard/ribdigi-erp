"""Credit limits, AR/AP aging, and statements."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import has_permission

DEFAULT_PAYMENT_TERMS_DAYS = 30
AGING_BUCKETS = ("current", "1_30", "31_60", "61_90", "90_plus")


def claims_may_override_credit(claims: dict) -> bool:
    role = claims.get("role", "") or ""
    perms = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    return has_permission(role, "credit", "approve", overrides=perms)


def enforce_customer_credit_limit(
    customer: m.Party,
    *,
    amount: float,
    override: bool = False,
    override_allowed: bool = False,
    override_reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Block sales that would exceed credit limit unless an authorized override is supplied.

    Returns override audit payload when an override was applied; otherwise None.
    ``credit_limit <= 0`` means unlimited (no enforcement).
    """
    credit_limit = float(customer.credit_limit or 0)
    if credit_limit <= 0:
        return None
    amount = float(amount or 0)
    if amount <= 0:
        return None
    current = float(customer.balance or 0)
    projected = current + amount
    if projected <= credit_limit + 1e-9:
        return None

    detail: dict[str, Any] = {
        "code": "CREDIT_LIMIT_EXCEEDED",
        "message": "This sale would exceed the customer credit limit",
        "credit_limit": credit_limit,
        "current_balance": current,
        "amount": amount,
        "projected_balance": round(projected, 2),
        "over_by": round(projected - credit_limit, 2),
        "customer_id": customer.id,
        "customer_name": customer.name,
    }
    if extra:
        detail.update(extra)

    if not override:
        raise HTTPException(status_code=409, detail=detail)

    if not override_allowed:
        raise HTTPException(
            status_code=403,
            detail={
                **detail,
                "code": "CREDIT_OVERRIDE_FORBIDDEN",
                "message": "Credit limit override requires credit:approve permission",
            },
        )

    reason = (override_reason or "").strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail={
                **detail,
                "code": "CREDIT_OVERRIDE_REASON_REQUIRED",
                "message": "override_reason is required when override_credit_limit is true",
            },
        )
    return {
        "customer_id": customer.id,
        "customer_name": customer.name,
        "credit_limit": credit_limit,
        "current_balance": current,
        "amount": amount,
        "projected_balance": round(projected, 2),
        "over_by": round(projected - credit_limit, 2),
        "reason": reason,
    }


def early_pay_settings(tenant: m.Tenant) -> dict:
    pct = float(getattr(tenant, "early_pay_discount_pct", None) or 0)
    days = int(getattr(tenant, "early_pay_discount_days", None) or 0)
    return {
        "early_pay_discount_pct": pct,
        "early_pay_discount_days": days,
        "enabled": pct > 0 and days > 0,
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
    if invoice.status not in {"posted", "sent", "partial", "overdue"}:
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
                m.SalesInvoice.status.in_(["posted", "sent", "partial", "overdue"]),
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

    for po in orders:
        if po.id in invoiced_po_ids:
            continue
        due = max(float(po.total_amount) - float(po.paid_amount or 0), 0)
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
                if inv.status in {"posted", "sent", "partial", "overdue"}
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


async def customer_history(
    db: AsyncSession,
    tenant_id: str,
    customer_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    """Purchase / return / payment history for a customer (BR-7.1)."""
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

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.customer_id == customer_id,
    )
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.created_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.created_at <= to_date)
    inv_stmt = inv_stmt.order_by(m.SalesInvoice.created_at.desc())
    invoices = (await db.execute(inv_stmt)).scalars().all()

    ret_stmt = select(m.SalesReturn).where(
        m.SalesReturn.tenant_id == tenant_id,
        m.SalesReturn.customer_id == customer_id,
    )
    if from_date:
        ret_stmt = ret_stmt.where(m.SalesReturn.created_at >= from_date)
    if to_date:
        ret_stmt = ret_stmt.where(m.SalesReturn.created_at <= to_date)
    ret_stmt = ret_stmt.order_by(m.SalesReturn.created_at.desc())
    returns = (await db.execute(ret_stmt)).scalars().all()

    pay_stmt = select(m.CustomerPayment).where(
        m.CustomerPayment.tenant_id == tenant_id,
        m.CustomerPayment.customer_id == customer_id,
    )
    if from_date:
        pay_stmt = pay_stmt.where(m.CustomerPayment.created_at >= from_date)
    if to_date:
        pay_stmt = pay_stmt.where(m.CustomerPayment.created_at <= to_date)
    pay_stmt = pay_stmt.order_by(m.CustomerPayment.created_at.desc())
    payments = (await db.execute(pay_stmt)).scalars().all()

    pos_stmt = select(m.Transaction).where(
        m.Transaction.tenant_id == tenant_id,
        m.Transaction.tx_type == "pos_sale",
        m.Transaction.party_id == customer_id,
    )
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    pos_stmt = pos_stmt.order_by(m.Transaction.created_at.desc())
    pos_rows = (await db.execute(pos_stmt)).scalars().all()

    purchase_rows: list[dict] = []
    for inv in invoices:
        purchase_rows.append(
            {
                "id": inv.id,
                "type": "invoice",
                "reference": inv.invoice_number,
                "status": inv.status,
                "subtotal": float(inv.subtotal or 0),
                "tax_amount": float(inv.tax_amount or 0),
                "total_amount": float(inv.total_amount or 0),
                "paid_amount": float(inv.paid_amount or 0),
                "posted_at": inv.posted_at,
                "created_at": inv.created_at,
            }
        )
    for tx in pos_rows:
        purchase_rows.append(
            {
                "id": tx.id,
                "type": "pos",
                "reference": tx.reference,
                "status": tx.status,
                "subtotal": float(tx.subtotal or 0),
                "tax_amount": float(tx.tax or 0),
                "total_amount": float(tx.total or 0),
                "paid_amount": float(tx.total or 0),
                "posted_at": tx.created_at,
                "created_at": tx.created_at,
            }
        )
    purchase_rows.sort(key=lambda x: x["created_at"] or datetime.utcnow(), reverse=True)

    return_rows = [
        {
            "id": r.id,
            "return_number": r.return_number,
            "credit_note_number": r.credit_note_number,
            "status": r.status,
            "reason": r.reason,
            "total_amount": float(r.total_amount or 0),
            "refunded_amount": float(r.refunded_amount or 0),
            "settlement_method": r.settlement_method,
            "sales_invoice_id": r.sales_invoice_id,
            "posted_at": r.posted_at,
            "created_at": r.created_at,
        }
        for r in returns
    ]
    payment_rows = [
        {
            "id": p.id,
            "payment_number": p.payment_number,
            "amount": float(p.amount or 0),
            "payment_method": p.payment_method,
            "sales_invoice_id": p.sales_invoice_id,
            "reference": p.reference,
            "created_at": p.created_at,
        }
        for p in payments
    ]

    purchase_total = round(sum(x["total_amount"] for x in purchase_rows), 2)
    return_total = round(sum(x["total_amount"] for x in return_rows), 2)
    payment_total = round(sum(x["amount"] for x in payment_rows), 2)
    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "credit_limit": float(customer.credit_limit or 0),
            "balance": float(customer.balance or 0),
        },
        "from_date": from_date,
        "to_date": to_date,
        "purchases": purchase_rows,
        "returns": return_rows,
        "payments": payment_rows,
        "summary": {
            "purchase_count": len(purchase_rows),
            "purchase_total": purchase_total,
            "return_count": len(return_rows),
            "return_total": return_total,
            "payment_count": len(payment_rows),
            "payment_total": payment_total,
        },
    }


async def supplier_history(
    db: AsyncSession,
    tenant_id: str,
    supplier_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> dict:
    """Purchase / return / payment history for a supplier (BR-6.1)."""
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

    po_stmt = select(m.PurchaseOrder).where(
        m.PurchaseOrder.tenant_id == tenant_id,
        m.PurchaseOrder.supplier_id == supplier_id,
    )
    if from_date:
        po_stmt = po_stmt.where(m.PurchaseOrder.created_at >= from_date)
    if to_date:
        po_stmt = po_stmt.where(m.PurchaseOrder.created_at <= to_date)
    po_stmt = po_stmt.order_by(m.PurchaseOrder.created_at.desc())
    orders = (await db.execute(po_stmt)).scalars().all()

    pi_stmt = select(m.PurchaseInvoice).where(
        m.PurchaseInvoice.tenant_id == tenant_id,
        m.PurchaseInvoice.supplier_id == supplier_id,
    )
    if from_date:
        pi_stmt = pi_stmt.where(m.PurchaseInvoice.created_at >= from_date)
    if to_date:
        pi_stmt = pi_stmt.where(m.PurchaseInvoice.created_at <= to_date)
    pi_stmt = pi_stmt.order_by(m.PurchaseInvoice.created_at.desc())
    invoices = (await db.execute(pi_stmt)).scalars().all()

    ret_stmt = select(m.PurchaseReturn).where(
        m.PurchaseReturn.tenant_id == tenant_id,
        m.PurchaseReturn.supplier_id == supplier_id,
    )
    if from_date:
        ret_stmt = ret_stmt.where(m.PurchaseReturn.created_at >= from_date)
    if to_date:
        ret_stmt = ret_stmt.where(m.PurchaseReturn.created_at <= to_date)
    ret_stmt = ret_stmt.order_by(m.PurchaseReturn.created_at.desc())
    returns = (await db.execute(ret_stmt)).scalars().all()

    pay_stmt = select(m.SupplierPayment).where(
        m.SupplierPayment.tenant_id == tenant_id,
        m.SupplierPayment.supplier_id == supplier_id,
    )
    if from_date:
        pay_stmt = pay_stmt.where(m.SupplierPayment.created_at >= from_date)
    if to_date:
        pay_stmt = pay_stmt.where(m.SupplierPayment.created_at <= to_date)
    pay_stmt = pay_stmt.order_by(m.SupplierPayment.created_at.desc())
    payments = (await db.execute(pay_stmt)).scalars().all()

    purchase_rows: list[dict] = []
    for po in orders:
        purchase_rows.append(
            {
                "id": po.id,
                "type": "purchase_order",
                "reference": po.po_number,
                "status": po.status,
                "total_amount": float(po.total_amount or 0),
                "paid_amount": float(po.paid_amount or 0),
                "created_at": po.created_at,
            }
        )
    for inv in invoices:
        purchase_rows.append(
            {
                "id": inv.id,
                "type": "purchase_invoice",
                "reference": inv.invoice_number,
                "status": inv.status,
                "total_amount": float(inv.total_amount or 0),
                "paid_amount": float(inv.paid_amount or 0),
                "created_at": inv.created_at,
            }
        )
    purchase_rows.sort(key=lambda x: x["created_at"] or datetime.utcnow(), reverse=True)

    return_rows = [
        {
            "id": r.id,
            "return_number": r.return_number,
            "debit_note_number": r.debit_note_number,
            "status": r.status,
            "reason": r.reason,
            "total_amount": float(r.total_amount or 0),
            "purchase_order_id": r.purchase_order_id,
            "goods_receipt_id": r.goods_receipt_id,
            "posted_at": r.posted_at,
            "created_at": r.created_at,
        }
        for r in returns
    ]
    payment_rows = [
        {
            "id": p.id,
            "payment_number": p.payment_number,
            "amount": float(p.amount or 0),
            "payment_method": p.payment_method,
            "purchase_order_id": p.purchase_order_id,
            "purchase_invoice_id": p.purchase_invoice_id,
            "reference": p.reference,
            "created_at": p.created_at,
        }
        for p in payments
    ]

    purchase_total = round(sum(x["total_amount"] for x in purchase_rows), 2)
    return_total = round(sum(x["total_amount"] for x in return_rows), 2)
    payment_total = round(sum(x["amount"] for x in payment_rows), 2)
    return {
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "balance": float(supplier.balance or 0),
            "payment_terms_days": getattr(supplier, "payment_terms_days", None),
        },
        "from_date": from_date,
        "to_date": to_date,
        "purchases": purchase_rows,
        "returns": return_rows,
        "payments": payment_rows,
        "summary": {
            "purchase_count": len(purchase_rows),
            "purchase_total": purchase_total,
            "return_count": len(return_rows),
            "return_total": return_total,
            "payment_count": len(payment_rows),
            "payment_total": payment_total,
        },
    }


async def customer_credit_info(db: AsyncSession, tenant_id: str, customer_id: str) -> dict:
    """Real-time customer balance + credit limit snapshot (BR-7.1)."""
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
                m.SalesInvoice.status.in_(["posted", "sent", "partial", "overdue"]),
            )
            .order_by(m.SalesInvoice.due_date.asc().nulls_last(), m.SalesInvoice.created_at.asc())
        )
    ).scalars().all()

    credit_sales: list[dict] = []
    open_invoice_total = 0.0
    for inv in invoices:
        due = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        open_invoice_total += due
        credit_sales.append(
            {
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "amount": round(due, 2),
                "total_amount": float(inv.total_amount or 0),
                "paid_amount": float(inv.paid_amount or 0),
                "due_date": inv.due_date,
                "status": inv.status,
            }
        )

    credit_limit = float(customer.credit_limit or 0)
    outstanding = float(customer.balance or 0)
    # Prefer live party balance; fall back to open invoice sum if balance unset/stale at 0
    if abs(outstanding) < 1e-9 and open_invoice_total > 0:
        outstanding = round(open_invoice_total, 2)
    unlimited = credit_limit <= 0
    available = None if unlimited else round(max(credit_limit - outstanding, 0), 2)
    over_limit = (not unlimited) and outstanding > credit_limit + 1e-9

    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "payment_terms_days": getattr(customer, "payment_terms_days", None),
        },
        "credit_limit": credit_limit,
        "credit_unlimited": unlimited,
        "outstanding_balance": round(outstanding, 2),
        "available_credit": available,
        "is_over_limit": over_limit,
        "open_invoice_count": len(credit_sales),
        "open_invoice_total": round(open_invoice_total, 2),
        "credit_sales": credit_sales,
    }


async def supplier_credit_info(db: AsyncSession, tenant_id: str, supplier_id: str) -> dict:
    """Real-time supplier payable balance snapshot (BR-6.1)."""
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

    open_bills: list[dict] = []
    open_total = 0.0
    for inv in invoices:
        due = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        open_total += due
        open_bills.append(
            {
                "document_type": "purchase_invoice",
                "purchase_invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "purchase_order_id": inv.purchase_order_id,
                "amount": round(due, 2),
                "due_date": inv.due_date,
                "status": inv.status,
            }
        )
    invoiced_pos = {i.purchase_order_id for i in invoices if i.purchase_order_id}
    for po in orders:
        if po.id in invoiced_pos:
            continue
        due = max(float(po.total_amount) - float(po.paid_amount or 0), 0)
        if due <= 0:
            continue
        open_total += due
        open_bills.append(
            {
                "document_type": "purchase_order",
                "purchase_order_id": po.id,
                "po_number": po.po_number,
                "amount": round(due, 2),
                "due_date": po.due_date,
                "status": po.status,
            }
        )

    outstanding = float(supplier.balance or 0)
    if abs(outstanding) < 1e-9 and open_total > 0:
        outstanding = round(open_total, 2)

    return {
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "email": getattr(supplier, "email", None),
            "phone": getattr(supplier, "phone", None),
            "payment_terms_days": getattr(supplier, "payment_terms_days", None),
        },
        "outstanding_balance": round(outstanding, 2),
        "open_bill_count": len(open_bills),
        "open_bill_total": round(open_total, 2),
        "open_bills": open_bills,
    }


async def supplier_payment_schedule(
    db: AsyncSession,
    tenant_id: str,
    supplier_id: str,
    *,
    as_of: datetime | None = None,
) -> dict:
    """Upcoming / overdue AP documents for a supplier (BR-11.2), sorted by due date."""
    from app.purchasing import PURCHASE_INVOICE_OPEN, refresh_overdue_purchase_invoices

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

    await refresh_overdue_purchase_invoices(db, tenant_id, as_of=as_of)

    invoices = (
        await db.execute(
            select(m.PurchaseInvoice).where(
                m.PurchaseInvoice.tenant_id == tenant_id,
                m.PurchaseInvoice.supplier_id == supplier_id,
                m.PurchaseInvoice.status.in_(list(PURCHASE_INVOICE_OPEN)),
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
    invoiced_pos = {i.purchase_order_id for i in invoices if i.purchase_order_id}

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one_or_none()
    ep = early_pay_settings(tenant) if tenant else {"enabled": False}

    items: list[dict] = []
    for inv in invoices:
        balance = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if balance <= 0:
            continue
        overdue_days = days_overdue(as_of, inv.due_date, inv.invoice_date or inv.created_at)
        days_until = None
        if inv.due_date:
            days_until = (inv.due_date.date() - as_of.date()).days
        early = None
        if ep.get("enabled"):
            quote = purchase_invoice_early_discount(
                inv,
                pct=float(ep["early_pay_discount_pct"]),
                days=int(ep["early_pay_discount_days"]),
                as_of=as_of,
            )
            if quote.get("eligible"):
                early = {
                    "discount_amount": quote.get("discount_amount"),
                    "cash_to_settle": quote.get("cash_to_settle"),
                    "window_days": quote.get("window_days"),
                    "discount_pct": quote.get("discount_pct"),
                }
        items.append(
            {
                "document_type": "purchase_invoice",
                "id": inv.id,
                "document_number": inv.invoice_number,
                "purchase_order_id": inv.purchase_order_id,
                "due_date": inv.due_date,
                "balance_due": round(balance, 2),
                "status": inv.status,
                "days_until_due": days_until,
                "days_overdue": overdue_days,
                "currency": getattr(inv, "currency", None) or "",
                "early_discount": early,
            }
        )

    for po in orders:
        if po.id in invoiced_pos:
            continue
        balance = max(float(po.total_amount) - float(po.paid_amount or 0), 0)
        if balance <= 0:
            continue
        overdue_days = days_overdue(as_of, po.due_date, po.created_at)
        days_until = None
        if po.due_date:
            days_until = (po.due_date.date() - as_of.date()).days
        items.append(
            {
                "document_type": "purchase_order",
                "id": po.id,
                "document_number": po.po_number,
                "purchase_order_id": po.id,
                "due_date": po.due_date,
                "balance_due": round(balance, 2),
                "status": po.status,
                "days_until_due": days_until,
                "days_overdue": overdue_days,
                "currency": "",
                "early_discount": None,
            }
        )

    def _sort_key(row: dict):
        due = row.get("due_date")
        if due is None:
            return (1, datetime.max, row.get("document_number") or "")
        return (0, due, row.get("document_number") or "")

    items.sort(key=_sort_key)
    upcoming = [r for r in items if (r.get("days_until_due") is None or r["days_until_due"] >= 0)]
    overdue = [r for r in items if r.get("days_until_due") is not None and r["days_until_due"] < 0]

    return {
        "as_of": as_of,
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "balance": float(supplier.balance or 0),
        },
        "total_due": round(sum(r["balance_due"] for r in items), 2),
        "overdue_count": len(overdue),
        "upcoming_count": len(upcoming),
        "items": items,
    }


def party_terms_days(party: m.Party | None) -> int:
    """Net payment terms in days for a customer/supplier (0 = due on receipt)."""
    if party is None:
        return DEFAULT_PAYMENT_TERMS_DAYS
    raw = getattr(party, "payment_terms_days", None)
    if raw is None:
        return DEFAULT_PAYMENT_TERMS_DAYS
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PAYMENT_TERMS_DAYS
    return max(0, days)


def default_due_date(from_dt: datetime | None = None, terms_days: int = DEFAULT_PAYMENT_TERMS_DAYS) -> datetime:
    return (from_dt or datetime.utcnow()) + timedelta(days=max(0, int(terms_days)))
