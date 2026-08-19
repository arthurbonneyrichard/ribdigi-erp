"""GrnItemCreate.manufacturing_date / expiry_date OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app import models as m
from app.schemas import GrnItemCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_grn_batch_date_schema():
    base = {"po_item_id": "poi-1", "received_qty": 1}
    omit = GrnItemCreate.model_validate(base)
    assert omit.manufacturing_date is None
    assert omit.expiry_date is None
    ok = GrnItemCreate.model_validate(
        {**base, "manufacturing_date": " 2026-01-15 ", "expiry_date": "2027-01-15T12:00:00"}
    )
    assert ok.manufacturing_date == "2026-01-15"
    assert ok.expiry_date == "2027-01-15T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            GrnItemCreate.model_validate({**base, "manufacturing_date": bad})
        with pytest.raises(ValidationError):
            GrnItemCreate.model_validate({**base, "expiry_date": bad})


def test_grn_batch_date_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="GRN manufacturing date"' in page
    assert 'aria-label="GRN expiry date"' in page
    assert "manufacturing_date: d.mfg.trim() || undefined" in page
    assert "expiry_date: d.expiry.trim() || undefined" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "GRN batch date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "GRN manufacturing date" in docs
    assert "GRN expiry date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_grn_batch_date_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"GRN Date Vendor {uuid4().hex[:6]}",
            "kind": "supplier",
            "email": f"grn-date-{uuid4().hex[:6]}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 3,
                    "unit_price": 5,
                }
            ],
            "notes": "grn batch date OpenAPI hello-world",
        },
    )
    assert created.status_code == 200, created.text
    po = created.json()["data"]
    po_id = po["id"]
    po_item_id = po["items"][0]["id"]

    row = await db_session.get(m.PurchaseOrder, po_id)
    row.status = "sent"
    await db_session.commit()

    product = await db_session.get(m.Product, seed["p1"].id)
    product.tracks_batches = False
    await db_session.commit()

    for field in ("manufacturing_date", "expiry_date"):
        for bad in ("", "not-a-date", "01/02/2024"):
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
                            field: bad,
                        }
                    ],
                },
            )
            assert resp.status_code == 422, (field, bad, resp.text)

    ok = await ac.post(
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
                    "batch_number": f"LOT-TIP109-{uuid4().hex[:4]}",
                    "manufacturing_date": "2026-01-15",
                    "expiry_date": "2027-01-15",
                }
            ],
        },
    )
    assert ok.status_code == 200, ok.text
    item = ok.json()["data"]["items"][0]
    assert str(item["manufacturing_date"]).startswith("2026-01-15")
    assert str(item["expiry_date"]).startswith("2027-01-15")
