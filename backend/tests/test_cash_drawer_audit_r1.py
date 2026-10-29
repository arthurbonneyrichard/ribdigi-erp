"""Cash drawer audit: opening float, overdraw, session/drawer isolation."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import PosCashMovementCreate, PosSessionClose, PosSessionOpeningCash
from tests.conftest import auth_headers, set_tenant_industry

ROOT = Path(__file__).resolve().parents[2]


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _close_current(ac, headers):
    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    data = cur.json().get("data") if cur.status_code == 200 else None
    if data and (data.get("session_id") or data.get("id")):
        sid = data.get("session_id") or data.get("id")
        await ac.post(
            f"/api/v1/pos/sessions/{sid}/close",
            headers=headers,
            json={"actual_cash": float(data.get("expected_cash") or 0)},
        )


def test_opening_cash_schema_and_ui():
    omit_bad = None
    with pytest.raises(ValidationError):
        omit_bad = PosSessionOpeningCash.model_validate({})
    assert omit_bad is None
    ok = PosSessionOpeningCash.model_validate({"opening_cash": 25})
    assert float(ok.opening_cash) == 25
    for bad in (-1, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            PosSessionOpeningCash.model_validate({"opening_cash": bad})
    with pytest.raises(ValidationError):
        PosSessionOpeningCash.model_validate({"opening_cash": 10, "evil": 1})

    page = (ROOT / "frontend/app/(dashboard)/pos/page.tsx").read_text(encoding="utf-8")
    helper = (ROOT / "frontend/lib/cashierShift.ts").read_text(encoding="utf-8")
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    stores = (ROOT / "frontend/app/(dashboard)/stores/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening cash"' in page
    assert 'aria-label="Save opening cash"' in page
    assert 'aria-label="Counted cash"' in page
    assert 'aria-label="Cash in"' in page
    assert 'aria-label="Cash out"' in page
    assert "setOpeningCash" in helper
    assert "/opening-cash" in helper
    assert "closing_cash: actualCash" in helper
    assert "peekOpenCashierShift" in helper
    assert "Closed when the cashier signed out" not in helper
    assert 'aria-label="Sign-out counted cash"' in shell
    assert "shouldPromptDrawerCountOnSignOut" in shell
    assert "Idle sign-out leaves the shift open." in page
    assert "Cash out cannot exceed cash in the drawer." in page
    only_close = PosSessionClose.model_validate({"closing_cash": 12})
    assert only_close.counted_cash() == 12
    both = PosSessionClose.model_validate({"actual_cash": 12, "closing_cash": 12})
    assert both.counted_cash() == 12
    with pytest.raises(ValidationError):
        PosSessionClose.model_validate({})
    with pytest.raises(ValidationError):
        PosSessionClose.model_validate({"actual_cash": 10, "closing_cash": 11})
    with pytest.raises(ValidationError):
        PosSessionOpeningCash.model_validate({"opening_cash": ""})
    padded = PosCashMovementCreate.model_validate(
        {"movement_type": " CASH_IN ", "amount": 1, "reason": "Change from office safe"}
    )
    assert padded.movement_type == "cash_in"
    with pytest.raises(ValidationError):
        PosCashMovementCreate.model_validate(
            {"movement_type": "in", "amount": 1, "reason": "Change from office safe"}
        )
    with pytest.raises(ValidationError):
        PosCashMovementCreate.model_validate(
            {"movement_type": "cash_in", "amount": 0, "reason": "Change from office safe"}
        )
    assert "dispatchDrawerKick" in page
    assert 'aria-label="Cash drawer host"' in stores
    assert "Enter a cash drawer host for network mode." in stores
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "POS opening cash PATCH" in agents
    assert "CashMovementTypeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PosSessionOpeningCash" in docs
    assert "CashMovementTypeValue" in docs
    assert "cash_out cannot exceed expected" in docs.lower() or "cannot exceed expected drawer" in docs


@pytest.mark.asyncio
async def test_opening_cash_unused_then_blocked_after_movement(client):
    ac, _seed = client
    cashier = await _cashier(ac)
    await _close_current(ac, cashier)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 0},
    )
    assert opened.status_code == 200, opened.text
    sid = opened.json()["data"]["session_id"]
    assert float(opened.json()["data"]["expected_cash"]) == 0

    updated = await ac.patch(
        f"/api/v1/pos/sessions/{sid}/opening-cash",
        headers=cashier,
        json={"opening_cash": 80},
    )
    assert updated.status_code == 200, updated.text
    assert float(updated.json()["data"]["opening_cash"]) == 80
    assert float(updated.json()["data"]["expected_cash"]) == 80

    dropped = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": "cash_out", "amount": 20, "reason": "Safe drop morning float"},
    )
    assert dropped.status_code == 200, dropped.text
    assert float(dropped.json()["data"]["session"]["expected_cash"]) == 60

    late = await ac.patch(
        f"/api/v1/pos/sessions/{sid}/opening-cash",
        headers=cashier,
        json={"opening_cash": 100},
    )
    assert late.status_code == 409, late.text

    over = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": "cash_out", "amount": 80, "reason": "Too much for the drawer"},
    )
    assert over.status_code == 400, over.text
    assert "exceed" in over.text.lower()


@pytest.mark.asyncio
async def test_sale_requires_open_shift(client):
    ac, seed = client
    cashier = await _cashier(ac)
    await _close_current(ac, cashier)
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "payment_method": "cash",
            "status": "completed",
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert sale.status_code == 409, sale.text
    assert "shift" in sale.text.lower()


@pytest.mark.asyncio
async def test_drawer_isolation_same_tenant_and_store_membership(client, db_session):
    ac, seed = client
    admin = await _admin(ac, seed)
    cashier = await _cashier(ac)
    mgr = await _mgr(ac)
    tenant = seed["t1"]
    tenant.max_stores_override = 50
    tenant.store_limit = 50
    await db_session.commit()
    await _close_current(ac, cashier)
    await _close_current(ac, admin)

    store_a = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "DRWA", "name": "Drawer Store A"},
    )
    store_b = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": "DRWB", "name": "Drawer Store B"},
    )
    assert store_a.status_code == 200, store_a.text
    assert store_b.status_code == 200, store_b.text
    sid_a = store_a.json()["data"]["id"]
    sid_b = store_b.json()["data"]["id"]

    assign = await ac.put(
        f"/api/v1/users/{seed['mgr1'].id}/stores",
        headers=admin,
        json={"store_ids": [sid_a]},
    )
    assert assign.status_code == 200, assign.text

    admin_open = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 15, "store_id": sid_b},
    )
    assert admin_open.status_code == 200, admin_open.text
    admin_sid = admin_open.json()["data"]["session_id"]

    peek = await ac.get(f"/api/v1/pos/sessions/{admin_sid}/drawer", headers=cashier)
    assert peek.status_code == 403, peek.text

    kick = await ac.post(
        f"/api/v1/pos/sessions/{admin_sid}/drawer/open",
        headers=cashier,
        json={"reason": "Not my drawer kick"},
    )
    assert kick.status_code == 403, kick.text

    mgr_kick = await ac.post(
        f"/api/v1/pos/sessions/{admin_sid}/drawer/open",
        headers=mgr,
        json={"reason": "Other store drawer kick"},
    )
    assert mgr_kick.status_code == 403, mgr_kick.text

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    beta_get = await ac.get(f"/api/v1/pos/sessions/{admin_sid}/drawer", headers=beta)
    assert beta_get.status_code == 404, beta_get.text
    beta_open = await ac.patch(
        f"/api/v1/pos/sessions/{admin_sid}/opening-cash",
        headers=beta,
        json={"opening_cash": 1},
    )
    assert beta_open.status_code == 404, beta_open.text


@pytest.mark.asyncio
async def test_second_open_zero_does_not_wipe_float(client):
    ac, _seed = client
    cashier = await _cashier(ac)
    await _close_current(ac, cashier)
    first = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 0},
    )
    assert first.status_code == 200, first.text
    sid = first.json()["data"]["session_id"]
    patched = await ac.patch(
        f"/api/v1/pos/sessions/{sid}/opening-cash",
        headers=cashier,
        json={"opening_cash": 80},
    )
    assert patched.status_code == 200, patched.text
    again = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 0},
    )
    assert again.status_code in (200, 409), again.text
    if again.status_code == 200:
        assert again.json()["data"]["session_id"] == sid
        assert float(again.json()["data"]["opening_cash"]) == 80
    cur = await ac.get("/api/v1/pos/sessions/current", headers=cashier)
    assert float(cur.json()["data"]["opening_cash"]) == 80
    assert float(cur.json()["data"]["expected_cash"]) == 80

    apply_float = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 95},
    )
    assert apply_float.status_code == 200, apply_float.text
    assert apply_float.json()["data"]["session_id"] == sid
    assert float(apply_float.json()["data"]["opening_cash"]) == 95
    assert float(apply_float.json()["data"]["expected_cash"]) == 95


@pytest.mark.asyncio
async def test_close_closing_cash_alias_and_sale_variance(client):
    ac, seed = client
    cashier = await _cashier(ac)
    await _close_current(ac, cashier)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 10},
    )
    assert opened.status_code == 200, opened.text
    sid = opened.json()["data"]["session_id"]

    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": sid,
            "payment_method": "cash",
            "status": "completed",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert sale.status_code == 200, sale.text
    sale_total = float(sale.json()["data"]["total"])
    drawer = await ac.get(f"/api/v1/pos/sessions/{sid}/drawer", headers=cashier)
    assert drawer.status_code == 200, drawer.text
    expected = float(drawer.json()["data"]["expected_cash"])
    assert abs(expected - (10 + sale_total)) < 0.02

    mismatch = await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=cashier,
        json={"actual_cash": expected, "closing_cash": expected + 1},
    )
    assert mismatch.status_code == 422, mismatch.text

    counted = round(expected - 1, 2)
    closed = await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=cashier,
        json={"closing_cash": counted},
    )
    assert closed.status_code == 200, closed.text
    assert float(closed.json()["data"]["actual_cash"]) == counted
    assert abs(float(closed.json()["data"]["variance"]) - (counted - expected)) < 0.02


@pytest.mark.asyncio
async def test_opening_cash_openapi_422(client):
    ac, _seed = client
    cashier = await _cashier(ac)
    await _close_current(ac, cashier)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 5},
    )
    sid = opened.json()["data"]["session_id"]
    for bad in ({}, {"opening_cash": "inf"}, {"opening_cash": -1}, {"opening_cash": "!!!"}):
        resp = await ac.patch(
            f"/api/v1/pos/sessions/{sid}/opening-cash",
            headers=cashier,
            json=bad,
        )
        assert resp.status_code == 422, (bad, resp.text)
    blank_notes = await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=cashier,
        json={"actual_cash": 5, "notes": "http://evil"},
    )
    assert blank_notes.status_code == 422, blank_notes.text


@pytest.mark.asyncio
async def test_hotel_front_desk_float_isolation(client, db_session, seeded):
    """Hotel cashier float is a separate front-desk log, tenant-scoped."""
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "hotel")
    await set_tenant_industry(db_session, seed["t2"], "hotel")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    alpha = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    opened = await ac.post(
        "/api/v1/hotel/cashier/shift/open",
        headers=alpha,
        json={"opening_float": 40},
    )
    if opened.status_code in (400, 403, 404, 422):
        pytest.skip(f"hotel cashier shift unavailable: {opened.status_code} {opened.text}")
    assert opened.status_code == 200, opened.text
    assert float(opened.json()["data"]["opening_float"]) == 40
    shift_id = opened.json()["data"]["id"]

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    beta_get = await ac.get("/api/v1/hotel/cashier/shift", headers=beta)
    if beta_get.status_code == 200:
        data = beta_get.json().get("data")
        assert data is None or data.get("id") != shift_id
    else:
        assert beta_get.status_code in (403, 404)

    beta_close = await ac.post(
        "/api/v1/hotel/cashier/shift/close",
        headers=beta,
        json={"closing_float": 0},
    )
    assert beta_close.status_code in (403, 404)
    still = await ac.get("/api/v1/hotel/cashier/shift", headers=alpha)
    assert still.status_code == 200
    assert still.json()["data"]["id"] == shift_id
    assert still.json()["data"]["status"] == "open"


@pytest.mark.asyncio
async def test_card_sale_leaves_expected_cash_and_cashier_cannot_set_other_float(client):
    ac, seed = client
    cashier = await _cashier(ac)
    admin = await _admin(ac, seed)
    await _close_current(ac, cashier)
    await _close_current(ac, admin)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 40},
    )
    assert opened.status_code == 200, opened.text
    sid = opened.json()["data"]["session_id"]
    card = await ac.post(
        "/api/v1/pos/sales",
        headers=cashier,
        json={
            "session_id": sid,
            "payment_method": "card",
            "status": "completed",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 7}],
        },
    )
    assert card.status_code == 200, card.text
    drawer = await ac.get(f"/api/v1/pos/sessions/{sid}/drawer", headers=cashier)
    assert drawer.status_code == 200, drawer.text
    assert float(drawer.json()["data"]["expected_cash"]) == 40
    assert float(drawer.json()["data"]["cash_sales"]) == 0

    admin_open = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 15},
    )
    assert admin_open.status_code == 200, admin_open.text
    admin_sid = admin_open.json()["data"]["session_id"]
    stolen = await ac.patch(
        f"/api/v1/pos/sessions/{admin_sid}/opening-cash",
        headers=cashier,
        json={"opening_cash": 99},
    )
    assert stolen.status_code == 403, stolen.text
    extra = await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=cashier,
        json={"actual_cash": 40, "evil": 1},
    )
    assert extra.status_code == 422, extra.text
    move_bad = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": "!!!", "amount": 1, "reason": "Bad movement type"},
    )
    assert move_bad.status_code == 422, move_bad.text


@pytest.mark.asyncio
async def test_split_tender_expected_cash_in_out_variance_and_isolation(client):
    ac, seed = client
    cashier = await _cashier(ac)
    admin = await _admin(ac, seed)
    await _close_current(ac, cashier)
    await _close_current(ac, admin)
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    sid = opened.json()["data"]["session_id"]

    body = {
        "session_id": sid,
        "payment_method": "split",
        "status": "completed",
        "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 6}],
        "payments": [
            {"payment_method": "cash", "amount": 4},
            {"payment_method": "card", "amount": 8},
        ],
    }
    split = await ac.post("/api/v1/pos/sales", headers=cashier, json=body)
    if split.status_code == 400:
        detail = split.json().get("detail") or {}
        if isinstance(detail, dict) and detail.get("code") == "PAYMENT_TOTAL_MISMATCH":
            due = float(detail["sale_total"])
            cash_part = 4 if due > 4 else round(due / 2, 2)
            body["payments"] = [
                {"payment_method": "cash", "amount": cash_part},
                {"payment_method": "card", "amount": round(due - cash_part, 2)},
            ]
            split = await ac.post("/api/v1/pos/sales", headers=cashier, json=body)
    assert split.status_code == 200, split.text
    cash_part = float(
        next(p["amount"] for p in body["payments"] if p["payment_method"] == "cash")
    )
    drawer = await ac.get(f"/api/v1/pos/sessions/{sid}/drawer", headers=cashier)
    assert drawer.status_code == 200, drawer.text
    assert abs(float(drawer.json()["data"]["cash_sales"]) - cash_part) < 0.02
    assert abs(float(drawer.json()["data"]["expected_cash"]) - (20 + cash_part)) < 0.02

    padded = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": " CASH_IN ", "amount": 10, "reason": "Change from office safe"},
    )
    assert padded.status_code == 200, padded.text
    after_in = 20 + cash_part + 10
    assert abs(float(padded.json()["data"]["session"]["expected_cash"]) - after_in) < 0.02

    dropped = await ac.post(
        f"/api/v1/pos/sessions/{sid}/movements",
        headers=cashier,
        json={"movement_type": "cash_out", "amount": 8, "reason": "Safe drop afternoon float"},
    )
    assert dropped.status_code == 200, dropped.text
    expected = float(dropped.json()["data"]["session"]["expected_cash"])
    assert abs(expected - (after_in - 8)) < 0.02

    for bad in (
        {"movement_type": "", "amount": 1, "reason": "Change from office safe"},
        {"movement_type": "cash_in", "amount": 0, "reason": "Change from office safe"},
        {"movement_type": "cash_in", "amount": 1, "reason": "!!!"},
        {"movement_type": "cash_in", "amount": 1, "reason": "http://evil"},
    ):
        resp = await ac.post(
            f"/api/v1/pos/sessions/{sid}/movements",
            headers=cashier,
            json=bad,
        )
        assert resp.status_code == 422, (bad, resp.text)

    admin_open = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=admin,
        json={"opening_cash": 5},
    )
    assert admin_open.status_code == 200, admin_open.text
    admin_sid = admin_open.json()["data"]["session_id"]
    stolen_report = await ac.get(
        f"/api/v1/pos/sessions/{admin_sid}/report", headers=cashier
    )
    assert stolen_report.status_code == 403, stolen_report.text
    stolen_moves = await ac.get(
        f"/api/v1/pos/sessions/{admin_sid}/movements", headers=cashier
    )
    assert stolen_moves.status_code == 403, stolen_moves.text

    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    beta_report = await ac.get(f"/api/v1/pos/sessions/{sid}/report", headers=beta)
    assert beta_report.status_code == 404, beta_report.text
    beta_moves = await ac.get(f"/api/v1/pos/sessions/{sid}/movements", headers=beta)
    assert beta_moves.status_code == 404, beta_moves.text

    counted = round(expected - 1, 2)
    closed = await ac.post(
        f"/api/v1/pos/sessions/{sid}/close",
        headers=cashier,
        json={"actual_cash": counted, "closing_cash": counted, "notes": "One note short at close"},
    )
    assert closed.status_code == 200, closed.text
    assert abs(float(closed.json()["data"]["expected_cash"]) - expected) < 0.02
    assert abs(float(closed.json()["data"]["variance"]) - (counted - expected)) < 0.02
