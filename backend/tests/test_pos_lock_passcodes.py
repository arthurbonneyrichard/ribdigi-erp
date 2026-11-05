"""Till lock: cashier passcodes, unlock, takeover, attribution and bypass attempts."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app import models as m
from app import pos_lock
from tests.conftest import auth_headers, set_tenant_industry

pytestmark = pytest.mark.asyncio

DEVICE = "till-device-0001"
CODE_A = "482915"
CODE_B = "736204"


async def _hire_cashier(ac, admin, email="second@alpha.example.com", name="Second Cashier", role="cashier"):
    made = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={"email": email, "full_name": name, "password": "SecurePass123!", "role": role},
    )
    assert made.status_code == 200, made.text
    return made.json()["data"]["id"]


async def _set_code(ac, admin, user_id, code):
    r = await ac.put(f"/api/v1/users/{user_id}/pos-passcode", headers=admin, json={"passcode": code})
    assert r.status_code == 200, r.text
    return r


async def _unlock(ac, headers, code, surface="retail", device=DEVICE):
    return await ac.post(
        "/api/v1/pos/lock/unlock",
        headers=headers,
        json={"surface": surface, "device_id": device, "passcode": code},
    )


def _op(headers, unlocked):
    return {**headers, "X-Pos-Operator": unlocked.json()["data"]["operator_token"]}


async def _setup(ac, seed):
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    login = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    await _set_code(ac, admin, seed["u1"].id, CODE_A)
    return admin, login


async def test_passcode_is_hashed_never_stored_plain(client, db_session):
    ac, seed = client
    await _setup(ac, seed)
    row = (
        await db_session.execute(select(m.PosCashierPasscode).where(m.PosCashierPasscode.user_id == seed["u1"].id))
    ).scalar_one()
    assert CODE_A not in row.passcode_hash and CODE_A not in row.lookup_hash
    assert row.passcode_hash.startswith("$2")


async def test_duplicate_passcode_rejected_within_company_but_not_across(client, db_session):
    ac, seed = client
    admin, _login = await _setup(ac, seed)
    second = await _hire_cashier(ac, admin)
    dup = await ac.put(f"/api/v1/users/{second}/pos-passcode", headers=admin, json={"passcode": CODE_A})
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "POS_PASSCODE_TAKEN"
    # The same digits at another company are a different lookup, so nothing leaks across tenants.
    assert pos_lock.lookup_hash(seed["t1"].id, CODE_A) != pos_lock.lookup_hash(seed["t2"].id, CODE_A)


async def test_weak_and_malformed_passcodes_rejected(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    for bad in ("111111", "123456", "654321"):
        r = await ac.put(f"/api/v1/users/{seed['u1'].id}/pos-passcode", headers=admin, json={"passcode": bad})
        assert r.status_code == 422, bad
    for bad in ("12345", "1234567", "12a456"):
        r = await ac.put(f"/api/v1/users/{seed['u1'].id}/pos-passcode", headers=admin, json={"passcode": bad})
        assert r.status_code == 422, bad


async def test_generated_passcode_shown_once_and_works(client):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    made = await ac.put(f"/api/v1/users/{seed['u1'].id}/pos-passcode", headers=admin, json={})
    code = made.json()["data"]["passcode"]
    assert len(code) == 6 and code.isdigit()
    listed = (await ac.get("/api/v1/users/pos-passcodes", headers=admin)).json()["data"]
    assert listed[0]["status"] == "active" and "passcode" not in listed[0]
    login = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    assert (await _unlock(ac, login, code)).status_code == 200


async def test_only_admins_manage_passcodes_and_only_their_own_tenant(client):
    ac, seed = client
    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.put(f"/api/v1/users/{seed['u1'].id}/pos-passcode", headers=cashier, json={"passcode": CODE_A})
    assert denied.status_code == 403
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    other = await ac.put(f"/api/v1/users/{seed['u2'].id}/pos-passcode", headers=admin, json={"passcode": CODE_A})
    assert other.status_code == 404


async def test_user_without_till_access_cannot_get_a_passcode(client):
    ac, _seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    accountant = await _hire_cashier(ac, admin, email="acc@alpha.example.com", name="Book Keeper", role="accountant")
    r = await ac.put(f"/api/v1/users/{accountant}/pos-passcode", headers=admin, json={"passcode": CODE_B})
    assert r.status_code == 409


async def test_unlock_identifies_cashier_and_shows_name(client):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    r = await _unlock(ac, login, CODE_A)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["operator"]["name"] == "Alpha Cashier" and data["switched"] is False


async def test_wrong_passcode_rejected_then_throttled_and_audited(client, db_session):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    for tries_left in (4, 3, 2, 1):
        bad = await _unlock(ac, login, "905172")
        assert bad.status_code == 403
        assert bad.json()["detail"]["code"] == "POS_PASSCODE_INVALID"
        assert bad.json()["detail"]["tries_left"] == tries_left
    locked = await _unlock(ac, login, "905172")
    assert locked.status_code == 429 and locked.json()["detail"]["code"] == "POS_UNLOCK_THROTTLED"
    # Even the right code waits out the lockout.
    assert (await _unlock(ac, login, CODE_A)).status_code == 429
    logs = (
        await db_session.execute(select(m.AuditLog).where(m.AuditLog.action == "pos_unlock_failed"))
    ).scalars().all()
    assert len(logs) == 5


async def test_rotating_the_device_id_does_not_escape_the_throttle(client):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    seen = []
    for n in range(pos_lock.ACCOUNT_FAIL_LIMIT + 1):
        r = await _unlock(ac, login, "905172", device=f"fresh-device-{n:04d}")
        seen.append(r.status_code)
    assert seen[-1] == 429


async def test_lockout_expires(client, db_session):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    for _ in range(pos_lock.DEVICE_FAIL_LIMIT):
        await _unlock(ac, login, "905172")
    assert (await _unlock(ac, login, CODE_A)).status_code == 429
    rows = (await db_session.execute(select(m.PosUnlockThrottle))).scalars().all()
    for row in rows:
        row.locked_until = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()
    assert (await _unlock(ac, login, CODE_A)).status_code == 200


async def test_no_passcodes_means_no_server_lock_so_tills_keep_selling(client):
    ac, _seed = client
    login = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    opened = await ac.post("/api/v1/pos/sessions/open", headers=login, json={"opening_cash": 10})
    assert opened.status_code == 200, opened.text
    state = await ac.get(f"/api/v1/pos/lock/state?surface=retail&device_id={DEVICE}", headers=login)
    assert state.json()["data"]["enforced"] is False and state.json()["data"]["locked"] is False


async def test_till_write_refused_without_an_unlocked_operator(client):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    r = await ac.post("/api/v1/pos/sessions/open", headers=login, json={"opening_cash": 10})
    assert r.status_code == 423 and r.json()["detail"]["code"] == "POS_LOCKED"
    state = await ac.get(f"/api/v1/pos/lock/state?surface=retail&device_id={DEVICE}", headers=login)
    assert state.json()["data"]["locked"] is True


async def test_lock_blocks_the_old_token_so_refresh_cannot_bypass(client):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    unlocked = await _unlock(ac, login, CODE_A)
    op = _op(login, unlocked)
    assert (await ac.post("/api/v1/pos/sessions/open", headers=op, json={"opening_cash": 10})).status_code == 200
    r = await ac.post(
        "/api/v1/pos/lock/lock", headers=op, json={"surface": "retail", "device_id": DEVICE, "reason": "idle"}
    )
    assert r.status_code == 200
    # A refresh that replays the token, and one that drops it, both stay locked.
    assert (await ac.get("/api/v1/pos/sessions/current", headers=op)).status_code == 423
    state = await ac.get(f"/api/v1/pos/lock/state?surface=retail&device_id={DEVICE}", headers=op)
    assert state.json()["data"]["locked"] is True
    state = await ac.get(f"/api/v1/pos/lock/state?surface=retail&device_id={DEVICE}", headers=login)
    assert state.json()["data"]["locked"] is True


async def test_server_locks_an_idle_till_even_if_the_browser_timer_is_disabled(client, db_session):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    unlocked = await _unlock(ac, login, CODE_A)
    op = _op(login, unlocked)
    row = await db_session.get(m.PosOperatorSession, unlocked.json()["data"]["session_id"])
    row.last_activity_at = datetime.utcnow() - timedelta(seconds=pos_lock.SERVER_IDLE_LIMIT_SECONDS + 5)
    await db_session.commit()
    assert (await ac.get("/api/v1/pos/sessions/current", headers=op)).status_code == 423


async def test_ping_keeps_an_active_till_open(client, db_session):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    unlocked = await _unlock(ac, login, CODE_A)
    op = _op(login, unlocked)
    row = await db_session.get(m.PosOperatorSession, unlocked.json()["data"]["session_id"])
    row.last_activity_at = datetime.utcnow() - timedelta(seconds=100)
    await db_session.commit()
    assert (
        await ac.post("/api/v1/pos/lock/ping", headers=op, json={"surface": "retail", "device_id": DEVICE})
    ).status_code == 200
    db_session.expire_all()
    row = await db_session.get(m.PosOperatorSession, unlocked.json()["data"]["session_id"])
    assert (datetime.utcnow() - row.last_activity_at).total_seconds() < 5


async def test_takeover_splits_sessions_and_attributes_sales_to_the_real_cashier(client, db_session):
    ac, seed = client
    admin, login = await _setup(ac, seed)
    second = await _hire_cashier(ac, admin)
    await _set_code(ac, admin, second, CODE_B)

    first = await _unlock(ac, login, CODE_A)
    op_a = _op(login, first)
    await ac.post("/api/v1/pos/lock/lock", headers=op_a, json={"surface": "retail", "device_id": DEVICE})

    # The browser is still signed in as the first cashier. The second takes over with a passcode.
    taken = await _unlock(ac, login, CODE_B)
    assert taken.status_code == 200
    data = taken.json()["data"]
    assert data["switched"] is True and data["previous_operator"]["name"] == "Alpha Cashier"
    assert data["operator"]["name"] == "Second Cashier"
    op_b = _op(login, taken)

    assert (await ac.get("/api/v1/pos/sessions/current", headers=op_a)).status_code == 423

    opened = await ac.post("/api/v1/pos/sessions/open", headers=op_b, json={"opening_cash": 20})
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=op_b,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
            "started_by_user_id": seed["u1"].id,
        },
    )
    assert sale.status_code == 200, sale.text
    tx = await db_session.get(m.Transaction, sale.json()["data"]["id"])
    assert tx.payload["cashier_user_id"] == second
    assert tx.payload["cashier_name"] == "Second Cashier"
    assert tx.payload["device_id"] == DEVICE
    assert tx.payload["started_by_user_id"] == seed["u1"].id

    sessions = (
        await db_session.execute(select(m.PosOperatorSession).order_by(m.PosOperatorSession.started_at))
    ).scalars().all()
    assert len(sessions) == 2
    assert sessions[0].user_id == seed["u1"].id and sessions[0].end_reason == "switched"
    assert sessions[1].user_id == second and sessions[1].previous_session_id == sessions[0].id
    switched = (
        await db_session.execute(select(m.AuditLog).where(m.AuditLog.action == "pos_cashier_switched"))
    ).scalar_one()
    assert switched.details["from_name"] == "Alpha Cashier" and switched.details["to_name"] == "Second Cashier"


async def test_started_by_must_be_in_the_same_company(client):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    op = _op(login, await _unlock(ac, login, CODE_A))
    opened = await ac.post("/api/v1/pos/sessions/open", headers=op, json={"opening_cash": 20})
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=op,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
            "started_by_user_id": seed["u2"].id,
        },
    )
    assert sale.status_code == 422


async def test_handover_records_who_answered_for_the_sale(client, db_session):
    ac, seed = client
    admin, login = await _setup(ac, seed)
    second = await _hire_cashier(ac, admin)
    await _set_code(ac, admin, second, CODE_B)
    op_b = _op(login, await _unlock(ac, login, CODE_B))
    r = await ac.post(
        "/api/v1/pos/lock/handover",
        headers=op_b,
        json={
            "surface": "retail", "device_id": DEVICE, "from_user_id": seed["u1"].id,
            "decision": "take_over", "item_count": 3, "total": 42.5,
        },
    )
    assert r.status_code == 200, r.text
    log = (await db_session.execute(select(m.AuditLog).where(m.AuditLog.action == "pos_sale_handover"))).scalar_one()
    assert log.user_id == second and log.details["from_user_id"] == seed["u1"].id
    assert log.details["decision"] == "take_over" and log.details["total"] == 42.5


async def test_passcode_identity_never_reaches_the_rest_of_the_erp(client):
    """A company admin's six digits on a cashier's till must not open admin screens."""
    ac, seed = client
    admin, login = await _setup(ac, seed)
    await _set_code(ac, admin, seed["admin1"].id, CODE_B)
    op = _op(login, await _unlock(ac, login, CODE_B))
    me = await ac.get("/api/v1/me", headers=op)
    assert me.json()["data"]["id"] == seed["admin1"].id
    # /users is off the till paths, so the signed-in cashier's rights apply.
    assert (await ac.post(
        "/api/v1/users", headers=op,
        json={"email": "x@alpha.example.com", "full_name": "Sneaky", "password": "SecurePass123!", "role": "cashier"},
    )).status_code == 403
    assert (await ac.get("/api/v1/audit-logs", headers=op)).status_code == 403


async def test_cashier_permissions_follow_the_operator(client, db_session):
    """A switch to a lower-rights cashier drops the rights, not just the name."""
    ac, seed = client
    admin, _login = await _setup(ac, seed)
    op = _op(admin, await _unlock(ac, admin, CODE_A))
    me = await ac.get("/api/v1/me", headers=op)
    assert me.json()["data"]["id"] == seed["u1"].id and me.json()["data"]["role"] == "cashier"
    denied = await ac.post("/api/v1/pos/offline/devices/some-device/block", headers=op, json={"blocked": True})
    assert denied.status_code == 403 and "pos:approve" in denied.text, denied.text


async def test_deactivating_a_passcode_stops_it_and_ends_live_stints(client):
    ac, seed = client
    admin, login = await _setup(ac, seed)
    op = _op(login, await _unlock(ac, login, CODE_A))
    off = await ac.patch(f"/api/v1/users/{seed['u1'].id}/pos-passcode", headers=admin, json={"is_active": False})
    assert off.status_code == 200 and off.json()["data"]["status"] == "inactive"
    assert (await _unlock(ac, login, CODE_A)).status_code == 403
    assert (await ac.get("/api/v1/pos/sessions/current", headers=op)).status_code == 423


async def test_reactivating_refuses_a_code_someone_else_took(client):
    ac, seed = client
    admin, _login = await _setup(ac, seed)
    second = await _hire_cashier(ac, admin)
    await ac.patch(f"/api/v1/users/{seed['u1'].id}/pos-passcode", headers=admin, json={"is_active": False})
    await _set_code(ac, admin, second, CODE_A)
    back = await ac.patch(f"/api/v1/users/{seed['u1'].id}/pos-passcode", headers=admin, json={"is_active": True})
    assert back.status_code == 409


async def test_changing_a_passcode_retires_the_old_one(client):
    ac, seed = client
    admin, login = await _setup(ac, seed)
    await _set_code(ac, admin, seed["u1"].id, CODE_B)
    assert (await _unlock(ac, login, CODE_A)).status_code == 403
    assert (await _unlock(ac, login, CODE_B)).status_code == 200


async def test_deactivated_staff_cannot_unlock(client):
    ac, seed = client
    admin, login = await _setup(ac, seed)
    second = await _hire_cashier(ac, admin)
    await _set_code(ac, admin, second, CODE_B)
    await ac.delete(f"/api/v1/users/{second}", headers=admin)
    assert (await _unlock(ac, login, CODE_B)).status_code == 403


async def test_operator_token_from_another_company_is_refused(client):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    op_token = (await _unlock(ac, login, CODE_A)).json()["data"]["operator_token"]
    beta = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    r = await ac.get("/api/v1/pos/sessions/current", headers={**beta, "X-Pos-Operator": op_token})
    assert r.status_code == 423


async def test_operator_token_cannot_be_used_as_a_login(client):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    op_token = (await _unlock(ac, login, CODE_A)).json()["data"]["operator_token"]
    r = await ac.get("/api/v1/me", headers={"Authorization": f"Bearer {op_token}"})
    assert r.status_code == 401


async def test_passcode_is_the_only_way_through_the_lock(client):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    r = await ac.post(
        "/api/v1/pos/lock/unlock-password", headers=login,
        json={"surface": "retail", "device_id": DEVICE, "password": "SecurePass123!"},
    )
    assert r.status_code in {404, 405}


async def test_company_without_passcodes_is_never_locked_out(client):
    ac, _seed = client
    login = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    await ac.post("/api/v1/pos/lock/lock", headers=login, json={"surface": "retail", "device_id": DEVICE})
    state = await ac.get(f"/api/v1/pos/lock/state?surface=retail&device_id={DEVICE}", headers=login)
    assert state.json()["data"]["locked"] is False


async def test_lock_and_unlock_are_audited(client, db_session):
    ac, seed = client
    _admin, login = await _setup(ac, seed)
    op = _op(login, await _unlock(ac, login, CODE_A))
    await ac.post(
        "/api/v1/pos/lock/lock", headers=op, json={"surface": "retail", "device_id": DEVICE, "reason": "manual"}
    )
    await _unlock(ac, login, CODE_A)
    actions = (
        await db_session.execute(select(m.AuditLog.action).where(m.AuditLog.module == "pos"))
    ).scalars().all()
    assert actions.count("pos_unlocked") == 2 and actions.count("pos_locked") == 1


async def test_state_shows_company_branding_for_the_lock_screen(client):
    ac, seed = client
    login = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    state = (await ac.get(f"/api/v1/pos/lock/state?surface=retail&device_id={DEVICE}", headers=login)).json()["data"]
    assert state["company"]["name"] == "Alpha Co" and state["company"]["has_logo"] is False
    assert state["idle_seconds"] == 60


async def test_restaurant_till_payment_needs_an_unlocked_operator_and_records_who_paid(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await ac.post(
        "/api/v1/products", headers=admin,
        json={"name": "Jollof", "selling_price": 30, "stock_qty": 50, "prep_station": "kitchen"},
    )
    await _set_code(ac, admin, seed["admin1"].id, CODE_A)
    body = {
        "service_mode": "takeaway", "payment_method": "cash", "customer_name": "Ama",
        "lines": [{"product_id": dish.json()["data"]["id"], "quantity": "1"}],
    }
    # Taking an order is not a till write, so waiter tablets keep working.
    order = await ac.post("/api/v1/restaurant/orders", headers=admin, json=body)
    assert order.status_code == 200, order.text
    oid = order.json()["data"]["id"]
    assert (await ac.post(f"/api/v1/restaurant/orders/{oid}/complete", headers=admin)).status_code == 423
    op = _op(admin, await _unlock(ac, admin, CODE_A, surface="restaurant"))
    done = await ac.post(f"/api/v1/restaurant/orders/{oid}/complete", headers=op)
    assert done.status_code == 200, done.text
    row = await db_session.get(m.RestaurantOrder, oid)
    assert row.completed_by == seed["admin1"].id and row.completed_device_id == DEVICE


async def test_each_desk_keeps_its_own_stint_on_a_device(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    _admin, login = await _setup(ac, seed)
    await _unlock(ac, login, CODE_A, surface="restaurant")
    await _unlock(ac, login, CODE_A, surface="retail")
    rows = (await db_session.execute(select(m.PosOperatorSession))).scalars().all()
    assert sorted(r.surface for r in rows) == ["restaurant", "retail"]


async def test_cashier_report_groups_sales_and_needs_reports_permission(client):
    ac, seed = client
    admin, login = await _setup(ac, seed)
    op = _op(login, await _unlock(ac, login, CODE_A))
    opened = await ac.post("/api/v1/pos/sessions/open", headers=op, json={"opening_cash": 20})
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]
    for _ in range(2):
        sale = await ac.post(
            "/api/v1/pos/sales", headers=op,
            json={
                "session_id": session_id, "payment_method": "cash", "discount_amount": 0.5,
                "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 2}],
            },
        )
        assert sale.status_code == 200, sale.text
    report = await ac.get("/api/v1/reports/sales/cashiers?period=month", headers=admin)
    assert report.status_code == 200, report.text
    data = report.json()["data"]
    row = data["cashiers"][0]
    assert row["cashier_id"] == seed["u1"].id and row["name"] == "Alpha Cashier"
    assert row["sale_count"] == 2 and row["discounts"] == 1.0
    assert data["periods"][0]["period"] == datetime.utcnow().strftime("%Y-%m")
    lines = await ac.get(f"/api/v1/reports/sales/cashiers/transactions?cashier_id={seed['u1'].id}", headers=admin)
    first = lines.json()["data"]["transactions"][0]
    assert first["name"] == "Alpha Cashier" and first["terminal"] and first["reference"]
    assert (await ac.get("/api/v1/reports/sales/cashiers", headers=login)).status_code == 403


async def test_restaurant_cashier_report_counts_voids_and_refunds_by_person(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await ac.post(
        "/api/v1/products", headers=admin,
        json={"name": "Waakye", "selling_price": 25, "stock_qty": 50, "prep_station": "kitchen"},
    )
    body = {
        "service_mode": "takeaway", "payment_method": "cash", "customer_name": "Kofi",
        "lines": [{"product_id": dish.json()["data"]["id"], "quantity": "1"}],
    }
    paid = (await ac.post("/api/v1/restaurant/orders", headers=admin, json=body)).json()["data"]["id"]
    voided = (await ac.post("/api/v1/restaurant/orders", headers=admin, json=body)).json()["data"]["id"]
    assert (await ac.post(f"/api/v1/restaurant/orders/{paid}/complete", headers=admin)).status_code == 200
    assert (await ac.post(f"/api/v1/restaurant/orders/{voided}/void", headers=admin)).status_code == 200
    assert (await ac.post(f"/api/v1/restaurant/orders/{paid}/refund", headers=admin)).status_code == 200
    report = (await ac.get("/api/v1/restaurant/reports/cashiers", headers=admin)).json()["data"]
    row = report["cashiers"][0]
    assert row["sale_count"] == 1 and row["void_count"] == 1
    assert row["refund_count"] == 1 and row["refunds_total"] == 25.0
    lines = (await ac.get("/api/v1/restaurant/reports/cashiers/transactions", headers=admin)).json()["data"]
    assert lines["transactions"][0]["status"] == "refunded"
    assert {a["action"] for a in lines["activity"]} >= {"restaurant_order_voided", "restaurant_order_refunded"}
