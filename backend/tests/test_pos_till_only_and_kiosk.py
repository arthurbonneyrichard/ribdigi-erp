"""A till opened with a passcode reaches the till and Sales only, until a full sign-in. Kiosk close code."""

from __future__ import annotations

import hashlib

import pytest

from app import pos_lock
from tests.conftest import auth_headers

pytestmark = pytest.mark.asyncio

DEVICE = "till-device-0001"
ADMIN_CODE = "482915"


async def _admin_session_with_passcode(ac, seed):
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    r = await ac.put(f"/api/v1/users/{seed['admin1'].id}/pos-passcode", headers=admin, json={"passcode": ADMIN_CODE})
    assert r.status_code == 200, r.text
    return admin


async def _unlock(ac, headers):
    r = await ac.post(
        "/api/v1/pos/lock/unlock",
        headers=headers,
        json={"surface": "retail", "device_id": DEVICE, "passcode": ADMIN_CODE},
    )
    assert r.status_code == 200, r.text
    return {**headers, "X-Pos-Operator": r.json()["data"]["operator_token"]}


async def test_full_session_is_not_restricted(client):
    ac, seed = client
    admin = await _admin_session_with_passcode(ac, seed)
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.json()["data"]["till_only"] is False
    assert (await ac.get("/api/v1/users", headers=admin)).status_code == 200


async def test_admin_passcode_holds_session_to_till_and_sales(client):
    ac, seed = client
    admin = await _admin_session_with_passcode(ac, seed)
    till = await _unlock(ac, admin)

    me = await ac.get("/api/v1/me", headers=till)
    assert me.json()["data"]["till_only"] is True

    # Sensitive screens refuse, with or without the operator header.
    for headers in (admin, till):
        for path in ("/api/v1/users", "/api/v1/accounting/accounts", "/api/v1/audit-logs", "/api/v1/backup"):
            r = await ac.get(path, headers=headers)
            assert r.status_code == 403, (path, r.text)
            assert r.json()["detail"]["code"] == "TILL_ONLY"
        r = await ac.patch("/api/v1/tenants/me", headers=headers, json={"company_name": "Hijacked Co"})
        assert r.status_code == 403 and r.json()["detail"]["code"] == "TILL_ONLY"

    # The till and Sales keep working.
    assert (await ac.get("/api/v1/pos/sessions", headers=till)).status_code == 200
    assert (await ac.get("/api/v1/sales/invoices", headers=admin)).status_code == 200
    assert (await ac.get("/api/v1/customers", headers=admin)).status_code == 200
    assert (await ac.get("/api/v1/products", headers=admin)).status_code == 200
    # Reads only for the catalog: no product edits from a passcode session.
    r = await ac.post("/api/v1/products", headers=admin, json={"name": "Sneaky", "selling_price": 1})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "TILL_ONLY"


