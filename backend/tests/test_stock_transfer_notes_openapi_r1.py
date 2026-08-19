"""StockTransferCreate.notes OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import models as m
from app.schemas import StockTransferCreate
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_transfer_notes_schema():
    base = {
        "from_warehouse_id": "wh1",
        "to_warehouse_id": "wh2",
        "items": [{"product_id": "p1", "quantity": 1}],
    }
    omit = StockTransferCreate.model_validate(base)
    assert omit.notes is None
    nullish = StockTransferCreate.model_validate({**base, "notes": None})
    assert nullish.notes is None
    ok = StockTransferCreate.model_validate({**base, "notes": "  Replenish till  "})
    assert ok.notes == "Replenish till"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StockTransferCreate.model_validate({**base, "notes": bad})


def test_stock_transfer_notes_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock transfer notes"' in page
    assert "xferNotes.trim() || null" in page
    assert 'aria-label="Create stock transfer"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock transfer notes OpenAPI" in agents
    assert "StockTransferNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockTransferNotesValue" in docs
    assert "Stock transfer notes" in docs


@pytest.mark.asyncio
async def test_stock_transfer_notes_api_blank_invalid_422(client, db_session, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip157 From", code=f"F157{suffix[:4]}"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Tip157 To", code=f"T157{suffix[:4]}"
    )
    await db_session.flush()
    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == from_store.id,
            )
        )
    ).scalar_one()
    to_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == to_store.id,
            )
        )
    ).scalar_one()
    await db_session.commit()

    body_base = {
        "from_warehouse_id": from_wh.id,
        "to_warehouse_id": to_wh.id,
        "submit": False,
        "items": [{"product_id": seed["p1"].id, "quantity": 1}],
    }

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/inventory/stock-transfers",
            headers=admin,
            json={**body_base, "notes": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json=body_base,
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("notes") in (None, "")

    ok = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=admin,
        json={**body_base, "notes": f"  Tip157 notes {suffix}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["notes"] == f"Tip157 notes {suffix}"
