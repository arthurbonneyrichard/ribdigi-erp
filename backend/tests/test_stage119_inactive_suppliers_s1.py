"""Stage 119 S1 — inactive suppliers honesty (?status=inactive)."""

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
async def test_suppliers_status_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "Soon Inactive Supplier"},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["id"]

    deact = await ac.delete(f"/api/v1/suppliers/{sid}", headers=headers)
    assert deact.status_code == 200, deact.text

    inactive = await ac.get("/api/v1/suppliers?status=inactive", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == sid for r in rows)
    assert all((r.get("status") or "active") == "inactive" for r in rows)

    active = await ac.get("/api/v1/suppliers?status=active", headers=headers)
    assert active.status_code == 200, active.text
    assert all((r.get("status") or "active") == "active" for r in active.json()["data"])
    assert not any(r["id"] == sid for r in active.json()["data"])

    active_only = await ac.get("/api/v1/suppliers?active_only=true", headers=headers)
    assert active_only.status_code == 200, active_only.text
    assert not any(r["id"] == sid for r in active_only.json()["data"])


def test_shell_and_purchasing_inactive_suppliers_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "supplier_status=inactive" in shell
    assert "Inactive Suppliers" in shell
    assert "Active Suppliers" in shell
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "Stage 119" in purchasing
    assert "supplier_status" in purchasing
    assert "setSupplierListStatus" in purchasing
