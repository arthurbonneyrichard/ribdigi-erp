"""BankConnectionCreate / Update.external_account_id OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BankConnectionCreate, BankConnectionUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_external_account_id_schema():
    omit = BankConnectionCreate.model_validate({"account_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"})
    assert omit.external_account_id is None
    ok = BankConnectionCreate.model_validate(
        {"account_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "external_account_id": "  demo-acct-1  "}
    )
    assert ok.external_account_id == "demo-acct-1"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BankConnectionCreate.model_validate(
                {"account_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "external_account_id": bad}
            )

    patch_omit = BankConnectionUpdate.model_validate({})
    assert patch_omit.external_account_id is None
    patch_ok = BankConnectionUpdate.model_validate(
        {"external_account_id": " Renamed-Acct-9 "}
    )
    assert patch_ok.external_account_id == "Renamed-Acct-9"
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"external_account_id": "!!!"})
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"external_account_id": "  "})


def test_bank_external_account_id_ui_and_docs():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Bank external account id"' in accounting
    assert "connExtId.trim()" in accounting
    assert 'aria-label="Connect bank account"' in accounting
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank external_account_id OpenAPI" in agents
    assert "BankExternalAccountIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankExternalAccountIdValue" in docs
    assert "Bank external account id" in docs


@pytest.mark.asyncio
async def test_bank_external_account_id_api_blank_invalid_422(client):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    accounts = (await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)).json()[
        "data"
    ]
    bank = next((a for a in accounts if a.get("code") == "1010"), accounts[0])
    suffix = uuid4().hex[:8]

    for bad in ("", "!!!", "http://evil"):
        r = await ac.post(
            "/api/v1/accounting/bank-connections",
            headers=headers,
            json={
                "account_id": bank["id"],
                "provider": "mock",
                "external_account_id": bad,
            },
        )
        assert r.status_code == 422, (bad, r.text)

    # Fresh liquid account so omit-external_account_id create is not blocked by 1:1 GL uniqueness
    cash = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": f"2{suffix[:3]}",
            "name": f"Tip233 Cash {suffix}",
            "liquid_kind": "cash",
        },
    )
    assert cash.status_code == 200, cash.text
    omit = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": cash.json()["data"]["id"],
            "provider": "mock",
            "display_name": f"Tip233 Omit Ext {suffix}",
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("external_account_id") in (None, "")

    ok = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": bank["id"],
            "provider": "mock",
            "display_name": f"Tip233 Feed {suffix}",
            "external_account_id": f"  tip233-{suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["external_account_id"] == f"tip233-{suffix}"
    cid = ok.json()["data"]["id"]

    patch_omit = await ac.patch(
        f"/api/v1/accounting/bank-connections/{cid}",
        headers=headers,
        json={"auto_sync": True},
    )
    assert patch_omit.status_code == 200, patch_omit.text
    assert patch_omit.json()["data"]["external_account_id"] == f"tip233-{suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/accounting/bank-connections/{cid}",
            headers=headers,
            json={"external_account_id": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/accounting/bank-connections/{cid}",
        headers=headers,
        json={"external_account_id": f"  tip233-renamed-{suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["external_account_id"] == f"tip233-renamed-{suffix}"
