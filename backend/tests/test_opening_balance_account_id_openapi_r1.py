"""OpeningBalanceLine.account_id ∈ UuidIdValue OpenAPI honesty (BR-10.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import OpeningBalanceLine, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_opening_balance_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = OpeningBalanceLine.model_validate({"account_code": "1000", "amount": 10})
    assert omit.account_id is None
    ok = OpeningBalanceLine.model_validate({"account_id": f"  {_VALID}  ", "amount": 10})
    assert ok.account_id == _VALID.lower()
    nullish = OpeningBalanceLine.model_validate(
        {"account_id": None, "account_code": "1000", "amount": 10}
    )
    assert nullish.account_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "acct_001", "a b"):
        with pytest.raises(ValidationError):
            OpeningBalanceLine.model_validate({"account_id": bad, "amount": 10})


def test_opening_balance_account_id_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening balance account"' in page
    assert "account_id: l.id.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Opening balance account_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Opening balance account" in docs
    assert "POST /accounting/opening-balances" in docs


@pytest.mark.asyncio
async def test_opening_balance_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    totp = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=totp
    )

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            "/api/v1/accounting/opening-balances",
            headers=headers,
            json={"lines": [{"account_id": bad, "amount": 25}]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    # Valid UUID shape that is not a tenant account → not 422 (existence is service).
    missing = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=headers,
        json={"lines": [{"account_id": f"  {str(uuid4()).upper()}  ", "amount": 25}]},
    )
    assert missing.status_code in (400, 404, 409), missing.text
    assert missing.status_code != 422

    # account_code path still works when openings not yet posted.
    status = await ac.get("/api/v1/accounting/opening-balances", headers=headers)
    assert status.status_code == 200, status.text
    already = bool((status.json().get("data") or {}).get("posted"))
    if already:
        return

    ok_code = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=headers,
        json={"lines": [{"account_code": "1000", "amount": 1}]},
    )
    assert ok_code.status_code == 200, ok_code.text
