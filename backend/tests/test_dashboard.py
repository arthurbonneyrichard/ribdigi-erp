"""Executive dashboard aggregates (BR-4.1 / 4.2 / 4.3)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from app.dashboard import _pct_change, build_dashboard
from tests.conftest import auth_headers


def test_pct_change():
    assert _pct_change(110, 100) == 10.0
    assert _pct_change(0, 0) is None
    assert _pct_change(5, 0) == 100.0


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
    await db_session.commit()

    res = await ac.get("/api/v1/dashboard", headers=admin)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["customers"] >= 1
    assert data["suppliers"] >= 0
    assert data["products"] >= 1
    assert data["out_of_stock"] >= 1
    assert data["low_stock"] >= 1
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
    assert data["links"]["sales"] == "/sales"
    assert data["links"]["low_stock"] == "/reports"


@pytest.mark.asyncio
async def test_build_dashboard_direct(db_session, seeded):
    data = await build_dashboard(db_session, seeded["t1"].id)
    assert set(data.keys()) >= {
        "total_sales",
        "comparisons",
        "top_products_by_revenue",
        "out_of_stock",
        "expiring_soon",
        "links",
    }
