"""Platform Owner staff deletion, admin reset, industry modules, and notification audience."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from sqlalchemy import select

from app import audit as audit_svc
from app import models as m
from app import notifications as note_svc
from app import packages as packages_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def _forbidden_password_keys(payload: dict) -> list[str]:
    blocked = {"password", "admin_password", "new_password", "password_hash", "reset_token", "token"}
    return [key for key in payload if key in blocked]


async def _owner(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_platform_console_ui_keeps_working_controls():
    overview = (ROOT / "frontend/app/(dashboard)/platform/page.tsx").read_text(encoding="utf-8")
    page = (ROOT / "frontend/app/(dashboard)/platform/tenants/page.tsx").read_text(encoding="utf-8")
    staff = (ROOT / "frontend/app/(dashboard)/platform/staff/page.tsx").read_text(encoding="utf-8")
    notes = (ROOT / "frontend/app/(dashboard)/notifications/page.tsx").read_text(encoding="utf-8")
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    nav = (ROOT / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    assert "Platform activity" in overview
    assert "Tenants by status" in overview
    assert "Tenants by industry" in overview
    assert "Create tenant" not in overview
    assert "Reset administrator password" in page
    assert "admin-password-reset" in page
    assert "industryAllowsModule(selected.industry, mod)" in page
    assert "(industry)" not in page
    head = page.split("type SubscriptionInfo", 1)[0]
    assert "Retail, Hotel, and Restaurant" in head
    for removed in ("fmcg", "hospital", "pharmacy", "wholesale"):
        assert removed not in head
    assert "['Tenant', '/platform/tenants', 'platform_tenants']" in nav
    platform_nav = nav.split("export const PLATFORM_NAV_ITEMS", 1)[1].split("const PLATFORM_SUPPORT_NAV_ROLES", 1)[0]
    assert "['Users', '/users', 'users']" not in platform_nav
    assert "platformNavItemsForRole" in shell
    assert "async function deleteStaff" not in staff
    assert "Delete platform staff" not in staff
    assert "Staff directory" in staff
    assert "PLATFORM_CATEGORY_CHIPS" in notes
    assert "low_stock" in notes
    assert "OPERATIONAL_CATEGORIES" in notes


def test_hotel_and_fmcg_stay_on_industry_allowlists():
    assert packages_svc.industry_allows_module("hotel", "hotel")
    assert packages_svc.industry_allows_module("restaurant", "restaurant")
    assert not packages_svc.industry_allows_module("fmcg", "fmcg")
    assert not packages_svc.industry_allows_module("retail", "hotel")
    assert not packages_svc.industry_allows_module("hotel", "fmcg")
    assert "hotel" in packages_svc.IMPLEMENTED_INDUSTRY_MODULES
    assert "restaurant" in packages_svc.IMPLEMENTED_INDUSTRY_MODULES
    assert "fmcg" not in packages_svc.IMPLEMENTED_INDUSTRY_MODULES


@pytest.mark.asyncio
async def test_staff_delete_retains_row_revokes_access_and_audits(client, seeded, db_session):
    ac, seed = client
    admin = await _owner(ac, seed)
    suffix = uuid4().hex[:8]
    email = f"del-staff-{suffix}@example.com"
    created = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": email,
            "full_name": f"Delete Me {suffix}",
            "password": "SecurePass123!",
            "role": "platform_support",
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["data"]["id"]
    verified = await ac.post(f"/api/v1/platform/staff/{uid}/verify-email", headers=admin)
    assert verified.status_code == 200, verified.text

    signed_in = await ac.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!", "tenant_id": "alpha"},
    )
    assert signed_in.status_code == 200, signed_in.text
    token = signed_in.json()["data"]["access_token"]
    staff_headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-ID": seed["t1"].id,
    }

    deleted = await ac.delete(f"/api/v1/platform/staff/{uid}", headers=admin)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["email"] == email
    assert "password" not in deleted.json()["data"]

    listed = await ac.get("/api/v1/platform/staff", headers=admin)
    assert uid not in {row["id"] for row in listed.json()["data"]}

    again = await ac.delete(f"/api/v1/platform/staff/{uid}", headers=admin)
    assert again.status_code == 404, again.text

    blocked = await ac.get("/api/v1/platform/staff", headers=staff_headers)
    assert blocked.status_code == 401, blocked.text

    relogin = await ac.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!", "tenant_id": "alpha"},
    )
    assert relogin.status_code == 401, relogin.text

    await db_session.commit()
    row = (
        await db_session.execute(select(m.User).where(m.User.id == uid))
    ).scalar_one()
    assert row.is_active is False
    assert row.permissions.get("_deleted") is True
    assert row.email != email

    logs = await ac.get(
        "/api/v1/audit-logs?module=platform_staff&action=delete",
        headers=admin,
    )
    assert logs.status_code == 200, logs.text
    assert any(item["entity_id"] == uid for item in logs.json()["data"])


@pytest.mark.asyncio
async def test_cannot_delete_last_active_platform_owner(client, seeded):
    ac, seed = client
    admin = await _owner(ac, seed)
    me = await ac.get("/api/v1/me", headers=admin)
    my_id = me.json()["data"]["id"]
    resp = await ac.delete(f"/api/v1/platform/staff/{my_id}", headers=admin)
    assert resp.status_code == 400, resp.text
    detail = resp.json()["detail"].lower()
    assert "own" in detail
    assert "last active" in detail

    suffix = uuid4().hex[:8]
    other = await ac.post(
        "/api/v1/platform/staff",
        headers=admin,
        json={
            "email": f"owner-{suffix}@example.com",
            "full_name": f"Second Owner {suffix}",
            "password": "SecurePass123!",
            "role": "platform_owner",
        },
    )
    assert other.status_code == 200, other.text
    removed = await ac.delete(
        f"/api/v1/platform/staff/{other.json()['data']['id']}",
        headers=admin,
    )
    assert removed.status_code == 200, removed.text
    still = await ac.delete(f"/api/v1/platform/staff/{my_id}", headers=admin)
    assert still.status_code == 400, still.text
    assert "last active" in still.json()["detail"].lower()


@pytest.mark.asyncio
async def test_tenant_admin_reset_is_scoped_and_hides_passwords(client, seeded, db_session):
    ac, seed = client
    admin = await _owner(ac, seed)
    session = m.AuthSession(
        tenant_id=seed["t1"].id,
        user_id=seed["admin1"].id,
        refresh_token_hash="hash-" + uuid4().hex,
        jti=uuid4().hex,
        expires_at=__import__("datetime").datetime.utcnow()
        + __import__("datetime").timedelta(hours=1),
    )
    db_session.add(session)
    await db_session.commit()

    reset = await ac.post(
        f"/api/v1/tenants/{seed['t1'].id}/admin-password-reset",
        headers=admin,
        json={"user_id": seed["admin1"].id},
    )
    assert reset.status_code == 200, reset.text
    body = reset.json()["data"]
    assert body["user_id"] == seed["admin1"].id
    assert body["initiated_by"] == seed["super"].id
    assert body["initiated_at"]
    assert _forbidden_password_keys(body) == []
    assert "reset_token" not in reset.text
    assert int(body["sessions_revoked"]) >= 1

    await db_session.refresh(session)
    assert session.revoked_at is not None

    cashier = await ac.post(
        f"/api/v1/tenants/{seed['t1'].id}/admin-password-reset",
        headers=admin,
        json={"user_id": seed["u1"].id},
    )
    assert cashier.status_code == 403, cashier.text

    cross = await ac.post(
        f"/api/v1/tenants/{seed['t1'].id}/admin-password-reset",
        headers=admin,
        json={"user_id": seed["u2"].id},
    )
    assert cross.status_code == 404, cross.text
    assert _forbidden_password_keys(cross.json()) == []

    tenant_admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(
        f"/api/v1/tenants/{seed['t1'].id}/admin-password-reset",
        headers=tenant_admin,
        json={},
    )
    assert denied.status_code == 403, denied.text

    leaked = await ac.post(
        f"/api/v1/tenants/{seed['t1'].id}/admin-password-reset",
        headers=admin,
        json={"user_id": seed["admin1"].id, "password": "NewSecret123!"},
    )
    assert leaked.status_code == 422, leaked.text


@pytest.mark.asyncio
async def test_modules_follow_tenant_industry(client, seeded, db_session):
    ac, seed = client
    admin = await _owner(ac, seed)
    retail = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/modules",
        headers=admin,
        json={"enabled_modules": ["inventory", "sales", "hotel", "fmcg"]},
    )
    assert retail.status_code == 422, retail.text
    assert "hotel" in retail.text or "fmcg" in retail.text

    seed["t1"].industry = "hotel"
    await db_session.commit()
    hotel = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/modules",
        headers=admin,
        json={"enabled_modules": ["inventory", "hotel"]},
    )
    assert hotel.status_code == 200, hotel.text
    mods = hotel.json()["data"]["enabled_modules"]
    assert "hotel" in mods
    assert "fmcg" not in mods

    other = await ac.patch(
        f"/api/v1/tenants/{seed['t1'].slug}/modules",
        headers=admin,
        json={"enabled_modules": ["inventory", "fmcg"]},
    )
    assert other.status_code == 422, other.text


@pytest.mark.asyncio
async def test_platform_directory_and_activity_skip_store_ops(client, seeded, db_session):
    ac, seed = client
    admin = await _owner(ac, seed)
    await audit_svc.record_event(
        db_session,
        tenant_id=seed["t1"].id,
        user_id=seed["super"].id,
        module="pos",
        action="sale_completed",
        entity="pos_sale",
        entity_id=seed["p1"].id,
        details={"total": 10},
    )
    await db_session.commit()

    directory = await ac.get("/api/v1/platform/directory", headers=admin)
    assert directory.status_code == 200, directory.text
    row = next(item for item in directory.json()["data"] if item["id"] == seed["t1"].id)
    for key in (
        "company_name",
        "status",
        "industry",
        "store_mode",
        "user_count",
        "store_count",
        "branch_count",
        "created_at",
        "account_status",
    ):
        assert key in row
    blob = directory.text.lower()
    for banned in ("total_sales", "low_stock", "pos_sale", "stock_qty"):
        assert banned not in blob

    granted = await ac.post(
        "/api/v1/platform/staff/grant",
        headers=admin,
        json={"user_id": seed["u1"].id, "role": "platform_support"},
    )
    assert granted.status_code == 200, granted.text

    activity = await ac.get("/api/v1/platform/activity", headers=admin)
    assert activity.status_code == 200, activity.text
    actions = {item["action"] for item in activity.json()["data"]}
    modules = {item["module"] for item in activity.json()["data"]}
    assert "sale_completed" not in actions
    assert "pos" not in modules
    assert "grant_dashboard" in actions

    notes = await ac.get("/api/v1/notifications?category=staff_account", headers=admin)
    assert notes.status_code == 200, notes.text
    assert any("granted" in (row.get("title") or "").lower() for row in notes.json()["data"])


@pytest.mark.asyncio
async def test_notification_audience_separates_platform_and_tenant(client, seeded, db_session):
    ac, seed = client
    owner = await _owner(ac, seed)
    tenant_admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    stock = await note_svc.create_notification(
        db_session,
        tenant_id=seed["t1"].id,
        category="low_stock",
        title="Stock alert",
        message="Widget is low",
        user_id=seed["admin1"].id,
    )
    platform_note = await note_svc.create_notification(
        db_session,
        tenant_id=seed["t1"].id,
        category="staff_account",
        title="Staff changed",
        message="A platform staff account changed",
        user_id=seed["super"].id,
    )
    assert stock and platform_note
    await db_session.commit()

    owner_list = await ac.get("/api/v1/notifications?limit=100", headers=owner)
    assert owner_list.status_code == 200, owner_list.text
    owner_cats = {row["category"] for row in owner_list.json()["data"]}
    assert "low_stock" not in owner_cats
    assert "staff_account" in owner_cats

    owner_stock = await ac.get("/api/v1/notifications?category=low_stock", headers=owner)
    assert owner_stock.status_code == 200, owner_stock.text
    assert owner_stock.json()["data"] == []

    tenant_list = await ac.get("/api/v1/notifications?category=low_stock", headers=tenant_admin)
    assert tenant_list.status_code == 200, tenant_list.text
    assert any(row["id"] == stock.id for row in tenant_list.json()["data"])

    hidden = await ac.patch(f"/api/v1/notifications/{stock.id}/read", headers=owner)
    assert hidden.status_code == 404, hidden.text
