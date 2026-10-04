"""PartyContactCreate / PartyContactUpdate.designation OpenAPI honesty (BR-6.1 / BR-7.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PartyContactCreate, PartyContactUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_party_contact_designation_schema():
    omit = PartyContactCreate.model_validate({"name": "Ada"})
    assert omit.designation is None
    nullish = PartyContactCreate.model_validate({"name": "Ada", "designation": None})
    assert nullish.designation is None
    ok = PartyContactCreate.model_validate(
        {"name": "Ada", "designation": "  Purchasing Manager  "}
    )
    assert ok.designation == "Purchasing Manager"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PartyContactCreate.model_validate({"name": "Ada", "designation": bad})

    patch_omit = PartyContactUpdate.model_validate({})
    assert patch_omit.designation is None
    patch_ok = PartyContactUpdate.model_validate({"designation": " Accounts "})
    assert patch_ok.designation == "Accounts"
    with pytest.raises(ValidationError):
        PartyContactUpdate.model_validate({"designation": "!!!"})
    with pytest.raises(ValidationError):
        PartyContactUpdate.model_validate({"designation": "  "})


def test_party_contact_designation_ui_and_docs():
    panel = (ROOT / "frontend/components/PartyContactsPanel.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Party contact designation"' in panel
    assert "designation.trim() || null" in panel
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party contact designation OpenAPI" in agents
    assert "PartyContactDesignationValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PartyContactDesignationValue" in docs
    assert "Party contact designation" in docs


@pytest.mark.asyncio
async def test_party_contact_designation_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": f"Tip143 Cust {suffix}"},
    )
    assert cust.status_code == 200, cust.text
    cust_id = cust.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            f"/api/v1/customers/{cust_id}/contacts",
            headers=headers,
            json={"name": f"Contact {suffix}", "designation": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    # omit designation OK
    omit = await ac.post(
        f"/api/v1/customers/{cust_id}/contacts",
        headers=headers,
        json={"name": f"Tip143 NoDesig {suffix}"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["designation"] is None

    ok = await ac.post(
        f"/api/v1/customers/{cust_id}/contacts",
        headers=headers,
        json={
            "name": f"Tip143 Contact {suffix}",
            "designation": f"  Buyer {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["designation"] == f"Buyer {suffix}"
    contact_id = ok.json()["data"]["id"]

    # PATCH omit → no change
    keep = await ac.patch(
        f"/api/v1/customers/{cust_id}/contacts/{contact_id}",
        headers=headers,
        json={"is_primary": True},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["data"]["designation"] == f"Buyer {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/customers/{cust_id}/contacts/{contact_id}",
            headers=headers,
            json={"designation": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/customers/{cust_id}/contacts/{contact_id}",
        headers=headers,
        json={"designation": f"  Accounts {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["designation"] == f"Accounts {suffix}"

    # Supplier path shares the same schema
    sup = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"Tip143 Sup {suffix}"},
    )
    assert sup.status_code == 200, sup.text
    sup_id = sup.json()["data"]["id"]
    bad_sup = await ac.post(
        f"/api/v1/suppliers/{sup_id}/contacts",
        headers=headers,
        json={"name": f"Sup Contact {suffix}", "designation": "!!!"},
    )
    assert bad_sup.status_code == 422, bad_sup.text
    ok_sup = await ac.post(
        f"/api/v1/suppliers/{sup_id}/contacts",
        headers=headers,
        json={"name": f"Sup Contact {suffix}", "designation": "Receiving"},
    )
    assert ok_sup.status_code == 200, ok_sup.text
    assert ok_sup.json()["data"]["designation"] == "Receiving"
