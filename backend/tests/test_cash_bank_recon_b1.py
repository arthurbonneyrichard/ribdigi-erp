"""Stage 22 B1: Cash/bank, recon, cheques fidelity (BR-10.3)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_cash_bank_recon_and_cheque_lifecycle(client, db_session):
    """BR-10.3: liquid cash/bank, deposits/withdrawals/transfers, recon, cheques."""
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id

    # --- Cash + bank accounts (petty cash / bank with name, number, branch) ---
    petty = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={"kind": "cash", "code": "1006", "name": "B1 Petty Cash"},
    )
    assert petty.status_code == 200, petty.text
    assert petty.json()["data"]["is_cash_account"] is True

    bank = await ac.post(
        "/api/v1/accounting/liquid-accounts",
        headers=headers,
        json={
            "kind": "bank",
            "code": "1016",
            "name": "B1 Operating Bank",
            "bank_name": "First National",
            "account_number": "BNK-B1-001",
            "bank_branch": "Central",
        },
    )
    assert bank.status_code == 200, bank.text
    bdata = bank.json()["data"]
    assert bdata["is_bank_account"] is True
    assert bdata["bank_name"] == "First National"
    assert bdata["account_number"] == "BNK-B1-001"
    assert bdata["bank_branch"] == "Central"
    bank_id = bdata["id"]

    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert liq.status_code == 200
    by_code = {r["code"]: r for r in liq.json()["data"]}
    assert "1000" in by_code and "1010" in by_code  # system main cash/bank
    assert "1006" in by_code and "1016" in by_code
    cash_id = by_code["1000"]["id"]
    main_bank_id = by_code["1010"]["id"]

    # Seed main cash so moves have funds
    seed_je = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "B1 seed cash",
            "lines": [
                {"account_code": "1000", "debit": 400, "credit": 0},
                {"account_code": "4000", "debit": 0, "credit": 400},
            ],
        },
    )
    assert seed_je.status_code == 200, seed_je.text

    # --- Deposits, withdrawals, transfers ---
    deposit = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": cash_id,
            "to_account_id": main_bank_id,
            "amount": 150,
            "kind": "deposit",
            "reference": "B1-DEP",
        },
    )
    assert deposit.status_code == 200, deposit.text
    assert deposit.json()["data"]["source_type"] == "liquid_deposit"

    withdraw = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": main_bank_id,
            "to_account_id": cash_id,
            "amount": 40,
            "kind": "withdrawal",
        },
    )
    assert withdraw.status_code == 200, withdraw.text
    assert withdraw.json()["data"]["source_type"] == "liquid_withdrawal"

    transfer = await ac.post(
        "/api/v1/accounting/liquid-transfers",
        headers=headers,
        json={
            "from_account_id": main_bank_id,
            "to_account_id": bank_id,
            "amount": 60,
            "kind": "transfer",
        },
    )
    assert transfer.status_code == 200, transfer.text
    assert transfer.json()["data"]["source_type"] == "liquid_transfer"

    liq2 = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    by_code = {r["code"]: r for r in liq2.json()["data"]}
    assert float(by_code["1000"]["balance"]) == pytest.approx(290)  # 400-150+40
    assert float(by_code["1010"]["balance"]) == pytest.approx(50)  # 150-40-60
    assert float(by_code["1016"]["balance"]) == pytest.approx(60)

    # --- Bank reconciliation (system book vs statement) ---
    stmt = await ac.post(
        "/api/v1/accounting/bank-statements",
        headers=headers,
        json={
            "account_id": bank_id,
            "statement_date": "2026-08-10",
            "opening_balance": 0,
            "closing_balance": 60,
            "notes": "B1 recon",
            "lines": [
                {
                    "txn_date": "2026-08-10",
                    "amount": 60,
                    "description": "Transfer in B1",
                    "external_ref": "B1-XFER",
                }
            ],
        },
    )
    assert stmt.status_code == 200, stmt.text
    sdata = stmt.json()["data"]
    sid = sdata["id"]
    assert sdata["status"] in {"open", "draft", "in_progress", "pending"} or sdata[
        "unmatched_count"
    ] == 1
    line_id = sdata["lines"][0]["id"]

    detail = await ac.get(f"/api/v1/accounting/bank-statements/{sid}", headers=headers)
    assert detail.status_code == 200, detail.text
    book = detail.json()["data"].get("unmatched_book_lines") or []
    assert book, "expected unmatched book lines for liquid transfer"
    jl_id = next(
        (
            b["journal_line_id"]
            for b in book
            if abs(float(b.get("signed_amount") or 0) - 60) < 0.01
        ),
        book[0]["journal_line_id"],
    )

    matched = await ac.post(
        f"/api/v1/accounting/bank-statements/{sid}/lines/{line_id}/match",
        headers=headers,
        json={"journal_line_id": jl_id},
    )
    assert matched.status_code == 200, matched.text
    assert matched.json()["data"]["status"] == "matched"

    done = await ac.post(
        f"/api/v1/accounting/bank-statements/{sid}/complete", headers=headers
    )
    assert done.status_code == 200, done.text
    assert done.json()["data"]["status"] == "reconciled"
    assert done.json()["data"].get("reconciled_at")

    # --- Cheques: received (deposit + bounce) and issued (clear) ---
    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "B1 Cheque Customer", "credit_limit": 0},
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 2,
                    "unit_price": 50,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]
    inv_total = float(inv.json()["data"]["total_amount"])

    posted = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post", headers=headers
    )
    assert posted.status_code == 200, posted.text

    pay = await ac.post(
        "/api/v1/sales/payments",
        headers=headers,
        json={
            "customer_id": customer_id,
            "amount": inv_total,
            "sales_invoice_id": invoice_id,
            "payment_method": "cheque",
            "reference": "B1-CHQ-RCV",
            "cheque_number": "B1-CHQ-RCV",
            "bank_name": "Customer Bank",
        },
    )
    assert pay.status_code == 200, pay.text

    cheques = await ac.get(
        "/api/v1/accounting/cheques", headers=headers, params={"direction": "received"}
    )
    assert cheques.status_code == 200, cheques.text
    rcv = next(c for c in cheques.json()["data"] if c["cheque_number"] == "B1-CHQ-RCV")
    assert rcv["status"] == "pending"
    rcv_id = rcv["id"]

    deposited = await ac.post(
        f"/api/v1/accounting/cheques/{rcv_id}/deposit", headers=headers
    )
    assert deposited.status_code == 200, deposited.text
    assert deposited.json()["data"]["status"] == "deposited"

    bounced = await ac.post(
        f"/api/v1/accounting/cheques/{rcv_id}/bounce",
        headers=headers,
        params={"reason": "NSF"},
    )
    assert bounced.status_code == 200, bounced.text
    assert bounced.json()["data"]["status"] == "bounced"

    # Issued cheque (supplier payment) → clear
    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "B1 Cheque Vendor"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    party = await db_session.get(m.Party, supplier_id)
    party.balance = 80
    await db_session.commit()

    spay = await ac.post(
        f"/api/v1/suppliers/{supplier_id}/payments",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "amount": 80,
            "payment_method": "cheque",
            "reference": "B1-CHQ-ISS",
            "cheque_number": "B1-CHQ-ISS",
            "bank_name": "Ops Bank",
        },
    )
    assert spay.status_code == 200, spay.text

    issued = await ac.get(
        "/api/v1/accounting/cheques", headers=headers, params={"direction": "issued"}
    )
    assert issued.status_code == 200
    iss = next(c for c in issued.json()["data"] if c["cheque_number"] == "B1-CHQ-ISS")
    assert iss["status"] == "pending"

    cleared = await ac.post(
        f"/api/v1/accounting/cheques/{iss['id']}/clear", headers=headers
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["data"]["status"] == "cleared"


def test_br_10_3_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s103 = br.split("#### BR-10.3 Cash & Bank Accounts")[1].split("#### BR-10.4")[0]
    assert "[x] Create cash accounts" in s103
    assert "[x] Create bank accounts" in s103
    assert "[x] Record deposits, withdrawals, transfers" in s103
    assert "[x] Bank reconciliation" in s103
    assert "[x] Cheque management" in s103
    assert "Stage 22 B1" in s103
    assert "test_cash_bank_recon_b1.py" in s103
    assert "Open Banking" in s103 or "open banking" in s103.lower()

    plan = (ROOT / "docs" / "STAGE_22_PLAN.md").read_text(encoding="utf-8")
    b1_line = [ln for ln in plan.splitlines() if "| **B1**" in ln][0]
    assert "COMPLETE" in b1_line
    assert "test_cash_bank_recon_b1.py" in plan
