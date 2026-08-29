"""OpeningStockLine.product_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

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


def test_opening_stock_line_product_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = OpeningStockLine.model_validate({"product_id": f"  {_VALID}  ", "quantity": 1})
    assert ok.product_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "prod_001", "a b"):
        with pytest.raises(ValidationError):
            OpeningStockLine.model_validate({"product_id": bad, "quantity": 1})
    with pytest.raises(ValidationError):
        OpeningStockLine.model_validate({"quantity": 1})

    create_ok = OpeningStockCreate.model_validate(
        {
            "lines": [{"product_id": f"  {_VALID}  ", "quantity": 1}],
            "post_journal": False,
        }
    )
    assert create_ok.lines[0].product_id == _VALID.lower()


def test_opening_stock_line_product_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Selected product"' in page
    assert "product_id: selectedId.trim()" in page
    assert 'aria-label="Post opening stock"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Opening stock line product_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /inventory/opening-stock" in docs
    assert "Selected product" in docs


@pytest.mark.asyncio
async def test_opening_stock_line_product_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "prod_001"):
        resp = await ac.post(
            "/api/v1/inventory/opening-stock",
            headers=headers,
            json={"post_journal": False, "lines": [{"product_id": bad, "quantity": 1}]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={"post_journal": False, "lines": [{"quantity": 1}]},
    )
    assert omit.status_code == 422, omit.text

    ok = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "post_journal": False,
            "lines": [{"product_id": f"  {str(product_id).upper()}  ", "quantity": 1}],
        },
    )
    assert ok.status_code == 200, ok.text

    missing = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "post_journal": False,
            "lines": [{"product_id": str(uuid4()), "quantity": 1}],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
