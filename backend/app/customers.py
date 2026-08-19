"""Customer profile, groups, GPS, contacts, and sales history."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

CUSTOMER_TYPES = frozenset({"walk-in", "registered"})
CUSTOMER_STATUSES = frozenset({"active", "inactive"})

DEFAULT_CUSTOMER_GROUPS = (
    ("Retail", 0),
    ("Wholesale", 10),
    ("VIP", 15),
)


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


def normalize_gps(
    latitude: float | None,
    longitude: float | None,
    *,
    partial_ok: bool = False,
) -> tuple[float | None, float | None]:
    """Validate GPS; require both coordinates when either is provided."""
    lat_missing = latitude is None
    lon_missing = longitude is None
    if lat_missing and lon_missing:
        return None, None
    if lat_missing or lon_missing:
        if partial_ok:
            return (
                None if lat_missing else float(latitude),
                None if lon_missing else float(longitude),
            )
        raise HTTPException(
            status_code=400,
            detail="latitude and longitude must both be set or both cleared",
        )
    lat = float(latitude)
    lon = float(longitude)
    if lat < -90 or lat > 90:
        raise HTTPException(status_code=400, detail="latitude must be between -90 and 90")
    if lon < -180 or lon > 180:
        raise HTTPException(status_code=400, detail="longitude must be between -180 and 180")
    return lat, lon


def serialize_contact(row: m.PartyContact) -> dict:
    return {
        "id": row.id,
        "company_id": getattr(row, "company_id", None),
        "party_id": row.party_id,
        "name": row.name,
        "email": row.email,
        "phone": row.phone,
        "designation": row.designation,
        "is_primary": bool(row.is_primary),
        "created_at": row.created_at,
    }


def serialize_group(row: m.CustomerGroup) -> dict:
    return {
        "id": row.id,
        "company_id": getattr(row, "company_id", None),
        "name": row.name,
        "discount_percent": float(row.discount_percent or 0),
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


def serialize_customer(
    row: m.Party,
    contacts: list[m.PartyContact] | None = None,
    group: m.CustomerGroup | None = None,
) -> dict:
    active_group = group if group is not None and bool(group.is_active) else None
    return {
        "id": row.id,
        "company_id": getattr(row, "company_id", None),
        "kind": row.kind,
        "name": row.name,
        "code": row.code,
        "party_type": row.party_type or "registered",
        "category": row.category,
        "customer_group_id": row.customer_group_id,
        "customer_group": serialize_group(group) if group is not None else None,
        "customer_group_name": group.name if group is not None else None,
        "group_discount_percent": float(active_group.discount_percent or 0) if active_group else 0.0,
        "status": row.status or "active",
        "email": row.email,
        "phone": row.phone,
        "address": row.address,
        "latitude": float(row.latitude) if row.latitude is not None else None,
        "longitude": float(row.longitude) if row.longitude is not None else None,
        "notes": row.notes,
        "payment_terms_days": int(row.payment_terms_days or 0),
        "credit_limit": float(row.credit_limit or 0),
        "balance": float(row.balance or 0),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "contacts": [serialize_contact(c) for c in (contacts or [])],
    }


async def ensure_default_customer_groups(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> None:
    q = select(m.CustomerGroup.id).where(m.CustomerGroup.tenant_id == tenant_id)
    if company_id:
        q = q.where(m.CustomerGroup.company_id == company_id)
    existing = (await db.execute(q.limit(1))).scalar_one_or_none()
    if existing:
        return
    now = datetime.utcnow()
    for name, discount in DEFAULT_CUSTOMER_GROUPS:
        db.add(
            m.CustomerGroup(
                tenant_id=tenant_id,
                company_id=company_id,
                name=name,
                discount_percent=discount,
                is_active=True,
                created_at=now,
            )
        )
    await db.flush()


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


async def get_customer_group(
    db: AsyncSession,
    tenant_id: str,
    group_id: str,
    *,
    active_only: bool = False,
    company_id: str | None = None,
) -> m.CustomerGroup:
    from app.workspace import assert_fk_company

    row = (
        await db.execute(
            select(m.CustomerGroup).where(
                m.CustomerGroup.id == group_id,
                m.CustomerGroup.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Customer group not found")
    assert_fk_company(row, company_id, detail="Customer group not found")
    if active_only and not row.is_active:
        raise HTTPException(status_code=409, detail="Customer group is inactive")
    return row


async def load_group_map(
    db: AsyncSession, tenant_id: str, group_ids: list[str]
) -> dict[str, m.CustomerGroup]:
    ids = [gid for gid in set(group_ids) if gid]
    if not ids:
        return {}
    rows = (
        await db.execute(
            select(m.CustomerGroup).where(
                m.CustomerGroup.tenant_id == tenant_id,
                m.CustomerGroup.id.in_(ids),
            )
        )
    ).scalars().all()
    return {r.id: r for r in rows}


async def resolve_group_ref(
    db: AsyncSession,
    tenant_id: str,
    *,
    customer_group_id: str | None = None,
    customer_group: str | None = None,
    required_active: bool = True,
    company_id: str | None = None,
) -> str | None:
    """Resolve group id from id or name; None clears/unsets."""
    if customer_group_id is not None:
        gid = str(customer_group_id).strip()
        if not gid:
            return None
        group = await get_customer_group(
            db,
            tenant_id,
            gid,
            active_only=required_active,
            company_id=company_id,
        )
        return group.id
    if customer_group is not None:
        name = str(customer_group).strip()
        if not name:
            return None
        await ensure_default_customer_groups(db, tenant_id, company_id=company_id)
        q = select(m.CustomerGroup).where(
            m.CustomerGroup.tenant_id == tenant_id,
            func.lower(m.CustomerGroup.name) == name.lower(),
        )
        if company_id:
            q = q.where(m.CustomerGroup.company_id == company_id)
        row = (await db.execute(q)).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="Customer group not found")
        if required_active and not row.is_active:
            raise HTTPException(status_code=409, detail="Customer group is inactive")
        return row.id
    return None


async def customer_group_discount_percent(
    db: AsyncSession, tenant_id: str, customer_id: str | None
) -> float:
    if not customer_id:
        return 0.0
    customer = await get_customer(db, tenant_id, customer_id)
    if not customer.customer_group_id:
        return 0.0
    group = (
        await db.execute(
            select(m.CustomerGroup).where(
                m.CustomerGroup.id == customer.customer_group_id,
                m.CustomerGroup.tenant_id == tenant_id,
                m.CustomerGroup.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if group is None:
        return 0.0
    return max(0.0, min(100.0, float(group.discount_percent or 0)))


async def list_groups(
    db: AsyncSession,
    tenant_id: str,
    *,
    active_only: bool = False,
    is_active: bool | None = None,
    company_id: str | None = None,
) -> list[m.CustomerGroup]:
    """Stage 123 G1 — is_active for honest inactive-only customer group lists."""
    await ensure_default_customer_groups(db, tenant_id, company_id=company_id)
    stmt = select(m.CustomerGroup).where(m.CustomerGroup.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.CustomerGroup.company_id == company_id)
    if is_active is not None:
        stmt = stmt.where(m.CustomerGroup.is_active.is_(bool(is_active)))
    elif active_only:
        stmt = stmt.where(m.CustomerGroup.is_active.is_(True))
    stmt = stmt.order_by(m.CustomerGroup.name)
    return list((await db.execute(stmt)).scalars().all())


async def create_group(
    db: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    discount_percent: float = 0,
    company_id: str | None = None,
) -> m.CustomerGroup:
    await ensure_default_customer_groups(db, tenant_id, company_id=company_id)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    if len(name) > 50:
        raise HTTPException(status_code=400, detail="name must be at most 50 characters")
    pct = float(discount_percent or 0)
    if pct < 0 or pct > 100:
        raise HTTPException(status_code=400, detail="discount_percent must be between 0 and 100")
    dup_stmt = select(m.CustomerGroup).where(
        m.CustomerGroup.tenant_id == tenant_id,
        func.lower(m.CustomerGroup.name) == name.lower(),
    )
    if company_id:
        dup_stmt = dup_stmt.where(m.CustomerGroup.company_id == company_id)
    dup = (await db.execute(dup_stmt)).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="Customer group name already exists")
    row = m.CustomerGroup(
        tenant_id=tenant_id,
        company_id=company_id,
        name=name,
        discount_percent=pct,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def update_group(
    db: AsyncSession,
    *,
    tenant_id: str,
    group_id: str,
    fields: dict,
) -> m.CustomerGroup:
    row = await get_customer_group(db, tenant_id, group_id)
    if "name" in fields and fields["name"] is not None:
        name = str(fields["name"]).strip()
        if not name:
            raise HTTPException(status_code=400, detail="name is required")
        if len(name) > 50:
            raise HTTPException(status_code=400, detail="name must be at most 50 characters")
        dup_stmt = select(m.CustomerGroup).where(
            m.CustomerGroup.tenant_id == tenant_id,
            func.lower(m.CustomerGroup.name) == name.lower(),
            m.CustomerGroup.id != row.id,
        )
        if getattr(row, "company_id", None):
            dup_stmt = dup_stmt.where(m.CustomerGroup.company_id == row.company_id)
        dup = (await db.execute(dup_stmt)).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=409, detail="Customer group name already exists")
        row.name = name
    if "discount_percent" in fields and fields["discount_percent"] is not None:
        pct = float(fields["discount_percent"])
        if pct < 0 or pct > 100:
            raise HTTPException(status_code=400, detail="discount_percent must be between 0 and 100")
        row.discount_percent = pct
    if "is_active" in fields and fields["is_active"] is not None:
        row.is_active = bool(fields["is_active"])
    await db.flush()
    return row


async def deactivate_group(
    db: AsyncSession, *, tenant_id: str, group_id: str
) -> m.CustomerGroup:
    return await update_group(
        db, tenant_id=tenant_id, group_id=group_id, fields={"is_active": False}
    )


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
    company_id: str | None = None,
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
    if company_id:
        stmt = stmt.where(m.Party.company_id == company_id)
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
    customer_group_id: str | None = None,
    customer_group: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    notes: str | None = None,
    payment_terms_days: int = 0,
    credit_limit: float = 0,
    contacts: list[dict] | None = None,
    company_id: str | None = None,
) -> m.Party:
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    await ensure_default_customer_groups(db, tenant_id, company_id=company_id)
    code = await assert_customer_code_available(
        db, tenant_id=tenant_id, code=code, company_id=company_id
    )
    ctype = normalize_customer_type(party_type) or "registered"
    group_id = await resolve_group_ref(
        db,
        tenant_id,
        customer_group_id=customer_group_id,
        customer_group=customer_group,
        company_id=company_id,
    )
    lat, lon = normalize_gps(latitude, longitude)
    now = datetime.utcnow()
    row = m.Party(
        tenant_id=tenant_id,
        company_id=company_id,
        kind="customer",
        name=name,
        code=code,
        party_type=ctype,
        category=(category or "").strip() or None,
        customer_group_id=group_id,
        status="active",
        email=str(email).strip() if email else None,
        phone=(phone or "").strip() or None,
        address=(address or "").strip() or None,
        latitude=lat,
        longitude=lon,
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
            db,
            tenant_id=tenant_id,
            code=fields["code"],
            exclude_id=row.id,
            company_id=getattr(row, "company_id", None),
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
    if "customer_group_id" in fields or "customer_group" in fields:
        # Explicit null clears; omitted keys leave unchanged (caller uses exclude_unset).
        if "customer_group_id" in fields and fields["customer_group_id"] is None:
            row.customer_group_id = None
        elif "customer_group" in fields and fields["customer_group"] is None and "customer_group_id" not in fields:
            row.customer_group_id = None
        else:
            row.customer_group_id = await resolve_group_ref(
                db,
                tenant_id,
                customer_group_id=fields.get("customer_group_id"),
                customer_group=fields.get("customer_group"),
                company_id=getattr(row, "company_id", None),
            )
    if "latitude" in fields or "longitude" in fields:
        lat = fields["latitude"] if "latitude" in fields else row.latitude
        lon = fields["longitude"] if "longitude" in fields else row.longitude
        if "latitude" in fields and fields["latitude"] is None and "longitude" in fields and fields["longitude"] is None:
            row.latitude = None
            row.longitude = None
        else:
            # When clearing only one side via null while other remains, reject unless both cleared.
            new_lat = None if ("latitude" in fields and fields["latitude"] is None) else lat
            new_lon = None if ("longitude" in fields and fields["longitude"] is None) else lon
            if new_lat is None and new_lon is None:
                row.latitude = None
                row.longitude = None
            else:
                row.latitude, row.longitude = normalize_gps(
                    None if new_lat is None else float(new_lat),
                    None if new_lon is None else float(new_lon),
                )
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
    party = await get_customer(db, tenant_id, customer_id)
    name = (name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="contact name is required")
    if is_primary:
        existing = await list_contacts(db, tenant_id, customer_id)
        for c in existing:
            c.is_primary = False
    row = m.PartyContact(
        tenant_id=tenant_id,
        company_id=getattr(party, "company_id", None),
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


async def customer_history(
    db: AsyncSession, *, tenant_id: str, customer_id: str, company_id: str | None = None
) -> dict:
    await get_customer(db, tenant_id, customer_id)

    def _scoped(model):
        clauses = [model.tenant_id == tenant_id]
        if company_id and hasattr(model, "company_id"):
            clauses.append(model.company_id == company_id)
        return clauses

    invoices = list(
        (
            await db.execute(
                select(m.SalesInvoice)
                .where(
                    *_scoped(m.SalesInvoice),
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
                    *_scoped(m.SalesQuotation),
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
                    *_scoped(m.SalesOrder),
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
                    *_scoped(m.SalesReturn),
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
                    *_scoped(m.CustomerPayment),
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
