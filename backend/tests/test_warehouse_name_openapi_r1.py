"""WarehouseCreate / WarehouseUpdate.name OpenAPI honesty (BR-2.4 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import WarehouseCreate, WarehouseUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_warehouse_name_schema():
    ok = WarehouseCreate.model_validate({"name": "  Main Stock  ", "code": "WH01"})
    assert ok.name == "Main Stock"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            WarehouseCreate.model_validate({"name": bad, "code": "X1"})

    patch_omit = WarehouseUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = WarehouseUpdate.model_validate({"name": " Renamed Wh "})
    assert patch_ok.name == "Renamed Wh"
    with pytest.raises(ValidationError):
        WarehouseUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        WarehouseUpdate.model_validate({"name": "  "})


def test_warehouse_name_ui_and_docs():
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Warehouse name" in stores
    assert "Edit warehouse name" in stores
    assert "whName.trim()" in stores
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Warehouse name OpenAPI" in agents
    assert "WarehouseNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "WarehouseNameValue" in docs
    assert "Warehouse name" in docs
    assert "Edit warehouse name" in docs


@pytest.mark.asyncio
async def test_warehouse_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    wh_code = f"W127{suffix[:4]}".upper()

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/warehouses",
            headers=headers,
            json={"name": bad, "code": wh_code},
        )
        assert r.status_code == 422, (bad, r.text)

    ok = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"name": f"  Tip127 Warehouse {suffix}  ", "code": wh_code},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["name"] == f"Tip127 Warehouse {suffix}"
    warehouse_id = ok.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_omit = await ac.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        headers=headers,
        json={},
    )
    assert patch_omit.status_code == 200, patch_omit.text
    assert patch_omit.json()["data"]["name"] == f"Tip127 Warehouse {suffix}"

    patch_ok = await ac.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        headers=headers,
        json={"name": f"Renamed {suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == f"Renamed {suffix}"
