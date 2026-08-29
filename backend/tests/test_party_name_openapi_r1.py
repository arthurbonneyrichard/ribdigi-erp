"""PartyCreate / PartyUpdate.name OpenAPI honesty (BR-6.1 / BR-7.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PartyCreate, PartyUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_party_name_schema():
    ok = PartyCreate.model_validate({"name": "  Acme Retail  "})
    assert ok.name == "Acme Retail"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PartyCreate.model_validate({"name": bad})

    patch_omit = PartyUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = PartyUpdate.model_validate({"name": " Renamed Co "})
    assert patch_ok.name == "Renamed Co"
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        PartyUpdate.model_validate({"name": "  "})


def test_party_name_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    purch = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Customer name"' in sales
    assert "customerName.trim()" in sales
    assert 'aria-label="Supplier name"' in purch
    assert "supplierName.trim()" in purch
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party name OpenAPI" in agents
    assert "PartyNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PartyNameValue" in docs
    assert "Customer name" in docs
    assert "Supplier name" in docs


@pytest.mark.asyncio
async def test_party_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        cust = await ac.post(
            "/api/v1/customers",
            headers=headers,
            json={"name": bad},
        )
        assert cust.status_code == 422, (bad, cust.text)
        supp = await ac.post(
            "/api/v1/suppliers",
            headers=headers,
            json={"name": bad},
        )
        assert supp.status_code == 422, (bad, supp.text)

    ok = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": f"  Tip124 Customer {suffix}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip124 Customer {suffix}"
    customer_id = ok.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/customers/{customer_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/customers/{customer_id}",
        headers=headers,
        json={"name": f"Renamed {suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == f"Renamed {suffix}"

    ok_s = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"Tip124 Supplier {suffix}"},
    )
    assert ok_s.status_code == 200, ok_s.text
    assert ok_s.json()["data"]["name"] == f"Tip124 Supplier {suffix}"
