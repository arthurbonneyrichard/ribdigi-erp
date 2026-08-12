"""Stage 122 O1 — inactive branches/departments honesty (?is_active=false)."""

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
async def test_branches_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/branches",
        headers=headers,
        json={"code": "BRINA122", "name": "Soon Inactive Branch"},
    )
    assert created.status_code == 200, created.text
    bid = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/branches/{bid}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text

    inactive = await ac.get("/api/v1/branches?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == bid for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/branches?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert not any(r["id"] == bid for r in active.json()["data"])

    active_only = await ac.get("/api/v1/branches?active_only=true", headers=headers)
    assert active_only.status_code == 200, active_only.text
    assert not any(r["id"] == bid for r in active_only.json()["data"])


@pytest.mark.asyncio
async def test_departments_is_active_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/departments",
        headers=headers,
        json={"code": "DPINA122", "name": "Soon Inactive Dept"},
    )
    assert created.status_code == 200, created.text
    did = created.json()["data"]["id"]

    patched = await ac.patch(
        f"/api/v1/departments/{did}",
        headers=headers,
        json={"is_active": False},
    )
    assert patched.status_code == 200, patched.text

    inactive = await ac.get("/api/v1/departments?is_active=false", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == did for r in rows)
    assert all(r.get("is_active") is False for r in rows)

    active = await ac.get("/api/v1/departments?is_active=true", headers=headers)
    assert active.status_code == 200, active.text
    assert not any(r["id"] == did for r in active.json()["data"])


def test_shell_and_company_inactive_org_units_o1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "branch_active=false" in shell
    assert "Inactive Branches" in shell
    assert "Active Branches" in shell
    assert "dept_active=false" in shell
    assert "Inactive Departments" in shell
    page = (ROOT / "frontend/app/company/page.tsx").read_text(encoding="utf-8")
    assert "Stage 122" in page
    assert "branch_active" in page
    assert "dept_active" in page
    assert "branchActiveFilter" in page
    assert "deptActiveFilter" in page
