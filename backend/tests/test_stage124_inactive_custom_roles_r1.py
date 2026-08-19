"""Stage 124 R1 — inactive custom roles honesty (?is_active=false)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_custom_roles_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/roles",
        headers=headers,
        json={
            "slug": "stage124_temp",
            "label": "Stage124 Temp Role",
            "base_role": "cashier",
            "record_scope": "own",
            "permissions": {
                "dashboard": ["read"],
                "pos": ["read"],
                "notifications": ["read"],
                "security": ["read"],
            },
        },
    )
    assert created.status_code == 200, created.text
    slug = created.json()["data"]["role"]

    patched = await ac.patch(
        f"/api/v1/roles/{slug}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["is_active"] is False

    inactive = await ac.get("/api/v1/roles?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r.get("role") == slug or r.get("slug") == slug for r in rows)
    assert all(r.get("is_active") is False for r in rows)
    assert all(r.get("system") is False for r in rows)

    active = await ac.get("/api/v1/roles?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert not any(r.get("role") == slug or r.get("slug") == slug for r in active.json()["data"])

    default_catalog = await ac.get("/api/v1/roles", headers=headers)
    assert default_catalog.status_code == 200, default_catalog.text
    assert not any(
        r.get("role") == slug or r.get("slug") == slug for r in default_catalog.json()["data"]
    )

    reactivated = await ac.patch(
        f"/api/v1/roles/{slug}",
        headers=headers,
        json={"is_active": True},
    )
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["data"]["is_active"] is True


def test_shell_and_admin_inactive_custom_roles_r1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "role_active=false" in shell
    assert "Inactive Custom Roles" in shell
    assert "Active Custom Roles" in shell
    page = (ROOT / "frontend/app/admin/roles/page.tsx").read_text(encoding="utf-8")
    assert "Stage 124" in page
    assert "role_active" in page
    assert "roleActiveFilter" in page
