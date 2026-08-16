from datetime import datetime, timedelta

from app.tenants import (
    VALID_INDUSTRIES,
    VALID_STATUSES,
    assert_tenant_active_for_login,
    assert_writable,
    calendar_days_until,
    default_trial_ends_at,
    is_read_only,
    serialize_tenant,
)
from app import models as m
from fastapi import HTTPException
import pytest


def test_assert_suspended_blocks_login():
    tenant = m.Tenant(slug="x", company_name="X", status="suspended")
    with pytest.raises(HTTPException) as exc:
        assert_tenant_active_for_login(tenant)
    assert exc.value.status_code == 403


def test_assert_grace_allows_login():
    tenant = m.Tenant(slug="x", company_name="X", status="grace")
    assert_tenant_active_for_login(tenant)


def test_assert_active_allows_login():
    tenant = m.Tenant(slug="x", company_name="X", status="active")
    assert_tenant_active_for_login(tenant)


def test_serialize_tenant_includes_trial_fields():
    ends = datetime.utcnow() + timedelta(days=5)
    tenant = m.Tenant(
        slug="acme",
        company_name="Acme",
        status="trial",
        industry="retail",
        currency="GHS",
        trial_ends_at=ends,
    )
    data = serialize_tenant(tenant)
    assert data["slug"] == "acme"
    assert data["status"] == "trial"
    assert data["read_only"] is False
    assert data["days_remaining"] == calendar_days_until(ends)
    assert "timezone" in data
    assert "trial_days" in data


def test_grace_is_read_only():
    tenant = m.Tenant(slug="g", company_name="G", status="grace")
    assert is_read_only(tenant) is True
    with pytest.raises(HTTPException) as exc:
        assert_writable({"read_only": True})
    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "TENANT_READ_ONLY"


def test_default_trial_ends_at_in_future():
    ends = default_trial_ends_at()
    assert ends > datetime.utcnow()


def test_grace_in_valid_statuses():
    assert "grace" in VALID_STATUSES


def test_industries_cover_brd():
    for item in ("retail", "pharmacy", "restaurant", "bakery", "wholesale", "manufacturing"):
        assert item in VALID_INDUSTRIES


def test_normalize_industry_accepts_and_rejects():
    from app.tenants import normalize_industry

    assert normalize_industry("Retail") == "retail"
    assert normalize_industry("  PHARMACY ") == "pharmacy"
    with pytest.raises(HTTPException) as exc:
        normalize_industry("spaceships")
    assert exc.value.status_code == 400
    assert "industry must be one of" in str(exc.value.detail)
    assert normalize_industry(None, required=False) is None


@pytest.mark.asyncio
async def test_create_tenant_rejects_invalid_industry(client):
    ac, _seed = client
    bad = await ac.post(
        "/api/v1/tenants",
        json={
            "company_name": "Bad Industry Co",
            "slug": "bad-industry-co",
            "industry": "spaceships",
            "currency": "GHS",
            "admin_email": "admin@bad-industry.example.com",
            "admin_password": "SecurePass123!",
        },
    )
    assert bad.status_code == 422, bad.text
    assert "industry" in bad.text.lower() or "literal" in bad.text.lower() or "Input" in bad.text

    ok = await ac.post(
        "/api/v1/tenants",
        json={
            "company_name": "Good Industry Co",
            "slug": "good-industry-co",
            "industry": "Wholesale",
            "currency": "GHS",
            "admin_email": "admin@good-industry.example.com",
            "admin_password": "SecurePass123!",
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "trial"
    assert body["slug"] == "good-industry-co"