"""PartyCreate / PartyUpdate.phone OpenAPI honesty (Customer + Supplier phone)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PartyCreate, PartyUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_party_phone_schema():
    create_omit = PartyCreate.model_validate({"name": "Ada"})
    assert create_omit.phone is None
    create_ok = PartyCreate.model_validate({"name": "Bea", "phone": " +233241111111 "})
    assert create_ok.phone == "+233241111111"
    for bad in ("", " ", "not-a-phone", "123", "241111111", "+123"):
        with pytest.raises(ValidationError):
            PartyCreate.model_validate({"name": "Cee", "phone": bad})

    patch_omit = PartyUpdate.model_validate({})
    assert patch_omit.phone is None
    patch_ok = PartyUpdate.model_validate({"phone": "+233200000001"})
    assert patch_ok.phone == "+233200000001"
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"phone": ""})
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"phone": "not-a-phone"})


def test_party_phone_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer phone"' in sales
    assert "customerPhone.trim() || null" in sales
    assert 'aria-label="Supplier phone"' in purchasing
    assert "supplierPhone.trim() || null" in purchasing
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party phone OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Customer phone" in docs
    assert "Supplier phone" in docs
    assert "E164PhoneValue" in docs


@pytest.mark.asyncio
async def test_party_phone_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank_c = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Blank Phone Cust", "phone": ""},
    )
    assert blank_c.status_code == 422, blank_c.text

    garbage_c = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Bad Phone Cust", "phone": "not-a-phone"},
    )
    assert garbage_c.status_code == 422, garbage_c.text

    ok_c = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Ok Phone Cust", "phone": "+233241111111"},
    )
    assert ok_c.status_code == 200, ok_c.text
    cust = ok_c.json()["data"]
    assert cust["phone"] == "+233241111111"
    cust_id = cust["id"]

    patch_bad = await ac.patch(
        f"/api/v1/customers/{cust_id}",
        headers=admin,
        json={"phone": "123"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/customers/{cust_id}",
        headers=admin,
        json={"phone": "+233200000099"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["phone"] == "+233200000099"

    blank_s = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Blank Phone Sup", "phone": ""},
    )
    assert blank_s.status_code == 422, blank_s.text

    ok_s = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Ok Phone Sup", "phone": "+233200000055"},
    )
    assert ok_s.status_code == 200, ok_s.text
    assert ok_s.json()["data"]["phone"] == "+233200000055"
