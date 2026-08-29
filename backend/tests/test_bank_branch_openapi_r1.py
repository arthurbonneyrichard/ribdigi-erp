"""AccountCreate / AccountUpdate.bank_branch OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import AccountCreate, AccountUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_branch_schema():
    create_omit = AccountCreate.model_validate(
        {"code": "1010", "name": "Bank", "liquid_kind": "bank", "bank_name": "Acme"}
    )
    assert create_omit.bank_branch is None
    create_ok = AccountCreate.model_validate(
        {
            "code": "1011",
            "name": "Savings",
            "liquid_kind": "bank",
            "bank_name": "Acme",
            "bank_branch": "  Accra Main  ",
        }
    )
    assert create_ok.bank_branch == "Accra Main"
    for bad in ("", " ", "!!!", "---", "http://branch.example", "ops@bank.example"):
        with pytest.raises(ValidationError):
            AccountCreate.model_validate(
                {
                    "code": "1012",
                    "name": "Bad",
                    "liquid_kind": "bank",
                    "bank_name": "Acme",
                    "bank_branch": bad,
                }
            )

    patch_omit = AccountUpdate.model_validate({})
    assert patch_omit.bank_branch is None
    patch_ok = AccountUpdate.model_validate({"bank_branch": "Kumasi"})
    assert patch_ok.bank_branch == "Kumasi"
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"bank_branch": ""})
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"bank_branch": "!!!"})


def test_bank_branch_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Bank branch"' in page
    assert "newBankBranch.trim() || null" in page
    assert 'aria-label="Create liquid account"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank branch OpenAPI" in agents
    assert "BankBranchValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Bank branch" in docs
    assert "BankBranchValue" in docs


@pytest.mark.asyncio
async def test_bank_branch_api_blank_invalid_422(client, seeded):
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
            "name": "Blank Branch Bank",
            "liquid_kind": "bank",
            "bank_name": "Acme Bank",
            "bank_branch": "",
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"G{uuid4().hex[:6].upper()}",
            "name": "Garbage Branch Bank",
            "liquid_kind": "bank",
            "bank_name": "Acme Bank",
            "bank_branch": "!!!",
        },
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"U{uuid4().hex[:6].upper()}",
            "name": "Url Branch Bank",
            "liquid_kind": "bank",
            "bank_name": "Acme Bank",
            "bank_branch": "http://branch.example",
        },
    )
    assert urlish.status_code == 422, urlish.text

    ok = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"O{uuid4().hex[:6].upper()}",
            "name": "Ok Branch Bank",
            "liquid_kind": "bank",
            "bank_name": "Acme Bank",
            "bank_branch": "Accra Main",
            "account_number": "1234567890",
        },
    )
    assert ok.status_code == 200, ok.text
    row = ok.json()["data"]
    assert row["bank_branch"] == "Accra Main"
    acct_id = row["id"]

    patch_bad = await ac.patch(
        f"/api/v1/accounting/accounts/{acct_id}",
        headers=admin,
        json={"bank_branch": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/accounting/accounts/{acct_id}",
        headers=admin,
        json={"bank_branch": "Kumasi Central"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["bank_branch"] == "Kumasi Central"

    omit = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"M{uuid4().hex[:6].upper()}",
            "name": "Omit Branch Bank",
            "liquid_kind": "bank",
            "bank_name": "Acme Bank",
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("bank_branch") in (None, "")
