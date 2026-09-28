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
    "GH": "Ghana",
    "NG": "Nigeria",
    "KE": "Kenya",
    "ZA": "South Africa",
    "TZ": "Tanzania",
    "UG": "Uganda",
    "RW": "Rwanda",
    "CI": "Cote d'Ivoire",
    "SN": "Senegal",
    "EG": "Egypt",
    "MA": "Morocco",
    "DZ": "Algeria",
    "AO": "Angola",
    "BJ": "Benin",
    "BW": "Botswana",
    "BF": "Burkina Faso",
    "BI": "Burundi",
    "CM": "Cameroon",
    "CV": "Cabo Verde",
    "CF": "Central African Republic",
    "TD": "Chad",
    "KM": "Comoros",
    "CD": "DR Congo",
    "CG": "Congo",
    "DJ": "Djibouti",
    "GQ": "Equatorial Guinea",
    "ER": "Eritrea",
    "SZ": "Eswatini",
    "ET": "Ethiopia",
    "GA": "Gabon",
    "GM": "Gambia",
    "GN": "Guinea",
    "GW": "Guinea-Bissau",
    "LS": "Lesotho",
    "LR": "Liberia",
    "LY": "Libya",
    "MG": "Madagascar",
    "MW": "Malawi",
    "ML": "Mali",
    "MR": "Mauritania",
    "MU": "Mauritius",
    "MZ": "Mozambique",
    "NA": "Namibia",
    "NE": "Niger",
    "ST": "Sao Tome and Principe",
    "SC": "Seychelles",
    "SL": "Sierra Leone",
    "SO": "Somalia",
    "SS": "South Sudan",
    "TG": "Togo",
    "TN": "Tunisia",
    "ZM": "Zambia",
    "ZW": "Zimbabwe",
    "GB": "United Kingdom",
    "US": "United States",
    "AE": "United Arab Emirates",
    "IN": "India",
    "CN": "China",
    "CA": "Canada",
    "FR": "France",
    "DE": "Germany",
    "NL": "Netherlands",
    "AU": "Australia",
    "SG": "Singapore",
    "SA": "Saudi Arabia",
    "QA": "Qatar",
    "TR": "Turkiye",
    "BR": "Brazil",
    "JP": "Japan",
    "KR": "South Korea",
    "IE": "Ireland",
    "IT": "Italy",
    "ES": "Spain",
    "PT": "Portugal",
    "CH": "Switzerland",
    "BE": "Belgium",
    "SE": "Sweden",
    "NO": "Norway",
    "DK": "Denmark",
    "NZ": "New Zealand",
    "PK": "Pakistan",
    "BD": "Bangladesh",
    "PH": "Philippines",
    "MY": "Malaysia",
    "ID": "Indonesia",
    "TH": "Thailand",
    "VN": "Vietnam",
    "HK": "Hong Kong",
    "IL": "Israel",
    "MX": "Mexico",
    "PL": "Poland",
    "AT": "Austria",
    "FI": "Finland",
    "CZ": "Czechia",
    "GR": "Greece",
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
    items = [{"code": code, "name": name} for code, name in TAX_COUNTRIES.items()]
    items.sort(key=lambda row: (0 if row["code"] == "GH" else 1, row["name"]))
    return items


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
    store_id: str | None = None,
) -> dict:
    from app import tax as tax_svc

    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    pack = await tax_svc.tax_filing_pack(
        db, tenant_id, from_date=from_date, to_date=to_date, store_id=store_id
    )
    tenant_juris = normalize_jurisdiction(
        getattr(tenant, "tax_jurisdiction", None) or "GH"
    )
    requested = (
        normalize_jurisdiction(jurisdiction) if jurisdiction else tenant_juris
    )
    government = None
    juris = tenant_juris
    # Ghana GRA mapping only when the stored tenant country is GH.
    if requested not in SUPPORTED:
        if requested != tenant_juris:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Government filing template not implemented for jurisdiction '{requested}'. "
                    f"Supported: {sorted(SUPPORTED)}"
                ),
            )
    elif tenant_juris in SUPPORTED:
        government = build_government_return(pack, tenant, jurisdiction=requested)
        juris = requested
    return {
        **pack,
        "jurisdiction": juris,
        "tax_registration_number": getattr(tenant, "tax_registration_number", None),
        "tax_filing_period": getattr(tenant, "tax_filing_period", None) or "monthly",
        "government": government,
        "supported_jurisdictions": list_supported(),
    }
