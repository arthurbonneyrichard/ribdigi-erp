"""Supplier profile, contacts, and purchase history."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m


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


def serialize_supplier(row: m.Party, contacts: list[m.PartyContact] | None = None) -> dict:
    pct = getattr(row, "early_pay_discount_pct", None)
    days = getattr(row, "early_pay_discount_days", None)
    return {
        "id": row.id,
        "kind": row.kind,
        "name": row.name,
        "code": row.code,
        "party_type": row.party_type,
        "category": row.category,
        "status": row.status or "active",
        "email": row.email,
        "phone": row.phone,
        "address": row.address,
        "notes": row.notes,
        "payment_terms_days": int(row.payment_terms_days or 0),
        "early_pay_discount_pct": None if pct is None else float(pct),
        "early_pay_discount_days": None if days is None else int(days),
        "credit_limit": float(row.credit_limit or 0),
        "balance": float(row.balance or 0),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "contacts": [serialize_contact(c) for c in (contacts or [])],
    }


def _coerce_early_pay_override(
    pct: float | None, days: int | None
) -> tuple[float | None, int | None]:
    """None/None means inherit tenant; otherwise store concrete override values."""
    if pct is None and days is None:
        return None, None
    out_pct = float(pct or 0)
    out_days = int(days or 0)
    if out_pct < 0 or out_pct > 100:
        raise HTTPException(status_code=400, detail="early_pay_discount_pct must be between 0 and 100")
    if out_days < 0 or out_days > 365:
        raise HTTPException(status_code=400, detail="early_pay_discount_days must be between 0 and 365")
    return out_pct, out_days


async def get_supplier(db: AsyncSession, tenant_id: str, supplier_id: str) -> m.Party:
    row = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == supplier_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == "supplier",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
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


async def assert_supplier_code_available(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str | None,
    exclude_id: str | None = None,
    company_id: str | None = None,
) -> str | None:
    if code is None:
        return None
    code = code.strip().upper()
    if not code:
        return None
    stmt = select(m.Party).where(
        m.Party.tenant_id == tenant_id,
        m.Party.kind == "supplier",
        m.Party.code == code,
    )
    if company_id:
        stmt = stmt.where(m.Party.company_id == company_id)
    if exclude_id:
        stmt = stmt.where(m.Party.id != exclude_id)
    if (await db.execute(stmt.limit(1))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Supplier code already exists")
    return code


async def create_supplier(
    db: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    code: str | None = None,
    party_type: str | None = None,
    category: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    notes: str | None = None,
    payment_terms_days: int = 0,
    early_pay_discount_pct: float | None = None,
    early_pay_discount_days: int | None = None,
    credit_limit: float = 0,
    contacts: list[dict] | None = None,
    company_id: str | None = None,
) -> m.Party:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    code = await assert_supplier_code_available(
        db, tenant_id=tenant_id, code=code, company_id=company_id
    )
    ep_pct, ep_days = _coerce_early_pay_override(early_pay_discount_pct, early_pay_discount_days)
    now = datetime.utcnow()
    row = m.Party(
        tenant_id=tenant_id,
        company_id=company_id,
        kind="supplier",
        name=name,
        code=code,
        party_type=(party_type or "").strip() or None,
        category=(category or "").strip() or None,
        status="active",
        email=str(email).strip() if email else None,
        phone=(phone or "").strip() or None,
        address=(address or "").strip() or None,
        notes=(notes or "").strip() or None,
        payment_terms_days=max(0, int(payment_terms_days or 0)),
        early_pay_discount_pct=ep_pct,
        early_pay_discount_days=ep_days,
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
            supplier_id=row.id,
            name=contact["name"],
            email=contact.get("email"),
            phone=contact.get("phone"),
            designation=contact.get("designation"),
            is_primary=bool(contact.get("is_primary")),
        )
    await db.flush()
    return row


async def update_supplier(
    db: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
    fields: dict,
) -> m.Party:
    row = await get_supplier(db, tenant_id, supplier_id)
    if "name" in fields and fields["name"] is not None:
        name = str(fields["name"]).strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if "code" in fields:
        row.code = await assert_supplier_code_available(
            db,
            tenant_id=tenant_id,
            code=fields["code"],
            exclude_id=row.id,
            company_id=getattr(row, "company_id", None),
        )
    for key in ("party_type", "category", "email", "phone", "address", "notes"):
        if key in fields:
            value = fields[key]
            if value is None or (isinstance(value, str) and not value.strip()):
                setattr(row, key, None)
            else:
                setattr(row, key, str(value).strip() if key != "email" else str(value).strip())
    if "payment_terms_days" in fields and fields["payment_terms_days"] is not None:
        row.payment_terms_days = max(0, int(fields["payment_terms_days"]))
    if "early_pay_discount_pct" in fields or "early_pay_discount_days" in fields:
        pct = (
            fields["early_pay_discount_pct"]
            if "early_pay_discount_pct" in fields
            else getattr(row, "early_pay_discount_pct", None)
        )
        days = (
            fields["early_pay_discount_days"]
            if "early_pay_discount_days" in fields
            else getattr(row, "early_pay_discount_days", None)
        )
        ep_pct, ep_days = _coerce_early_pay_override(pct, days)
        row.early_pay_discount_pct = ep_pct
        row.early_pay_discount_days = ep_days
    if "credit_limit" in fields and fields["credit_limit"] is not None:
        row.credit_limit = float(fields["credit_limit"])
    if "status" in fields and fields["status"] is not None:
        status = str(fields["status"]).strip().lower()
        if status not in {"active", "inactive"}:
            raise HTTPException(status_code=400, detail="status must be active or inactive")
        row.status = status
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def deactivate_supplier(db: AsyncSession, *, tenant_id: str, supplier_id: str) -> m.Party:
    return await update_supplier(
        db, tenant_id=tenant_id, supplier_id=supplier_id, fields={"status": "inactive"}
    )


async def add_contact(
    db: AsyncSession,
    *,
    tenant_id: str,
    supplier_id: str,
    name: str,
    email: str | None = None,
    phone: str | None = None,
    designation: str | None = None,
    is_primary: bool = False,
) -> m.PartyContact:
    party = await get_supplier(db, tenant_id, supplier_id)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="contact name is required")
    if is_primary:
        existing = await list_contacts(db, tenant_id, supplier_id)
        for c in existing:
            c.is_primary = False
    row = m.PartyContact(
        tenant_id=tenant_id,
        company_id=getattr(party, "company_id", None),
        party_id=supplier_id,
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
    db: AsyncSession, *, tenant_id: str, supplier_id: str, contact_id: str
) -> None:
    await get_supplier(db, tenant_id, supplier_id)
    row = await db.get(m.PartyContact, contact_id)
    if row is None or row.tenant_id != tenant_id or row.party_id != supplier_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    await db.delete(row)
    await db.flush()


async def supplier_history(
    db: AsyncSession, *, tenant_id: str, supplier_id: str, company_id: str | None = None
) -> dict:
    await get_supplier(db, tenant_id, supplier_id)

    def _scoped(model):
        clauses = [model.tenant_id == tenant_id]
        if company_id and hasattr(model, "company_id"):
            clauses.append(model.company_id == company_id)
        return clauses

    orders = list(
        (
            await db.execute(
                select(m.PurchaseOrder)
                .where(
                    *_scoped(m.PurchaseOrder),
                    m.PurchaseOrder.supplier_id == supplier_id,
                )
                .order_by(m.PurchaseOrder.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    invoices = list(
        (
            await db.execute(
                select(m.PurchaseInvoice)
                .where(
                    *_scoped(m.PurchaseInvoice),
                    m.PurchaseInvoice.supplier_id == supplier_id,
                )
                .order_by(m.PurchaseInvoice.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    returns = list(
        (
            await db.execute(
                select(m.PurchaseReturn)
                .where(
                    *_scoped(m.PurchaseReturn),
                    m.PurchaseReturn.supplier_id == supplier_id,
                )
                .order_by(m.PurchaseReturn.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    payments = list(
        (
            await db.execute(
                select(m.SupplierPayment)
                .where(
                    *_scoped(m.SupplierPayment),
                    m.SupplierPayment.supplier_id == supplier_id,
                )
                .order_by(m.SupplierPayment.created_at.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return {
        "supplier_id": supplier_id,
        "orders": [
            {
                "id": o.id,
                "po_number": o.po_number,
                "status": o.status,
                "total_amount": float(o.total_amount or 0),
                "created_at": o.created_at,
            }
            for o in orders
        ],
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
