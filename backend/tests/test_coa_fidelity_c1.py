"""Stage 22 C1: Chart of Accounts fidelity (BR-10.1)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.accounting import ACCOUNT_TYPES, DEFAULT_ACCOUNTS
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_coa_seed_types_hierarchy_crud_opening_balance(client):
    """BR-10.1: seeded COA, types, hierarchy, non-system CRUD, opening balances."""
    ac, seed = client
    headers = await _super(ac, seed)

    listed = await ac.get("/api/v1/accounting/accounts", headers=headers)
    assert listed.status_code == 200, listed.text
    rows = listed.json()["data"]
    by_code = {r["code"]: r for r in rows}

    # Predefined system COA (industry-agnostic MVP seed)
    for code, name, account_type, _is_cash, _is_bank in DEFAULT_ACCOUNTS:
        assert code in by_code, code
        assert by_code[code]["name"] == name
        assert by_code[code]["account_type"] == account_type
        assert by_code[code]["is_system"] is True

    present_types = {r["account_type"] for r in rows}
    assert ACCOUNT_TYPES <= present_types

    # Hierarchy: code bands + parent/child tree
    assert by_code["1000"]["account_type"] == "asset"
    assert by_code["1100"]["account_type"] == "asset"
    assert by_code["2000"]["account_type"] == "liability"
    assert by_code["3000"]["account_type"] == "equity"
    assert by_code["4000"]["account_type"] == "income"
    assert by_code["6000"]["account_type"] == "expense"

    cash_id = by_code["1000"]["id"]
    child = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "1045",
            "name": "C1 Petty Float",
            "account_type": "asset",
            "parent_id": cash_id,
        },
    )
    assert child.status_code == 200, child.text
    cdata = child.json()["data"]
    assert cdata["parent_id"] == cash_id
    assert cdata["is_system"] is False
    assert cdata["account_type"] == "asset"
    cid = cdata["id"]

    tree = await ac.get("/api/v1/accounting/accounts?tree=true", headers=headers)
    assert tree.status_code == 200, tree.text
    cash_node = next(n for n in tree.json()["data"] if n["code"] == "1000")
    assert any(c["code"] == "1045" for c in cash_node.get("children") or [])

    # Non-system edit
    patched = await ac.patch(
        f"/api/v1/accounting/accounts/{cid}",
        headers=headers,
        json={"name": "C1 Petty Float Desk"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["name"] == "C1 Petty Float Desk"

    system_blocked = await ac.patch(
        f"/api/v1/accounting/accounts/{cash_id}",
        headers=headers,
        json={"name": "Should Fail"},
    )
    assert system_blocked.status_code == 409

    # Opening balance on non-system child
    ob = await ac.post(
        f"/api/v1/accounting/accounts/{cid}/opening-balance",
        headers=headers,
        json={"amount": 125.5, "description": "C1 go-live float"},
    )
    assert ob.status_code == 200, ob.text
    entry = ob.json()["data"]
    assert entry["status"] == "posted"
    assert entry["source_type"] == "opening_balance"
    assert abs(float(entry["total_debit"]) - float(entry["total_credit"])) < 0.01

    got = await ac.get(f"/api/v1/accounting/accounts/{cid}", headers=headers)
    assert got.status_code == 200
    assert float(got.json()["data"]["balance"]) == pytest.approx(125.5)


def test_br_10_1_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s101 = br.split("#### BR-10.1 Chart of Accounts (COA)")[1].split("#### BR-10.2")[0]
    assert "[x] Predefined COA" in s101
    assert "[x] Account types: Asset, Liability, Equity, Income, Expense" in s101
    assert "[x] Account code hierarchy" in s101
    assert "[x] Add/edit accounts (non-system accounts)" in s101
    assert "[x] Opening balance entry" in s101
    assert "Stage 22 C1" in s101
    assert "test_coa_fidelity_c1.py" in s101
    assert "industry-agnostic" in s101.lower() or "Industry-agnostic" in s101

    plan = (ROOT / "docs" / "STAGE_22_PLAN.md").read_text(encoding="utf-8")
    c1_line = [ln for ln in plan.splitlines() if "| **C1**" in ln][0]
    assert "COMPLETE" in c1_line
    assert "test_coa_fidelity_c1.py" in plan
