"""StockCountItemUpdate.notes OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import StockCountItemUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_count_item_notes_schema():
    omit = StockCountItemUpdate.model_validate(
        {"product_id": "p1", "counted_qty": 1}
    )
    assert omit.notes is None
    nullish = StockCountItemUpdate.model_validate(
        {"product_id": "p1", "counted_qty": 1, "notes": None}
    )
    assert nullish.notes is None
    ok = StockCountItemUpdate.model_validate(
        {"product_id": "p1", "counted_qty": 1, "notes": "  Damaged shelf  "}
    )
    assert ok.notes == "Damaged shelf"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StockCountItemUpdate.model_validate(
                {"product_id": "p1", "counted_qty": 1, "notes": bad}
            )


def test_stock_count_item_notes_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "countLineNotes" in page
    assert "(countLineNotes[item.product_id] || '').trim() || null" in page
    assert 'aria-label="Save count lines"' in page
    assert "Stock count line notes" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock count item notes OpenAPI" in agents
    assert "StockCountItemNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockCountItemNotesValue" in docs
    assert "Stock count line notes" in docs


@pytest.mark.asyncio
async def test_stock_count_item_notes_api_blank_invalid_422(client, seeded, db_session):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    from sqlalchemy import select

    from app import models as m
    from app.stores import create_store

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip169 Count Store", code="T169"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()
    await db_session.commit()
    warehouse_id = wh.id
    product_id = seed["p1"].id

    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=admin,
        json={"warehouse_id": warehouse_id, "product_ids": [product_id]},
    )
    assert created.status_code == 200, created.text
    count_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.patch(
            f"/api/v1/inventory/stock-counts/{count_id}/items",
            headers=admin,
            json={
                "items": [
                    {"product_id": product_id, "counted_qty": 1, "notes": bad}
                ]
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    tag = f"Tip169 line {suffix}"
    ok = await ac.patch(
        f"/api/v1/inventory/stock-counts/{count_id}/items",
        headers=admin,
        json={
            "items": [
                {
                    "product_id": product_id,
                    "counted_qty": 2,
                    "notes": f"  {tag}  ",
                }
            ]
        },
    )
    assert ok.status_code == 200, ok.text
    items = ok.json()["data"].get("items") or []
    assert items and items[0].get("notes") == tag, ok.json()

    clear = await ac.patch(
        f"/api/v1/inventory/stock-counts/{count_id}/items",
        headers=admin,
        json={
            "items": [
                {"product_id": product_id, "counted_qty": 2, "notes": None}
            ]
        },
    )
    assert clear.status_code == 200, clear.text
    cleared = (clear.json()["data"].get("items") or [None])[0]
    assert cleared and cleared.get("notes") in (None, ""), clear.json()
