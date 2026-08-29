"""StoreCreate / StoreUpdate.name OpenAPI honesty (BR-13.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import StoreCreate, StoreUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_store_name_schema():
    ok = StoreCreate.model_validate({"name": "  Downtown Hub  ", "code": "DT01"})
    assert ok.name == "Downtown Hub"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StoreCreate.model_validate({"name": bad, "code": "X1"})

    patch_omit = StoreUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = StoreUpdate.model_validate({"name": " Renamed Store "})
    assert patch_ok.name == "Renamed Store"
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        StoreUpdate.model_validate({"name": "  "})


def test_store_name_ui_and_docs():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Store name"' in stores
    assert 'aria-label="Edit store name"' in stores
    assert "name.trim()" in stores
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Store name OpenAPI" in agents
    assert "StoreNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StoreNameValue" in docs
    assert "Store name" in docs
    assert "Edit store name" in docs


@pytest.mark.asyncio
async def test_store_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    store_code = f"T126{suffix[:4]}".upper()

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/stores",
            headers=headers,
            json={"name": bad, "code": store_code},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={"name": f"  Tip126 Store {suffix}  ", "code": store_code},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip126 Store {suffix}"
    store_id = ok.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_omit = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={},
    )
    assert patch_omit.status_code == 200, patch_omit.text
    assert patch_omit.json()["data"]["name"] == f"Tip126 Store {suffix}"

    patch_ok = await ac.patch(
        f"/api/v1/stores/{store_id}",
        headers=headers,
        json={"name": f"Renamed {suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == f"Renamed {suffix}"
