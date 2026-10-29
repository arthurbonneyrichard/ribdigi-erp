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
    assert "getPrefetched(`/dashboard${qs}`" in text
    assert "out_of_stock" in text
    assert "/inventory?tab=lowstock" in text
    assert "/inventory?tab=products&stock=oos" in text
    assert "label: 'Products'" not in text
    assert "label: 'Low stock'" not in text
    assert "label: 'Expiring soon'" not in text
    health = text[text.find("Inventory health") : text.find("Cash flow")]
    assert "Low stock" in health
    assert "Out of stock" in health
    assert "Expiring soon" in health
    assert "lots expiring within 30 days" in health
    assert "label: 'Posted returns'" not in text
    assert "label: 'Suppliers'" not in text
    assert "label: 'Customers'" not in text
    assert "label: 'Credit'" not in text
    assert "ar_total_due" in text
    assert "ap_total_due" in text
    assert "credit_outstanding" in text
    headline = text[text.find("const stats = [") : text.find("const liveIndustry")]
    assert "label: 'Gross profit'" in headline
    assert "dash-kpis" in text
    assert 'aria-label="Total sales, purchases, expenses, net position, and gross profit"' in text
    assert "Batches" not in headline
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
    assert "label: 'Gross profit'" in text
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
    assert "EmptyState" in text
    assert "Money owed" in text
    assert "Receivables" in text
    assert "Payables" in text
    assert 'aria-label="New sale"' not in text
    assert "Open point of sale" not in text
    assert "Record expense" not in text
    assert "Dashboard shortcuts" not in text
    assert "dash-pair" in text
    assert 'aria-label="Inventory health, business mix, cash flow, and money owed"' in text
    assert 'aria-label="Daily sales, revenue trend, and monthly sales"' in text
    assert "info-grid dash-charts" in text
    css = (Path(__file__).resolve().parents[2] / "frontend/app/globals.css").read_text(encoding="utf-8")
    compact = css.replace(" ", "").replace("\n", "")
    assert ".info-grid>.panel:last-child{grid-column:1/-1}" in compact
    assert ".info-grid.dash-charts{gap:14px;align-items:stretch;grid-template-columns:repeat(3,minmax(0,1fr))" in compact
    assert ".info-grid.dash-charts>.panel:last-child{grid-column:auto}" in compact
    assert ".info-grid.dash-charts{grid-template-columns:1fr;gap:12px}" in compact
    assert ".dash-chart-svg,.dash-chartsvg{width:100%;height:168px;display:block}" in compact
    assert ".dash-pair{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))" in compact
    assert ".dash-pair.panel{min-width:0;padding:16px" in compact
    assert ".dash-pair{grid-template-columns:repeat(2,minmax(0,1fr))" in compact
    assert ".dash-pair.bar-row.bar-track{display:block" in compact
    assert ".stat-grid.dash-kpis{grid-template-columns:repeat(5,minmax(0,1fr))" in compact
    assert ".stat-grid.dash-kpis>.stat:last-child{grid-column:1/-1}" in compact
    assert ".dash-hero.greet-clock,.greet-clock{display:none}" in compact
    assert '[data-theme="dark"].dash-hero.greet,[data-theme="dark"].dash-hero.greet-hello{color:var(--mist)!important}' in compact
    assert '[data-theme="dark"].dash-pair.health.pill,[data-theme="dark"].dash-pair.legend.li{background:#001A0E;color:#E8F5D8}' in compact
    assert "credit_outstanding" in text
    assert "d.store_name" in text
    assert "top_products_by_quantity" in text
    assert "Rank top products by revenue" in text
    assert "Rank top products by quantity" in text
    assert "returns_count" in text


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


@pytest.mark.asyncio
async def test_dashboard_purchases_count_recorded_bills_not_drafts(db_session, seeded):
    """Headline Purchases is to-date recorded bills plus legacy purchase transactions.

    Draft and cancelled invoices, and unbilled purchase orders, do not count.
    A bill dated last year still counts: the tile is not a today or month window.
    """
    from datetime import datetime, timedelta

    from app.dashboard import RECORDED_PURCHASE_INVOICE_STATUSES

    t1 = seeded["t1"].id
    t2 = seeded["t2"].id
    supplier = m.Party(tenant_id=t1, name="Desk Supplier", kind="supplier")
    other = m.Party(tenant_id=t2, name="Other Supplier", kind="supplier")
    store_a = m.Store(tenant_id=t1, name="Accra", code="ACC-DASH")
    store_b = m.Store(tenant_id=t1, name="Tema", code="TEM-DASH")
    db_session.add_all([supplier, other, store_a, store_b])
    await db_session.flush()

    old = datetime.utcnow() - timedelta(days=400)
    db_session.add_all(
        [
            m.PurchaseInvoice(
                tenant_id=t1,
                supplier_id=supplier.id,
                invoice_number="PINV-DASH-OLD",
                status="unpaid",
                invoice_date=old,
                subtotal=377.20,
                total_amount=377.20,
                paid_amount=0,
                store_id=store_a.id,
            ),
            m.PurchaseInvoice(
                tenant_id=t1,
                supplier_id=supplier.id,
                invoice_number="PINV-DASH-PAID",
                status="paid",
                invoice_date=datetime.utcnow(),
                subtotal=138,
                total_amount=138,
                paid_amount=138,
                store_id=store_b.id,
            ),
            m.PurchaseInvoice(
                tenant_id=t1,
                supplier_id=supplier.id,
                invoice_number="PINV-DASH-DRAFT",
                status="draft",
                invoice_date=datetime.utcnow(),
                subtotal=50,
                total_amount=50,
                store_id=store_a.id,
            ),
            m.PurchaseInvoice(
                tenant_id=t1,
                supplier_id=supplier.id,
                invoice_number="PINV-DASH-CANCEL",
                status="cancelled",
                invoice_date=datetime.utcnow(),
                subtotal=25,
                total_amount=25,
                store_id=store_a.id,
            ),
            m.PurchaseInvoice(
                tenant_id=t2,
                supplier_id=other.id,
                invoice_number="PINV-DASH-OTHER",
                status="unpaid",
                invoice_date=datetime.utcnow(),
                subtotal=999,
                total_amount=999,
            ),
            m.PurchaseOrder(
                tenant_id=t1,
                supplier_id=supplier.id,
                po_number="PO-DASH-1",
                status="received",
                total_amount=943,
            ),
            m.Transaction(
                tenant_id=t1,
                tx_type="purchase",
                reference="PUR-DASH-LEGACY",
                total=10,
                subtotal=10,
                tax=0,
            ),
        ]
    )
    await db_session.commit()

    data = await build_dashboard(db_session, t1)
    assert set(RECORDED_PURCHASE_INVOICE_STATUSES) == {"unpaid", "partial", "paid", "overdue"}
    assert data["total_purchases"] == pytest.approx(377.20 + 138 + 10)

    scoped = await build_dashboard(db_session, t1, store_id=store_a.id)
    assert scoped["total_purchases"] == pytest.approx(377.20)
