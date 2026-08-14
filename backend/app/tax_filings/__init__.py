"""Jurisdiction-specific government VAT/GST filing templates."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from . import gh_vat, ke_vat, ng_vat

SUPPORTED = {
    "GH": gh_vat,
    "KE": ke_vat,
    "NG": ng_vat,
}


def normalize_jurisdiction(code: str | None) -> str:
    cur = (code or "").strip().upper()
    if not cur:
        raise HTTPException(status_code=400, detail="jurisdiction is required")
    if len(cur) < 2 or len(cur) > 10:
        raise HTTPException(status_code=400, detail="Invalid jurisdiction code")
    return cur


def list_supported() -> list[dict]:
    return [
        {
            "jurisdiction": code,
            "template": mod.TEMPLATE_CODE,
            "template_name": mod.TEMPLATE_NAME,
        }
        for code, mod in sorted(SUPPORTED.items())
    ]


def build_government_return(pack: dict, tenant: m.Tenant, *, jurisdiction: str) -> dict:
    code = normalize_jurisdiction(jurisdiction)
    mod = SUPPORTED.get(code)
    if not mod:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Government filing template not implemented for jurisdiction '{code}'. "
                f"Supported: {sorted(SUPPORTED)}"
            ),
        )
    return mod.map_return(pack, tenant)


async def government_filing_pack(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date=None,
    to_date=None,
    jurisdiction: str | None = None,
    company_id: str | None = None,
) -> dict:
    from app import tax as tax_svc

    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    pack = await tax_svc.tax_filing_pack(
        db, tenant_id, from_date=from_date, to_date=to_date, company_id=company_id
    )
    juris = normalize_jurisdiction(jurisdiction or getattr(tenant, "tax_jurisdiction", None) or "GH")
    government = build_government_return(pack, tenant, jurisdiction=juris)
    return {
        **pack,
        "jurisdiction": juris,
        "tax_registration_number": getattr(tenant, "tax_registration_number", None),
        "tax_filing_period": getattr(tenant, "tax_filing_period", None) or "monthly",
        "government": government,
        "supported_jurisdictions": list_supported(),
    }
