"""Supplier soft-deactivate UI + inactive PO/PR/PI guards (BR-6.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_supplier_deactivate_ui_wired():
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "setSupplierActive" in purchasing
    assert "Deactivate" in purchasing
    assert "Activate" in purchasing
    assert "status !== 'inactive'" in purchasing
    assert "[inactive]" in purchasing
    assert "supplierManageFilter" in purchasing
    assert 'aria-label="Supplier status filter"' in purchasing


@pytest.mark.asyncio
async def test_inactive_supplier_blocked_on_po_and_reactivates(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": "Obsolete Vendor Co", "status": "active"},
    )
    assert created.status_code == 200, created.text
    sid = created.json()["data"]["id"]

    deact = await ac.patch(
        f"/api/v1/suppliers/{sid}",
        headers=admin,
        json={"status": "inactive"},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["status"] == "inactive"

    blocked = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": sid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.text.lower()

    pr_blocked = await ac.post(
        "/api/v1/purchasing/requests",
        headers=admin,
        json={
            "preferred_supplier_id": sid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert pr_blocked.status_code == 400, pr_blocked.text
    assert "inactive" in pr_blocked.text.lower()

    pi_blocked = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=admin,
        json={
            "supplier_id": sid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert pi_blocked.status_code == 400, pi_blocked.text
    assert "inactive" in pi_blocked.text.lower()

    react = await ac.patch(
        f"/api/v1/suppliers/{sid}",
        headers=admin,
        json={"status": "active"},
    )
    assert react.status_code == 200
    assert react.json()["data"]["status"] == "active"

    ok = await ac.post(
        "/api/v1/purchasing/orders",
        headers=admin,
        json={
            "supplier_id": sid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 5}],
        },
    )
    assert ok.status_code == 200, ok.text
