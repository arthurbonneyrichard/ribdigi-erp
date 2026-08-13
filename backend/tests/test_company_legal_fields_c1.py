"""Company legal name, registration, contact, billing/shipping (BR-2.1 / BR-20.1)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.tenants import serialize_tenant, update_profile
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_serialize_tenant_includes_legal_fields():
    tenant = m.Tenant(
        slug="acme",
        company_name="Acme Trading",
        status="active",
        legal_name="Acme Retail Limited",
        registration_number="CS123456789",
        contact_person="Ama Mensah",
        address="1 HQ Road",
        billing_address="2 Billing Ave",
        shipping_address="3 Ship Lane",
        tax_registration_number="C0001112223",
    )
    data = serialize_tenant(tenant)
    assert data["legal_name"] == "Acme Retail Limited"
    assert data["registration_number"] == "CS123456789"
    assert data["contact_person"] == "Ama Mensah"
    assert data["billing_address"] == "2 Billing Ave"
    assert data["shipping_address"] == "3 Ship Lane"
    assert data["tax_registration_number"] == "C0001112223"


@pytest.mark.asyncio
async def test_update_profile_legal_fields(db_session):
    row = m.Tenant(slug="legal-unit", company_name="Unit Co", status="active")
    db_session.add(row)
    await db_session.flush()

    updated = await update_profile(
        db_session,
        row,
        legal_name="Unit Co Ltd",
        registration_number="BN-99",
        contact_person="Kojo",
        billing_address="Bill St",
        shipping_address="Ship St",
        tax_registration_number="TIN-1",
    )
    assert updated.legal_name == "Unit Co Ltd"
    assert updated.registration_number == "BN-99"
    assert updated.contact_person == "Kojo"
    assert updated.billing_address == "Bill St"
    assert updated.shipping_address == "Ship St"
    assert updated.tax_registration_number == "TIN-1"

    cleared = await update_profile(
        db_session,
        updated,
        legal_name="",
        registration_number="",
        contact_person="",
        billing_address="",
        shipping_address="",
    )
    assert cleared.legal_name is None
    assert cleared.registration_number is None
    assert cleared.contact_person is None
    assert cleared.billing_address is None
    assert cleared.shipping_address is None


@pytest.mark.asyncio
async def test_company_legal_fields_patch_and_get(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    patched = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={
            "legal_name": "Alpha Holdings Limited",
            "registration_number": "CS99887766",
            "contact_person": "Nana Yaa",
            "billing_address": "Billing House, Accra",
            "shipping_address": "Warehouse Gate, Tema",
            "tax_registration_number": "C0005556667",
            "address": "HQ Ring Road",
        },
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()["data"]
    assert data["legal_name"] == "Alpha Holdings Limited"
    assert data["registration_number"] == "CS99887766"
    assert data["contact_person"] == "Nana Yaa"
    assert data["billing_address"] == "Billing House, Accra"
    assert data["shipping_address"] == "Warehouse Gate, Tema"
    assert data["tax_registration_number"] == "C0005556667"
    assert data["address"] == "HQ Ring Road"

    got = await ac.get("/api/v1/tenants/me", headers=headers)
    assert got.status_code == 200
    body = got.json()["data"]
    assert body["legal_name"] == "Alpha Holdings Limited"
    assert body["registration_number"] == "CS99887766"
    assert body["contact_person"] == "Nana Yaa"

    bad = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"legal_name": "X"},
    )
    assert bad.status_code == 400
