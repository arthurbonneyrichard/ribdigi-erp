"""AccountCreate.code OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import AccountCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_account_code_schema():
    ok = AccountCreate.model_validate(
        {"code": " 1001 ", "name": "Petty Cash", "liquid_kind": "cash"}
    )
    assert ok.code == "1001"
    assert AccountCreate.model_validate(
        {"code": "CASH-1", "name": "Till", "liquid_kind": "cash"}
    ).code == "CASH-1"
    for bad in ("", " ", "!!!", "a b", "http://x", "-100", "_X"):
        with pytest.raises(ValidationError):
            AccountCreate.model_validate(
                {"code": bad, "name": "Petty Cash", "liquid_kind": "cash"}
            )


def test_account_code_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Account code"' in page
    assert "newAcctCode.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Account code OpenAPI" in agents
    assert "AccountCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AccountCodeValue" in docs
    assert "Account code" in docs


@pytest.mark.asyncio
async def test_account_code_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    name = f"Tip123 {uuid4().hex[:6]}"

    for bad in ("", "!!!", "a b"):
        resp = await ac.post(
            "/api/v1/accounting/accounts",
            headers=headers,
            json={"code": bad, "name": name, "liquid_kind": "cash"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    acct_code = f"1{uuid4().hex[:3]}"
    ok = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": f" {acct_code} ", "name": name, "liquid_kind": "cash"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["code"] == acct_code
    assert ok.json()["data"]["name"] == name
