"""StockMove / OpeningStockLine manufacturing_date / expiry_date OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import OpeningStockLine, StockMove
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_batch_date_schema():
    base = {"product_id": "p1", "quantity": 1}
    omit = StockMove.model_validate(base)
    assert omit.manufacturing_date is None
    assert omit.expiry_date is None
    ok = StockMove.model_validate(
        {**base, "manufacturing_date": " 2026-01-15 ", "expiry_date": "2027-01-15T12:00:00"}
    )
    assert ok.manufacturing_date == "2026-01-15"
    assert ok.expiry_date == "2027-01-15T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            StockMove.model_validate({**base, "manufacturing_date": bad})
        with pytest.raises(ValidationError):
            StockMove.model_validate({**base, "expiry_date": bad})

    open_ok = OpeningStockLine.model_validate(
        {**base, "manufacturing_date": "2026-02-01", "expiry_date": "2027-02-01"}
    )
    assert open_ok.manufacturing_date == "2026-02-01"
    with pytest.raises(ValidationError):
        OpeningStockLine.model_validate({**base, "expiry_date": "not-a-date"})


def test_stock_batch_date_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-in manufacturing date"' in page
    assert 'aria-label="Stock-in expiry date"' in page
    assert 'aria-label="Opening stock manufacturing date"' in page
    assert 'aria-label="Opening stock expiry date"' in page
    assert "mfgDate.trim() || null" in page
    assert "openingMfg.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock-in / opening-stock batch date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Stock-in manufacturing date" in docs
    assert "Opening stock manufacturing date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_stock_batch_date_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    lot = f"LOT-TIP110-{uuid4().hex[:4]}"

    for field in ("manufacturing_date", "expiry_date"):
        for bad in ("", "not-a-date", "01/02/2024"):
            resp = await ac.post(
                "/api/v1/inventory/stock-in",
                headers=headers,
                json={
                    "product_id": product_id,
                    "quantity": 1,
                    "batch_number": lot,
                    field: bad,
                },
            )
            assert resp.status_code == 422, (field, bad, resp.text)

            open_resp = await ac.post(
                "/api/v1/inventory/opening-stock",
                headers=headers,
                json={
                    "post_journal": False,
                    "lines": [
                        {
                            "product_id": product_id,
                            "quantity": 1,
                            "batch_number": f"{lot}-OS",
                            field: bad,
                        }
                    ],
                },
            )
            assert open_resp.status_code == 422, (field, bad, open_resp.text)

    ok = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={
            "product_id": product_id,
            "quantity": 2,
            "batch_number": lot,
            "manufacturing_date": "2026-01-15",
            "expiry_date": "2027-06-30",
        },
    )
    assert ok.status_code == 200, ok.text
    batch = (ok.json().get("data") or {}).get("batch") or {}
    assert str(batch.get("manufacturing_date") or "").startswith("2026-01-15")
    assert str(batch.get("expiry_date") or "").startswith("2027-06-30")

    open_ok = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=headers,
        json={
            "post_journal": False,
            "reference": f"TIP110-{uuid4().hex[:6]}",
            "lines": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "batch_number": f"{lot}-OS",
                    "manufacturing_date": "2026-03-01",
                    "expiry_date": "2027-03-01",
                }
            ],
        },
    )
    assert open_ok.status_code == 200, open_ok.text
