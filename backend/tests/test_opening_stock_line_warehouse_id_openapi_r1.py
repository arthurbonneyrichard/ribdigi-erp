"""OpeningStockLine.warehouse_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import OpeningStockCreate, OpeningStockLine, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_PRODUCT = "11111111-2222-3333-4444-555555555555"
_BASE = {"product_id": _PRODUCT, "quantity": 1}


def test_opening_stock_line_warehouse_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = OpeningStockLine.model_validate(_BASE)
    assert omit.warehouse_id is None
    ok = OpeningStockLine.model_validate({**_BASE, "warehouse_id": f"  {_VALID}  "})
    assert ok.warehouse_id == _VALID.lower()
    nullish = OpeningStockLine.model_validate({**_BASE, "warehouse_id": None})
    assert nullish.warehouse_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "wh_001", "a b"):
        with pytest.raises(ValidationError):
            OpeningStockLine.model_validate({**_BASE, "warehouse_id": bad})

    create_ok = OpeningStockCreate.model_validate(
        {
            "lines": [{**_BASE, "warehouse_id": f"  {_VALID}  "}],
            "post_journal": False,
        }
    )
    assert create_ok.lines[0].warehouse_id == _VALID.lower()


def test_opening_stock_line_warehouse_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening stock warehouse"' in page
    assert "warehouse_id: openingWarehouseId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Opening stock line warehouse_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Opening stock warehouse" in docs
    assert "POST /inventory/opening-stock" in docs


@pytest.mark.asyncio
async def test_opening_stock_line_warehouse_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "wh_001"):
        resp = await ac.post(
            "/api/v1/inventory/opening-stock",
            headers=admin,
            json={
                "post_journal": False,
                "lines": [
                    {
                        "product_id": product_id,
                        "quantity": 1,
                        "warehouse_id": bad,
                    }
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=admin,
        json={
            "post_journal": False,
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=admin,
        json={
            "post_journal": False,
            "lines": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "warehouse_id": f"  {str(uuid4()).upper()}  ",
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
