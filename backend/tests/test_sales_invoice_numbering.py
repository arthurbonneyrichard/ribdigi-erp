"""Configurable sales invoice numbering (BR-7.4 / BR-20.4)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sales_invoice_numbering_settings_and_allocation(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    year = datetime.utcnow().year

    got = await ac.get("/api/v1/sales/settings", headers=admin)
    assert got.status_code == 200, got.text
    numbering = got.json()["data"]["invoice_numbering"]
    assert numbering["prefix"] == "INV"
    assert numbering["preview"] == f"INV-{year}-0001"

    patched = await ac.patch(
        "/api/v1/sales/settings",
        headers=admin,
        json={"prefix": "si", "next_number": 7},
    )
    assert patched.status_code == 200, patched.text
    numbering = patched.json()["data"]["invoice_numbering"]
    assert numbering["prefix"] == "SI"
    assert numbering["next_number"] == 7
    assert numbering["preview"] == f"SI-{year}-0007"

    bad = await ac.patch(
        "/api/v1/sales/settings",
        headers=admin,
        json={"prefix": "bad prefix!", "next_number": 1},
    )
    assert bad.status_code == 400

    cust = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": "Numbering Co", "email": "num@example.com"},
    )
    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": cust.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["invoice_number"] == f"SI-{year}-0007"

    created2 = await ac.post(
        "/api/v1/sales/invoices",
        headers=admin,
        json={
            "customer_id": cust.json()["data"]["id"],
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert created2.json()["data"]["invoice_number"] == f"SI-{year}-0008"

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    await db_session.refresh(tenant)
    assert tenant.sales_invoice_number_prefix == "SI"
    assert tenant.sales_invoice_number_next == 9
    assert tenant.sales_invoice_number_year == year

    preview = await ac.get("/api/v1/sales/settings", headers=admin)
    assert preview.json()["data"]["invoice_numbering"]["preview"] == f"SI-{year}-0009"
