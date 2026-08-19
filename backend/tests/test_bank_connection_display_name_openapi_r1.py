"""BankConnectionCreate / Update.display_name OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BankConnectionCreate, BankConnectionUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_bank_connection_display_name_schema():
    omit = BankConnectionCreate.model_validate({"account_id": "a1"})
    assert omit.display_name is None
    ok = BankConnectionCreate.model_validate(
        {"account_id": "a1", "display_name": "  Operating feed  "}
    )
    assert ok.display_name == "Operating feed"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            BankConnectionCreate.model_validate({"account_id": "a1", "display_name": bad})

    patch_omit = BankConnectionUpdate.model_validate({})
    assert patch_omit.display_name is None
    patch_ok = BankConnectionUpdate.model_validate({"display_name": " Renamed Feed "})
    assert patch_ok.display_name == "Renamed Feed"
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"display_name": "!!!"})
    with pytest.raises(ValidationError):
        BankConnectionUpdate.model_validate({"display_name": "  "})


def test_bank_connection_display_name_ui_and_docs():
    accounting = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Bank connection display name"' in accounting
    assert "connName.trim()" in accounting
    assert 'aria-label="Connect bank account"' in accounting
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank connection display_name OpenAPI" in agents
    assert "BankConnectionDisplayNameValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "BankConnectionDisplayNameValue" in docs
    assert "Bank connection display name" in docs


@pytest.mark.asyncio
async def test_bank_connection_display_name_api_blank_invalid_422(client):
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
                "display_name": bad,
            },
        )
        assert r.status_code == 422, (bad, r.text)

    # Fresh liquid account so omit-display_name create is not blocked by 1:1 GL uniqueness
    cash = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": f"1{suffix[:3]}",
            "name": f"Tip139 Cash {suffix}",
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
            "external_account_id": f"omit-{suffix}",
        },
    )
    assert omit.status_code == 200, omit.text
    # Service may default a label when display_name is omitted; blank/invalid still 422 above.

    ok = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": bank["id"],
            "provider": "mock",
            "display_name": f"  Tip139 Feed {suffix}  ",
            "external_account_id": f"tip139-{suffix}",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["display_name"] == f"Tip139 Feed {suffix}"
    cid = ok.json()["data"]["id"]

    patch_omit = await ac.patch(
        f"/api/v1/accounting/bank-connections/{cid}",
        headers=headers,
        json={"auto_sync": True},
    )
    assert patch_omit.status_code == 200, patch_omit.text
    assert patch_omit.json()["data"]["display_name"] == f"Tip139 Feed {suffix}"

    for bad in ("", "!!!", "http://evil"):
        bad_patch = await ac.patch(
            f"/api/v1/accounting/bank-connections/{cid}",
            headers=headers,
            json={"display_name": bad},
        )
        assert bad_patch.status_code == 422, (bad, bad_patch.text)

    renamed = await ac.patch(
        f"/api/v1/accounting/bank-connections/{cid}",
        headers=headers,
        json={"display_name": f"  Tip139 Renamed {suffix}  "},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["display_name"] == f"Tip139 Renamed {suffix}"
