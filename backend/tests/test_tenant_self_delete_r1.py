"""Company users cannot delete a tenant. Only the software owner can."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.config import settings
from tests.conftest import auth_headers, platform_owner_headers

ROOT = Path(__file__).resolve().parents[2]
OWNER_ONLY = "Only the software owner can delete a tenant"


def test_company_delete_ui_wired():
    page = (ROOT / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    assert "Delete tenant" not in page
    assert "/tenants/me/delete" not in page
    assert 'href="/printers"' in page
    assert "retention" in page.lower() or "backup" in page.lower()
    platform = (ROOT / "frontend/app/(dashboard)/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "Delete tenant" in platform
    assert "confirm_slug" in platform
    assert 'aria-label="Delete tenant confirmation"' in platform


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


def _owner_only(resp) -> None:
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"] == OWNER_ONLY


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
    _owner_only(wrong_name)
    wrong_password = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "WrongPass123!", "confirm_name": name, "confirm": True},
    )
    _owner_only(wrong_password)
    deleted = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": name, "confirm": True},
    )
    _owner_only(deleted)

    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert tenant_id in ids
    assert seed["t1"].id in ids
    assert media.exists()
    assert backup.exists()

    still = await ac.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!", "tenant_id": slug},
    )
    assert still.status_code == 200, still.text


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
    own = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": "Alpha Co", "confirm": True},
    )
    _owner_only(own)
    other_path = await ac.post(
        "/api/v1/tenants/beta/delete",
        headers=admin,
        json={"confirm_slug": "beta"},
    )
    assert other_path.status_code == 403, other_path.text
    still = await ac.get("/api/v1/tenants/me", headers=admin)
    assert still.status_code == 200, still.text
    assert still.json()["data"]["id"] == seed["t1"].id
    beta = await ac.get("/api/v1/tenants", headers=await _owner(ac, seed))
    assert seed["t2"].id in {row["id"] for row in beta.json()["data"]}


@pytest.mark.asyncio
async def test_owner_workspace_host_cannot_self_delete(client, seeded):
    ac, seed = client
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    resp = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": "Alpha Co", "confirm": True},
    )
    _owner_only(resp)
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
    blocked = await ac.post(
        "/api/v1/tenants/me/delete",
        headers=admin,
        json={"password": "SecurePass123!", "confirm_name": name, "confirm": True},
    )
    _owner_only(blocked)
    assert calls["n"] == 0
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200, me.text

    first = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=owner,
        json={"confirm_slug": slug},
    )
    assert first.status_code == 409, first.text
    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert tenant_id in {row["id"] for row in listed.json()["data"]}
    still = await ac.get("/api/v1/me", headers=admin)
    assert still.status_code == 200, still.text

    second = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=owner,
        json={"confirm_slug": slug},
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["id"] == tenant_id
    assert second.json()["data"]["slug"] == slug
    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert tenant_id not in {row["id"] for row in listed.json()["data"]}
    assert calls["n"] == 2
    gone = await ac.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!", "tenant_id": slug},
    )
    assert gone.status_code in {401, 403, 404}, gone.text
