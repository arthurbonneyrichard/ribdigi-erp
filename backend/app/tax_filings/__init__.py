"""Jurisdiction-specific government VAT/GST filing templates."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from . import gh_vat

SUPPORTED = {
    "GH": gh_vat,
}

# Company tax country (ISO-3166 alpha-2). Government return templates stay in SUPPORTED.
TAX_COUNTRIES: dict[str, str] = {
    "AE": "United Arab Emirates",
    "AU": "Australia",
    "BF": "Burkina Faso",
    "BJ": "Benin",
    "CA": "Canada",
    "CI": "Côte d'Ivoire",
    "CM": "Cameroon",
    "CN": "China",
    "DE": "Germany",
    "EG": "Egypt",
    "FR": "France",
    "GB": "United Kingdom",
    "GH": "Ghana",
    "GM": "Gambia",
    "IN": "India",
    "KE": "Kenya",
    "LR": "Liberia",
    "MA": "Morocco",
    "ML": "Mali",
    "NE": "Niger",
    "NG": "Nigeria",
    "RW": "Rwanda",
    "SL": "Sierra Leone",
    "SN": "Senegal",
    "TG": "Togo",
    "TZ": "Tanzania",
    "UG": "Uganda",
    "US": "United States",
    "ZA": "South Africa",
}
TAX_COUNTRY_CODES = frozenset(TAX_COUNTRIES)


def coerce_tax_filing_jurisdiction_value(value: object) -> object:
    """Pydantic BeforeValidator: strip/uppercase; blank stays blank for Literal 422."""
    if value is None:
        return value
    if not isinstance(value, str):
        return value
    return value.strip().upper()


def validate_tenant_tax_jurisdiction_value(value: str) -> str:
    """AfterValidator: company profile country list (not filing-template Complete)."""
    code = (value or "").strip().upper()
    if code not in TAX_COUNTRY_CODES:
        raise ValueError("tax_jurisdiction must be a supported ISO country code")
    return code


def list_tax_countries() -> list[dict]:
    return [{"code": code, "name": name} for code, name in TAX_COUNTRIES.items()]


def normalize_jurisdiction(code: str | None) -> str:
    # Schema TaxFilingJurisdictionValue rejects blank/unknown Query → 422 when the
    # client passes jurisdiction=; keep length checks for tenant-default / export paths.
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
    store_id: str | None = None,
) -> dict:
    from app import tax as tax_svc

    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    pack = await tax_svc.tax_filing_pack(
        db, tenant_id, from_date=from_date, to_date=to_date, store_id=store_id
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
