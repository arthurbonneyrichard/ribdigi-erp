"""Platform owner can permanently delete a company tenant."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_platform_tenant_delete_ui_wired():
    plat = (ROOT / "frontend/app/(dashboard)/platform/page.tsx").read_text(encoding="utf-8")
    assert "async function deleteTenant" in plat
    assert "/delete" in plat
    assert "confirm_slug" in plat
    assert 'aria-label={`Delete tenant ${t.slug || t.id}`}' in plat
    assert "canDeleteTenant" in plat


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
