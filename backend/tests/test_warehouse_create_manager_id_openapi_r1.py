"""WarehouseCreate.manager_id ∈ UuidIdValue OpenAPI honesty (BR-2.4 / BR-13)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import WarehouseCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_warehouse_create_manager_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = WarehouseCreate.model_validate({"code": "WH01", "name": "Main"})
    assert omit.manager_id is None
    ok = WarehouseCreate.model_validate(
        {"code": "WH01", "name": "Main", "manager_id": f"  {_VALID}  "}
    )
    assert ok.manager_id == _VALID.lower()
    nullish = WarehouseCreate.model_validate(
        {"code": "WH01", "name": "Main", "manager_id": None}
    )
    assert nullish.manager_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "user_001", "a b"):
        with pytest.raises(ValidationError):
            WarehouseCreate.model_validate(
                {"code": "WH01", "name": "Main", "manager_id": bad}
            )


def test_warehouse_create_manager_id_ui_and_docs():
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Warehouse manager" in page
    assert "manager_id: whManagerId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Warehouse create manager_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Warehouse manager" in docs
    assert "POST /warehouses" in docs


@pytest.mark.asyncio
async def test_warehouse_create_manager_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "user_001"):
        resp = await ac.post(
            "/api/v1/warehouses",
            headers=headers,
            json={
                "code": f"W336{suffix[:4]}".upper(),
                "name": f"Tip336 Warehouse {suffix}",
                "manager_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "code": f"W336O{suffix[:3]}".upper(),
            "name": f"Tip336 omit manager {suffix}",
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "code": f"W336M{suffix[:3]}".upper(),
            "name": f"Tip336 missing manager {suffix}",
            "manager_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
