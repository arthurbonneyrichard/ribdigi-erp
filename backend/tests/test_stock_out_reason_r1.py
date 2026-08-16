"""Stock Out / Adjust coded reason honesty (BR-5.2) — no silent defaults."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.inventory import apply_stock_change
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_out_adjust_reason_ui_wired():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "const [outRefType, setOutRefType] = useState('');" in inv
    assert "const [adjReason, setAdjReason] = useState('');" in inv
    assert "Select a stock-out reference type" in inv
    assert "Select an adjustment reason" in inv
    assert "Select reference type" in inv
    assert "Select reason" in inv
    assert "useState('other')" not in inv
    assert "useState('damage')" not in inv
    assert "!outRefType" in inv
    assert "!adjReason" in inv


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_out_explicit_reference_type(client, db_session, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=product.id,
        quantity_delta=3,
        movement_type="stock_in",
        user_id=seed["super"].id,
        allow_negative=False,
    )
    await db_session.commit()

    blank = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={"product_id": product.id, "quantity": 1, "reference_type": "  "},
    )
    assert blank.status_code == 422, blank.text

    ok = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=headers,
        json={
            "product_id": product.id,
            "quantity": 1,
            "reference_type": "damage",
            "notes": "Stock-out reason honesty hello-world",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["reference_type"] == "damage"


@pytest.mark.asyncio
async def test_stock_adjust_explicit_reason(client, seeded):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]

    omit = await ac.post(
        f"/api/v1/inventory/adjust/{product.id}",
        headers=headers,
        json={"quantity": -1},
    )
    assert omit.status_code == 422, omit.text

    ok = await ac.post(
        f"/api/v1/inventory/adjust/{product.id}",
        headers=headers,
        json={"quantity": -1, "reason": "theft", "notes": "Adjust reason honesty"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["reason"] == "theft"
