"""Two sign-ins: Admin (company code, email, password) for owners and admins, and User
(username or email, password) for the staff they create."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers

PW = "SecurePass123!"


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _staff_user(db_session, tenant, *, role="cashier", email=None, username=None):
    user = m.User(
        tenant_id=tenant.id, email=email or f"staff-{uuid4().hex[:6]}@example.com", username=username,
        full_name="Staff Person", password_hash=hash_password(PW), role=role, email_verified=True,
        permissions=permissions_for_role(role),
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_admin_sign_in_lets_owners_in_and_sends_staff_to_the_user_tab(client, seeded):
    ac, _seed = client
    ok = await ac.post("/api/v1/auth/login", json={"tenant_id": "alpha", "email": "admin@alpha.example.com", "password": PW, "portal": "admin"})
    assert ok.status_code == 200, ok.text
    staff = await ac.post("/api/v1/auth/login", json={"tenant_id": "alpha", "email": "cashier@alpha.example.com", "password": PW, "portal": "admin"})
    assert staff.status_code == 403 and staff.json()["detail"]["code"] == "USE_USER_SIGN_IN"
    wrong = await ac.post("/api/v1/auth/login", json={"tenant_id": "alpha", "email": "cashier@alpha.example.com", "password": "WrongPass123!", "portal": "admin"})
    assert wrong.status_code == 401


@pytest.mark.asyncio
async def test_staff_sign_in_by_username_needs_no_company_code(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac)
    user = await _staff_user(db_session, seed["t1"])
    r = await ac.patch(f"/api/v1/users/{user.id}", headers=h, json={"username": "  Ama.Owusu "})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["username"] == "ama.owusu"
    signed = await ac.post("/api/v1/auth/staff-login", json={"login": "AMA.owusu", "password": PW})
    assert signed.status_code == 200, signed.text
    assert signed.json()["data"]["user"]["tenant_id"] == seed["t1"].id
    wrong = await ac.post("/api/v1/auth/staff-login", json={"login": "ama.owusu", "password": "WrongPass123!"})
    assert wrong.status_code == 401
    nobody = await ac.post("/api/v1/auth/staff-login", json={"login": "no.such.person", "password": PW})
    assert nobody.status_code == 401


@pytest.mark.asyncio
async def test_staff_sign_in_by_email_and_owners_are_sent_to_the_admin_tab(client, seeded):
    ac, _seed = client
    r = await ac.post("/api/v1/auth/staff-login", json={"login": "Cashier@Alpha.example.com", "password": PW})
    assert r.status_code == 200, r.text
    owner = await ac.post("/api/v1/auth/staff-login", json={"login": "admin@alpha.example.com", "password": PW})
    assert owner.status_code == 403 and owner.json()["detail"]["code"] == "USE_ADMIN_SIGN_IN"


@pytest.mark.asyncio
async def test_an_email_in_two_companies_asks_for_a_username(client, seeded, db_session):
    ac, seed = client
    email = f"shared-{uuid4().hex[:6]}@example.com"
    await _staff_user(db_session, seed["t1"], email=email)
    await _staff_user(db_session, seed["t2"], email=email)
    r = await ac.post("/api/v1/auth/staff-login", json={"login": email, "password": PW})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "LOGIN_NOT_UNIQUE"


@pytest.mark.asyncio
async def test_usernames_are_unique_across_every_company(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac)
    await _staff_user(db_session, seed["t2"], username="kofi.b")
    body = {"email": f"new-{uuid4().hex[:6]}@example.com", "full_name": "Kofi Boateng", "password": PW, "role": "cashier"}
    taken = await ac.post("/api/v1/users", headers=h, json={**body, "username": "KOFI.B"})
    assert taken.status_code == 409
    bad = await ac.post("/api/v1/users", headers=h, json={**body, "username": "k!"})
    assert bad.status_code == 422
    made = await ac.post("/api/v1/users", headers=h, json={**body, "username": "kofi.boateng"})
    assert made.status_code == 200, made.text
    assert made.json()["data"]["user"]["username"] == "kofi.boateng"
    r = await ac.post("/api/v1/auth/staff-login", json={"login": "kofi.boateng", "password": PW})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_the_old_sign_in_still_works_for_api_clients(client, seeded):
    ac, _seed = client
    r = await ac.post("/api/v1/auth/login", json={"tenant_id": "alpha", "email": "cashier@alpha.example.com", "password": PW})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_an_owner_of_two_companies_is_sent_to_the_admin_tab(client, seeded, db_session):
    ac, seed = client
    email = f"owner-{uuid4().hex[:6]}@example.com"
    await _staff_user(db_session, seed["t1"], email=email, role="company_admin")
    await _staff_user(db_session, seed["t2"], email=email, role="company_admin")
    r = await ac.post("/api/v1/auth/staff-login", json={"login": email, "password": PW})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "USE_ADMIN_SIGN_IN"
