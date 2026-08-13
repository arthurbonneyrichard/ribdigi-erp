"""Cash flow Operating / Investing / Financing classification (BR-10.6 / BR-14.5)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pyotp
import pytest

from app import accounting as accounting_svc
from app.reports import cash_flow_activity
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_cash_flow_activity_mapping():
    assert cash_flow_activity("expense") == "operating"
    assert cash_flow_activity("customer_payment") == "operating"
    assert cash_flow_activity("coa_opening") == "financing"
    assert cash_flow_activity("cash_transfer", transfer_kind="deposit") == "financing"
    assert cash_flow_activity("cash_transfer", transfer_kind="withdrawal") == "financing"
    assert cash_flow_activity("cash_transfer", transfer_kind="transfer") == "transfers"
    assert cash_flow_activity(None) == "operating"


@pytest.mark.asyncio
async def test_cash_flow_sections_operating_financing_transfers(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id

    # Ensure liquid accounts exist
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200
    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    by_code = {a["code"]: a for a in liq.json()["data"]}
    cash_id = by_code["1000"]["id"]
    bank_id = by_code["1010"]["id"]

    # Financing: owner deposit into cash
    dep = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={"kind": "deposit", "to_account_id": cash_id, "amount": 500, "reference": "EQ"},
    )
    assert dep.status_code == 200, dep.text

    # Operating: expense paid from cash
    await accounting_svc.post_journal_entry(
        db_session,
        tenant_id=tenant_id,
        user_id=seed["admin1"].id,
        description="Office supplies",
        source_type="expense",
        lines=[
            {"account_code": "6000", "debit": 40, "credit": 0},
            {"account_code": "1000", "debit": 0, "credit": 40},
        ],
    )
    await db_session.commit()

    # Transfers: cash → bank (internal)
    xfer = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={
            "kind": "transfer",
            "from_account_id": cash_id,
            "to_account_id": bank_id,
            "amount": 100,
            "reference": "TILL",
        },
    )
    assert xfer.status_code == 200, xfer.text

    r = await ac.get("/api/v1/reports/cash-flow", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert "operating" in data and "investing" in data and "financing" in data
    assert "transfers" in data
    assert abs(float(data["investing"]["net"])) < 0.01

    # Deposit: cash Dr 500 → financing inflow 500
    assert abs(float(data["financing"]["inflows"]) - 500) < 0.01
    # Expense: cash Cr 40 → operating outflow 40
    assert abs(float(data["operating"]["outflows"]) - 40) < 0.01
    # Transfer: cash Cr 100 + bank Dr 100 → transfers in 100 out 100
    assert abs(float(data["transfers"]["inflows"]) - 100) < 0.01
    assert abs(float(data["transfers"]["outflows"]) - 100) < 0.01
    assert abs(float(data["transfers"]["net"])) < 0.01

    # Back-compat totals = sum of sections
    section_in = sum(
        float(data[k]["inflows"]) for k in ("operating", "investing", "financing", "transfers")
    )
    section_out = sum(
        float(data[k]["outflows"]) for k in ("operating", "investing", "financing", "transfers")
    )
    assert abs(section_in - float(data["inflows"])) < 0.01
    assert abs(section_out - float(data["outflows"])) < 0.01
    assert all("activity" in line for line in data["lines"])
    assert any(line["activity"] == "operating" for line in data["lines"])
    assert any(line["activity"] == "financing" for line in data["lines"])
    assert any(line["activity"] == "transfers" for line in data["lines"])

    # Date filter excludes future-dated activity
    far = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
    empty = await ac.get(
        f"/api/v1/reports/cash-flow?from_date={far}&to_date={far}",
        headers=headers,
    )
    assert empty.status_code == 200
    edata = empty.json()["data"]
    assert float(edata["inflows"]) == 0
    assert float(edata["operating"]["outflows"]) == 0
