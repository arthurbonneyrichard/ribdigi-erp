"""BankConnectionCreate / Update.access_token ∈ BankAccessTokenValue OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BankAccessTokenValue, BankConnectionCreate, BankConnectionUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_token = TypeAdapter(BankAccessTokenValue)


def test_bank_access_token_value_schema():
    assert _token.validate_python("  Tip249Token!  ") == "Tip249Token!"
    assert _token.validate_python("a" * 128) == "a" * 128
    for bad in ("", " ", "!!!", "http://evil", "a@b", "tok en", "a" * 129):
        with pytest.raises(ValidationError):
            _token.validate_python(bad)

    omit = BankConnectionCreate.model_validate({"account_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"})
    assert omit.access_token is None
    ok = BankConnectionCreate.model_validate(
        {"account_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "access_token": "  secretToken1  "}
    )
    assert ok.access_token == "secretToken1"
    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        with pytest.raises(ValidationError):
            BankConnectionCreate.model_validate({"account_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "access_token": bad})

    patch_omit = BankConnectionUpdate.model_validate({})
    assert patch_omit.access_token is None
    patch_ok = BankConnectionUpdate.model_validate({"access_token": "  RotatedToken1  "})
    assert patch_ok.access_token == "RotatedToken1"
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"access_token": ""})
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"access_token": "!!!"})
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"access_token": "http://evil"})


def test_bank_access_token_ui_and_docs():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Bank connection access token"' in accounting
    assert "connAccessToken" in accounting
    assert 'aria-label="Connect bank account"' in accounting
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank connection access_token OpenAPI" in agents
    assert "BankAccessTokenValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankAccessTokenValue" in docs
    assert "Bank connection access token" in docs


@pytest.mark.asyncio
async def test_bank_access_token_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    accounts = (await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)).json()[
        "data"
    ]
    assert accounts, "expected seeded liquid accounts"
    bank = next((a for a in accounts if a.get("code") == "1010"), accounts[0])
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil", "a@b", "tok en"):
        resp = await ac.post(
            "/api/v1/accounting/bank-connections",
            headers=headers,
            json={
                "account_id": bank["id"],
                "provider": "mock",
                "display_name": f"tip249-bad-{suffix}-{abs(hash(bad)) % 10000}",
                "access_token": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    # Fresh liquid account so create is not blocked by 1:1 GL uniqueness
    cash = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": f"1{suffix[:3]}",
            "name": f"Tip249 Cash {suffix}",
            "liquid_kind": "cash",
        },
    )
    assert cash.status_code == 200, cash.text
    cash_id = cash.json()["data"]["id"]

    omit = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": cash_id,
            "provider": "mock",
            "display_name": f"Tip249 Omit Token {suffix}",
            "external_account_id": f"omit-tok-{suffix}",
        },
    )
    assert omit.status_code == 200, omit.text
    omit_body = omit.json()["data"]
    assert omit_body.get("has_credentials") is False or omit_body.get(
        "credentials_configured"
    ) in (False, None)
    assert "access_token" not in omit_body

    ok = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": bank["id"],
            "provider": "mock",
            "display_name": f"  Tip249 Feed {suffix}  ",
            "external_account_id": f"tip249-{suffix}",
            "access_token": "  Tip249Token!  ",
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["display_name"] == f"Tip249 Feed {suffix}"
    assert body.get("has_credentials") is True or body.get("credentials_configured") is True
    assert "access_token" not in body
    cid = body["id"]

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/accounting/bank-connections/{cid}",
            headers=headers,
            json={"access_token": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    rotated = await ac.patch(
        f"/api/v1/accounting/bank-connections/{cid}",
        headers=headers,
        json={"access_token": "  Tip249Rotated!  "},
    )
    assert rotated.status_code == 200, rotated.text
    assert "access_token" not in rotated.json()["data"]
    assert rotated.json()["data"].get("has_credentials") is True or rotated.json()[
        "data"
    ].get("credentials_configured") is True
