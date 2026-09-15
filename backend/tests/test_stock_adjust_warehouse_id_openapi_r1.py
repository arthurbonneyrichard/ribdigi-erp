"""StockAdjust.warehouse_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StockAdjust, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_BASE = {"quantity": -1, "reason": "damage"}


def test_stock_adjust_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = StockAdjust.model_validate(_BASE)
    assert omit.warehouse_id is None
    ok = StockAdjust.model_validate({**_BASE, "warehouse_id": f"  {_VALID}  "})
    assert ok.warehouse_id == _VALID.lower()
    nullish = StockAdjust.model_validate({**_BASE, "warehouse_id": None})
    assert nullish.warehouse_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "wh_001", "a b"):
        with pytest.raises(ValidationError):
            StockAdjust.model_validate({**_BASE, "warehouse_id": bad})


def test_stock_adjust_warehouse_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock adjustment warehouse"' in page
    assert "warehouse_id: adjWarehouseId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock adjustment warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Stock adjustment warehouse" in docs
    assert "POST /inventory/adjust" in docs


@pytest.mark.asyncio
async def test_stock_adjust_warehouse_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        resp = await ac.post(
            f"/api/v1/inventory/adjust/{product_id}",
            headers=admin,
            json={"quantity": 1, "reason": "found", "warehouse_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        f"/api/v1/inventory/adjust/{product_id}",
        headers=admin,
        json={"quantity": 1, "reason": "found"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        f"/api/v1/inventory/adjust/{product_id}",
        headers=admin,
        json={
            "quantity": 1,
            "reason": "found",
            "warehouse_id": f"  {str(uuid4()).upper()}  ",
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
