"""Bank CSV / OFX feed import tests."""

from datetime import datetime

import pytest

from app import accounting as accounting_svc
from app import bank_feed
from app import bank_recon as recon


def test_parse_csv_amount_and_debit_credit():
    csv_text = (
        "Date,Description,Amount,Reference\n"
        "2026-08-01,Salary,1500.00,PAY-1\n"
        "2026-08-02,Rent,-800.50,RENT\n"
    )
    parsed = bank_feed.parse_csv_feed(csv_text)
    assert parsed["format"] == "csv"
    assert len(parsed["lines"]) == 2
    assert parsed["lines"][0]["amount"] == 1500.0
    assert parsed["lines"][0]["external_ref"] == "PAY-1"
    assert parsed["lines"][1]["amount"] == -800.5


def test_parse_csv_split_debit_credit_columns():
    csv_text = (
        "Txn Date,Narration,Debit,Credit\n"
        "08/08/2026,Supplier,100.00,\n"
        "08/08/2026,Customer deposit,,250.00\n"
    )
    parsed = bank_feed.parse_csv_feed(csv_text)
    assert len(parsed["lines"]) == 2
    amounts = sorted(ln["amount"] for ln in parsed["lines"])
    assert amounts == [-100.0, 250.0]


def test_parse_ofx_stmttrn():
    ofx = """OFXHEADER:100
DATA:OFXSGML
<OFX>
<BANKMSGSRSV1>
<STMTTRNRS>
<STMTRS>
<BANKTRANLIST>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260805
<TRNAMT>500.00
<FITID>FIT-9
<NAME>Wire in
<MEMO>Customer payment
</STMTTRN>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260806
<TRNAMT>-120.25
<FITID>FIT-10
<NAME>Utilities
</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL>
<BALAMT>1379.75
<DTASOF>20260808
</LEDGERBAL>
</STMTRS>
</STMTTRNRS>
</BANKMSGSRSV1>
</OFX>
"""
    parsed = bank_feed.parse_ofx_feed(ofx)
    assert parsed["format"] == "ofx"
    assert len(parsed["lines"]) == 2
    assert parsed["lines"][0]["amount"] == 500.0
    assert parsed["lines"][0]["external_ref"] == "FIT-9"
    assert parsed["closing_balance"] == 1379.75
    assert parsed["opening_balance"] == round(1379.75 - (500 - 120.25), 2)


def test_detect_format():
    assert bank_feed.detect_format("stmt.ofx", "x") == "ofx"
    assert bank_feed.detect_format("a.csv", "Date,Amount\n") == "csv"


@pytest.mark.asyncio
async def test_import_statement_from_csv_feed(db_session, seeded):
    tenant_id = seeded["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    bank = await accounting_svc.get_account_by_code(db_session, tenant_id, "1010")

    csv_text = (
        "date,amount,description,ref\n"
        "2026-08-01,200,Deposit,D1\n"
        "2026-08-02,-50,Fee,F1\n"
    )
    stmt, meta = await recon.import_statement_from_feed(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        account_id=bank.id,
        content=csv_text,
        filename="bank.csv",
        opening_balance=1000,
    )
    await db_session.commit()
    assert meta["format"] == "csv"
    assert meta["line_count"] == 2
    assert meta["closing_balance"] == 1150.0  # 1000 + 200 - 50
    lines = await recon.list_statement_lines(db_session, tenant_id, stmt.id)
    assert len(lines) == 2
    assert all(ln.status == "unmatched" for ln in lines)
    assert float(stmt.opening_balance) == 1000
    assert "Imported CSV" in (stmt.notes or "")
