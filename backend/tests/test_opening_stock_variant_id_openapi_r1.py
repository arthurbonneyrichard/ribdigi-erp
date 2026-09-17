"""OpeningStockLine.variant_id ∈ UuidIdValue OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import OpeningStockLine
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_VALID = "11111111-2222-3333-4444-555555555555"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_opening_stock_variant_id_schema():
    ok = OpeningStockLine.model_validate(
        {"product_id": _PRODUCT, "quantity": 1, "variant_id": f"  {_VALID}  "}
    )
    assert ok.variant_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "var_001"):
        with pytest.raises(ValidationError):
            OpeningStockLine.model_validate(
                {"product_id": _PRODUCT, "quantity": 1, "variant_id": bad}
            )


def test_opening_stock_variant_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening stock variant"' in page
    assert "variant_id: openingVariantId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Opening stock variant_id OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Opening stock variant" in docs


@pytest.mark.asyncio
async def test_opening_stock_variant_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "var_001"):
        resp = await ac.post(
            "/api/v1/inventory/opening-stock",
            headers=headers,
            json={
                "post_journal": False,
                "lines": [{"product_id": product_id, "quantity": 1, "variant_id": bad}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)
    missing = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "post_journal": False,
            "lines": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "variant_id": f"  {str(uuid4()).upper()}  ",
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
