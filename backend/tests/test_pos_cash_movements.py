"""POS cash in/out movements feed expected drawer cash (EOD recon)."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_cash_in_out_updates_expected_and_close_variance(client):
    ac, _seed = client
    cashier = await _cashier(ac)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 100},
    )
    assert opened.status_code == 200, opened.text
    session = opened.json()["data"]
    sid = session["session_id"]
    assert float(session["expected_cash"]) == 100

    dropped = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": "cash_out", "amount": 30, "reason": "Safe drop lunch float"},
    )
    assert dropped.status_code == 200, dropped.text
    assert float(dropped.json()["data"]["session"]["cash_out"]) == 30
    assert float(dropped.json()["data"]["session"]["expected_cash"]) == 70

    added = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": "cash_in", "amount": 10, "reason": "Change from office safe"},
    )
    assert added.status_code == 200, added.text
    assert float(added.json()["data"]["session"]["expected_cash"]) == 80

    listed = await ac.get(f"/api/v1/pos/sessions/{sid}/movements", headers=cashier)
    assert listed.status_code == 200, listed.text
    assert len(listed.json()["data"]) == 2

    closed = await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=cashier,
        json={"actual_cash": 80, "notes": "Counted drawer at close"},
    )
    assert closed.status_code == 200, closed.text
    assert float(closed.json()["data"]["expected_cash"]) == 80
    assert float(closed.json()["data"]["variance"]) == 0

    blocked = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": "cash_in", "amount": 5, "reason": "Too late after close"},
    )
    assert blocked.status_code == 409


@pytest.mark.asyncio
async def test_cashier_cannot_operate_another_shift(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cashier = await _cashier(ac)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 50},
    )
    assert opened.status_code == 200, opened.text
    sid = opened.json()["data"]["session_id"]
    denied = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": "cash_out", "amount": 5, "reason": "Not my drawer"},
    )
    assert denied.status_code == 403
    close_denied = await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=cashier,
        json={"actual_cash": 50},
    )
    assert close_denied.status_code == 403
    await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=admin,
        json={"actual_cash": 50, "notes": "Admin close"},
    )


def test_pos_exposes_counted_cash_close_without_changing_sign_out():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    helper = (root / "frontend/lib/cashierShift.ts").read_text(encoding="utf-8")
    page = (root / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    assert "actual_cash: Number(session.expected_cash || 0)" in helper
    assert "export async function countAndCloseOpenShift" in helper
    assert "before closing this shift" in helper
    sign_out = helper.split("export async function closeShiftForSignOut", 1)[1]
    assert "Leave the shift open when the queue cannot be read." in sign_out
    assert 'aria-label="Counted cash"' in page
    assert 'aria-label="Cash count notes"' in page
    assert 'aria-label="Record cash count and close shift"' in page
    assert 'aria-label="Start a new shift"' in page
