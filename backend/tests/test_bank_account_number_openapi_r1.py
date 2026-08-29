"""AccountCreate / AccountUpdate.account_number OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import AccountCreate, AccountUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_account_number_schema():
    create_omit = AccountCreate.model_validate(
        {"code": "1010", "name": "Bank", "liquid_kind": "bank"}
    )
    assert create_omit.account_number is None
    create_ok = AccountCreate.model_validate(
        {
            "code": "1011",
            "name": "Savings",
            "liquid_kind": "bank",
            "account_number": "  12 345-6789  ",
        }
    )
    assert create_ok.account_number == "12 345-6789"
    for bad in ("", " ", "not!!!", "http://bank.example/acc", "acc@bank", "---"):
        with pytest.raises(ValidationError):
            AccountCreate.model_validate(
                {
                    "code": "1012",
                    "name": "Bad",
                    "liquid_kind": "bank",
                    "account_number": bad,
                }
            )

    patch_omit = AccountUpdate.model_validate({})
    assert patch_omit.account_number is None
    patch_ok = AccountUpdate.model_validate({"account_number": "ABC123"})
    assert patch_ok.account_number == "ABC123"
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"account_number": ""})
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"account_number": "not!!!"})


def test_bank_account_number_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Bank account number"' in page
    assert "newAcctNumber.trim() || null" in page
    assert 'aria-label="Create liquid account"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank account number OpenAPI" in agents
    assert "BankAccountNumberValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Bank account number" in docs
    assert "BankAccountNumberValue" in docs


@pytest.mark.asyncio
async def test_bank_account_number_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"B{uuid4().hex[:6].upper()}",
            "name": "Blank Acct",
            "liquid_kind": "bank",
            "account_number": "",
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"G{uuid4().hex[:6].upper()}",
            "name": "Garbage Acct",
            "liquid_kind": "bank",
            "account_number": "not!!!",
        },
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"U{uuid4().hex[:6].upper()}",
            "name": "Url Acct",
            "liquid_kind": "bank",
            "account_number": "http://bank.example/1",
        },
    )
    assert urlish.status_code == 422, urlish.text

    ok_code = f"O{uuid4().hex[:6].upper()}"
    ok = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": ok_code,
            "name": "Ok Bank",
            "liquid_kind": "bank",
            "bank_name": "Acme Bank",
            "account_number": "1234567890",
            "bank_branch": "Main",
        },
    )
    assert ok.status_code == 200, ok.text
    row = ok.json()["data"]
    assert row["account_number"] == "1234567890"
    acct_id = row["id"]

    patch_bad = await ac.patch(
        f"/api/v1/accounting/accounts/{acct_id}",
        headers=admin,
        json={"account_number": "bad!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/accounting/accounts/{acct_id}",
        headers=admin,
        json={"account_number": "9988776655"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["account_number"] == "9988776655"

    omit = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"M{uuid4().hex[:6].upper()}",
            "name": "Omit Number",
            "liquid_kind": "bank",
            "bank_name": "Acme Bank",
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("account_number") in (None, "")
