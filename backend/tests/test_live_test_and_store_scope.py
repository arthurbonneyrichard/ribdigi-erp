"""Assigned-store report limits and the live-test PDF."""

from datetime import datetime
from uuid import uuid4

import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_live_test_script_pdf_covers_three_industries(client):
    ac, _seed = client
    headers = await _admin(ac)
    response = await ac.get("/api/v1/live-test-script", headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    body = response.content
    assert body.startswith(b"%PDF-1.4")
    text = body.decode("latin-1", errors="ignore")
    assert "Retail" in text
    assert "Pharmacy" in text
    assert "Wholesale" in text
    assert "does not fall again" in text
    assert text.count("/Type /Page") >= 2


@pytest.mark.asyncio
async def test_assigned_store_hides_other_store_sales_and_tax(client, db_session):
    ac, seed = client
    admin = await _admin(ac)
    suffix = uuid4().hex[:6].upper()
    keep = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": f"K{suffix}", "name": "Keep Store"},
    )
    other = await ac.post(
        "/api/v1/stores",
        headers=admin,
        json={"code": f"O{suffix}", "name": "Other Store"},
    )
    assert keep.status_code == 200, keep.text
    assert other.status_code == 200, other.text
    keep_id = keep.json()["data"]["id"]
    other_id = other.json()["data"]["id"]

    email = f"mgr-{suffix.lower()}@alpha.example.com"
    created = await ac.post(
        "/api/v1/users",
        headers=admin,
        json={
            "email": email,
            "full_name": "Store Manager",
            "password": "SecurePass123!",
            "role": "store_manager",
            "store_id": keep_id,
        },
    )
    assert created.status_code == 200, created.text

    party = m.Party(tenant_id=seed["t1"].id, name="Buyer", kind="customer", credit_limit=0)
    db_session.add(party)
    await db_session.flush()
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"INV-KEEP-{suffix}",
                customer_id=party.id,
                status="posted",
                subtotal=10,
                tax_amount=1,
                total_amount=11,
                paid_amount=0,
                store_id=keep_id,
                posted_at=datetime.utcnow(),
                created_by=seed["admin1"].id,
            ),
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"INV-OTHER-{suffix}",
                customer_id=party.id,
                status="posted",
                subtotal=90,
                tax_amount=9,
                total_amount=99,
                paid_amount=0,
                store_id=other_id,
                posted_at=datetime.utcnow(),
                created_by=seed["admin1"].id,
            ),
        ]
    )
    await db_session.commit()

    headers = await auth_headers(ac, email=email, tenant_slug="alpha")
    customers = await ac.get("/api/v1/reports/sales/customers", headers=headers)
    assert customers.status_code == 200, customers.text
    rows = customers.json()["data"].get("customers") or customers.json()["data"].get("rows") or []
    if not rows and isinstance(customers.json()["data"], dict):
        payload = customers.json()["data"]
        revenue = payload.get("total_revenue")
        if revenue is None:
            revenue = sum(float(row.get("revenue") or 0) for row in payload.get("customers") or [])
    else:
        revenue = sum(float(row.get("revenue") or 0) for row in rows)
    assert float(revenue) == 11.0

    tax = await ac.get("/api/v1/reports/tax", headers=headers)
    assert tax.status_code == 200, tax.text
    assert float(tax.json()["data"]["output_tax"]) == 1.0

    denied = await ac.get(
        "/api/v1/reports/sales/customers",
        headers=headers,
        params={"store_id": other_id},
    )
    assert denied.status_code in {403, 404}
