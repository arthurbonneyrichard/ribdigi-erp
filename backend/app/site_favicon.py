"""A company's own browser-tab icon (favicon) for its public pages: restaurant, hotel and shop sites.

The picture is kept with the company settings. The restaurant and hotel public pages read it, so a guest
sees the company's icon on the browser tab, not the ERP's.
"""

from __future__ import annotations

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import logo_media as logo_media_svc
from app import models as m
from app import storage as storage_svc
from app.config import settings

KEY = "site_favicon"


def key_of(tenant: m.Tenant) -> str | None:
    raw = getattr(tenant, "document_numbering", None) or {}
    value = raw.get(KEY) if isinstance(raw, dict) else None
    return value if isinstance(value, str) and value else None


def version_of(tenant: m.Tenant) -> str | None:
    key = key_of(tenant)
    return logo_media_svc.logo_version(tenant.id, key) if key else None


async def save(db: AsyncSession, tenant: m.Tenant, upload: UploadFile, *, user_id: str | None) -> dict:
    stored = await storage_svc.save_upload(
        tenant_id=tenant.id,
        category="favicons",
        upload=upload,
        allowed_types=storage_svc.LOGO_CONTENT_TYPES,
        max_bytes=int(settings.MEDIA_MAX_LOGO_BYTES),
    )
    doc = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    doc[KEY] = stored.key
    tenant.document_numbering = doc
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant.id, user_id=user_id, module="company", action="site_favicon_saved",
        entity="site_favicon", entity_id=tenant.id, details={},
    )
    return {"has_favicon": True, "version": version_of(tenant)}


async def remove(db: AsyncSession, tenant: m.Tenant, *, user_id: str | None) -> dict:
    doc = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    doc.pop(KEY, None)
    tenant.document_numbering = doc
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant.id, user_id=user_id, module="company", action="site_favicon_removed",
        entity="site_favicon", entity_id=tenant.id, details={},
    )
    return {"has_favicon": False, "version": None}


def image_response(tenant: m.Tenant, request: Request | None, *, public: bool) -> Response:
    key = key_of(tenant)
    if not key:
        raise HTTPException(status_code=404, detail="No icon uploaded")
    return logo_media_svc.keyed_media_response(
        key,
        tenant_id=tenant.id,
        request=request,
        cache_control="public, max-age=86400" if public else "private, no-cache",
        vary="Accept" if public else "Authorization",
    )
