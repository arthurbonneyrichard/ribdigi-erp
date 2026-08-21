"""StockMove / StockOut.reference_id ∈ StockMovementReferenceIdValue OpenAPI (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app import models as m
from app.schemas import StockMove, StockMovementReferenceIdValue, StockOut
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_ref = TypeAdapter(StockMovementReferenceIdValue)


def test_stock_movement_reference_id_value_schema():
    assert _ref.validate_python("  inv_001  ") == "inv_001"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 37):
        with pytest.raises(ValidationError):
            _ref.validate_python(bad)

    base_in = {"product_id": "p1", "quantity": 1}
    omit = StockMove.model_validate(base_in)
    assert omit.reference_id is None
    ok = StockMove.model_validate({**base_in, "reference_id": "  PO-99  "})
    assert ok.reference_id == "PO-99"
    for bad in ("", " ", "!!!", "http://x"):
        with pytest.raises(ValidationError):
            StockMove.model_validate({**base_in, "reference_id": bad})

    base_out = {**base_in, "reference_type": "sale"}
    out_ok = StockOut.model_validate({**base_out, "reference_id": " INV-7 "})
    assert out_ok.reference_id == "INV-7"
    with pytest.raises(ValidationError):
        StockOut.model_validate({**base_out, "reference_id": "!!!"})
    with pytest.raises(ValidationError):
        StockOut.model_validate({**base_out, "reference_id": ""})


def test_stock_movement_reference_id_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-out reference id"' in inv
    assert "reference_id: outRefId.trim() || null" in inv
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock movement reference_id OpenAPI" in agents
    assert "StockMovementReferenceIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockMovementReferenceIdValue" in docs
    assert "Stock-out reference id" in docs


@pytest.mark.asyncio
async def test_stock_movement_reference_id_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:6]

    product = await db_session.get(m.Product, product_id)
    product.tracks_batches = False
    await db_session.commit()

    # Seed stock so stock-out can succeed
    seed_in = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": product_id, "quantity": 50},
    )
    assert seed_in.status_code == 200, seed_in.text

    for bad in ("!!!", "", "http://evil.example/p", "a" * 37):
        stock_out = await ac.post(
            "/api/v1/inventory/stock-out",
            headers=headers,
            json={
                "product_id": product_id,
                "quantity": 1,
                "reference_type": "sale",
                "reference_id": bad,
            },
        )
        assert stock_out.status_code == 422, (bad, stock_out.text)

        stock_in = await ac.post(
            "/api/v1/inventory/stock-in",
            headers=headers,
            json={"product_id": product_id, "quantity": 1, "reference_id": bad},
        )
        assert stock_in.status_code == 422, (bad, stock_in.text)

    hello = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1,
            "reference_type": "other",
            "reference_id": f"  tip237-{suffix}  ",
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["reference_id"] == f"tip237-{suffix}"

    omit = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 1,
            "reference_type": "internal",
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("reference_id") in (None, "")
