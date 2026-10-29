"""Count drawer on Log out is cashiers only and company-toggleable."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app import models as m
from app.schemas import TenantProfileUpdate
from app.tenants import count_drawer_on_sign_out, serialize_tenant, update_profile
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_count_drawer_sign_out_schema_and_ui():
    omit = TenantProfileUpdate.model_validate({})
    assert omit.count_drawer_on_sign_out is None
    on = TenantProfileUpdate.model_validate({"count_drawer_on_sign_out": True})
    assert on.count_drawer_on_sign_out is True
    off = TenantProfileUpdate.model_validate({"count_drawer_on_sign_out": False})
    assert off.count_drawer_on_sign_out is False
    with pytest.raises(ValidationError):
        TenantProfileUpdate.model_validate({"count_drawer_on_sign_out": True, "evil": 1})

    helper = (ROOT / "frontend/lib/cashierShift.ts").read_text(encoding="utf-8")
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    company = (ROOT / "frontend/app/(dashboard)/company/page.tsx").read_text(encoding="utf-8")
    assert "export function shouldPromptDrawerCountOnSignOut" in helper
    assert "isCashierSignOutRole" in helper
    assert "shouldPromptDrawerCountOnSignOut" in shell
    assert 'aria-label="Enable cashier drawer count on sign-out"' in company
    assert 'aria-label="Disable cashier drawer count on sign-out"' in company
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "count_drawer_on_sign_out" in docs


def test_serialize_tenant_count_drawer_default_on():
    tenant = m.Tenant(slug="count-drawer", company_name="Count Co", status="active")
    data = serialize_tenant(tenant)
    assert data["count_drawer_on_sign_out"] is True
    assert count_drawer_on_sign_out(tenant) is True


@pytest.mark.asyncio
async def test_update_profile_count_drawer_toggle(db_session):
    row = m.Tenant(slug="count-unit", company_name="Unit Count", status="active")
    db_session.add(row)
    await db_session.flush()

    off = await update_profile(db_session, row, count_drawer_on_sign_out=False)
    assert count_drawer_on_sign_out(off) is False
    on = await update_profile(db_session, off, count_drawer_on_sign_out=True)
    assert count_drawer_on_sign_out(on) is True


@pytest.mark.asyncio
async def test_count_drawer_patch_get_me_and_isolation(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    got = await ac.get("/api/v1/tenants/me", headers=headers)
    assert got.status_code == 200
    assert got.json()["data"]["count_drawer_on_sign_out"] is True

    patched = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"count_drawer_on_sign_out": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["count_drawer_on_sign_out"] is False

    again = await ac.get("/api/v1/tenants/me", headers=headers)
    assert again.json()["data"]["count_drawer_on_sign_out"] is False

    me = await ac.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["count_drawer_on_sign_out"] is False

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    cashier_me = await ac.get("/api/v1/me", headers=cashier)
    assert cashier_me.status_code == 200
    assert cashier_me.json()["data"]["count_drawer_on_sign_out"] is False
    assert cashier_me.json()["data"]["role"] == "cashier"

    denied = await ac.patch(
        "/api/v1/tenants/me",
        headers=cashier,
        json={"count_drawer_on_sign_out": True},
    )
    assert denied.status_code == 403

    foreign = await ac.get(
        "/api/v1/tenants/me",
        headers={**headers, "X-Tenant-ID": seed["t2"].id},
    )
    assert foreign.status_code == 403
