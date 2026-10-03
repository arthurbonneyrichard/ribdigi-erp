"""Executive dashboard aggregates (BR-4.1 / 4.2 / 4.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from app.dashboard import _pct_change, build_dashboard
from tests.conftest import auth_headers


def test_pct_change():
    assert _pct_change(110, 100) == 10.0
    assert _pct_change(0, 0) is None
    assert _pct_change(5, 0) == 100.0


def test_dashboard_product_query_skips_unmigrated_pharmacy_columns():
    import inspect

    src = inspect.getsource(build_dashboard)
    assert "select(m.Product).where" not in src
    assert "table_column_names" in src
    assert "minimum_stock" in src
    assert "rx_only = :rx" in src


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_dashboard_comparisons_top_products_and_alerts(client, db_session, seeded):
    ac, seed = client
    admin = await _super(ac, seed)
    from datetime import datetime, timedelta

    # Seed POS sales: yesterday + today with product lines
    yest = datetime.utcnow() - timedelta(days=1)
    today = datetime.utcnow()
    db_session.add_all(
        [
            m.Transaction(
                tenant_id=seed["t1"].id,
                tx_type="pos_sale",
                reference="POS-YEST-1",
                total=40,
                subtotal=40,
                tax=0,
                created_at=yest,
                payload={
                    "items": [
                        {
                            "product_id": seed["p1"].id,
                            "quantity": 2,
                            "unit_price": 20,
                            "line_total": 40,
                        }
                    ]
                },
            ),
            m.Transaction(
                tenant_id=seed["t1"].id,
                tx_type="pos_sale",
                reference="POS-TODAY-1",
                total=100,
                subtotal=100,
                tax=0,
                created_at=today,
                payload={
                    "items": [
                        {
                            "product_id": seed["p1"].id,
                            "quantity": 5,
                            "unit_price": 20,
                            "line_total": 100,
                        }
                    ]
                },
            ),
        ]
    )
    # Force low / out of stock product
    seed["p1"].stock_qty = 0
    seed["p1"].reorder_level = 5
    low_p = m.Product(
        tenant_id=seed["t1"].id,
        name="Low Widget",
        sku="A-LOW",
        cost_price=1,
        selling_price=2,
        stock_qty=2,
        reorder_level=5,
        is_active=True,
    )
    db_session.add(low_p)
    await db_session.commit()

    res = await ac.get("/api/v1/dashboard", headers=admin)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["customers"] >= 1
    assert data["suppliers"] >= 0
    assert data["products"] >= 1
    assert data["out_of_stock"] >= 1
    assert data["low_stock"] >= 1
    assert data["links"]["sales"] == "/sales"
    assert data["links"]["low_stock"] == "/inventory?tab=lowstock"
    assert data["links"]["out_of_stock"] == "/inventory?tab=products&stock=oos"
    assert data["links"]["customers"] == "/customers"
    assert data["links"]["expiring"] == "/inventory?tab=expiry"
    assert data["links"]["credit"] == "/credit"
    assert data["links"]["ar_total_due"] == "/credit?kind=receivable"
    assert data["links"]["ap_total_due"] == "/credit?kind=payable"
    assert "ar_total_due" in data
    assert "ap_total_due" in data
    assert "credit_outstanding" in data
    assert data["credit_outstanding"] == pytest.approx(
        float(data["ar_total_due"]) + float(data["ap_total_due"])
    )
    assert "comparisons" in data
    assert data["comparisons"]["sales_today"] >= 100
    assert data["comparisons"]["sales_yesterday"] >= 40
    assert data["comparisons"]["sales_today_pct"] is not None
    assert len(data["daily_sales"]) == 30
    assert len(data["monthly_sales"]) == 12
    assert len(data["recent_sales"]) >= 2
    assert data["top_products_by_revenue"]
    assert data["top_products_by_revenue"][0]["product_id"] == seed["p1"].id
    assert data["top_products_by_revenue"][0]["revenue"] >= 140
    assert "gross_profit_7d" in data
    assert "gross_profit_30d" in data
    assert data.get("rx_queue") is None


def test_dashboard_page_surfaces_load_errors():
    text = (Path(__file__).resolve().parents[2] / "frontend/app/(dashboard)/dashboard/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "setDashError" in text
    assert "Retry dashboard" in text
    assert "api(`/dashboard${qs}`)" in text
    assert "out_of_stock" in text
    assert "/inventory?tab=lowstock" in text
    assert "/inventory?tab=products&stock=oos" in text
    # Infographic order: Products → Low stock → Out of stock → Expiring soon only
    products_i = text.find("label: 'Products'")
    low_i = text.find("label: 'Low stock'")
    oos_i = text.find("label: 'Out of stock'")
    expiring_i = text.find("label: 'Expiring soon'")
    assert 0 <= products_i < low_i < oos_i < expiring_i
    assert "label: 'Suppliers'" not in text
    assert "label: 'Customers'" not in text
    assert "label: 'Credit'" not in text
    assert "ar_total_due" in text
    assert "ap_total_due" in text
    assert "credit_outstanding" in text
    count_block = text[products_i : text.find("const liveIndustry")]
    assert "Batches" not in count_block
    assert "featureCards.length > 0" in text
    assert "industryHomePath" in text
    assert "industryHomePath(ind) === '/hotel'" in text
    assert "Retail operations" not in text
    assert "Gross profit (7d)" in text
    assert "rx_queue" in text


@pytest.mark.asyncio
async def test_build_dashboard_direct(db_session, seeded):
    data = await build_dashboard(db_session, seeded["t1"].id)
    assert set(data.keys()) >= {
        "total_sales",
        "comparisons",
        "top_products_by_revenue",
        "out_of_stock",
        "expiring_soon",
        "ar_total_due",
        "ap_total_due",
        "credit_outstanding",
        "links",
        "industry",
        "industry_home",
        "industry_features",
    }
    assert data["credit_outstanding"] == pytest.approx(
        float(data["ar_total_due"]) + float(data["ap_total_due"])
    )
    assert data["industry"] == "retail"
    assert data["industry_home"] == "/dashboard"
    assert isinstance(data["industry_features"], list)
