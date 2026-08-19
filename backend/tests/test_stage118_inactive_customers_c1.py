"""Stage 118 C1 — inactive customers honesty (?status=inactive)."""

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
async def test_customers_status_inactive_only(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Soon Inactive Co", "party_type": "registered"},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["id"]

    deact = await ac.delete(f"/api/v1/customers/{cid}", headers=headers)
    assert deact.status_code == 200, deact.text

    inactive = await ac.get("/api/v1/customers?status=inactive", headers=headers)
    assert inactive.status_code == 200, inactive.text
    rows = inactive.json()["data"]
    assert any(r["id"] == cid for r in rows)
    assert all((r.get("status") or "active") == "inactive" for r in rows)

    active = await ac.get("/api/v1/customers?status=active", headers=headers)
    assert active.status_code == 200, active.text
    assert all((r.get("status") or "active") == "active" for r in active.json()["data"])
    assert not any(r["id"] == cid for r in active.json()["data"])


def test_shell_and_sales_inactive_customers_c1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "customer_status=inactive" in shell
    assert "Inactive Customers" in shell
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "Stage 118" in sales
    assert "customer_status" in sales
    assert "setCustomerListStatus" in sales
