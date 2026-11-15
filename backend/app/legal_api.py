"""Editable legal pages: the software owner edits privacy, terms, refunds and cookies in the console.

Every save is a new version (history kept). The public page shows the newest published version;
with none saved, the frontend shows its built-in text. Text is plain with a small markdown subset
(## headings, - lists, **bold**, [links](/path)); the frontend renders it without HTML.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.db import get_db
from app.privacy_api import _main_db
from app.rbac import is_platform_owner_role
from app.security import require_platform_permission

router = APIRouter(tags=["legal"])

LegalSlug = Literal["privacy", "terms", "refunds", "cookies"]
SLUGS: tuple[str, ...] = ("privacy", "terms", "refunds", "cookies")
DEFAULT_TITLES = {
    "privacy": "Privacy Policy",
    "terms": "Terms of Service",
    "refunds": "Refund Policy",
    "cookies": "Cookie Policy",
}

TitleValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
BodyValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=60000)]
NoteValue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


def _editor(claims: dict) -> dict:
    role = claims.get("role") or ""
    if not (is_platform_owner_role(role) or role == "platform_admin"):
        raise HTTPException(status_code=403, detail="Only the software owner or a platform admin can edit legal pages")
    return claims


def _serialize(row: m.LegalDocumentVersion, *, with_body: bool = True) -> dict:
    out = {
        "id": row.id,
        "slug": row.slug,
        "version": row.version,
        "title": row.title,
        "effective_date": row.effective_date.isoformat() if row.effective_date else None,
        "status": row.status,
        "note": row.note,
        "created_by_name": row.created_by_name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "published_at": row.published_at.isoformat() if row.published_at else None,
    }
    if with_body:
        out["body"] = row.body
    return out


async def _latest(db: AsyncSession, slug: str, *, published_only: bool) -> m.LegalDocumentVersion | None:
    stmt = select(m.LegalDocumentVersion).where(m.LegalDocumentVersion.slug == slug)
    if published_only:
        stmt = stmt.where(m.LegalDocumentVersion.status == "published")
    stmt = stmt.order_by(m.LegalDocumentVersion.version.desc()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


# ---- Public ---------------------------------------------------------------------------


@router.get("/legal/{slug}")
async def public_legal_document(slug: LegalSlug, db: AsyncSession = Depends(get_db)):
    """The published text of one legal page, or null when the built-in text is in use."""
    async with _main_db(db) as main:
        row = await _latest(main, slug, published_only=True)
        return env(_serialize(row) if row else None)


# ---- Owner console --------------------------------------------------------------------


@router.get("/platform/legal")
async def platform_legal_list(
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    out = []
    async with _main_db(db) as main:
        for slug in SLUGS:
            published = await _latest(main, slug, published_only=True)
            newest = await _latest(main, slug, published_only=False)
            out.append(
                {
                    "slug": slug,
                    "default_title": DEFAULT_TITLES[slug],
                    "published": _serialize(published, with_body=False) if published else None,
                    "draft": _serialize(newest, with_body=False) if newest and newest.status == "draft" else None,
                }
            )
    return env(out)


@router.get("/platform/legal/{slug}")
async def platform_legal_document(
    slug: LegalSlug,
    claims=Depends(require_platform_permission("platform", "read")),
    db: AsyncSession = Depends(get_db),
):
    async with _main_db(db) as main:
        rows = (
            await main.execute(
                select(m.LegalDocumentVersion)
                .where(m.LegalDocumentVersion.slug == slug)
                .order_by(m.LegalDocumentVersion.version.desc())
                .limit(100)
            )
        ).scalars().all()
        published = next((r for r in rows if r.status == "published"), None)
        return env(
            {
                "slug": slug,
                "default_title": DEFAULT_TITLES[slug],
                "latest": _serialize(rows[0]) if rows else None,
                "published": _serialize(published) if published else None,
                "versions": [_serialize(r) for r in rows],
            }
        )


class SaveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: TitleValue
    body: BodyValue
    effective_date: date | None = None
    note: NoteValue | None = None
    publish: bool = False


@router.post("/platform/legal/{slug}")
async def platform_legal_save(
    slug: LegalSlug,
    payload: SaveBody,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    _editor(claims)
    actor_id = str(claims.get("sub") or "") or None
    async with _main_db(db) as main:
        actor = await main.get(m.User, actor_id) if actor_id else None
        current = (
            await main.execute(
                select(func.max(m.LegalDocumentVersion.version)).where(m.LegalDocumentVersion.slug == slug)
            )
        ).scalar()
        now = datetime.utcnow()
        row = m.LegalDocumentVersion(
            slug=slug,
            version=int(current or 0) + 1,
            title=payload.title,
            body=payload.body,
            effective_date=payload.effective_date,
            status="published" if payload.publish else "draft",
            note=payload.note or None,
            created_by=actor_id,
            created_by_name=(actor.full_name if actor else None),
            created_at=now,
            published_at=now if payload.publish else None,
        )
        main.add(row)
        tenant_id = str(claims.get("tenant_id") or "")
        if tenant_id:
            await audit_svc.record_event(
                main,
                tenant_id=tenant_id,
                user_id=actor_id,
                module="system",
                action="legal_document_published" if payload.publish else "legal_document_draft_saved",
                entity="legal_document",
                entity_id=row.id,
                details={"slug": slug, "version": row.version, "title": row.title, "note": row.note},
            )
        await main.commit()
        data = _serialize(row)
    return env(data, "Published. The public page now shows this version" if payload.publish else "Draft saved")


@router.post("/platform/legal/{slug}/versions/{version}/publish")
async def platform_legal_publish_version(
    slug: LegalSlug,
    version: int,
    claims=Depends(require_platform_permission("platform", "write")),
    db: AsyncSession = Depends(get_db),
):
    """Publish an older draft or bring back an earlier version: saved as a new published version."""
    _editor(claims)
    async with _main_db(db) as main:
        src = (
            await main.execute(
                select(m.LegalDocumentVersion).where(
                    m.LegalDocumentVersion.slug == slug, m.LegalDocumentVersion.version == version
                )
            )
        ).scalar_one_or_none()
        if not src:
            raise HTTPException(status_code=404, detail="Version not found")
        title, body, eff = src.title, src.body, src.effective_date
    return await platform_legal_save(
        slug,
        SaveBody(title=title, body=body, effective_date=eff, note=f"Published from version {version}", publish=True),
        claims,
        db,
    )
