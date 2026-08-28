"""UnitConvertPreview.from_unit_id ∈ UuidIdValue OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import UnitConvertPreview, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_unit_convert_from_unit_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = UnitConvertPreview.model_validate(
        {
            "product_id": _PRODUCT,
            "quantity": 2,
            "from_unit_id": f"  {_VALID}  ",
        }
    )
    assert ok.from_unit_id == _VALID.lower()
    omit_ok = UnitConvertPreview.model_validate(
        {"product_id": _PRODUCT, "quantity": 1}
    )
    assert omit_ok.from_unit_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "uom_002", "a b"):
        with pytest.raises(ValidationError):
            UnitConvertPreview.model_validate(
                {"product_id": _PRODUCT, "quantity": 1, "from_unit_id": bad}
            )


def test_unit_convert_from_unit_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Unit convert from_unit_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "from_unit_id" in docs
    assert "POST /catalog/units/convert" in docs


@pytest.mark.asyncio
async def test_unit_convert_from_unit_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "uom_002"):
        resp = await ac.post(
            "/api/v1/catalog/units/convert",
            headers=headers,
            json={
                "product_id": product_id,
                "quantity": 1,
                "from_unit_id": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/catalog/units/convert",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1,
            "from_unit_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    # Lookup only runs when product.unit_id is set (to_stock_qty early-return otherwise).
    assert missing.status_code in (200, 400, 404), missing.text
    assert missing.status_code != 422
