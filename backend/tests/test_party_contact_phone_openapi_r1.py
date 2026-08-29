"""PartyContactCreate / PartyContactUpdate.phone OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PartyContactCreate, PartyContactUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_party_contact_phone_schema():
    create_omit = PartyContactCreate.model_validate({"name": "Ada"})
    assert create_omit.phone is None
    create_ok = PartyContactCreate.model_validate(
        {"name": "Bea", "phone": " +233241111111 "}
    )
    assert create_ok.phone == "+233241111111"
    for bad in ("", " ", "not-a-phone", "123", "241111111", "+123"):
        with pytest.raises(ValidationError):
            PartyContactCreate.model_validate({"name": "Cee", "phone": bad})

    patch_omit = PartyContactUpdate.model_validate({})
    assert patch_omit.phone is None
    patch_ok = PartyContactUpdate.model_validate({"phone": "+233200000001"})
    assert patch_ok.phone == "+233200000001"
    with pytest.raises(ValidationError):
        PartyContactUpdate.model_validate({"phone": ""})
    with pytest.raises(ValidationError):
        PartyContactUpdate.model_validate({"phone": "not-a-phone"})


def test_party_contact_phone_ui_and_docs():
    panel = (ROOT / "frontend/components/PartyContactsPanel.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Party contact phone"' in panel
    assert "phone.trim() || null" in panel
    assert "E.164" in panel
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party contact phone OpenAPI" in agents
    assert "E164PhoneValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Party contact phone" in docs
    assert "E164PhoneValue" in docs


@pytest.mark.asyncio
async def test_party_contact_phone_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Contact Phone Host Cust"},
    )
    assert cust.status_code == 200, cust.text
    cust_id = cust.json()["data"]["id"]

    blank = await ac.post(
        f"/api/v1/customers/{cust_id}/contacts",
        headers=admin,
        json={"name": "Blank Phone Contact", "phone": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        f"/api/v1/customers/{cust_id}/contacts",
        headers=admin,
        json={"name": "Bad Phone Contact", "phone": "not-a-phone"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        f"/api/v1/customers/{cust_id}/contacts",
        headers=admin,
        json={"name": "Ok Phone Contact", "phone": "+233241111111"},
    )
    assert ok.status_code == 200, ok.text
    contact = ok.json()["data"]
    assert contact["phone"] == "+233241111111"
    contact_id = contact["id"]

    patch_bad = await ac.patch(
        f"/api/v1/customers/{cust_id}/contacts/{contact_id}",
        headers=admin,
        json={"phone": "123"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/customers/{cust_id}/contacts/{contact_id}",
        headers=admin,
        json={"phone": "+233200000099"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["phone"] == "+233200000099"

    omit = await ac.post(
        f"/api/v1/customers/{cust_id}/contacts",
        headers=admin,
        json={"name": "Omit Phone Contact"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["phone"] is None

    sup = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Contact Phone Host Sup"},
    )
    assert sup.status_code == 200, sup.text
    sup_id = sup.json()["data"]["id"]

    blank_s = await ac.post(
        f"/api/v1/suppliers/{sup_id}/contacts",
        headers=admin,
        json={"name": "Blank Sup Contact", "phone": ""},
    )
    assert blank_s.status_code == 422, blank_s.text

    ok_s = await ac.post(
        f"/api/v1/suppliers/{sup_id}/contacts",
        headers=admin,
        json={"name": "Ok Sup Contact", "phone": "+233200000055"},
    )
    assert ok_s.status_code == 200, ok_s.text
    assert ok_s.json()["data"]["phone"] == "+233200000055"
