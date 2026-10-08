"""Company admin can delete only the company on their own token."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app import models as m
from app.config import settings
from tests.conftest import auth_headers, platform_owner_headers

ROOT = Path(__file__).resolve().parents[2]


def test_company_delete_ui_wired():
    page = (ROOT / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    assert "Delete tenant" in page
    assert 'aria-label="Delete tenant"' in page
    assert 'aria-label="Delete tenant confirmation name"' in page
    assert 'aria-label="Delete tenant password"' in page
    assert "/tenants/me/delete" in page
    assert 'href="/printers"' in page
    assert "retention" in page.lower() or "backup" in page.lower()


async def _owner(ac, seed):
    return await platform_owner_headers(ac, seed)


async def _company(ac, headers, *, slug: str, name: str, email: str) -> str:
    created = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={
            "company_name": name,
            "slug": slug,
            "admin_email": email,
            "admin_password": "SecurePass123!",
            "industry": "retail",
            "currency": "GHS",
        },
    )
    assert created.status_code == 200, created.text
    verified = await ac.post(f"/api/v1/tenants/{slug}/verify-admin", headers=headers)
    assert verified.status_code == 200, verified.text
    return created.json()["data"]["tenant_id"]


@pytest.mark.asyncio
async def test_company_admin_deletes_only_own_tenant(client, seeded):
    ac, seed = client
    owner = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    slug = f"gone-{suffix}"
    name = f"Gone Co {suffix}"
    email = f"admin-{suffix}@gone.example.com"
    tenant_id = await _company(ac, owner, slug=slug, name=name, email=email)
    media = Path(settings.MEDIA_DIR) / tenant_id
    media.mkdir(parents=True)
    (media / "logo.txt").write_text("company-file", encoding="utf-8")
    backup = Path(settings.BACKUP_DIR) / tenant_id
    backup.mkdir(parents=True)
    (backup / "archive.ribbak").write_text("archive", encoding="utf-8")

    admin = await auth_headers(ac, email=email, tenant_slug=slug)
    wrong_name = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": "Other Co", "confirm": True},
    )
    assert wrong_name.status_code == 400, wrong_name.text
    wrong_password = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "WrongPass123!", "confirm_name": name, "confirm": True},
    )
    assert wrong_password.status_code == 401, wrong_password.text

    deleted = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": name, "confirm": True},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["deleted_tenant_id"] == tenant_id
    assert deleted.json()["data"]["status"] == "completed"
    assert not media.exists()
    assert not backup.exists()

    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert tenant_id not in ids
    assert seed["t1"].id in ids

    again = await ac.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!", "tenant_id": slug},
    )
    assert again.status_code in {401, 403, 404}, again.text

    import app.jobs as jobs_mod

    async with jobs_mod.SessionLocal() as db:
        row = (
            await db.execute(
                select(m.PlatformTenantDeletion).where(
                    m.PlatformTenantDeletion.deleted_tenant_id == tenant_id
                )
            )
        ).scalar_one()
        assert row.status == "completed"
        assert row.actor_user_id
        assert not hasattr(row, "company_name")
        owners = (
            await db.execute(
                select(func.count()).select_from(m.User).where(m.User.role == "super_admin")
            )
        ).scalar_one()
        assert owners >= 1
        note = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.user_id == seed["super"].id,
                    m.Notification.entity_id == tenant_id,
                )
            )
        ).scalar_one()
        assert note.title == "Tenant deletion completed"
        assert tenant_id in note.message
        assert name not in note.message


@pytest.mark.asyncio
async def test_staff_and_other_tenant_cannot_delete(client, seeded):
    ac, seed = client
    cashier = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    blocked = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=cashier,
        json={"password": "SecurePass123!", "confirm_name": "Alpha Co", "confirm": True},
    )
    assert blocked.status_code == 403, blocked.text

    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    poisoned = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={
            "password": "SecurePass123!",
            "confirm_name": "Beta Co",
            "confirm": True,
            "tenant_id": seed["t2"].id,
        },
    )
    assert poisoned.status_code == 422, poisoned.text
    other_path = await ac.post(
        "/api/v1/tenants/beta/delete",
        headers=admin,
        json={"confirm_slug": "beta"},
    )
    assert other_path.status_code == 403, other_path.text
    still = await ac.get("/api/v1/tenants/me", headers=admin)
    assert still.status_code == 200, still.text
    assert still.json()["data"]["id"] == seed["t1"].id


@pytest.mark.asyncio
async def test_owner_workspace_host_cannot_self_delete(client, seeded):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    resp = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": "Alpha Co", "confirm": True},
    )
    assert resp.status_code == 400, resp.text
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text
    assert me.json()["data"]["tenant_id"] == seed["t1"].id


@pytest.mark.asyncio
async def test_failed_purge_can_be_retried(client, seeded, monkeypatch):
    ac, seed = client
    owner = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    slug = f"retry-{suffix}"
    name = f"Retry Co {suffix}"
    email = f"admin-{suffix}@retry.example.com"
    tenant_id = await _company(ac, owner, slug=slug, name=name, email=email)
    admin = await auth_headers(ac, email=email, tenant_slug=slug)

    calls = {"n": 0}
    real = __import__("app.tenants", fromlist=["purge_tenant_records"]).purge_tenant_records

    async def flaky(db, tenant):
        calls["n"] += 1
        if calls["n"] == 1:
            raise HTTPException(status_code=409, detail="boom")
        return await real(db, tenant)

    monkeypatch.setattr("app.tenants.purge_tenant_records", flaky)
    first = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": name, "confirm": True},
    )
    assert first.status_code == 409, first.text
    stale = await ac.get("/api/v1/me", headers=admin)
    assert stale.status_code == 401, stale.text

    admin = await auth_headers(ac, email=email, tenant_slug=slug)
    second = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": name, "confirm": True},
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["status"] == "completed"
    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert tenant_id not in {row["id"] for row in listed.json()["data"]}
