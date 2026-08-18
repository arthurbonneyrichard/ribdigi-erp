"""PartyCreate / PartyUpdate.address OpenAPI honesty (Customer + Supplier address)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PartyCreate, PartyUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_party_address_schema():
    create_omit = PartyCreate.model_validate({"name": "Ada"})
    assert create_omit.address is None
    create_ok = PartyCreate.model_validate({"name": "Bea", "address": "  12 Market St  "})
    assert create_ok.address == "12 Market St"
    for bad in ("", " ", "!!!", "---", "http://addr.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            PartyCreate.model_validate({"name": "Cee", "address": bad})

    patch_omit = PartyUpdate.model_validate({})
    assert patch_omit.address is None
    patch_ok = PartyUpdate.model_validate({"address": "99 Ring Road"})
    assert patch_ok.address == "99 Ring Road"
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"address": ""})
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"address": "!!!"})


def test_party_address_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer address"' in sales
    assert "AddressValue" in sales or "customerAddress.trim() || null" in sales
    assert 'aria-label="Supplier address"' in purchasing
    assert "AddressValue" in purchasing or "supplierAddress.trim() || null" in purchasing
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party address OpenAPI" in agents
    assert "AddressValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Customer address" in docs
    assert "Supplier address" in docs
    assert "AddressValue" in docs


@pytest.mark.asyncio
async def test_party_address_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank_c = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Blank Address Cust", "address": ""},
    )
    assert blank_c.status_code == 422, blank_c.text

    garbage_c = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Bad Address Cust", "address": "!!!"},
    )
    assert garbage_c.status_code == 422, garbage_c.text

    ok_c = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Ok Address Cust", "address": "12 Market Street, Accra"},
    )
    assert ok_c.status_code == 200, ok_c.text
    cust = ok_c.json()["data"]
    assert cust["address"] == "12 Market Street, Accra"
    cust_id = cust["id"]

    patch_bad = await ac.patch(
        f"/api/v1/customers/{cust_id}",
        headers=admin,
        json={"address": "http://addr.example"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/customers/{cust_id}",
        headers=admin,
        json={"address": "99 Ring Road, Accra"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["address"] == "99 Ring Road, Accra"

    omit = await ac.patch(
        f"/api/v1/customers/{cust_id}",
        headers=admin,
        json={"name": "Ok Address Cust"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["address"] == "99 Ring Road, Accra"

    blank_s = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Blank Address Sup", "address": ""},
    )
    assert blank_s.status_code == 422, blank_s.text

    ok_s = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Ok Address Sup", "address": "55 Supply Ave, Tema"},
    )
    assert ok_s.status_code == 200, ok_s.text
    assert ok_s.json()["data"]["address"] == "55 Supply Ave, Tema"
