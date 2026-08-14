"""Customer soft-deactivate UI + inactive sale/quote/order guards (BR-7.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_customer_deactivate_ui_wired():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "setCustomerActive" in sales
    assert "Deactivate" in sales
    assert "Activate" in sales
    assert "status !== 'inactive'" in sales
    assert "[inactive]" in sales
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "status !== 'inactive'" in pos


@pytest.mark.asyncio
async def test_inactive_customer_blocked_on_invoice_and_reactivates(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    created = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Obsolete Buyer Co", "status": "active"},
    )
    assert created.status_code == 200, created.text
    cid = created.json()["data"]["id"]

    deact = await ac.patch(
        f"/api/v1/customers/{cid}",
        headers=admin,
        json={"status": "inactive"},
    )
    assert deact.status_code == 200, deact.text
    assert deact.json()["data"]["status"] == "inactive"

    blocked = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": cid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert blocked.status_code == 400, blocked.text
    assert "inactive" in blocked.text.lower()

    qt_blocked = await ac.post(
        "/api/v1/sales/quotations",
        headers=admin,
        json={
            "customer_id": cid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert qt_blocked.status_code == 400, qt_blocked.text
    assert "inactive" in qt_blocked.text.lower()

    so_blocked = await ac.post(
        "/api/v1/sales/orders",
        headers=admin,
        json={
            "customer_id": cid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert so_blocked.status_code == 400, so_blocked.text
    assert "inactive" in so_blocked.text.lower()

    react = await ac.patch(
        f"/api/v1/customers/{cid}",
        headers=admin,
        json={"status": "active"},
    )
    assert react.status_code == 200
    assert react.json()["data"]["status"] == "active"

    ok = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": cid,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert ok.status_code == 200, ok.text
