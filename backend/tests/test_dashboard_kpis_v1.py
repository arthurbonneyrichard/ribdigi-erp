"""Stage 21 V1: Dashboard KPIs & visualizations fidelity (BR-4.1–4.3)."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest

from app import models as m
from app.config import settings
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_dashboard_kpis_alerts_and_charts_fidelity(client, db_session):
    """BR-4.1–4.3: KPI cards, DoD/MoM, inventory alerts, sales viz series."""
    ac, seed = client
    tid = seed["t1"].id
    now = datetime.utcnow()
    day = now.replace(hour=11, minute=0, second=0, microsecond=0)
    yesterday = day - timedelta(days=1)
    prior_month = (day.replace(day=1) - timedelta(days=1)).replace(hour=12)

    product = seed["p1"]
    product.stock_qty = 0
    product.reorder_level = 5
    db_session.add(
        m.Product(
            tenant_id=tid,
            name="V1 Low Stock Item",
            sku="V1-LOW",
            cost_price=1,
            selling_price=2,
            stock_qty=2,
            reorder_level=10,
        )
    )
    db_session.add(
        m.ProductBatch(
            tenant_id=tid,
            product_id=product.id,
            batch_number="V1-BATCH",
            quantity=3,
            expiry_date=now + timedelta(days=10),
        )
    )
    supplier = m.Party(tenant_id=tid, name="V1 Supplier", kind="supplier", credit_limit=0)
    db_session.add(supplier)
    db_session.add_all(
        [
            m.Transaction(
                tenant_id=tid,
                tx_type="pos_sale",
                reference="V1-TODAY",
                total=50,
                subtotal=50,
                tax=0,
                created_at=day,
                payload={"items": []},
            ),
            m.Transaction(
                tenant_id=tid,
                tx_type="pos_sale",
                reference="V1-YDAY",
                total=25,
                subtotal=25,
                tax=0,
                created_at=yesterday,
                payload={},
            ),
            m.Transaction(
                tenant_id=tid,
                tx_type="pos_sale",
                reference="V1-PRIOR-M",
                total=40,
                subtotal=40,
                tax=0,
                created_at=prior_month,
                payload={},
            ),
            m.Expense(
                tenant_id=tid,
                category="General",
                amount=12,
                description="V1 expense",
                payment_method="cash",
                status="approved",
                created_by=seed["mgr1"].id,
            ),
        ]
    )
    inv = m.SalesInvoice(
        tenant_id=tid,
        invoice_number="INV-V1-1",
        customer_id=seed["party1"].id,
        status="posted",
        subtotal=30,
        tax_amount=0,
        total_amount=30,
        posted_at=day,
    )
    db_session.add(inv)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=tid,
            sales_invoice_id=inv.id,
            product_id=product.id,
            quantity=3,
            unit_price=10,
            line_total=30,
            tax_rate=0,
        )
    )
    await db_session.commit()

    headers = await _super(ac, seed)
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    # BR-4.1 KPI totals
    for key in (
        "total_sales",
        "total_purchases",
        "total_expenses",
        "customers",
        "suppliers",
        "products",
    ):
        assert key in data, key
    assert float(data["total_expenses"]) >= 12
    assert int(data["customers"]) >= 1
    assert int(data["suppliers"]) >= 1
    assert int(data["products"]) >= 2
    assert float(data["total_sales"]) >= 50

    # Near-real-time cache budget (≤5 minutes)
    assert int(settings.CACHE_DASHBOARD_TTL_SECONDS) <= 300

    # Period compare: Today vs Yesterday + MoM
    assert float(data["daily_revenue"]) >= 50
    assert float(data["yesterday_revenue"]) >= 25
    assert data["dod_change_pct"] is not None
    assert float(data["prior_month_revenue"]) >= 40
    assert "mom_change_pct" in data

    links = data["kpi_links"]
    for key, path in {
        "total_sales": "/sales?tab=invoices",
        "total_purchases": "/purchasing?tab=invoices",
        "total_expenses": "/expenses",
        "customers": "/sales?tab=customers",
        "suppliers": "/purchasing?tab=suppliers",
        "products": "/inventory?tab=products",
        "low_stock": "/inventory?tab=lowstock",
        "out_of_stock": "/inventory?tab=lowstock",
        "expiring_batches": "/inventory?tab=expiry",
        "daily_revenue": "/reports?tab=sales",
        "yesterday_revenue": "/reports?tab=sales",
        "dod_change_pct": "/reports?tab=sales",
        "monthly_revenue": "/reports?tab=sales",
        "mom_change_pct": "/reports?tab=sales",
    }.items():
        assert links.get(key) == path, key

    # BR-4.2 inventory alerts
    assert int(data["low_stock"]) >= 1
    assert int(data["out_of_stock"]) >= 1
    assert int(data["expiring_batches"]) >= 1

    # BR-4.3 sales visualization
    assert isinstance(data["recent_sales"], list)
    assert len(data["recent_sales"]) <= 10
    assert any(row.get("reference") == "V1-TODAY" for row in data["recent_sales"])
    for row in data["recent_sales"]:
        assert "source" in row and "reference" in row and "total" in row

    assert isinstance(data["top_products"], list)
    assert any(p.get("sku") == product.sku for p in data["top_products"])
    top = next(p for p in data["top_products"] if p.get("sku") == product.sku)
    assert float(top["quantity"]) >= 3
    assert float(top["revenue"]) >= 30

    assert len(data["daily_revenue_series"]) == 30
    assert len(data["monthly_revenue_series"]) == 12
    assert "date" in data["daily_revenue_series"][0]
    assert "revenue" in data["daily_revenue_series"][0]
    assert "month" in data["monthly_revenue_series"][0]
    assert "revenue" in data["monthly_revenue_series"][0]


def test_br_4_1_to_4_3_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s41 = br.split("#### BR-4.1 KPI Cards")[1].split("#### BR-4.2")[0]
    assert "[x] Display: Total Sales, Total Purchases, Total Expenses" in s41
    assert "[x] Real-time or near-real-time updates" in s41
    assert "[x] Period comparison" in s41
    assert "[x] Click-through to detailed reports" in s41
    assert "Stage 21 V1" in s41
    assert "test_dashboard_kpis_v1.py" in s41
    assert "yesterday_revenue" in s41 or "DoD" in s41 or "dod_change_pct" in s41

    s42 = br.split("#### BR-4.2 Inventory Alerts")[1].split("#### BR-4.3")[0]
    assert "[x] Low stock products count" in s42
    assert "[x] Out-of-stock products count" in s42
    assert "[x] Expiring products" in s42
    assert "Stage 21 V1" in s42

    s43 = br.split("#### BR-4.3 Sales Visualization")[1].split("#### BR-4.4")[0]
    assert "[x] Recent sales list" in s43
    assert "[x] Top products by revenue and quantity" in s43
    assert "[x] Daily revenue line chart" in s43
    assert "[x] Monthly revenue bar chart" in s43
    assert "Stage 21 V1" in s43

    plan = (ROOT / "docs" / "STAGE_21_PLAN.md").read_text(encoding="utf-8")
    v1_line = [ln for ln in plan.splitlines() if "| **V1**" in ln][0]
    assert "COMPLETE" in v1_line
    assert "test_dashboard_kpis_v1.py" in plan
