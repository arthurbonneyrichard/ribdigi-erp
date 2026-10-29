"""Daily/monthly sales and dashboard purchases convert at stored invoice rates."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from app import models as m
from app.dashboard import build_dashboard
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_report_and_dashboard_source_converts_invoice_amounts():
    reports = (ROOT / "backend" / "app" / "reports.py").read_text(encoding="utf-8")
    assert "def _amount_base(" in reports
    assert "invoice_total = sum(_amount_base(i, i.total_amount)" in reports
    assert "by_day[key] += _amount_base(inv, inv.total_amount)" in reports
    assert "pos_total = sum(_tx_base(t)" in reports
    assert "by_day[key] += _tx_base(tx)" in reports
    assert "func.sum(m.SalesInvoice.total_amount)" not in reports
    assert "amount = _amount_base(fx_src, ret.total_amount)" in reports
    assert "async def _linked_sales_invoices(" in reports
    assert "async def _linked_purchase_invoices_by_po(" in reports
    dash = (ROOT / "backend" / "app" / "dashboard.py").read_text(encoding="utf-8")
    assert "func.sum(m.PurchaseInvoice.total_amount)" not in dash
    assert "to_base(amount, rate" in dash
    assert "def _tx_rate(" in dash
    assert "def _tx_amount_base(" in dash
    assert "async def _invoice_sales_base(" in dash
    assert "async def _invoice_line_metrics(" in dash
    assert "func.sum(m.Transaction.total)" not in dash
    assert '"total": money_json(_tx_amount_base(t)),' in dash
    assert "m.Party.tenant_id == tenant_id" in dash
    sales_lists = (ROOT / "backend" / "app" / "sales_reports.py").read_text(encoding="utf-8")
    assert '"total": _amount_base(inv, inv.total_amount or 0),' in sales_lists
    assert '"total": _tx_base(tx),' in sales_lists
    assert "paid = _amount_base(pay, pay.amount)" in sales_lists
    credit = (ROOT / "backend" / "app" / "credit.py").read_text(encoding="utf-8")
    assert '"total_amount_base": money_json(_tx_amount_base(tx)),' in credit
    ai_sales = (ROOT / "backend" / "app" / "ai_sales.py").read_text(encoding="utf-8")
    assert '"total": _amount_base(inv, inv.total_amount or 0),' in ai_sales
    assert '"total": money_json(_tx_amount_base(tx)),' in ai_sales


@pytest.mark.asyncio
async def test_ghs_and_usd_daily_monthly_sales_use_base(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Report Buyer {suffix}"},
    )
    assert customer.status_code == 200, customer.text
    cid = customer.json()["data"]["id"]
    now = datetime.utcnow()
    store = m.Store(tenant_id=seed["t1"].id, name=f"FX Desk {suffix}", code=f"FX{suffix[:6]}")
    db_session.add(store)
    await db_session.flush()
    session = m.PosSession(
        tenant_id=seed["t1"].id,
        store_id=store.id,
        user_id=seed["admin1"].id,
        session_number=f"SHIFT-FX-{suffix[:8]}",
        status="closed",
        opening_cash=0,
    )
    db_session.add(session)
    await db_session.flush()
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"INV-REP-GHS-{suffix}",
                customer_id=cid,
                store_id=store.id,
                status="posted",
                currency="",
                exchange_rate=1,
                total_amount=60,
                tax_amount=0,
                discount_amount=0,
                posted_at=now,
            ),
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"INV-REP-USD-{suffix}",
                customer_id=cid,
                store_id=store.id,
                status="posted",
                currency="USD",
                exchange_rate=12,
                total_amount=40,
                tax_amount=0,
                discount_amount=0,
                posted_at=now,
            ),
            m.Transaction(
                tenant_id=seed["t1"].id,
                tx_type="pos_sale",
                reference=f"POS-REP-FX-{suffix}",
                session_id=session.id,
                total=10,
                subtotal=10,
                tax=0,
                status="completed",
                created_at=now,
                payload={"exchange_rate": 12},
            ),
        ]
    )
    await db_session.commit()

    expected = 60 + 40 * 12 + 10 * 12
    daily = await ac.get(
        f"/api/v1/reports/sales/daily?store_id={store.id}", headers=admin
    )
    assert daily.status_code == 200, daily.text
    body = daily.json()["data"]
    assert body["total_revenue"] == pytest.approx(expected)
    assert body["invoice_revenue"] == pytest.approx(60 + 40 * 12)
    assert body["pos_revenue"] == pytest.approx(120)
    assert body["total_revenue"] != pytest.approx(110.0)
    assert body["invoice_count"] == 2
    assert body["pos_count"] == 1

    monthly = await ac.get(
        f"/api/v1/reports/sales/monthly?year={now.year}&month={now.month}&store_id={store.id}",
        headers=admin,
    )
    assert monthly.status_code == 200, monthly.text
    month = monthly.json()["data"]
    assert month["total_revenue"] == pytest.approx(expected)
    assert month["total_revenue"] != pytest.approx(110.0)

    by_store = await ac.get("/api/v1/reports/sales/by-store", headers=admin)
    assert by_store.status_code == 200, by_store.text
    store_row = next(r for r in by_store.json()["data"]["stores"] if r["store_id"] == store.id)
    assert store_row["revenue"] == pytest.approx(expected)
    assert store_row["revenue"] != pytest.approx(110.0)

    made = await ac.get("/api/v1/sales/made", headers=admin)
    assert made.status_code == 200, made.text
    pos_row = next(
        r
        for r in made.json()["data"]
        if r.get("number") == f"POS-REP-FX-{suffix}"
    )
    assert float(pos_row["total"]) == pytest.approx(120)


@pytest.mark.asyncio
async def test_dashboard_purchases_ghs_and_usd_use_base(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Dash Vendor {suffix}"},
    )
    assert supplier.status_code == 200, supplier.text
    sid = supplier.json()["data"]["id"]
    before = await build_dashboard(db_session, seed["t1"].id)
    prior = float(before["total_purchases"])
    db_session.add_all(
        [
            m.PurchaseInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"PI-DASH-GHS-{suffix}",
                supplier_id=sid,
                status="unpaid",
                currency="",
                exchange_rate=1,
                total_amount=60,
            ),
            m.PurchaseInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"PI-DASH-USD-{suffix}",
                supplier_id=sid,
                status="paid",
                currency="USD",
                exchange_rate=12,
                total_amount=40,
                paid_amount=40,
            ),
        ]
    )
    await db_session.commit()

    dash = await ac.get("/api/v1/dashboard", headers=admin)
    assert dash.status_code == 200, dash.text
    total = float(dash.json()["data"]["total_purchases"])
    assert total == pytest.approx(prior + 60 + 40 * 12)
    assert total != pytest.approx(prior + 100.0)


@pytest.mark.asyncio
async def test_dashboard_sales_ghs_and_usd_invoices_use_base(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Dash Buyer {suffix}"},
    )
    assert customer.status_code == 200, customer.text
    cid = customer.json()["data"]["id"]
    now = datetime.utcnow()
    before = await build_dashboard(db_session, seed["t1"].id)
    prior_sales = float(before["total_sales"])
    prior_today = float(before["comparisons"]["sales_today"])
    db_session.add_all(
        [
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"INV-DASH-GHS-{suffix}",
                customer_id=cid,
                status="posted",
                currency="",
                exchange_rate=1,
                total_amount=60,
                posted_at=now,
            ),
            m.SalesInvoice(
                tenant_id=seed["t1"].id,
                invoice_number=f"INV-DASH-USD-{suffix}",
                customer_id=cid,
                status="posted",
                currency="USD",
                exchange_rate=12,
                total_amount=40,
                posted_at=now,
            ),
            m.Transaction(
                tenant_id=seed["t1"].id,
                tx_type="pos_sale",
                reference=f"POS-DASH-BASE-{suffix}",
                total=10,
                subtotal=10,
                tax=0,
                created_at=now,
                payload={},
            ),
            m.Transaction(
                tenant_id=seed["t1"].id,
                tx_type="pos_sale",
                reference=f"POS-DASH-FX-{suffix}",
                total=10,
                subtotal=10,
                tax=0,
                created_at=now,
                payload={"exchange_rate": 12},
            ),
        ]
    )
    await db_session.commit()

    dash = await ac.get("/api/v1/dashboard", headers=admin)
    assert dash.status_code == 200, dash.text
    body = dash.json()["data"]
    added = 60 + 40 * 12 + 10 + 10 * 12
    assert float(body["total_sales"]) == pytest.approx(prior_sales + added)
    assert float(body["comparisons"]["sales_today"]) == pytest.approx(prior_today + added)
    assert float(body["total_sales"]) != pytest.approx(prior_sales + 120.0)
    recent_base = next(r for r in body["recent_sales"] if r["reference"] == f"POS-DASH-BASE-{suffix}")
    recent_fx = next(r for r in body["recent_sales"] if r["reference"] == f"POS-DASH-FX-{suffix}")
    assert float(recent_base["total"]) == pytest.approx(10)
    assert float(recent_fx["total"]) == pytest.approx(120)
    month_row = next(
        r for r in body["monthly_sales"] if r["year"] == now.year and r["month"] == now.month
    )
    assert float(month_row["total"]) >= added


@pytest.mark.asyncio
async def test_dashboard_profit_and_top_products_use_invoice_fx(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Dash Top {suffix}"},
    )
    assert customer.status_code == 200, customer.text
    cid = customer.json()["data"]["id"]
    now = datetime.utcnow()
    product = m.Product(
        tenant_id=seed["t1"].id,
        name=f"FX Top {suffix}",
        sku=f"FXT{suffix[:8]}",
        cost_price=1,
        selling_price=30,
        stock_qty=100,
    )
    db_session.add(product)
    await db_session.flush()
    ghs = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number=f"INV-TOP-GHS-{suffix}",
        customer_id=cid,
        status="posted",
        currency="",
        exchange_rate=1,
        total_amount=60,
        posted_at=now,
    )
    usd = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number=f"INV-TOP-USD-{suffix}",
        customer_id=cid,
        status="posted",
        currency="USD",
        exchange_rate=12,
        total_amount=40,
        posted_at=now,
    )
    db_session.add_all([ghs, usd])
    await db_session.flush()
    db_session.add_all(
        [
            m.SalesInvoiceItem(
                tenant_id=seed["t1"].id,
                sales_invoice_id=ghs.id,
                product_id=product.id,
                quantity=2,
                unit_price=30,
                line_subtotal=60,
                line_total=60,
            ),
            m.SalesInvoiceItem(
                tenant_id=seed["t1"].id,
                sales_invoice_id=usd.id,
                product_id=product.id,
                quantity=2,
                unit_price=20,
                line_subtotal=40,
                line_total=40,
            ),
            m.Transaction(
                tenant_id=seed["t1"].id,
                tx_type="pos_sale",
                reference=f"POS-TOP-FX-{suffix}",
                total=10,
                subtotal=10,
                tax=0,
                created_at=now,
                payload={
                    "exchange_rate": 12,
                    "items": [
                        {
                            "product_id": product.id,
                            "quantity": 1,
                            "unit_price": 10,
                            "line_total": 10,
                        }
                    ],
                },
            ),
        ]
    )
    await db_session.commit()

    dash = await ac.get("/api/v1/dashboard", headers=admin)
    assert dash.status_code == 200, dash.text
    body = dash.json()["data"]
    top = next(r for r in body["top_products_by_revenue"] if r["product_id"] == product.id)
    expected_rev = 60 + 40 * 12 + 10 * 12
    assert float(top["revenue"]) == pytest.approx(expected_rev)
    assert float(top["revenue"]) != pytest.approx(110.0)
    assert float(top["quantity"]) == pytest.approx(5)
    today_row = next(r for r in body["daily_sales"] if r["date"] == now.date().isoformat())
    expected_profit = 2 * (30 - 1) + 2 * (240 - 1) + 1 * (120 - 1)
    assert float(today_row["profit"]) == pytest.approx(expected_profit)
    assert float(today_row["profit"]) != pytest.approx(2 * (30 - 1) + 2 * (20 - 1) + 1 * (10 - 1))


@pytest.mark.asyncio
async def test_report_and_dashboard_exclude_other_tenant(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    now = datetime.utcnow()
    beta_product = m.Product(
        tenant_id=seed["t2"].id,
        name=f"Beta FX Top {suffix}",
        sku=f"BFT{suffix[:8]}",
        cost_price=1,
        selling_price=999,
        stock_qty=10,
    )
    db_session.add(beta_product)
    await db_session.flush()
    beta_inv = m.SalesInvoice(
        tenant_id=seed["t2"].id,
        invoice_number=f"INV-BETA-REP-{suffix}",
        customer_id=seed["party2"].id,
        status="posted",
        currency="USD",
        exchange_rate=12,
        total_amount=999,
        posted_at=now,
    )
    db_session.add(beta_inv)
    await db_session.flush()
    db_session.add(
        m.SalesInvoiceItem(
            tenant_id=seed["t2"].id,
            sales_invoice_id=beta_inv.id,
            product_id=beta_product.id,
            quantity=1,
            unit_price=999,
            line_subtotal=999,
            line_total=999,
        )
    )
    db_session.add(
        m.PurchaseInvoice(
            tenant_id=seed["t2"].id,
            invoice_number=f"PI-BETA-DASH-{suffix}",
            supplier_id=seed["supplier2"].id,
            status="unpaid",
            currency="USD",
            exchange_rate=12,
            total_amount=888,
        )
    )
    await db_session.commit()

    before_alpha = await build_dashboard(db_session, seed["t1"].id)
    daily = await ac.get("/api/v1/reports/sales/daily", headers=admin)
    assert daily.status_code == 200, daily.text
    assert daily.json()["data"]["total_revenue"] != pytest.approx(999 * 12)

    after_alpha = await build_dashboard(db_session, seed["t1"].id)
    assert after_alpha["total_purchases"] == pytest.approx(before_alpha["total_purchases"])
    assert after_alpha["total_sales"] == pytest.approx(before_alpha["total_sales"])
    assert after_alpha["comparisons"]["sales_today"] == pytest.approx(
        before_alpha["comparisons"]["sales_today"]
    )
    assert after_alpha["gross_profit_30d"] == pytest.approx(before_alpha["gross_profit_30d"])
    assert all(
        row["product_id"] != beta_product.id for row in after_alpha["top_products_by_revenue"]
    )


@pytest.mark.asyncio
async def test_ghs_and_usd_sales_returns_and_lists_use_base(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    customer = await ac.post(
        "/api/v1/customers",
        headers=admin,
        json={"name": f"Return Buyer {suffix}"},
    )
    assert customer.status_code == 200, customer.text
    cid = customer.json()["data"]["id"]
    now = datetime.utcnow()
    store = m.Store(tenant_id=seed["t1"].id, name=f"FX Returns {suffix}", code=f"FR{suffix[:6]}")
    db_session.add(store)
    await db_session.flush()
    ghs = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number=f"INV-RET-GHS-{suffix}",
        customer_id=cid,
        store_id=store.id,
        status="posted",
        currency="",
        exchange_rate=1,
        total_amount=60,
        posted_at=now,
    )
    usd = m.SalesInvoice(
        tenant_id=seed["t1"].id,
        invoice_number=f"INV-RET-USD-{suffix}",
        customer_id=cid,
        store_id=store.id,
        status="posted",
        currency="USD",
        exchange_rate=12,
        total_amount=40,
        posted_at=now,
    )
    db_session.add_all([ghs, usd])
    await db_session.flush()
    ghs_ret = m.SalesReturn(
        tenant_id=seed["t1"].id,
        return_number=f"SR-GHS-{suffix}",
        customer_id=cid,
        sales_invoice_id=ghs.id,
        status="posted",
        reason="damaged",
        total_amount=60,
        refunded_amount=0,
        posted_at=now,
    )
    usd_ret = m.SalesReturn(
        tenant_id=seed["t1"].id,
        return_number=f"SR-USD-{suffix}",
        customer_id=cid,
        sales_invoice_id=usd.id,
        status="posted",
        reason="damaged",
        total_amount=40,
        refunded_amount=10,
        posted_at=now,
    )
    db_session.add_all([ghs_ret, usd_ret])
    await db_session.flush()
    db_session.add_all(
        [
            m.SalesReturnItem(
                tenant_id=seed["t1"].id,
                sales_return_id=ghs_ret.id,
                product_id=seed["p1"].id,
                quantity=1,
                unit_price=60,
                line_total=60,
            ),
            m.SalesReturnItem(
                tenant_id=seed["t1"].id,
                sales_return_id=usd_ret.id,
                product_id=seed["p1"].id,
                quantity=1,
                unit_price=40,
                line_total=40,
            ),
        ]
    )
    await db_session.commit()

    ret = await ac.get(f"/api/v1/reports/sales/returns?store_id={store.id}", headers=admin)
    assert ret.status_code == 200, ret.text
    body = ret.json()["data"]
    assert body["total_amount"] == pytest.approx(60 + 40 * 12)
    assert body["posted_amount"] == pytest.approx(60 + 40 * 12)
    assert body["refunded_amount"] == pytest.approx(10 * 12)
    assert body["total_amount"] != pytest.approx(100.0)

    tx = await ac.get(f"/api/v1/reports/sales/transactions?store_id={store.id}", headers=admin)
    assert tx.status_code == 200, tx.text
    assert tx.json()["data"]["total"] == pytest.approx(60 + 40 * 12)

    hist = await ac.get(f"/api/v1/customers/{cid}/history", headers=admin)
    assert hist.status_code == 200, hist.text
    assert hist.json()["data"]["summary"]["return_total"] == pytest.approx(60 + 40 * 12)


@pytest.mark.asyncio
async def test_ghs_and_usd_purchase_returns_use_linked_bill_rate(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=admin,
        json={"name": f"Return Vendor {suffix}"},
    )
    assert supplier.status_code == 200, supplier.text
    sid = supplier.json()["data"]["id"]
    t1 = seed["t1"].id
    product = seed["p1"]

    po_ghs = m.PurchaseOrder(
        tenant_id=t1, po_number=f"PO-RET-GHS-{suffix}", supplier_id=sid, status="received", total_amount=60
    )
    po_usd = m.PurchaseOrder(
        tenant_id=t1, po_number=f"PO-RET-USD-{suffix}", supplier_id=sid, status="received", total_amount=40
    )
    db_session.add_all([po_ghs, po_usd])
    await db_session.flush()
    poi_ghs = m.PurchaseOrderItem(
        tenant_id=t1,
        purchase_order_id=po_ghs.id,
        product_id=product.id,
        quantity=1,
        received_qty=1,
        unit_price=60,
        line_total=60,
    )
    poi_usd = m.PurchaseOrderItem(
        tenant_id=t1,
        purchase_order_id=po_usd.id,
        product_id=product.id,
        quantity=1,
        received_qty=1,
        unit_price=40,
        line_total=40,
    )
    db_session.add_all([poi_ghs, poi_usd])
    await db_session.flush()
    grn_ghs = m.GoodsReceipt(
        tenant_id=t1,
        grn_number=f"GRN-RET-GHS-{suffix}",
        purchase_order_id=po_ghs.id,
        supplier_id=sid,
        status="posted",
    )
    grn_usd = m.GoodsReceipt(
        tenant_id=t1,
        grn_number=f"GRN-RET-USD-{suffix}",
        purchase_order_id=po_usd.id,
        supplier_id=sid,
        status="posted",
    )
    db_session.add_all([grn_ghs, grn_usd])
    await db_session.flush()
    item_ghs = m.GoodsReceiptItem(
        tenant_id=t1,
        goods_receipt_id=grn_ghs.id,
        po_item_id=poi_ghs.id,
        product_id=product.id,
        received_qty=1,
        accepted_qty=1,
        rejected_qty=0,
    )
    item_usd = m.GoodsReceiptItem(
        tenant_id=t1,
        goods_receipt_id=grn_usd.id,
        po_item_id=poi_usd.id,
        product_id=product.id,
        received_qty=1,
        accepted_qty=1,
        rejected_qty=0,
    )
    db_session.add_all([item_ghs, item_usd])
    db_session.add_all(
        [
            m.PurchaseInvoice(
                tenant_id=t1,
                invoice_number=f"PI-RET-GHS-{suffix}",
                supplier_id=sid,
                purchase_order_id=po_ghs.id,
                status="unpaid",
                currency="",
                exchange_rate=1,
                total_amount=60,
            ),
            m.PurchaseInvoice(
                tenant_id=t1,
                invoice_number=f"PI-RET-USD-{suffix}",
                supplier_id=sid,
                purchase_order_id=po_usd.id,
                status="unpaid",
                currency="USD",
                exchange_rate=12,
                total_amount=40,
            ),
        ]
    )
    await db_session.flush()
    ret_ghs = m.PurchaseReturn(
        tenant_id=t1,
        return_number=f"PR-GHS-{suffix}",
        supplier_id=sid,
        purchase_order_id=po_ghs.id,
        goods_receipt_id=grn_ghs.id,
        status="posted",
        reason="damaged",
        total_amount=60,
        posted_at=datetime.utcnow(),
    )
    ret_usd = m.PurchaseReturn(
        tenant_id=t1,
        return_number=f"PR-USD-{suffix}",
        supplier_id=sid,
        purchase_order_id=po_usd.id,
        goods_receipt_id=grn_usd.id,
        status="posted",
        reason="damaged",
        total_amount=40,
        posted_at=datetime.utcnow(),
    )
    db_session.add_all([ret_ghs, ret_usd])
    await db_session.flush()
    db_session.add_all(
        [
            m.PurchaseReturnItem(
                tenant_id=t1,
                purchase_return_id=ret_ghs.id,
                goods_receipt_item_id=item_ghs.id,
                product_id=product.id,
                quantity=1,
                unit_price=60,
                line_total=60,
            ),
            m.PurchaseReturnItem(
                tenant_id=t1,
                purchase_return_id=ret_usd.id,
                goods_receipt_item_id=item_usd.id,
                product_id=product.id,
                quantity=1,
                unit_price=40,
                line_total=40,
            ),
        ]
    )
    await db_session.commit()

    ret = await ac.get("/api/v1/reports/purchases/returns", headers=admin)
    assert ret.status_code == 200, ret.text
    body = ret.json()["data"]
    assert body["total_amount"] == pytest.approx(60 + 40 * 12)
    assert body["posted_amount"] == pytest.approx(60 + 40 * 12)
    assert body["total_amount"] != pytest.approx(100.0)

    hist = await ac.get(f"/api/v1/suppliers/{sid}/history", headers=admin)
    assert hist.status_code == 200, hist.text
    assert hist.json()["data"]["summary"]["return_total"] == pytest.approx(60 + 40 * 12)


@pytest.mark.asyncio
async def test_return_reports_exclude_other_tenant(client, db_session):
    ac, seed = client
    admin = await _super(ac, seed)
    suffix = uuid4().hex[:8]
    now = datetime.utcnow()
    inv = m.SalesInvoice(
        tenant_id=seed["t2"].id,
        invoice_number=f"INV-BETA-RET-{suffix}",
        customer_id=seed["party2"].id,
        status="posted",
        currency="USD",
        exchange_rate=12,
        total_amount=999,
        posted_at=now,
    )
    db_session.add(inv)
    await db_session.flush()
    ret = m.SalesReturn(
        tenant_id=seed["t2"].id,
        return_number=f"SR-BETA-{suffix}",
        customer_id=seed["party2"].id,
        sales_invoice_id=inv.id,
        status="posted",
        reason="damaged",
        total_amount=999,
        posted_at=now,
    )
    db_session.add(ret)
    await db_session.flush()
    db_session.add(
        m.SalesReturnItem(
            tenant_id=seed["t2"].id,
            sales_return_id=ret.id,
            product_id=seed["p2"].id,
            quantity=1,
            unit_price=999,
            line_total=999,
        )
    )
    await db_session.commit()

    before = await ac.get("/api/v1/reports/sales/returns", headers=admin)
    assert before.status_code == 200, before.text
    assert before.json()["data"]["total_amount"] != pytest.approx(999 * 12)
