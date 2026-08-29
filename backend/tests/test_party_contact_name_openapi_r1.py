"""PartyContactCreate / PartyContactUpdate.name OpenAPI honesty (BR-6.1 / BR-7.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PartyContactCreate, PartyContactUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_party_contact_name_schema():
    ok = PartyContactCreate.model_validate({"name": "  Ada Lovelace  "})
    assert ok.name == "Ada Lovelace"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PartyContactCreate.model_validate({"name": bad})

    patch_omit = PartyContactUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = PartyContactUpdate.model_validate({"name": " Renamed Contact "})
    assert patch_ok.name == "Renamed Contact"
    with pytest.raises(ValidationError):
        PartyContactUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        PartyContactUpdate.model_validate({"name": "  "})


def test_party_contact_name_ui_and_docs():
    panel = (ROOT / "frontend/components/PartyContactsPanel.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Party contact name"' in panel
    assert "name.trim()" in panel
    assert 'aria-label="Add party contact"' in panel
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Party contact name OpenAPI" in agents
    assert "PartyContactNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PartyContactNameValue" in docs
    assert "Party contact name" in docs


@pytest.mark.asyncio
async def test_party_contact_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": f"Tip137 Cust {suffix}"},
    )
    assert cust.status_code == 200, cust.text
    cust_id = cust.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            f"/api/v1/customers/{cust_id}/contacts",
            headers=headers,
            json={"name": bad},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        f"/api/v1/customers/{cust_id}/contacts",
        headers=headers,
        json={"name": f"  Tip137 Contact {suffix}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip137 Contact {suffix}"
    contact_id = ok.json()["data"]["id"]

    omit = await ac.patch(
        f"/api/v1/customers/{cust_id}/contacts/{contact_id}",
        headers=headers,
        json={"is_primary": True},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["name"] == f"Tip137 Contact {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/customers/{cust_id}/contacts/{contact_id}",
            headers=headers,
            json={"name": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/customers/{cust_id}/contacts/{contact_id}",
        headers=headers,
        json={"name": f"  Tip137 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["name"] == f"Tip137 Renamed {suffix}"

    # Supplier path shares the same schema
    sup = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"Tip137 Sup {suffix}"},
    )
    assert sup.status_code == 200, sup.text
    sup_id = sup.json()["data"]["id"]
    bad_sup = await ac.post(
        f"/api/v1/suppliers/{sup_id}/contacts",
        headers=headers,
        json={"name": "!!!"},
    )
    assert bad_sup.status_code == 422, bad_sup.text
    ok_sup = await ac.post(
        f"/api/v1/suppliers/{sup_id}/contacts",
        headers=headers,
        json={"name": f"  Tip137 Sup Contact {suffix}  "},
    )
    assert ok_sup.status_code == 200, ok_sup.text
    assert ok_sup.json()["data"]["name"] == f"Tip137 Sup Contact {suffix}"
