"""Stage 1 B6 — isolation hygiene for user import, SMTP settings, warehouse PATCH."""

from __future__ import annotations

import io

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.stores import create_store
from tests.conftest import auth_headers


async def _super_headers(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _mgr_headers(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_mismatched_tenant_header_on_users_import_403(client):
    ac, seed = client
    headers = await _super_headers(ac, seed)
    headers["X-Tenant-ID"] = seed["t2"].id

    tmpl = await ac.get("/api/v1/users/import/template", headers=headers)
    assert tmpl.status_code == 403, tmpl.text

    csv_body = (
        "full_name,email,phone,role,branch_code,department_code,password,record_scope\n"
        "Leak Attempt,leak@alpha.example.com,,cashier,,,SecurePass123!,own\n"
    )
    posted = await ac.post(
        "/api/v1/users/import?dry_run=false",
        headers=headers,
        files={"file": ("users.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert posted.status_code == 403, posted.text


@pytest.mark.asyncio
async def test_user_import_commit_scopes_to_actor_tenant(client, db_session):
    ac, seed = client
    headers = await _super_headers(ac, seed)
    csv_body = (
        "full_name,email,phone,role,branch_code,department_code,password,record_scope\n"
        "Scoped Import,scoped-import@alpha.example.com,,cashier,,,SecurePass123!,own\n"
    )
    committed = await ac.post(
        "/api/v1/users/import?dry_run=false",
        headers=headers,
        files={"file": ("users.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert committed.status_code == 200, committed.text
    created = committed.json()["data"]["created"]
    assert len(created) == 1

    row = (
        await db_session.execute(
            select(m.User).where(m.User.email == "scoped-import@alpha.example.com")
        )
    ).scalar_one()
    assert row.tenant_id == seed["t1"].id

    beta_has = (
        await db_session.execute(
            select(m.User).where(
                m.User.tenant_id == seed["t2"].id,
                m.User.email == "scoped-import@alpha.example.com",
            )
        )
    ).scalar_one_or_none()
    assert beta_has is None


@pytest.mark.asyncio
async def test_user_import_rejects_foreign_branch_code(client, db_session):
    ac, seed = client
    beta_branch = m.Branch(
        tenant_id=seed["t2"].id,
        code="BETA-BR",
        name="Beta Branch",
        is_active=True,
    )
    db_session.add(beta_branch)
    await db_session.commit()

    headers = await _super_headers(ac, seed)
    csv_body = (
        "full_name,email,phone,role,branch_code,department_code,password,record_scope\n"
        f"Cross Branch,cross-branch@alpha.example.com,,cashier,{beta_branch.code},,SecurePass123!,own\n"
    )
    dry = await ac.post(
        "/api/v1/users/import?dry_run=true",
        headers=headers,
        files={"file": ("users.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert dry.status_code == 200, dry.text
    data = dry.json()["data"]
    assert data["valid_rows"] == 0
    assert data["error_rows"] == 1
    flat = " ".join(
        " ".join(err.get("errors") or [])
        for err in (data.get("errors") or [])
    ).lower()
    assert "branch" in flat


@pytest.mark.asyncio
async def test_user_import_allows_email_used_in_other_tenant(client, db_session):
    ac, seed = client
    # Beta already has cashier@beta.example.com; reuse same email under alpha is allowed
    # (per-tenant unique). Use a distinct shared-looking local part on alpha.
    headers = await _super_headers(ac, seed)
    shared = "shared.user@example.com"
    beta_user = m.User(
        tenant_id=seed["t2"].id,
        email=shared,
        full_name="Beta Shared",
        password_hash=seed["u2"].password_hash,
        role="cashier",
        email_verified=True,
        permissions=seed["u2"].permissions,
    )
    db_session.add(beta_user)
    await db_session.commit()

    csv_body = (
        "full_name,email,phone,role,branch_code,department_code,password,record_scope\n"
        f"Alpha Shared,{shared},,cashier,,,SecurePass123!,own\n"
    )
    committed = await ac.post(
        "/api/v1/users/import?dry_run=false",
        headers=headers,
        files={"file": ("users.csv", io.BytesIO(csv_body.encode()), "text/csv")},
    )
    assert committed.status_code == 200, committed.text
    assert committed.json()["data"]["valid_rows"] == 1
    rows = (
        await db_session.execute(select(m.User).where(m.User.email == shared))
    ).scalars().all()
    assert len(rows) == 2
    assert {r.tenant_id for r in rows} == {seed["t1"].id, seed["t2"].id}


@pytest.mark.asyncio
async def test_mismatched_tenant_header_on_settings_email_403(client):
    ac, seed = client
    headers = await _super_headers(ac, seed)
    headers["X-Tenant-ID"] = seed["t2"].id
    get_r = await ac.get("/api/v1/settings/email", headers=headers)
    assert get_r.status_code == 403, get_r.text
    patch_r = await ac.patch(
        "/api/v1/settings/email",
        headers=headers,
        json={"smtp_enabled": True, "smtp_host": "evil.example.com"},
    )
    assert patch_r.status_code == 403, patch_r.text


@pytest.mark.asyncio
async def test_smtp_patch_does_not_mutate_other_tenant(client, db_session):
    ac, seed = client
    headers = await _super_headers(ac, seed)
    seed["t2"].smtp_host = "beta-original.example.com"
    seed["t2"].smtp_enabled = True
    await db_session.commit()

    saved = await ac.patch(
        "/api/v1/settings/email",
        headers=headers,
        json={
            "smtp_enabled": True,
            "smtp_host": "alpha-only.example.com",
            "smtp_from_email": "noreply@alpha.example.com",
            "smtp_password": "alpha-secret",
        },
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    assert data["host"] == "alpha-only.example.com"
    assert "smtp_password" not in data
    assert data.get("password") is None

    await db_session.refresh(seed["t2"])
    assert seed["t2"].smtp_host == "beta-original.example.com"


@pytest.mark.asyncio
async def test_foreign_warehouse_patch_404(client, db_session):
    ac, seed = client
    beta_wh = m.Warehouse(
        tenant_id=seed["t2"].id,
        code="BETA-WH",
        name="Beta Warehouse",
        warehouse_type="main",
        is_active=True,
    )
    db_session.add(beta_wh)
    await db_session.commit()

    headers = await _mgr_headers(ac)
    r = await ac.patch(
        f"/api/v1/warehouses/{beta_wh.id}",
        headers=headers,
        json={"name": "Hijacked Name", "capacity": 999},
    )
    assert r.status_code == 404, r.text
    await db_session.refresh(beta_wh)
    assert beta_wh.name == "Beta Warehouse"
    assert beta_wh.capacity is None or float(beta_wh.capacity or 0) != 999


@pytest.mark.asyncio
async def test_foreign_manager_id_on_warehouse_patch_404(client, db_session):
    ac, seed = client
    store = await create_store(
        db_session,
        tenant_id=seed["t1"].id,
        code="WH-ISO",
        name="Isolation Store",
    )
    await db_session.commit()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()

    headers = await _mgr_headers(ac)
    r = await ac.patch(
        f"/api/v1/warehouses/{wh.id}",
        headers=headers,
        json={"manager_id": seed["u2"].id},
    )
    assert r.status_code == 404, r.text
    await db_session.refresh(wh)
    assert wh.manager_id != seed["u2"].id


@pytest.mark.asyncio
async def test_mismatched_tenant_header_on_warehouse_patch_403(client, db_session):
    ac, seed = client
    store = await create_store(
        db_session,
        tenant_id=seed["t1"].id,
        code="WH-HDR",
        name="Header Store",
    )
    await db_session.commit()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()

    headers = await _mgr_headers(ac)
    headers["X-Tenant-ID"] = seed["t2"].id
    r = await ac.patch(
        f"/api/v1/warehouses/{wh.id}",
        headers=headers,
        json={"name": "Should Fail"},
    )
    assert r.status_code == 403, r.text
