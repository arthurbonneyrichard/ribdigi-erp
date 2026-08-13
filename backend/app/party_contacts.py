"""Party multi-contact helpers (BR-6.1)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

MAX_PARTY_CONTACTS = 20


def serialize_contact(row: m.PartyContact) -> dict:
    return {
        "id": row.id,
        "party_id": row.party_id,
        "name": row.name,
        "phone": row.phone,
        "email": row.email,
        "designation": row.designation,
        "is_primary": bool(row.is_primary),
        "sort_order": int(row.sort_order or 0),
        "created_at": row.created_at,
    }


async def get_party_of_kind(
    db: AsyncSession, *, tenant_id: str, party_id: str, kind: str
) -> m.Party:
    party = (
        await db.execute(
            select(m.Party).where(
                m.Party.id == party_id,
                m.Party.tenant_id == tenant_id,
                m.Party.kind == kind,
            )
        )
    ).scalar_one_or_none()
    if not party:
        label = "Customer" if kind == "customer" else "Supplier"
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return party


async def list_contacts(
    db: AsyncSession, *, tenant_id: str, party_id: str, kind: str
) -> list[m.PartyContact]:
    await get_party_of_kind(db, tenant_id=tenant_id, party_id=party_id, kind=kind)
    rows = (
        await db.execute(
            select(m.PartyContact)
            .where(
                m.PartyContact.tenant_id == tenant_id,
                m.PartyContact.party_id == party_id,
            )
            .order_by(
                m.PartyContact.sort_order.asc(),
                m.PartyContact.created_at.asc(),
            )
        )
    ).scalars().all()
    return list(rows)


async def _sync_primary_to_party(party: m.Party, contact: m.PartyContact | None) -> None:
    if contact is None:
        return
    if contact.email is not None:
        party.email = contact.email.strip() or None
    if contact.phone is not None:
        party.phone = contact.phone.strip() or None


async def create_contact(
    db: AsyncSession,
    *,
    tenant_id: str,
    party_id: str,
    kind: str,
    name: str,
    phone: str | None = None,
    email: str | None = None,
    designation: str | None = None,
    is_primary: bool = False,
) -> m.PartyContact:
    party = await get_party_of_kind(db, tenant_id=tenant_id, party_id=party_id, kind=kind)
    cleaned = (name or "").strip()
    if len(cleaned) < 1:
        raise HTTPException(status_code=400, detail="name is required")
    if len(cleaned) > 150:
        raise HTTPException(status_code=400, detail="name must be at most 150 characters")

    existing = await list_contacts(db, tenant_id=tenant_id, party_id=party_id, kind=kind)
    if len(existing) >= MAX_PARTY_CONTACTS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum of {MAX_PARTY_CONTACTS} contacts per party",
        )

    make_primary = bool(is_primary) or len(existing) == 0
    if make_primary:
        for row in existing:
            row.is_primary = False

    phone_n = (phone or "").strip() or None
    email_n = (email or "").strip() or None
    desig_n = (designation or "").strip() or None
    if desig_n and len(desig_n) > 120:
        raise HTTPException(status_code=400, detail="designation must be at most 120 characters")

    row = m.PartyContact(
        tenant_id=tenant_id,
        party_id=party_id,
        name=cleaned,
        phone=phone_n,
        email=email_n,
        designation=desig_n,
        is_primary=make_primary,
        sort_order=len(existing),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    if make_primary:
        await _sync_primary_to_party(party, row)
    await db.flush()
    return row


async def update_contact(
    db: AsyncSession,
    *,
    tenant_id: str,
    party_id: str,
    kind: str,
    contact_id: str,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    designation: str | None = None,
    is_primary: bool | None = None,
) -> m.PartyContact:
    party = await get_party_of_kind(db, tenant_id=tenant_id, party_id=party_id, kind=kind)
    target = await db.get(m.PartyContact, contact_id)
    if (
        target is None
        or target.tenant_id != tenant_id
        or target.party_id != party_id
    ):
        raise HTTPException(status_code=404, detail="Contact not found")

    if name is not None:
        cleaned = name.strip()
        if len(cleaned) < 1:
            raise HTTPException(status_code=400, detail="name is required")
        if len(cleaned) > 150:
            raise HTTPException(status_code=400, detail="name must be at most 150 characters")
        target.name = cleaned
    if phone is not None:
        target.phone = phone.strip() or None
    if email is not None:
        target.email = email.strip() or None
    if designation is not None:
        desig = designation.strip() or None
        if desig and len(desig) > 120:
            raise HTTPException(status_code=400, detail="designation must be at most 120 characters")
        target.designation = desig

    if is_primary is True:
        others = await list_contacts(db, tenant_id=tenant_id, party_id=party_id, kind=kind)
        for row in others:
            row.is_primary = row.id == contact_id
        target.is_primary = True
        await _sync_primary_to_party(party, target)
    elif target.is_primary:
        await _sync_primary_to_party(party, target)

    await db.flush()
    return target


async def delete_contact(
    db: AsyncSession,
    *,
    tenant_id: str,
    party_id: str,
    kind: str,
    contact_id: str,
) -> None:
    party = await get_party_of_kind(db, tenant_id=tenant_id, party_id=party_id, kind=kind)
    target = await db.get(m.PartyContact, contact_id)
    if (
        target is None
        or target.tenant_id != tenant_id
        or target.party_id != party_id
    ):
        raise HTTPException(status_code=404, detail="Contact not found")
    was_primary = bool(target.is_primary)
    await db.delete(target)
    await db.flush()
    remaining = await list_contacts(db, tenant_id=tenant_id, party_id=party_id, kind=kind)
    if was_primary and remaining:
        remaining[0].is_primary = True
        await _sync_primary_to_party(party, remaining[0])
    for idx, row in enumerate(remaining):
        row.sort_order = idx
    await db.flush()
