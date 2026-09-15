"""AccountCreate / AccountUpdate.name OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import AccountCreate, AccountUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_account_name_schema():
    ok = AccountCreate.model_validate(
        {"code": "1099", "name": "  Petty Cash  ", "liquid_kind": "cash"}
    )
    assert ok.name == "Petty Cash"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            AccountCreate.model_validate(
                {"code": "1099", "name": bad, "liquid_kind": "cash"}
            )

    patch_omit = AccountUpdate.model_validate({})
    assert patch_omit.name is None
    patch_ok = AccountUpdate.model_validate({"name": " Main Till "})
    assert patch_ok.name == "Main Till"
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"name": "!!!"})
    with pytest.raises(ValidationError):
        AccountUpdate.model_validate({"name": "  "})


def test_account_name_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Account name"' in page
    assert 'aria-label="Edit account name"' in page
    assert "newAcctName.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Account name OpenAPI" in agents
    assert "AccountNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "AccountNameValue" in docs
    assert "Account name" in docs


@pytest.mark.asyncio
async def test_account_name_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    acct_code = f"1{uuid4().hex[:3]}"

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/accounting/accounts",
            headers=headers,
            json={"code": acct_code, "name": bad, "liquid_kind": "cash"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": acct_code,
            "name": "  Tip122 Petty Cash  ",
            "liquid_kind": "cash",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert data["name"] == "Tip122 Petty Cash"
    account_id = data["id"]

    patch_bad = await ac.patch(
        f"/api/v1/accounting/accounts/{account_id}",
        headers=headers,
        json={"name": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/accounting/accounts/{account_id}",
        headers=headers,
        json={"name": "Tip122 Till Cash"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["name"] == "Tip122 Till Cash"
