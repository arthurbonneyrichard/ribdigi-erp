"""Stage 165 H1 — POS Hold/Resume Partial (no stock reservation)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_pos_hold_resume_discard_h1(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    product = seed["p1"]
    stock_before = float(product.stock_qty or 0)

    held = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "Table 3",
            "cart_payload": {
                "items": [
                    {
                        "product_id": product.id,
                        "quantity": 2,
                        "discount": 0,
                        "name": product.name,
                        "sku": product.sku,
                        "selling_price": float(product.selling_price or 0),
                    }
                ],
                "party_id": None,
                "discount_amount": 0,
            },
        },
    )
    assert held.status_code == 200, held.text
    data = held.json()["data"]
    assert data["status"] == "held"
    assert data["stock_reserved"] is False
    hold_id = data["id"]

    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == stock_before

    listed = await ac.get("/api/v1/pos/holds?status=held", headers=headers)
    assert listed.status_code == 200, listed.text
    assert any(r["id"] == hold_id for r in listed.json()["data"])

    resumed = await ac.post(
        f"/api/v1/pos/holds/{hold_id}/resume", headers=headers, json={}
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["data"]["status"] == "resumed"
    assert resumed.json()["data"]["cart_payload"]["items"]

    await db_session.refresh(product)
    assert float(product.stock_qty or 0) == stock_before

    # Create another hold to discard
    held2 = await ac.post(
        "/api/v1/pos/holds",
        headers=headers,
        json={
            "label": "Discard me",
            "cart_payload": {"items": [{"product_id": product.id, "quantity": 1}]},
        },
    )
    hid2 = held2.json()["data"]["id"]
    discarded = await ac.delete(f"/api/v1/pos/holds/{hid2}", headers=headers)
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["data"]["status"] == "discarded"


def test_pos_hold_model_ui_and_migration_h1():
    models = (ROOT / "backend/app/models.py").read_text(encoding="utf-8")
    assert "class PosHeldCart" in models
    mig = (ROOT / "backend/alembic/versions/20260813_0093_pos_held_carts.py").read_text(
        encoding="utf-8"
    )
    assert "pos_held_carts" in mig
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "Hold cart" in pos
    assert "id=\"holds\"" in pos or "id='holds'" in pos
    assert "stock not reserved" in pos.lower() or "stock_reserved" in pos
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "/pos#holds" in shell
