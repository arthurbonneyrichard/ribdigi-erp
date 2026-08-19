"""StockCountCreate.notes OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import StockCountCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_count_notes_schema():
    omit = StockCountCreate.model_validate({"warehouse_id": "wh1"})
    assert omit.notes is None
    nullish = StockCountCreate.model_validate(
        {"warehouse_id": "wh1", "notes": None}
    )
    assert nullish.notes is None
    ok = StockCountCreate.model_validate(
        {"warehouse_id": "wh1", "notes": "  Month-end cycle  "}
    )
    assert ok.notes == "Month-end cycle"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StockCountCreate.model_validate({"warehouse_id": "wh1", "notes": bad})


def test_stock_count_notes_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock count notes"' in page
    assert "countNotes.trim() || null" in page
    assert 'aria-label="Create draft count"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock count notes OpenAPI" in agents
    assert "StockCountNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockCountNotesValue" in docs
    assert "Stock count notes" in docs


@pytest.mark.asyncio
async def test_stock_count_notes_api_blank_invalid_422(client, seeded, db_session):
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
        db_session, tenant_id=seed["t1"].id, name="Tip163 Count Store", code="T163"
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

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/inventory/stock-counts",
            headers=admin,
            json={"warehouse_id": warehouse_id, "notes": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=admin,
        json={"warehouse_id": warehouse_id, "product_ids": [seed["p1"].id]},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=admin,
        json={
            "warehouse_id": warehouse_id,
            "product_ids": [seed["p1"].id],
            "notes": f"  Tip163 notes {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("notes") == f"Tip163 notes {suffix}"
