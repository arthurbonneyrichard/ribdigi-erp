"""StockMove / OpeningStockLine / GrnItemCreate.batch_number ∈ BatchNumberValue OpenAPI."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app import models as m
from app.schemas import BatchNumberValue, GrnItemCreate, OpeningStockLine, StockMove
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_lot = TypeAdapter(BatchNumberValue)


def test_batch_number_value_schema():
    assert _lot.validate_python("  LOT-001  ") == "LOT-001"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 81):
        with pytest.raises(ValidationError):
            _lot.validate_python(bad)

    base = {"product_id": "p1", "quantity": 1}
    omit = StockMove.model_validate(base)
    assert omit.batch_number is None
    ok = StockMove.model_validate({**base, "batch_number": "  LOT-A1  "})
    assert ok.batch_number == "LOT-A1"
    for bad in ("", " ", "!!!", "http://x"):
        with pytest.raises(ValidationError):
            StockMove.model_validate({**base, "batch_number": bad})

    open_ok = OpeningStockLine.model_validate({**base, "batch_number": "OS-1"})
    assert open_ok.batch_number == "OS-1"
    with pytest.raises(ValidationError):
        OpeningStockLine.model_validate({**base, "batch_number": "!!!"})

    grn_base = {"po_item_id": "poi-1", "received_qty": 1}
    grn_ok = GrnItemCreate.model_validate({**grn_base, "batch_number": " GRN-1 "})
    assert grn_ok.batch_number == "GRN-1"
    with pytest.raises(ValidationError):
        GrnItemCreate.model_validate({**grn_base, "batch_number": ""})


def test_batch_number_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-in batch number"' in inv
    assert 'aria-label="Opening stock batch number"' in inv
    assert "batch_number: batchNumber.trim()" in inv
    assert "batch_number: openingBatch.trim() || null" in inv
    purch = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="GRN batch number"' in purch
    assert "batch_number: d.batch.trim() || undefined" in purch
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Batch number OpenAPI" in agents
    assert "BatchNumberValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BatchNumberValue" in docs
    assert "Stock-in batch number" in docs
    assert "GRN batch number" in docs


@pytest.mark.asyncio
async def test_batch_number_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:6]

    product = await db_session.get(m.Product, product_id)
    product.tracks_batches = False
    await db_session.commit()

    for bad in ("!!!", "", "http://evil.example/p"):
        stock = await ac.post(
            "/api/v1/inventory/stock-in",
            headers=headers,
            json={"product_id": product_id, "quantity": 1, "batch_number": bad},
        )
        assert stock.status_code == 422, (bad, stock.text)

        opening = await ac.post(
            "/api/v1/inventory/opening-stock",
            headers=headers,
            json={
                "post_journal": False,
                "lines": [{"product_id": product_id, "quantity": 1, "batch_number": bad}],
            },
        )
        assert opening.status_code == 422, (bad, opening.text)

    hello = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 2,
            "batch_number": f"  LOT-TIP230-{suffix}  ",
        },
    )
    assert hello.status_code == 200, hello.text
    batch = (hello.json().get("data") or {}).get("batch") or {}
    assert batch.get("batch_number") == f"LOT-TIP230-{suffix}"

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"GRN Batch Vendor {suffix}",
            "kind": "supplier",
            "email": f"grn-batch-{suffix}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [{"product_id": product_id, "quantity": 3, "unit_price": 5}],
            "notes": "batch number OpenAPI hello-world",
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    po_id = po["id"]
    po_item_id = po["items"][0]["id"]

    row = await db_session.get(m.PurchaseOrder, po_id)
    row.status = "sent"
    await db_session.commit()

    for bad in ("!!!", "", "http://evil.example/p"):
        resp = await ac.post(
            "/api/v1/purchasing/grn",
            headers=headers,
            json={
                "purchase_order_id": po_id,
                "items": [
                    {
                        "po_item_id": po_item_id,
                        "received_qty": 1,
                        "accepted_qty": 1,
                        "rejected_qty": 0,
                        "batch_number": bad,
                    }
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    grn_ok = await ac.post(
        "/api/v1/purchasing/grn",
        headers=headers,
        json={
            "purchase_order_id": po_id,
            "items": [
                {
                    "po_item_id": po_item_id,
                    "received_qty": 2,
                    "accepted_qty": 2,
                    "rejected_qty": 0,
                    "batch_number": f"  GRN-TIP230-{suffix}  ",
                }
            ],
        },
    )
    assert grn_ok.status_code == 200, grn_ok.text
    assert grn_ok.json()["data"]["items"][0]["batch_number"] == f"GRN-TIP230-{suffix}"
