"""Stage 22 R1: Customer credit surface fidelity (BR-11.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_customer_credit_limit_block_override_balance_payment_statement(
    client, db_session
):
    """BR-11.1: limit, block+override, balance, collections, statement (allocate cited Stage 14)."""
    ac, seed = client
    mgr_h = await _mgr(ac)
    super_h = await _super(ac, seed)
    seed["p1"].stock_qty = 100
    await db_session.commit()

    # --- Set per-customer credit limit ---
    created = await ac.post(
        "/api/v1/customers",
        headers=mgr_h,
        json={"name": "R1 Credit Customer", "credit_limit": 50},
    )
    assert created.status_code == 200, created.text
    customer_id = created.json()["data"]["id"]
    assert float(created.json()["data"]["credit_limit"]) == pytest.approx(50)

    patched = await ac.patch(
        f"/api/v1/customers/{customer_id}/credit-limit",
        headers=mgr_h,
        json={"credit_limit": 100},
    )
    assert patched.status_code == 200, patched.text
    assert float(patched.json()["data"]["credit_limit"]) == pytest.approx(100)
    assert "balance" in patched.json()["data"]

    profile = await ac.get(f"/api/v1/customers/{customer_id}", headers=mgr_h)
    assert profile.status_code == 200, profile.text
    assert float(profile.json()["data"]["credit_limit"]) == pytest.approx(100)
    assert float(profile.json()["data"]["balance"]) == pytest.approx(0)

    # Invoice that exceeds limit (150 > 100)
    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=mgr_h,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 150,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    assert float(inv.json()["data"]["total_amount"]) == pytest.approx(150)

    blocked = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post",
        headers=super_h,
        json={},
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json()["detail"]
    assert detail["code"] == "CREDIT_LIMIT_EXCEEDED" or (
        isinstance(detail, dict) and detail.get("code") == "CREDIT_LIMIT_EXCEEDED"
    )

    posted = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post",
        headers=super_h,
        json={
            "credit_limit_override": True,
            "credit_override_reason": "R1 VIP credit override approved",
        },
    )
    assert posted.status_code == 200, posted.text
    pdata = posted.json()["data"]
    assert pdata["status"] in {"posted", "unpaid", "partial"}
    assert pdata.get("credit_limit_overridden") is True

    # Outstanding balance on customer profile
    profile2 = await ac.get(f"/api/v1/customers/{customer_id}", headers=mgr_h)
    assert profile2.status_code == 200
    assert float(profile2.json()["data"]["balance"]) == pytest.approx(150)

    outstanding = await ac.get(
        f"/api/v1/customers/{customer_id}/outstanding", headers=mgr_h
    )
    assert outstanding.status_code == 200, outstanding.text
    docs = outstanding.json()["data"]
    assert isinstance(docs, list)
    assert any(d.get("invoice_id") == invoice_id for d in docs)

    # Payment collections with date, amount, method, reference
    pay = await ac.post(
        f"/api/v1/customers/{customer_id}/payments",
        headers=mgr_h,
        json={
            "customer_id": customer_id,
            "amount": 60,
            "sales_invoice_id": invoice_id,
            "payment_method": "bank_transfer",
            "reference": "R1-COLL-001",
        },
    )
    assert pay.status_code == 200, pay.text
    pay_body = pay.json()["data"]
    assert pay_body.get("payment_number") or pay_body.get("id")
    assert float(pay_body.get("amount") or 60) == pytest.approx(60)
    profile3 = await ac.get(f"/api/v1/customers/{customer_id}", headers=mgr_h)
    assert float(profile3.json()["data"]["balance"]) == pytest.approx(90)

    # Customer statement: invoices + payments + balance
    stmt = await ac.get(
        f"/api/v1/credit/customers/{customer_id}/statement", headers=mgr_h
    )
    assert stmt.status_code == 200, stmt.text
    sdata = stmt.json()["data"]
    assert sdata["customer"]["id"] == customer_id
    assert float(sdata["customer"]["credit_limit"]) == pytest.approx(100)
    assert float(sdata["customer"]["balance"]) == pytest.approx(90)
    lines = sdata["lines"]
    assert any(ln.get("type") == "invoice" for ln in lines)
    assert any(ln.get("type") == "payment" for ln in lines)
    pay_line = next(ln for ln in lines if ln.get("type") == "payment")
    assert float(pay_line["credit"]) == pytest.approx(60)


def test_br_11_1_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s111 = br.split("#### BR-11.1 Customer Credit")[1].split("#### BR-11.2")[0]
    assert "[x] Set per-customer credit limit" in s111
    assert "[x] Block sales that exceed credit limit" in s111
    assert "[x] Display outstanding balance on customer profile" in s111
    assert "[x] Record payment collections" in s111
    assert "[x] Allocate payments to specific invoices" in s111
    assert "[x] Customer statement generation" in s111
    assert "Stage 22 R1" in s111
    assert "test_customer_credit_r1.py" in s111
    assert "Stage 14 R1" in s111

    plan = (ROOT / "docs" / "STAGE_22_PLAN.md").read_text(encoding="utf-8")
    r1_line = [ln for ln in plan.splitlines() if "| **R1**" in ln][0]
    assert "COMPLETE" in r1_line
    assert "test_customer_credit_r1.py" in plan
