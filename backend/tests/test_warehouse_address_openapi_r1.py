"""WarehouseCreate / WarehouseUpdate.address OpenAPI honesty (Multi-Store Warehouse address)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import WarehouseCreate, WarehouseUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_warehouse_address_schema():
    create_omit = WarehouseCreate.model_validate({"code": "WH1", "name": "Main"})
    assert create_omit.address is None
    create_ok = WarehouseCreate.model_validate(
        {"code": "WH2", "name": "Cold", "address": "  Zone 3  "}
    )
    assert create_ok.address == "Zone 3"
    for bad in ("", " ", "!!!", "---", "http://addr.example", "ops@example.com"):
        with pytest.raises(ValidationError):
            WarehouseCreate.model_validate({"code": "X", "name": "X", "address": bad})

    patch_omit = WarehouseUpdate.model_validate({})
    assert patch_omit.address is None
    patch_ok = WarehouseUpdate.model_validate({"address": "99 Industrial"})
    assert patch_ok.address == "99 Industrial"
    with pytest.raises(ValidationError):
        WarehouseUpdate.model_validate({"address": ""})
    with pytest.raises(ValidationError):
        WarehouseUpdate.model_validate({"address": "!!!"})


def test_warehouse_address_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Warehouse address"' in page
    assert "AddressValue" in page or "Omit blank address" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Warehouse address OpenAPI" in agents
    assert "AddressValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Warehouse address" in docs
    assert "AddressValue" in docs


@pytest.mark.asyncio
async def test_warehouse_address_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.post(
        "/api/v1/warehouses",
        headers=admin,
        json={"code": "BLA", "name": "Blank Address", "address": ""},
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/warehouses",
        headers=admin,
        json={"code": "BAD", "name": "Bad Address", "address": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text

    ok = await ac.post(
        "/api/v1/warehouses",
        headers=admin,
        json={
            "code": "OKA",
            "name": "Ok Address Warehouse",
            "address": "12 Warehouse Street, Accra",
        },
    )
    assert ok.status_code == 200, ok.text
    warehouse = ok.json()["data"]
    assert warehouse["address"] == "12 Warehouse Street, Accra"
    warehouse_id = warehouse["id"]

    patch_bad = await ac.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        headers=admin,
        json={"address": "http://addr.example"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        headers=admin,
        json={"address": "99 Industrial Road, Accra"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["address"] == "99 Industrial Road, Accra"

    omit = await ac.patch(
        f"/api/v1/warehouses/{warehouse_id}",
        headers=admin,
        json={"name": "Ok Address Warehouse"},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["address"] == "99 Industrial Road, Accra"
