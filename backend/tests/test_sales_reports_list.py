"""Sales report list: totals, tenant isolation, industry gates, and cost permission."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app import models as m
from tests.conftest import auth_headers, set_tenant_industry


async def _admin(ac):
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_header_discount_is_not_subtracted_twice(client, db_session):
    ac, seed = client
    headers = await _admin(ac)
    now = datetime.utcnow()
    db_session.add(
        m.SalesInvoice(
            tenant_id=seed["t1"].id,
            invoice_number="INV-DISC-1",
            customer_id=seed["party1"].id,
            status="posted",
            subtotal=100,
            tax_amount=0,
            discount_amount=10,
            total_amount=90,
            posted_at=now,
        )
    )
    await db_session.commit()

    res = await ac.get("/api/v1/reports/sales/daily", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert abs(float(data["total_revenue"]) - 90) < 0.01
    assert abs(float(data["discounts"]) - 10) < 0.01
    assert abs(float(data["net_sales"]) - 90) < 0.01
    assert "Sales returns" in data["returns_note"]


@pytest.mark.asyncio
async def test_linked_pos_sale_is_not_counted_twice(client, db_session):
    ac, seed = client
    headers = await _admin(ac)
    now = datetime.utcnow()
    invoice = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-LINK-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=90,
        tax_amount=0,
        discount_amount=0,
        total_amount=90,
        posted_at=now,
    )
    db_session.add(invoice)
    await db_session.flush()
    db_session.add(
        m.Transaction(
            tenant_id=seed["t1"].id,
            tx_type="pos_sale",
            reference="POS-LINK-1",
            client_request_id="pos-link-1",
            status="completed",
            subtotal=90,
            tax=0,
            total=90,
            payload={"sales_invoice_id": invoice.id, "items": []},
            created_at=now,
        )
    )
    other = m.SalesInvoice(
        tenant_id=seed["t2"].id,
        invoice_number="INV-OTHER-1",
        customer_id=seed["party2"].id,
        status="posted",
        subtotal=500,
        tax_amount=0,
        discount_amount=0,
        total_amount=500,
        posted_at=now,
    )
    db_session.add(other)
    await db_session.commit()

    daily = await ac.get("/api/v1/reports/sales/daily", headers=headers)
    assert daily.status_code == 200, daily.text
    data = daily.json()["data"]
    assert data["invoice_count"] == 1
    assert data["pos_count"] == 0
    assert abs(float(data["total_revenue"]) - 90) < 0.01

    tx = await ac.get("/api/v1/reports/sales/transactions", headers=headers)
    assert tx.status_code == 200, tx.text
    rows = tx.json()["data"]["rows"]
    numbers = {row["number"] for row in rows}
    assert "INV-LINK-1" in numbers
    assert "POS-LINK-1" not in numbers
    assert "INV-OTHER-1" not in numbers
    assert abs(float(tx.json()["data"]["total"]) - 90) < 0.01


@pytest.mark.asyncio
async def test_product_lines_columns_cost_and_date_filter(client, db_session):
    ac, seed = client
    now = datetime.utcnow()
    invoice = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-LINE-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=20,
        tax_amount=0,
        discount_amount=0,
        total_amount=20,
        posted_at=now,
        created_by=seed["admin1"].id,
    )
    db_session.add(invoice)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t1"].id,
            sales_invoice_id=invoice.id,
            product_id=seed["p1"].id,
            quantity=2,
            unit_price=10,
            discount=0,
            line_tax=0,
            line_subtotal=20,
            line_total=20,
        )
    )
    await db_session.commit()

    admin = await _admin(ac)
    lines = await ac.get("/api/v1/reports/sales/lines", headers=admin)
    assert lines.status_code == 200, lines.text
    body = lines.json()["data"]
    assert body["include_cost"] is True
    assert len(body["lines"]) == 1
    row = body["lines"][0]
    assert row["number"] == "INV-LINE-1"
    assert row["product"] == "Alpha Widget"
    assert row["sku"] == "A-1"
    assert row["category"] == "General"
    assert "barcode" in row
    assert "brand" in row
    assert abs(float(row["quantity"]) - 2) < 0.01
    assert abs(float(row["sales_total"]) - 20) < 0.01
    assert abs(float(row["cost"]) - 2) < 0.01
    assert abs(float(body["total_sales"]) - 20) < 0.01

    future = (now + timedelta(days=2)).date().isoformat()
    empty = await ac.get(f"/api/v1/reports/sales/lines?from_date={future}", headers=admin)
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"]["lines"] == []
    assert float(empty.json()["data"]["total_sales"]) == 0

    manager = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    hidden = await ac.get("/api/v1/reports/sales/lines", headers=manager)
    assert hidden.status_code == 200, hidden.text
    hidden_row = hidden.json()["data"]["lines"][0]
    assert hidden.json()["data"]["include_cost"] is False
    assert "cost" not in hidden_row
    assert "profit" not in hidden_row


@pytest.mark.asyncio
async def test_store_filter_limits_transactions(client, db_session):
    ac, seed = client
    headers = await _admin(ac)
    store_a = m.Store(tenant_id=seed["t1"].id, code="SL-A", name="List A")
    store_b = m.Store(tenant_id=seed["t1"].id, code="SL-B", name="List B")
    db_session.add_all([store_a, store_b])
    await db_session.flush()
    now = datetime.utcnow()
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number="INV-STA",
                customer_id=seed["party1"].id,
                store_id=store_a.id,
                status="posted",
                subtotal=15,
                tax_amount=0,
                discount_amount=0,
                total_amount=15,
                posted_at=now,
            ),
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number="INV-STB",
                customer_id=seed["party1"].id,
                store_id=store_b.id,
                status="posted",
                subtotal=25,
                tax_amount=0,
                discount_amount=0,
                total_amount=25,
                posted_at=now,
            ),
        ]
    )
    await db_session.commit()
    res = await ac.get(f"/api/v1/reports/sales/transactions?store_id={store_a.id}", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert {row["number"] for row in data["rows"]} == {"INV-STA"}
    assert abs(float(data["total"]) - 15) < 0.01
    assert data["rows"][0]["store_name"] == "List A"


@pytest.mark.asyncio
async def test_cashier_cannot_read_sales_reports(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    res = await ac.get("/api/v1/reports/sales/transactions", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_pos_and_quotation_reports_follow_industry(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "wholesale")
    wholesale = await _admin(ac)
    pos = await ac.get("/api/v1/reports/sales/pos", headers=wholesale)
    assert pos.status_code == 403
    assert pos.json()["detail"]["code"] == "INDUSTRY_MODULE_DISABLED"

    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    fmcg = await _admin(ac)
    assert (await ac.get("/api/v1/reports/sales/pos", headers=fmcg)).status_code == 403

    await set_tenant_industry(db_session, seed["t1"], "hotel")
    hotel = await _admin(ac)
    quotes = await ac.get("/api/v1/reports/sales/quotations", headers=hotel)
    assert quotes.status_code == 403
    assert (await ac.get("/api/v1/reports/sales/pos", headers=hotel)).status_code == 200

    await set_tenant_industry(db_session, seed["t1"], "retail")
    retail = await _admin(ac)
    ok = await ac.get("/api/v1/reports/sales/quotations", headers=retail)
    assert ok.status_code == 200, ok.text
    assert "not sales" in ok.json()["data"]["returns_note"].lower() or "Quotations" in ok.json()["data"]["returns_note"]


@pytest.mark.asyncio
async def test_product_rollup_cost_and_period_filters(client, db_session):
    ac, seed = client
    now = datetime.utcnow()
    invoice = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number="INV-ROLL-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=20,
        tax_amount=0,
        discount_amount=0,
        total_amount=20,
        posted_at=now,
        created_by=seed["admin1"].id,
    )
    db_session.add(invoice)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t1"].id,
            sales_invoice_id=invoice.id,
            product_id=seed["p1"].id,
            quantity=2,
            unit_price=10,
            discount=0,
            line_tax=0,
            line_subtotal=20,
            line_total=20,
        )
    )
    await db_session.commit()

    admin = await _admin(ac)
    products = await ac.get("/api/v1/reports/sales/products", headers=admin)
    assert products.status_code == 200, products.text
    body = products.json()["data"]
    assert body["include_cost"] is True
    assert "total_profit" in body
    widget = next(row for row in body["products"] if row["sku"] == "A-1")
    assert float(widget["quantity"]) >= 2
    assert float(widget["revenue"]) >= 20
    assert "profit" in widget and "cost" in widget
    assert body["categories"]
    assert body["brands"]
    assert abs(sum(float(row["revenue"]) for row in body["categories"]) - float(body["total_revenue"])) < 0.01
    assert abs(sum(float(row["revenue"]) for row in body["brands"]) - float(body["total_revenue"])) < 0.01

    future = (now + timedelta(days=2)).date().isoformat()
    empty = await ac.get(f"/api/v1/reports/sales/products?from_date={future}", headers=admin)
    assert empty.status_code == 200, empty.text
    blank = empty.json()["data"]
    assert blank["products"] == []
    assert blank["categories"] == []
    assert blank["brands"] == []
    assert float(blank["total_revenue"]) == 0
    assert float(blank["total_quantity"]) == 0

    manager = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    hidden = await ac.get("/api/v1/reports/sales/products", headers=manager)
    assert hidden.status_code == 200, hidden.text
    hidden_body = hidden.json()["data"]
    assert hidden_body["include_cost"] is False
    assert "total_cost" not in hidden_body
    assert "total_profit" not in hidden_body
    assert hidden_body["products"]
    assert "cost" not in hidden_body["products"][0]
    assert "profit" not in hidden_body["products"][0]
    assert "cost" not in hidden_body["categories"][0]
    assert "profit" not in hidden_body["categories"][0]
    assert "cost" not in hidden_body["brands"][0]
    assert "profit" not in hidden_body["brands"][0]

    month = await ac.get(
        "/api/v1/reports/sales/monthly?year=2099&month=1",
        headers=admin,
    )
    assert month.status_code == 200, month.text
    assert float(month.json()["data"]["total_revenue"]) == 0
    assert month.json()["data"]["daily"] == []

    for path in (
        "/api/v1/reports/sales/salesperson",
        "/api/v1/reports/sales/by-store",
        "/api/v1/reports/sales/by-department",
    ):
        rolled = await ac.get(path, headers=admin)
        assert rolled.status_code == 200, rolled.text
        assert "total_revenue" in rolled.json()["data"]
