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
    assert "pharmacy_desk" in src
    assert "awaiting_review" in src


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
    assert "const home = industryHomePath(ind);" in text
    assert "router.replace(home)" in text
    home_src = (
        Path(__file__).resolve().parents[2] / "frontend/lib/industryDashboard.ts"
    ).read_text(encoding="utf-8")
    assert "export function industryHomePath" in home_src
    assert "if (ind === 'hotel') return '/hotel';" in home_src
    assert "if (ind === 'restaurant') return '/restaurant';" in home_src
    assert "return '/dashboard';" in home_src
    assert "Retail operations" not in text
    assert "Gross profit (7d)" in text
    assert "rx_queue" in text
    assert "aria-label=\"Pharmacy\"" in text
    assert "New prescription" in text
    assert "Pharmacy POS" in text
    assert "/inventory?tab=expiry&when=soon" in text
    assert "/inventory?tab=expiry&when=expired" in text
    assert "/prescriptions?holds=quarantine#lot-holds" in text
    assert "/prescriptions?holds=recall#lot-holds" in text
    assert "pharmacy_desk?.on_hand_lots" in text
    assert "Daily sales (7d)" in text
    assert "Revenue trend (30d)" in text
    assert "Monthly sales (12 mo)" in text


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
    assert data["pharmacy_desk"] is None
    assert isinstance(data["industry_features"], list)


@pytest.mark.asyncio
async def test_pharmacy_dashboard_desk_counts(db_session, seeded):
    tenant = await db_session.get(m.Tenant, seeded["t1"].id)
    tenant.industry = "pharmacy"
    await db_session.commit()
    data = await build_dashboard(db_session, seeded["t1"].id)
    desk = data["pharmacy_desk"]
    assert desk["awaiting_review"] == 0
    assert desk["ready_to_dispense"] == 0
    assert desk["partially_dispensed"] == 0
    assert desk["returns_today"] == 0
    assert "expired_lots" in desk
    assert "on_hand_lots" in desk
    assert "quarantined" in desk
    assert "recalled" in desk
    assert "pending_purchase_orders" in desk
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    db_session.add_all(
        [
            m.ProductBatch(
                tenant_id=seeded["t1"].id,
                product_id=seeded["p1"].id,
                batch_number="DESK-EXP",
                quantity=2,
                expiry_date=now - timedelta(days=3),
            ),
            m.ProductBatch(
                tenant_id=seeded["t1"].id,
                product_id=seeded["p1"].id,
                batch_number="DESK-SOON",
                quantity=2,
                expiry_date=now + timedelta(days=10),
            ),
            m.ProductBatch(
                tenant_id=seeded["t1"].id,
                product_id=seeded["p1"].id,
                batch_number="DESK-LATER",
                quantity=2,
                expiry_date=now + timedelta(days=90),
            ),
        ]
    )
    await db_session.commit()
    after = await build_dashboard(db_session, seeded["t1"].id)
    desk_after = after["pharmacy_desk"]
    assert desk_after["expired_lots"] == desk["expired_lots"] + 1
    assert desk_after["expiring_soon"] == desk["expiring_soon"] + 1
    assert desk_after["on_hand_lots"] == desk["on_hand_lots"] + 3
