"""UnitOfMeasureUpdate.base_unit_id ∈ UuidIdValue OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UnitOfMeasureUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID_BASE = "11111111-2222-3333-4444-555555555555"


def test_unit_update_base_unit_id_schema():
    assert _uuid.validate_python(f"  {_VALID_BASE}  ") == _VALID_BASE.lower()
    ok = UnitOfMeasureUpdate.model_validate({"base_unit_id": f"  {_VALID_BASE}  "})
    assert ok.base_unit_id == _VALID_BASE.lower()
    omit_ok = UnitOfMeasureUpdate.model_validate({"name": "Renamed"})
    assert omit_ok.base_unit_id is None
    nullish = UnitOfMeasureUpdate.model_validate({"base_unit_id": None})
    assert nullish.base_unit_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "uom_002", "a b"):
        with pytest.raises(ValidationError):
            UnitOfMeasureUpdate.model_validate({"base_unit_id": bad})


def test_unit_update_base_unit_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Unit update base_unit_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "base_unit_id" in docs
    assert "PATCH /catalog/units/{unit_id}" in docs
    # Create form owns the select; update honesty is API-only in Catalog manage.
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Unit base unit"' in page


@pytest.mark.asyncio
async def test_unit_update_base_unit_id_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/catalog/units",
        headers=headers,
        json={"code": f"u347{suffix}"[:20], "name": f"TIP347 Unit {suffix}"},
    )
    assert created.status_code == 200, created.text
    unit_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "uom_002"):
        resp = await ac.patch(
            f"/api/v1/catalog/units/{unit_id}",
            headers=headers,
            json={"base_unit_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.patch(
        f"/api/v1/catalog/units/{unit_id}",
        headers=headers,
        json={
            "base_unit_id": f"  {str(uuid4()).upper()}  ",
            "conversion_ratio": 12,
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