async def test_hold_survives_token_refresh(client):
    ac, seed = client
    login = await ac.post(
        "/api/v1/auth/login",
        json={"email": "admin@alpha.example.com", "password": "SecurePass123!", "tenant_id": "alpha"},
    )
    data = login.json()["data"]
    headers = {"Authorization": f"Bearer {data['access_token']}", "X-Tenant-ID": data["user"]["tenant_id"]}
    r = await ac.put(f"/api/v1/users/{seed['admin1'].id}/pos-passcode", headers=headers, json={"passcode": ADMIN_CODE})
    assert r.status_code == 200
    await _unlock(ac, headers)
    fresh = await ac.post("/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]})
    assert fresh.status_code == 200, fresh.text
    renewed = {**headers, "Authorization": f"Bearer {fresh.json()['data']['access_token']}"}
    r = await ac.get("/api/v1/users", headers=renewed)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "TILL_ONLY"


async def test_full_sign_in_needs_the_password_and_lifts_the_hold(client):
    ac, seed = client
    admin = await _admin_session_with_passcode(ac, seed)
    await _unlock(ac, admin)

    wrong = await ac.post("/api/v1/auth/full-sign-in", headers=admin, json={"password": "not-it"})
    assert wrong.status_code == 403 and wrong.json()["detail"]["code"] == "PASSWORD_INVALID"
    # The passcode is not the password.
    code = await ac.post("/api/v1/auth/full-sign-in", headers=admin, json={"password": ADMIN_CODE})
    assert code.status_code == 403
    assert (await ac.get("/api/v1/users", headers=admin)).status_code == 403

    ok = await ac.post("/api/v1/auth/full-sign-in", headers=admin, json={"password": "SecurePass123!"})
    assert ok.status_code == 200, ok.text
    assert (await ac.get("/api/v1/users", headers=admin)).status_code == 200
    assert (await ac.get("/api/v1/me", headers=admin)).json()["data"]["till_only"] is False


async def test_full_sign_in_is_throttled(client):
    ac, seed = client
    admin = await _admin_session_with_passcode(ac, seed)
    await _unlock(ac, admin)
    last = None
    for _ in range(pos_lock.DEVICE_FAIL_LIMIT):
        last = await ac.post("/api/v1/auth/full-sign-in", headers=admin, json={"password": "guess"})
    assert last.status_code == 429
    blocked = await ac.post("/api/v1/auth/full-sign-in", headers=admin, json={"password": "SecurePass123!"})
    assert blocked.status_code == 429


async def test_other_browser_sessions_stay_full(client):
    ac, seed = client
    admin = await _admin_session_with_passcode(ac, seed)
    await _unlock(ac, admin)
    office = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/users", headers=office)).status_code == 200


async def test_till_only_paths():
    allowed = pos_lock.till_only_path_allowed
    assert allowed("POST", "/api/v1/pos/sales")
    assert allowed("POST", "/api/v1/sales/invoices")
    assert allowed("GET", "/api/v1/me")
    assert not allowed("PATCH", "/api/v1/me")
    assert allowed("POST", "/api/v1/auth/full-sign-in")
    assert allowed("GET", "/api/v1/products")
    assert not allowed("PATCH", "/api/v1/products/x")
    assert not allowed("GET", "/api/v1/accounting/accounts")
    assert not allowed("GET", "/api/v1/restaurant/staff")
    assert not allowed("POST", "/api/v1/auth/2fa/disable")


async def test_kiosk_close_code(client):
    ac, _seed = client
    staff = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    body = {"surface": "retail", "device_id": DEVICE}
    bad = await ac.post("/api/v1/pos/kiosk/close", headers=staff, json={**body, "code": "12345678"})
    assert bad.status_code == 403 and bad.json()["detail"]["code"] == "KIOSK_CODE_INVALID"
    good = await ac.post("/api/v1/pos/kiosk/close", headers=staff, json={**body, "code": "11223300"})
    assert good.status_code == 200 and good.json()["data"]["closed"] is True


async def test_kiosk_close_is_throttled(client):
    ac, _seed = client
    staff = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    body = {"surface": "retail", "device_id": DEVICE}
    for _ in range(pos_lock.DEVICE_FAIL_LIMIT):
        last = await ac.post("/api/v1/pos/kiosk/close", headers=staff, json={**body, "code": "99999999"})
    assert last.status_code == 429
    assert (await ac.post("/api/v1/pos/kiosk/close", headers=staff, json={**body, "code": "11223300"})).status_code == 429


async def test_kiosk_offline_verifier_matches_code_without_revealing_it(client):
    ac, _seed = client
    staff = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/pos/kiosk/verifier", headers=staff)
    data = r.json()["data"]
    assert "11223300" not in r.text
    digest = hashlib.pbkdf2_hmac("sha256", b"11223300", bytes.fromhex(data["salt"]), data["rounds"]).hex()
    assert digest == data["hash"] and data["length"] == 8
