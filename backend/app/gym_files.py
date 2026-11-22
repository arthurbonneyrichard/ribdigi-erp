"""Gym member files (photo, ID, waiver, progress photo) and the printable membership card.

Access: a photo, ID and waiver are front-desk records (`members` area). A progress photo is body
information, so it needs the `fitness` area (trainer or manager), the same as measurements. The
member portal never lists or serves files. Files live in tenant media storage; only an image or
PDF of a sane size is accepted, and a key outside the tenant's folder is refused by storage.

The card: printing issues a fresh `card` credential (one live printed card per member; the last
one stops working) and shows its QR. The page is plain HTML to print or save as PDF from the
browser. It carries no health data and no payment details.
"""

from __future__ import annotations

import html as html_mod
from datetime import date

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_door
from app import models as m
from app import print_branding
from app import storage as storage_svc
from app.config import settings
from app.gym import _audit, _member

KINDS = {"photo": "members", "id_document": "members", "waiver": "members", "progress_photo": "fitness"}
IMAGES = frozenset({"image/png", "image/jpeg", "image/jpg", "image/webp"})
DOCS = storage_svc.ATTACHMENT_CONTENT_TYPES
MAX_FILES_PER_MEMBER = 60


def area_for(kind: str) -> str:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail="Kind must be photo, id_document, waiver or progress_photo")
    return KINDS[kind]


def present_file(row: m.GymMemberFile) -> dict:
    return {
        "id": row.id, "member_id": row.member_id, "kind": row.kind, "filename": row.filename,
        "content_type": row.content_type, "size_bytes": int(row.size_bytes or 0), "created_at": row.created_at.isoformat(),
    }


async def add_file(db: AsyncSession, tenant_id: str, member_id: str, *, kind: str, upload: UploadFile, user_id) -> dict:
    member = await _member(db, tenant_id, member_id)
    count = len((await db.execute(select(m.GymMemberFile.id).where(m.GymMemberFile.member_id == member.id))).all())
    if count >= MAX_FILES_PER_MEMBER:
        raise HTTPException(status_code=409, detail="This member has too many files. Remove some first.")
    allowed = IMAGES if kind in ("photo", "progress_photo") else DOCS
    stored = await storage_svc.save_upload(
        tenant_id=tenant_id, category="gym_members", upload=upload, allowed_types=allowed, max_bytes=int(settings.MEDIA_MAX_ATTACHMENT_BYTES),
    )
    if kind == "photo":  # one profile photo: the new one replaces the old
        for old in (await db.execute(select(m.GymMemberFile).where(m.GymMemberFile.member_id == member.id, m.GymMemberFile.kind == "photo"))).scalars().all():
            storage_svc.delete_key(old.storage_key, tenant_id=tenant_id)
            await db.delete(old)
    row = m.GymMemberFile(
        tenant_id=tenant_id, member_id=member.id, kind=kind, storage_key=stored.key, filename=stored.original_filename,
        content_type=stored.content_type, size_bytes=stored.size, created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_member_file_added", "gym_member", member.id, {"kind": kind, "file_id": row.id})
    return present_file(row)


async def list_files(db: AsyncSession, tenant_id: str, member_id: str, *, kinds: set[str]) -> list[dict]:
    await _member(db, tenant_id, member_id)
    rows = (
        await db.execute(select(m.GymMemberFile).where(m.GymMemberFile.tenant_id == tenant_id, m.GymMemberFile.member_id == member_id).order_by(m.GymMemberFile.created_at.desc()))
    ).scalars().all()
    return [present_file(r) for r in rows if r.kind in kinds]


async def get_file(db: AsyncSession, tenant_id: str, file_id: str) -> m.GymMemberFile:
    row = await db.get(m.GymMemberFile, file_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="File not found")
    return row


async def delete_file(db: AsyncSession, tenant_id: str, file_id: str, *, user_id) -> dict:
    row = await get_file(db, tenant_id, file_id)
    storage_svc.delete_key(row.storage_key, tenant_id=tenant_id)
    await db.delete(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_member_file_deleted", "gym_member", row.member_id, {"kind": row.kind})
    return {"id": file_id}


def _esc(value) -> str:
    return html_mod.escape(str(value or ""))


async def print_card(db: AsyncSession, tenant_id: str, member_id: str, *, user_id) -> str:
    member = await _member(db, tenant_id, member_id)
    tenant = await db.get(m.Tenant, tenant_id)
    # Only one printed card works at a time: a lost or replaced card stops at the door.
    for old in (
        await db.execute(select(m.GymCredential).where(m.GymCredential.member_id == member.id, m.GymCredential.label == "printed card", m.GymCredential.status == "active"))
    ).scalars().all():
        old.status = "revoked"
    token = "gym_" + __import__("secrets").token_urlsafe(24)
    db.add(m.GymCredential(tenant_id=tenant_id, member_id=member.id, kind="card", label="printed card", token_hash=gym_door.hash_token(token), created_by=user_id))
    photo = (
        await db.execute(select(m.GymMemberFile).where(m.GymMemberFile.member_id == member.id, m.GymMemberFile.kind == "photo"))
    ).scalar_one_or_none()
    photo_html = ""
    if photo is not None:
        import base64

        media = storage_svc.read_object(photo.storage_key, tenant_id=tenant_id)
        photo_html = f'<img class="photo" alt="" src="data:{_esc(media.content_type)};base64,{base64.b64encode(media.data).decode("ascii")}"/>'
    info = await base.present_member(db, member)
    company = (getattr(tenant, "company_name", None) or "Gym").strip()
    body = f"""
<style>
  .card {{ width: 86mm; height: 54mm; border: 1px solid #003d1f; border-radius: 3mm; padding: 4mm; display: flex; gap: 4mm; margin: 8mm auto; background: #fff; }}
  .card .photo {{ width: 22mm; height: 28mm; object-fit: cover; border-radius: 2mm; }}
  .card h2 {{ margin: 0 0 1mm; font-size: 12pt; }} .card p {{ margin: 0 0 1mm; font-size: 8pt; }}
  .card .qr {{ width: 26mm; height: 26mm; }} .card .col {{ display: flex; flex-direction: column; justify-content: space-between; }}
</style>
<div class="card">
  {photo_html}
  <div class="col">
    <div><h2>{_esc(member.full_name)}</h2><p>Member {_esc(member.member_number)}</p><p>{_esc(info.get("plan_name") or "No plan")}{(" until " + _esc(info["ends_on"])) if info.get("ends_on") else ""}</p></div>
    <p>{_esc(company)}</p>
  </div>
  <img class="qr" alt="Door QR code" src="{gym_door.qr_image(token)}"/>
</div>
<p style="text-align:center;font-size:9pt">Printed {date.today().isoformat()}. Any earlier printed card for this member no longer opens the door.</p>"""
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_card_printed", "gym_member", member.id, {})
    return print_branding.document_print_shell(title=f"Membership card {member.member_number}", company_name=company, body_html=body, tenant=tenant)
