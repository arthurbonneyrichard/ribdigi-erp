"""Customer profile, contacts, and sales history."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

CUSTOMER_TYPES = frozenset({"walk-in", "registered"})
CUSTOMER_STATUSES = frozenset({"active", "inactive"})


def normalize_customer_type(value: str | None, *, required: bool = False) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise HTTPException(status_code=400, detail="party_type is required")
        return None
    normalized = str(value).strip().lower().replace("_", "-")
    if normalized in {"walkin", "walk in"}:
        normalized = "walk-in"
    if normalized not in CUSTOMER_TYPES:
        raise HTTPException(
            status_code=400,
            detail="party_type must be walk-in or registered",
        )
    return normalized


def serialize_contact(row: m.PartyContact) -> dict:
    return {
        "id": row.id,
        "party_id": row.party_id,
        "name": row.name,
        "email": row.email,
        "phone": row.phone,
        "designation": row.designation,
        "is_primary": bool(row.is_primary),
        "created_at": row.created_at,
    }


def serialize_customer(row: m.Party, contacts: list[m.PartyContact] | None = None) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "name": row.name,
        "code": row.code,
        "party_type": row.party_type or "registered",
        "category": row.category,
        "status": row.status or "active",
        "email": row.email,
        "phone": row.phone,
        "address": row.address,
        "notes": row.notes,
        "payment_terms_days": int(row.payment_terms_days or 0),
        "credit_limit": float(row.credit_limit or 0),
        "balance": float(row.balance or 0),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "contacts": [serialize_contact(c) for c in (contacts or [])],
    }


async def get_customer(db: AsyncSession, tenant_id: str, customer_id: str) -> m.Party:
    row = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == customer_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "customer",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return row


async def list_contacts(db: AsyncSession, tenant_id: str, party_id: str) -> list[m.PartyContact]:
    return list(
        (
            await db.execute(
                select(m.PartyContact)
                .where(
                    m.PartyContact.tenant_id == tenant_id,
                    m.PartyContact.party_id == party_id,
                )
                .order_by(m.PartyContact.is_primary.desc(), m.PartyContact.name)
            )
        )
        .scalars()
        .all()
    )


async def assert_customer_code_available(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str | None,
    exclude_id: str | None = None,
) -> str | None:
    if code is None:
        return None
    code = code.strip().upper()
    if not code:
        return None
    stmt = select(m.Party).where(
        m.Party.tenant_id == tenant_id,
        m.Party.kind == "customer",
        m.Party.code == code,
    )
    if exclude_id:
        stmt = stmt.where(m.Party.id != exclude_id)
    if (await db.execute(stmt.limit(1))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Customer code already exists")
    return code


async def create_customer(
    db: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    code: str | None = None,
    party_type: str | None = "registered",
    category: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    notes: str | None = None,
    payment_terms_days: int = 0,
    credit_limit: float = 0,
    contacts: list[dict] | None = None,
) -> m.Party:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    code = await assert_customer_code_available(db, tenant_id=tenant_id, code=code)
    ctype = normalize_customer_type(party_type) or "registered"
    now = datetime.utcnow()
    row = m.Party(
        tenant_id=tenant_id,
        kind="customer",
        name=name,
        code=code,
        party_type=ctype,
        category=(category or "").strip() or None,
        status="active",
        email=str(email).strip() if email else None,
        phone=(phone or "").strip() or None,
        address=(address or "").strip() or None,
        notes=(notes or "").strip() or None,
        payment_terms_days=max(0, int(payment_terms_days or 0)),
        credit_limit=float(credit_limit or 0),
        balance=0,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    await db.flush()
    for contact in contacts or []:
        await add_contact(
            db,
            tenant_id=tenant_id,
            customer_id=row.id,
            name=contact["name"],
            email=contact.get("email"),
            phone=contact.get("phone"),
            designation=contact.get("designation"),
            is_primary=bool(contact.get("is_primary")),
        )
    await db.flush()
    return row


async def update_customer(
    db: AsyncSession,
    *,
    tenant_id: str,
    customer_id: str,
    fields: dict,
) -> m.Party:
    row = await get_customer(db, tenant_id, customer_id)
    if "name" in fields and fields["name"] is not None:
        name = str(fields["name"]).strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if "code" in fields:
        row.code = await assert_customer_code_available(
            db, tenant_id=tenant_id, code=fields["code"], exclude_id=row.id
        )
    if "party_type" in fields:
        ctype = normalize_customer_type(fields["party_type"])
        if ctype is not None:
            row.party_type = ctype
    for key in ("category", "email", "phone", "address", "notes"):
        if key in fields:
            value = fields[key]
            if value is None or (isinstance(value, str) and not value.strip()):
                setattr(row, key, None)
            else:
                setattr(row, key, str(value).strip())
    if "payment_terms_days" in fields and fields["payment_terms_days"] is not None:
        row.payment_terms_days = max(0, int(fields["payment_terms_days"]))
    if "credit_limit" in fields and fields["credit_limit"] is not None:
        row.credit_limit = float(fields["credit_limit"])
    if "status" in fields and fields["status"] is not None:
        status = str(fields["status"]).strip().lower()
        if status not in CUSTOMER_STATUSES:
            raise HTTPException(status_code=400, detail="status must be active or inactive")
        row.status = status
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def deactivate_customer(db: AsyncSession, *, tenant_id: str, customer_id: str) -> m.Party:
    return await update_customer(
        db, tenant_id=tenant_id, customer_id=customer_id, fields={"status": "inactive"}
    )


async def add_contact(
    db: AsyncSession,
    *,
    tenant_id: str,
    customer_id: str,
    name: str,
    email: str | None = None,
    phone: str | None = None,
    designation: str | None = None,
    is_primary: bool = False,
) -> m.PartyContact:
    await get_customer(db, tenant_id, customer_id)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="contact name is required")
    if is_primary:
        existing = await list_contacts(db, tenant_id, customer_id)
        for c in existing:
            c.is_primary = False
    row = m.PartyContact(
        tenant_id=tenant_id,
        party_id=customer_id,
        name=name,
        email=str(email).strip() if email else None,
        phone=(phone or "").strip() or None,
        designation=(designation or "").strip() or None,
        is_primary=bool(is_primary),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def delete_contact(
    db: AsyncSession, *, tenant_id: str, customer_id: str, contact_id: str
) -> None:
    await get_customer(db, tenant_id, customer_id)
    row = await db.get(m.PartyContact, contact_id)
    if row is None or row.tenant_id != tenant_id or row.party_id != customer_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(row)
    await db.flush()


async def customer_history(db: AsyncSession, *, tenant_id: str, customer_id: str) -> dict:
    await get_customer(db, tenant_id, customer_id)
    invoices = list(
        (
            await db.execute(
                select(m.SalesInvoice)
                .where(
                    m.SalesInvoice.tenant_id == tenant_id,
                    m.SalesInvoice.customer_id == customer_id,
                )
                .order_by(m.SalesInvoice.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    quotations = list(
        (
            await db.execute(
                select(m.SalesQuotation)
                .where(
                    m.SalesQuotation.tenant_id == tenant_id,
                    m.SalesQuotation.customer_id == customer_id,
                )
                .order_by(m.SalesQuotation.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    orders = list(
        (
            await db.execute(
                select(m.SalesOrder)
                .where(
                    m.SalesOrder.tenant_id == tenant_id,
                    m.SalesOrder.customer_id == customer_id,
                )
                .order_by(m.SalesOrder.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    returns = list(
        (
            await db.execute(
                select(m.SalesReturn)
                .where(
                    m.SalesReturn.tenant_id == tenant_id,
                    m.SalesReturn.customer_id == customer_id,
                )
                .order_by(m.SalesReturn.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    payments = list(
        (
            await db.execute(
                select(m.CustomerPayment)
                .where(
                    m.CustomerPayment.tenant_id == tenant_id,
                    m.CustomerPayment.customer_id == customer_id,
                )
                .order_by(m.CustomerPayment.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return {
        "customer_id": customer_id,
        "invoices": [
            {
                "id": i.id,
                "invoice_number": i.invoice_number,
                "status": i.status,
                "total_amount": float(i.total_amount or 0),
                "created_at": i.created_at,
            }
            for i in invoices
        ],
        "quotations": [
            {
                "id": q.id,
                "quotation_number": q.quotation_number,
                "status": q.status,
                "total_amount": float(q.total_amount or 0),
                "created_at": q.created_at,
            }
            for q in quotations
        ],
        "orders": [
            {
                "id": o.id,
                "order_number": o.order_number,
                "status": o.status,
                "total_amount": float(o.total_amount or 0),
                "created_at": o.created_at,
            }
            for o in orders
        ],
        "returns": [
            {
                "id": r.id,
                "return_number": r.return_number,
                "status": r.status,
                "total_amount": float(r.total_amount or 0),
                "created_at": r.created_at,
            }
            for r in returns
        ],
        "payments": [
            {
                "id": p.id,
                "amount": float(p.amount or 0),
                "payment_method": p.payment_method,
                "created_at": p.created_at,
            }
            for p in payments
        ],
    }
