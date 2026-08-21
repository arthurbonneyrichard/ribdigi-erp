"""StockMove.reference_type ∈ StockInReferenceTypeValue OpenAPI (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app import models as m
from app.schemas import StockInReferenceTypeValue, StockMove
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_ref = TypeAdapter(StockInReferenceTypeValue)


def test_stock_in_reference_type_value_schema():
    assert _ref.validate_python("  Purchase  ") == "purchase"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 51):
        with pytest.raises(ValidationError):
            _ref.validate_python(bad)

    base = {"product_id": "p1", "quantity": 1}
    omit = StockMove.model_validate(base)
    assert omit.reference_type is None
    ok = StockMove.model_validate({**base, "reference_type": "  GRN  "})
    assert ok.reference_type == "grn"
    for bad in ("", " ", "!!!", "http://x"):
        with pytest.raises(ValidationError):
            StockMove.model_validate({**base, "reference_type": bad})


def test_stock_in_reference_type_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-in reference type"' in inv
    assert "reference_type: stockRefType.trim() || null" in inv
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock-in reference_type OpenAPI" in agents
    assert "StockInReferenceTypeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockInReferenceTypeValue" in docs
    assert "Stock-in reference type" in docs


@pytest.mark.asyncio
async def test_stock_in_reference_type_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:6]

    product = await db_session.get(m.Product, product_id)
    product.tracks_batches = False
    await db_session.commit()

    for bad in ("!!!", "", "http://evil.example/p", "a" * 51):
        stock_in = await ac.post(
            "/api/v1/inventory/stock-in",
            headers=headers,
            json={"product_id": product_id, "quantity": 1, "reference_type": bad},
        )
        assert stock_in.status_code == 422, (bad, stock_in.text)

    hello = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 2,
            "reference_type": f"  Tip241-{suffix}  ",
            "reference_id": f"po-{suffix}",
        },
    )
    assert hello.status_code == 200, hello.text

    omit = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product_id, "quantity": 1},
    )
    assert omit.status_code == 200, omit.text
