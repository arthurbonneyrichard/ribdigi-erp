"""StoreCreate / StoreUpdate.address OpenAPI honesty (Multi-Store Store address)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import StoreCreate, StoreUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_store_address_schema():
    create_omit = StoreCreate.model_validate({"code": "DT", "name": "Downtown"})
    assert create_omit.address is None
    create_ok = StoreCreate.model_validate(
        {"code": "UP", "name": "Uptown", "address": "  12 Market St  "}
    )
    assert create_ok.address == "12 Market St"
    for bad in ("", " ", "!!!", "---", "http://addr.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            StoreCreate.model_validate({"code": "X", "name": "X", "address": bad})

    patch_omit = StoreUpdate.model_validate({})
    assert patch_omit.address is None
    patch_ok = StoreUpdate.model_validate({"address": "99 Ring Road"})
    assert patch_ok.address == "99 Ring Road"
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"address": ""})
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"address": "!!!"})


def test_store_address_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert page.count('aria-label="Store address"') >= 2
    assert "AddressValue" in page or "Omit blank address" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Store address OpenAPI" in agents
    assert "AddressValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Store address" in docs
    assert "AddressValue" in docs


@pytest.mark.asyncio
async def test_store_address_api_blank_invalid_422(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "BLA", "name": "Blank Address", "address": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "BAD", "name": "Bad Address", "address": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    # Raise store quota for alpha so create can succeed in seeded tenant.
    tenant = seed["t1"]
    tenant.max_stores_override = 50
    tenant.store_limit = 50
    await db_session.commit()

    ok = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={
            "code": "OKA",
            "name": "Ok Address Store",
            "address": "12 Market Street, Accra",
        },
    )
    assert ok.status_code == 200, ok.text
    store = ok.json()["data"]
    assert store["address"] == "12 Market Street, Accra"
    store_id = store["id"]

    patch_bad = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=admin,
        json={"address": "http://addr.example"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=admin,
        json={"address": "99 Ring Road, Accra"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["address"] == "99 Ring Road, Accra"

    omit = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=admin,
        json={"name": "Ok Address Store"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["address"] == "99 Ring Road, Accra"
