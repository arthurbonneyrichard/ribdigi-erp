"""Stage 2 I6: UoM conversion, brand logo, product weight/dimensions (BR-5.1)."""

from __future__ import annotations

import io

import pytest

from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_uom_conversion_ratios(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    pcs = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": "IPCS", "name": "Inventory Pieces"},
    )
    assert pcs.status_code == 200, pcs.text
    pcs_id = pcs.json()["data"]["id"]

    box = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={
            "code": "IBOX",
            "name": "Inventory Box",
            "base_unit_id": pcs_id,
            "conversion_factor": 12,
        },
    )
    assert box.status_code == 200, box.text
    box_id = box.json()["data"]["id"]
    assert float(box.json()["data"]["conversion_factor"]) == 12
    assert box.json()["data"]["base_unit_id"] == pcs_id

    conv = await ac.get(
        "/api/v1/catalog/units/convert",
        headers=headers,
        params={"from_unit_id": box_id, "to_unit_id": pcs_id, "quantity": 2},
    )
    assert conv.status_code == 200, conv.text
    assert float(conv.json()["data"]["converted_quantity"]) == 24

    back = await ac.get(
        "/api/v1/catalog/units/convert",
        headers=headers,
        params={"from_unit_id": pcs_id, "to_unit_id": box_id, "quantity": 24},
    )
    assert back.status_code == 200, back.text
    assert float(back.json()["data"]["converted_quantity"]) == 2

    # Multi-level chain rejected
    nested = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={
            "code": "IPAL",
            "name": "Pallet",
            "base_unit_id": box_id,
            "conversion_factor": 10,
        },
    )
    assert nested.status_code == 400


@pytest.mark.asyncio
async def test_brand_logo_upload_get_delete(client, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    monkeypatch.setattr(storage_svc.settings, "STORAGE_BACKEND", "local")
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    created = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": "LOGO", "name": "Logo Brand"},
    )
    assert created.status_code == 200, created.text
    brand_id = created.json()["data"]["id"]
    assert created.json()["data"]["has_logo"] is False

    png = b"\x89PNG\r\n\x1a\n" + b"fake-png-bytes"
    up = await ac.post(
        f"/api/v1/catalog/brands/{brand_id}/logo",
        headers=headers,
        files={"file": ("logo.png", io.BytesIO(png), "image/png")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["data"]["has_logo"] is True

    got = await ac.get(f"/api/v1/catalog/brands/{brand_id}/logo", headers=headers)
    assert got.status_code == 200
    assert got.content[:8] == b"\x89PNG\r\n\x1a\n"

    deleted = await ac.delete(f"/api/v1/catalog/brands/{brand_id}/logo", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["has_logo"] is False

    missing = await ac.get(f"/api/v1/catalog/brands/{brand_id}/logo", headers=headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_product_weight_and_dimensions(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    patched = await ac.patch(
        f"/api/v1/products/{seed['p1'].id}",
        headers=headers,
        json={"weight": 1.25, "length": 10, "width": 5, "height": 2.5},
    )
    assert patched.status_code == 200, patched.text
    data = patched.json()["data"]
    assert float(data["weight"]) == 1.25
    assert float(data["length"]) == 10
    assert float(data["width"]) == 5
    assert float(data["height"]) == 2.5

    cleared = await ac.patch(
        f"/api/v1/products/{seed['p1'].id}",
        headers=headers,
        json={"weight": None, "height": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["weight"] is None
    assert cleared.json()["data"]["height"] is None
    assert float(cleared.json()["data"]["length"]) == 10
