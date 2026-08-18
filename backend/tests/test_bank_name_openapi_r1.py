"""AccountCreate / AccountUpdate.bank_name OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import AccountCreate, AccountUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_name_schema():
    create_omit = AccountCreate.model_validate(
        {"code": "1010", "name": "Bank", "liquid_kind": "bank"}
    )
    assert create_omit.bank_name is None
    create_ok = AccountCreate.model_validate(
        {
            "code": "1011",
            "name": "Savings",
            "liquid_kind": "bank",
            "bank_name": "  Acme Bank & Co.  ",
        }
    )
    assert create_ok.bank_name == "Acme Bank & Co."
    for bad in ("", " ", "!!!", "---", "http://bank.example", "ops@bank.example"):
        with pytest.raises(ValidationError):
            AccountCreate.model_validate(
                {
                    "code": "1012",
                    "name": "Bad",
                    "liquid_kind": "bank",
                    "bank_name": bad,
                }
            )

    patch_omit = AccountUpdate.model_validate({})
    assert patch_omit.bank_name is None
    patch_ok = AccountUpdate.model_validate({"bank_name": "GCB"})
    assert patch_ok.bank_name == "GCB"
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"bank_name": ""})
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"bank_name": "!!!"})


def test_bank_name_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Bank name"' in page
    assert "trimmedBank" in page or "newBankName.trim()" in page
    assert 'aria-label="Create liquid account"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank name OpenAPI" in agents
    assert "BankNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Bank name" in docs
    assert "BankNameValue" in docs


@pytest.mark.asyncio
async def test_bank_name_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    blank = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"N{uuid4().hex[:6].upper()}",
            "name": "Blank Name Bank",
            "liquid_kind": "bank",
            "bank_name": "",
        },
    )
    assert blank.status_code == 422, blank.text

    garbage = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"X{uuid4().hex[:6].upper()}",
            "name": "Garbage Name Bank",
            "liquid_kind": "bank",
            "bank_name": "!!!",
        },
    )
    assert garbage.status_code == 422, garbage.text

    urlish = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"H{uuid4().hex[:6].upper()}",
            "name": "Url Name Bank",
            "liquid_kind": "bank",
            "bank_name": "http://bank.example",
        },
    )
    assert urlish.status_code == 422, urlish.text

    # omit bank_name with liquid_kind=bank → service required-name 400
    missing = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"M{uuid4().hex[:6].upper()}",
            "name": "Missing Name Bank",
            "liquid_kind": "bank",
        },
    )
    assert missing.status_code == 400, missing.text

    ok = await ac.post(
        "/api/v1/accounting/accounts",
        headers=admin,
        json={
            "code": f"O{uuid4().hex[:6].upper()}",
            "name": "Ok Name Bank",
            "liquid_kind": "bank",
            "bank_name": "Acme Bank",
            "account_number": "1234567890",
        },
    )
    assert ok.status_code == 200, ok.text
    row = ok.json()["data"]
    assert row["bank_name"] == "Acme Bank"
    acct_id = row["id"]

    patch_bad = await ac.patch(
        f"/api/v1/accounting/accounts/{acct_id}",
        headers=admin,
        json={"bank_name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/accounting/accounts/{acct_id}",
        headers=admin,
        json={"bank_name": "GCB Limited"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["bank_name"] == "GCB Limited"
