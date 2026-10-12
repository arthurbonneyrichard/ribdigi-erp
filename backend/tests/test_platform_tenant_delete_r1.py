"""Only the software owner can permanently delete a company tenant."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers, platform_owner_headers

ROOT = Path(__file__).resolve().parents[2]


def test_platform_tenant_delete_ui_wired():
    plat = (ROOT / "frontend/app/(dashboard)/platform/tenants/page.tsx").read_text(encoding="utf-8")
    assert "async function deleteTenant" in plat
    assert "/delete" in plat
    assert "confirm_slug" in plat
    assert 'aria-label={`Delete tenant ${t.slug || t.id}`}' in plat
    assert 'aria-label="Delete tenant confirmation"' in plat
    assert "canDeleteTenant" in plat
    assert "const canHardDeleteTenant = canDeleteTenant" in plat
    assert "meRole === 'platform_admin'" not in plat
    assert "Only the software owner can delete a company." in plat


@pytest.mark.asyncio
async def test_platform_owner_can_delete_tenant(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    slug = f"del-co-{suffix}"
    created = await ac.post(
        "/api/v1/tenants",
        headers=admin,
        json={
            "company_name": f"Delete Co {suffix}",
            "slug": slug,
            "admin_email": f"admin-{suffix}@deleteco.example.com",
            "admin_password": "SecurePass123!",
            "industry": "retail",
            "currency": "GHS",
        },
    )
    assert created.status_code == 200, created.text
    tenant_id = created.json()["data"]["tenant_id"]
    assert created.json()["data"]["slug"] == slug

    bad_confirm = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=admin,
        json={"confirm_slug": "wrong-slug"},
    )
    assert bad_confirm.status_code == 400, bad_confirm.text

    deleted = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=admin,
        json={"confirm_slug": slug},
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["id"] == tenant_id
    assert deleted.json()["data"]["slug"] == slug

    listed = await ac.get("/api/v1/tenants", headers=admin)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert tenant_id not in ids

    missing = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=admin,
        json={"confirm_slug": slug},
    )
    assert missing.status_code == 404, missing.text


@pytest.mark.asyncio
async def test_cannot_delete_own_workspace(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    me = await ac.get("/api/v1/me", headers=admin)
    assert me.status_code == 200
    my_tenant = me.json()["data"]["tenant_id"]
    listed = await ac.get("/api/v1/tenants", headers=admin)
    own = next((t for t in listed.json()["data"] if t["id"] == my_tenant), None)
    assert own is not None
    resp = await ac.post(
        f"/api/v1/tenants/{own['slug']}/delete",
        headers=admin,
        json={"confirm_slug": own["slug"]},
    )
    assert resp.status_code == 400, resp.text
    assert "own" in resp.json()["detail"].lower() or "workspace" in resp.json()["detail"].lower()


async def _owner(ac, seed):
    return await platform_owner_headers(ac, seed)


async def _create_company(ac, headers, *, slug: str, email: str) -> dict:
    created = await ac.post(
        "/api/v1/tenants",
        headers=headers,
        json={
            "company_name": f"Company {slug}",
            "slug": slug,
            "admin_email": email,
            "admin_password": "SecurePass123!",
            "industry": "retail",
            "currency": "GHS",
        },
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]


async def _staff(ac, owner_headers, db_session, *, email: str, role: str) -> dict:
    created = await ac.post(
        "/api/v1/platform/staff",
        headers=owner_headers,
        json={
            "email": email,
            "full_name": role.replace("_", " ").title(),
            "password": "SecurePass123!",
            "role": role,
        },
    )
    assert created.status_code == 200, created.text
    user = (
        await db_session.execute(select(m.User).where(m.User.email == email))
    ).scalar_one()
    user.email_verified = True
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug="alpha")


@pytest.mark.asyncio
async def test_platform_admin_can_delete_tenant(client, db_session):
    ac, seed = client
    owner = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    slug = f"admin-del-{suffix}"
    await _create_company(ac, owner, slug=slug, email=f"admin-{suffix}@deleteco.example.com")
    admin = await _staff(
        ac, owner, db_session, email=f"padmin-{suffix}@alpha.example.com", role="platform_admin"
    )
    deleted = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=admin,
        json={"confirm_slug": slug},
    )
    assert deleted.status_code == 403, deleted.text
    assert "software owner" in str(deleted.json()["detail"]).lower()
    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert slug in {row["slug"] for row in listed.json()["data"]}


@pytest.mark.asyncio
async def test_delete_forbidden_for_support_finance_and_company_admin(client, db_session):
    ac, seed = client
    owner = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    slug = f"keep-del-{suffix}"
    await _create_company(ac, owner, slug=slug, email=f"keep-{suffix}@deleteco.example.com")
    support = await _staff(
        ac, owner, db_session, email=f"psup-{suffix}@alpha.example.com", role="platform_support"
    )
    finance = await _staff(
        ac, owner, db_session, email=f"pfin-{suffix}@alpha.example.com", role="platform_finance"
    )
    company = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    body = {"confirm_slug": slug}
    for headers in (support, finance, company):
        denied = await ac.post(f"/api/v1/tenants/{slug}/delete", headers=headers, json=body)
        assert denied.status_code == 403, denied.text
    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert slug in {row["slug"] for row in listed.json()["data"]}


@pytest.mark.asyncio
async def test_delete_confirmation_is_required(client, seeded):
    ac, seed = client
    owner = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    slug = f"confirm-del-{suffix}"
    await _create_company(ac, owner, slug=slug, email=f"confirm-{suffix}@deleteco.example.com")
    missing = await ac.post(f"/api/v1/tenants/{slug}/delete", headers=owner, json={})
    assert missing.status_code == 422, missing.text
    garbage = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=owner,
        json={"confirm_slug": "!!!"},
    )
    assert garbage.status_code == 422, garbage.text
    extra = await ac.post(
        f"/api/v1/tenants/{slug}/delete",
        headers=owner,
        json={"confirm_slug": slug, "reason": "nope"},
    )
    assert extra.status_code == 422, extra.text
    unknown = await ac.post(
        "/api/v1/tenants/no-such-company/delete",
        headers=owner,
        json={"confirm_slug": "no-such-company"},
    )
    assert unknown.status_code == 404, unknown.text
    listed = await ac.get("/api/v1/tenants", headers=owner)
    assert slug in {row["slug"] for row in listed.json()["data"]}


@pytest.mark.asyncio
async def test_delete_leaves_the_other_tenant(client, seeded):
    ac, seed = client
    owner = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    keep = f"keep-co-{suffix}"
    drop = f"drop-co-{suffix}"
    await _create_company(ac, owner, slug=keep, email=f"keep-{suffix}@deleteco.example.com")
    await _create_company(ac, owner, slug=drop, email=f"drop-{suffix}@deleteco.example.com")
    for slug in (keep, drop):
        verified = await ac.post(f"/api/v1/tenants/{slug}/verify-admin", headers=owner)
        assert verified.status_code == 200, verified.text
    keep_headers = await auth_headers(
        ac, email=f"keep-{suffix}@deleteco.example.com", tenant_slug=keep
    )
    drop_headers = await auth_headers(
        ac, email=f"drop-{suffix}@deleteco.example.com", tenant_slug=drop
    )
    keep_product = await ac.post(
        "/api/v1/products",
        headers=keep_headers,
        json={"name": f"Keep item {suffix}"},
    )
    assert keep_product.status_code == 200, keep_product.text
    drop_product = await ac.post(
        "/api/v1/products",
        headers=drop_headers,
        json={"name": f"Drop item {suffix}"},
    )
    assert drop_product.status_code == 200, drop_product.text

    deleted = await ac.post(
        f"/api/v1/tenants/{drop}/delete",
        headers=owner,
        json={"confirm_slug": drop},
    )
    assert deleted.status_code == 200, deleted.text

    still = await ac.get("/api/v1/products", headers=keep_headers)
    assert still.status_code == 200, still.text
    names = {row["name"] for row in still.json()["data"]}
    assert f"Keep item {suffix}" in names
    assert f"Drop item {suffix}" not in names

    gone = await ac.post(
        "/api/v1/auth/login",
        json={
            "email": f"drop-{suffix}@deleteco.example.com",
            "password": "SecurePass123!",
            "tenant_id": drop,
        },
    )
    assert gone.status_code == 404, gone.text
