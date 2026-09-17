"""LowStockSuggestionLine.preferred_supplier_id ∈ UuidIdValue OpenAPI honesty (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import LowStockSuggestionLine, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_low_stock_suggestion_preferred_supplier_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = LowStockSuggestionLine.model_validate(
        {
            "product_id": _PRODUCT,
            "quantity": 1,
            "preferred_supplier_id": f"  {_VALID}  ",
        }
    )
    assert ok.preferred_supplier_id == _VALID.lower()
    omit_ok = LowStockSuggestionLine.model_validate(
        {"product_id": _PRODUCT, "quantity": 1}
    )
    assert omit_ok.preferred_supplier_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "sup_002", "a b"):
        with pytest.raises(ValidationError):
            LowStockSuggestionLine.model_validate(
                {
                    "product_id": _PRODUCT,
                    "quantity": 1,
                    "preferred_supplier_id": bad,
                }
            )


def test_low_stock_suggestion_preferred_supplier_id_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "preferred_supplier_id: ln.preferred_supplier_id" in page
    assert "String(ln.preferred_supplier_id).trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Low-stock suggestion preferred_supplier_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "from-low-stock" in docs
    assert "preferred_supplier_id" in docs


@pytest.mark.asyncio
async def test_low_stock_suggestion_preferred_supplier_id_api_blank_invalid_422(
    client, seeded
):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "sup_002"):
        resp = await ac.post(
            "/api/v1/purchasing/requests/from-low-stock",
            headers=headers,
            json={
                "lines": [
                    {
                        "product_id": product_id,
                        "quantity": 1,
                        "preferred_supplier_id": bad,
                    }
                ]
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/purchasing/requests/from-low-stock",
        headers=headers,
        json={
            "lines": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "preferred_supplier_id": f"  {str(uuid4()).upper()}  ",
                }
            ]
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
