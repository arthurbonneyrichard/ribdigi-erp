"""WarehouseUpdate.store_id ∈ UuidIdValue OpenAPI honesty (BR-2.4 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import WarehouseUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_warehouse_update_store_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = WarehouseUpdate.model_validate({})
    assert omit.store_id is None
    ok = WarehouseUpdate.model_validate({"store_id": f"  {_VALID}  "})
    assert ok.store_id == _VALID.lower()
    nullish = WarehouseUpdate.model_validate({"store_id": None})
    assert nullish.store_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "store_001", "a b"):
        with pytest.raises(ValidationError):
            WarehouseUpdate.model_validate({"store_id": bad})


def test_warehouse_update_store_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Edit warehouse store" in page
    assert "store_id: whStoreId.trim() || null" in page
    assert "clear_store: !whStoreId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Warehouse update store_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit warehouse store" in docs
    assert "PATCH /warehouses/{warehouse_id}" in docs


@pytest.mark.asyncio
async def test_warehouse_update_store_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={"code": f"W339{suffix[:4]}".upper(), "name": f"Tip339 Warehouse {suffix}"},
    )
    assert created.status_code == 200, created.text
    wh_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "store_001"):
        resp = await ac.patch(
            f"/api/v1/warehouses/{wh_id}",
            headers=headers,
            json={"store_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/warehouses/{wh_id}",
        headers=headers,
        json={"name": f"Tip339 omit store {suffix}"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.patch(
        f"/api/v1/warehouses/{wh_id}",
        headers=headers,
        json={"store_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
