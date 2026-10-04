"""Department-based sales report filters (BR-2.5)."""

from __future__ import annotations

from datetime import datetime

import pyotp
import pytest

from app import models as m
from app.security import hash_password
from app.rbac import permissions_for_role
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_sales_by_department_and_filters(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    customer = seed["party1"]
    admin = seed["admin1"]

    dept_sales = m.Department(tenant_id=tenant_id, code="SALES", name="Sales")
    dept_ops = m.Department(tenant_id=tenant_id, code="OPS", name="Operations")
    db_session.add_all([dept_sales, dept_ops])
    await db_session.flush()

    seller_a = m.User(
        tenant_id=tenant_id,
        email="seller-a@alpha.example.com",
        full_name="Seller A",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=True,
        permissions=permissions_for_role("cashier"),
        department_id=dept_sales.id,
        is_active=True,
    )
    seller_b = m.User(
        tenant_id=tenant_id,
        email="seller-b@alpha.example.com",
        full_name="Seller B",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=True,
        permissions=permissions_for_role("cashier"),
        department_id=dept_ops.id,
        is_active=True,
    )
    db_session.add_all([seller_a, seller_b])
    await db_session.flush()

    async def _invoice(user_id: str, amount: float, number: str):
        inv = m.SalesInvoice(
            tenant_id=tenant_id,
            invoice_number=number,
            customer_id=customer.id,
            status="posted",
            subtotal=amount,
            tax_amount=0,
            total_amount=amount,
            posted_at=datetime.utcnow(),
            created_by=user_id,
        )
        db_session.add(inv)

    await _invoice(seller_a.id, 100, "INV-DEPT-A1")
    await _invoice(seller_b.id, 40, "INV-DEPT-B1")
    await _invoice(admin.id, 10, "INV-DEPT-UNASSIGNED")
    await db_session.commit()

    all_r = await ac.get("/api/v1/reports/sales/by-department", headers=headers)
    assert all_r.status_code == 200, all_r.text
    all_data = all_r.json()["data"]
    by_code = {d["code"]: d for d in all_data["departments"] if d.get("code")}
    assert abs(float(by_code["SALES"]["revenue"]) - 100) < 0.01
    assert abs(float(by_code["OPS"]["revenue"]) - 40) < 0.01
    assert abs(float(all_data["total_revenue"]) - 150) < 0.01

    filtered = await ac.get(
        f"/api/v1/reports/sales/by-department?department_id={dept_sales.id}",
        headers=headers,
    )
    assert filtered.status_code == 200
    fdata = filtered.json()["data"]
    assert fdata["department_id"] == dept_sales.id
    assert fdata["department_name"] == "Sales"
    assert len(fdata["departments"]) == 1
    assert abs(float(fdata["total_revenue"]) - 100) < 0.01

    sp = await ac.get(
        f"/api/v1/reports/sales/salesperson?department_id={dept_sales.id}",
        headers=headers,
    )
    assert sp.status_code == 200
    names = {row["full_name"] for row in sp.json()["data"]["salespeople"]}
    assert "Seller A" in names
    assert "Seller B" not in names
    assert abs(float(sp.json()["data"]["total_revenue"]) - 100) < 0.01

    store_r = await ac.get(
        f"/api/v1/reports/sales/by-store?department_id={dept_ops.id}",
        headers=headers,
    )
    assert store_r.status_code == 200
    assert abs(float(store_r.json()["data"]["total_revenue"]) - 40) < 0.01

    bad = await ac.get(
        "/api/v1/reports/sales/by-department?department_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert bad.status_code == 404
