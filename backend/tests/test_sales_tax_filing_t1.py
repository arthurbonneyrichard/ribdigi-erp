"""Stage 15 T1: live HTTP-posted invoices feed tax report and filing boxes."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app.inventory import apply_stock_change
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_live_posted_invoices_feed_tax_report_and_filing(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id

    std = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "S15 T1 Standard VAT",
            "rate": 15,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": True,
            "is_reverse_charge": False,
        },
    )
    assert std.status_code == 200, std.text
    std_id = std.json()["data"]["id"]

    rc = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "S15 T1 Reverse Charge VAT",
            "rate": 15,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": False,
            "is_reverse_charge": True,
        },
    )
    assert rc.status_code == 200, rc.text
    rc_id = rc.json()["data"]["id"]

    zero = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={
            "name": "S15 T1 Zero Rated",
            "rate": 0,
            "tax_type": "vat",
            "pricing_mode": "exclusive",
            "is_default": False,
        },
    )
    assert zero.status_code == 200, zero.text
    zero_id = zero.json()["data"]["id"]

    async def _product(name: str, sku: str, **extra) -> str:
        body = {
            "name": name,
            "sku": sku,
            "cost_price": 1,
            "selling_price": 10,
            "stock_qty": 0,
            **extra,
        }
        created = await ac.post("/api/v1/products", headers=headers, json=body)
        assert created.status_code == 200, created.text
        pid = created.json()["data"]["id"]
        await apply_stock_change(
            db_session,
            tenant_id=tenant_id,
            product_id=pid,
            quantity_delta=50,
            movement_type="stock_in",
            user_id=seed["admin1"].id,
        )
        await db_session.commit()
        return pid

    p_std = await _product("T1 Std Widget", "T1-STD", tax_rate_id=std_id)
    p_rc = await _product("T1 RC Widget", "T1-RC", tax_rate_id=rc_id)
    p_zero = await _product("T1 Zero Widget", "T1-ZERO", tax_rate_id=zero_id)
    p_ex = await _product("T1 Exempt Widget", "T1-EX", tax_exempt=True)

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "T1 Tax Filing Customer", "credit_limit": 50000},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    async def _post_invoice(items: list[dict]) -> dict:
        created = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={"customer_id": customer_id, "items": items},
        )
        assert created.status_code == 200, created.text
        inv_id = created.json()["data"]["id"]
        posted = await ac.post(f"/api/v1/sales/invoices/{inv_id}/post", headers=headers)
        assert posted.status_code == 200, posted.text
        return posted.json()["data"]

    # Standard: 2 × 100 @ 15% → net 200, tax 30, total 230
    inv_std = await _post_invoice(
        [{"product_id": p_std, "quantity": 2, "unit_price": 100}]
    )
    assert float(inv_std["tax_amount"]) == pytest.approx(30)
    assert float(inv_std["total_amount"]) == pytest.approx(230)
    assert float(inv_std.get("reverse_charge_tax") or 0) == pytest.approx(0)

    # Reverse charge memo: 1 × 100 @ 15% RC → customer total 100, RC memo 15
    inv_rc = await _post_invoice(
        [{"product_id": p_rc, "quantity": 1, "unit_price": 100}]
    )
    assert float(inv_rc["tax_amount"]) == pytest.approx(0)
    assert float(inv_rc["total_amount"]) == pytest.approx(100)
    assert float(inv_rc.get("reverse_charge_tax") or 0) == pytest.approx(15)

    # Zero + exempt supply split on one invoice
    inv_split = await _post_invoice(
        [
            {"product_id": p_zero, "quantity": 1, "unit_price": 80},
            {"product_id": p_ex, "quantity": 1, "unit_price": 50},
        ]
    )
    assert float(inv_split["tax_amount"]) == pytest.approx(0)
    assert float(inv_split["total_amount"]) == pytest.approx(130)

    now = datetime.utcnow()
    params = {
        "from_date": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
        "to_date": (now + timedelta(days=1)).strftime("%Y-%m-%d"),
    }

    tax_resp = await ac.get("/api/v1/reports/tax", headers=headers, params=params)
    assert tax_resp.status_code == 200, tax_resp.text
    tax = tax_resp.json()["data"]
    assert int(tax["invoice_count"]) >= 3
    assert float(tax["output_tax_invoices"]) >= 30
    assert float(tax["output_tax"]) >= 30
    assert float(tax["reverse_charge_tax"]) >= 15
    assert float(tax["taxable_outputs_net"]) >= 200
    assert float(tax["zero_rated_outputs_net"]) >= 80
    assert float(tax["exempt_outputs_net"]) >= 50

    filing_resp = await ac.get(
        "/api/v1/reports/tax/filing", headers=headers, params=params
    )
    assert filing_resp.status_code == 200, filing_resp.text
    pack = filing_resp.json()["data"]
    boxes = pack["filing_boxes"]
    assert float(boxes["output_tax"]) >= 30
    assert float(boxes["reverse_charge_tax"]) >= 15
    assert float(boxes["taxable_outputs_net"]) >= 200
    assert float(boxes["zero_rated_outputs_net"]) >= 80
    assert float(boxes["exempt_outputs_net"]) >= 50

    by_box_code = {b["code"]: b["amount"] for b in boxes["boxes"]}
    assert float(by_box_code["output_tax"]) >= 30
    assert float(by_box_code["reverse_charge_tax"]) >= 15
    assert float(by_box_code["taxable_outputs_net"]) >= 200

    output_sched = pack["schedules"]["output"]
    by_doc = {
        row["document_id"]: row
        for row in output_sched
        if row.get("document_type") == "sales_invoice"
    }
    assert inv_std["id"] in by_doc
    assert inv_rc["id"] in by_doc
    assert inv_split["id"] in by_doc
    assert float(by_doc[inv_std["id"]]["tax_amount"]) == pytest.approx(30)
    assert float(by_doc[inv_rc["id"]]["reverse_charge_tax"]) == pytest.approx(15)
    assert float(by_doc[inv_rc["id"]]["tax_amount"]) == pytest.approx(0)
    assert by_doc[inv_std["id"]]["document_number"] == inv_std["invoice_number"]

    # Period helper still resolves monthly bounds for the live posts
    monthly = await ac.get(
        "/api/v1/reports/tax",
        headers=headers,
        params={"period": "monthly", "year": now.year, "month": now.month},
    )
    assert monthly.status_code == 200, monthly.text
    mdata = monthly.json()["data"]
    assert mdata["period"] == "monthly"
    assert float(mdata["output_tax_invoices"]) >= 30
    assert float(mdata["reverse_charge_tax"]) >= 15
