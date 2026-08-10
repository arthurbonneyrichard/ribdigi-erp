"""Stage 12 C2: POS open → cart/discount/tax → pay → receipt → stock → close/variance."""

from __future__ import annotations

import pytest

from app import accounting as accounting_svc
from app import models as m
from tests.conftest import auth_headers


async def _cashier(ac):
    return await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_pos_shift_sale_receipt_stock_close(client, db_session):
    ac, seed = client
    headers = await _cashier(ac)
    mgr = await _mgr(ac)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)

    rate = m.TaxRate(
        tenant_id=tenant_id,
        name="POS VAT 15",
        rate=15,
        tax_type="vat",
        pricing_mode="exclusive",
        is_default=False,
        is_active=True,
    )
    db_session.add(rate)
    await db_session.flush()

    product = seed["p1"]
    product.selling_price = 100
    product.stock_qty = 40
    product.tax_rate_id = rate.id
    product.barcode = "POSC2-SCAN-001"
    await db_session.commit()
    opening_stock = 40.0

    # Product search / barcode resolve
    search = await ac.get(
        "/api/v1/pos/products/search",
        headers=headers,
        params={"q": "POSC2-SCAN-001"},
    )
    assert search.status_code == 200, search.text
    found = search.json()["data"]
    assert any(p["id"] == product.id for p in found)

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 200},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"].get("session_id") or opened.json()["data"].get(
        "id"
    )
    assert session_id

    # Line: 2 × 100 = 200, line discount 20 → net 180, tax 15% → 27, line gross 207
    # Cart discount 7 → total 200
    sale = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "payment_method": "cash",
            "discount_amount": 7,
            "items": [
                {
                    "product_id": product.id,
                    "quantity": 2,
                    "discount": 20,
                }
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    data = sale.json()["data"]
    sale_id = data["id"]
    assert float(data["subtotal"]) == pytest.approx(180)
    assert float(data["tax"]) == pytest.approx(27)
    assert float(data["discount_amount"]) == pytest.approx(7)
    assert float(data["total"]) == pytest.approx(200)

    receipt = await ac.get(f"/api/v1/pos/sales/{sale_id}/receipt", headers=headers)
    assert receipt.status_code == 200, receipt.text
    rbody = receipt.json()["data"]
    assert float(rbody["total"]) == pytest.approx(200)
    assert "Discount" in (rbody.get("text") or "") or float(rbody.get("discount_amount") or 0) == 7

    prod = await ac.get(f"/api/v1/products/{product.id}", headers=mgr)
    assert prod.status_code == 200
    assert float(prod.json()["data"]["stock_qty"]) == pytest.approx(opening_stock - 2)

    journals = await ac.get("/api/v1/accounting/journal-entries", headers=mgr)
    assert journals.status_code == 200
    pos_jes = [
        j
        for j in journals.json()["data"]
        if j.get("source_type") == "pos_sale" and j.get("source_id") == sale_id
    ]
    assert len(pos_jes) == 1
    assert float(pos_jes[0]["total_debit"]) == pytest.approx(200)

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    assert cur.status_code == 200
    sess = cur.json()["data"]
    assert float(sess["cash_sales"]) == pytest.approx(200)
    expected_cash = 200 + 200  # opening + cash sales

    # Close short by 5 → variance -5
    closed = await ac.post(
        f"/api/v1/pos/sessions/{session_id}/close",
        headers=headers,
        json={"actual_cash": expected_cash - 5, "notes": "C2 short"},
    )
    assert closed.status_code == 200, closed.text
    cdata = closed.json()["data"]
    assert cdata["status"] == "closed"
    assert float(cdata["expected_cash"]) == pytest.approx(expected_cash)
    assert float(cdata["actual_cash"]) == pytest.approx(expected_cash - 5)
    assert float(cdata["variance"]) == pytest.approx(-5)

    report = await ac.get(
        f"/api/v1/pos/sessions/{session_id}/report", headers=headers
    )
    assert report.status_code == 200, report.text
    rdata = report.json()["data"]
    session_block = rdata.get("session") or rdata
    assert float(session_block["cash_sales"]) == pytest.approx(200)
    assert int(session_block["sale_count"]) >= 1
    assert len(rdata.get("sales") or []) >= 1
