"""CashTransferCreate.to_account_id ∈ UuidIdValue OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import CashTransferCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_cash_transfer_to_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = CashTransferCreate.model_validate({"amount": 10})
    assert omit.to_account_id is None
    ok = CashTransferCreate.model_validate(
        {"amount": 10, "to_account_id": f"  {_VALID}  "}
    )
    assert ok.to_account_id == _VALID.lower()
    nullish = CashTransferCreate.model_validate({"amount": 10, "to_account_id": None})
    assert nullish.to_account_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "acct_001", "a b"):
        with pytest.raises(ValidationError):
            CashTransferCreate.model_validate({"amount": 10, "to_account_id": bad})


def test_cash_transfer_to_account_id_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cash transfer to account"' in page
    assert "body.to_account_id = xferTo.trim() || null" in page
    assert 'aria-label="Post cash transfer"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Cash transfer to_account_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /accounting/transfers" in docs
    assert "Cash transfer to account" in docs


@pytest.mark.asyncio
async def test_cash_transfer_to_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )

    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=admin)
    assert liq.status_code == 200, liq.text
    by_code = {a["code"]: a for a in liq.json()["data"]}
    cash = by_code["1000"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            "/api/v1/accounting/transfers",
            headers=admin,
            json={"kind": "deposit", "to_account_id": bad, "amount": 5},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/accounting/transfers",
        headers=admin,
        json={
            "kind": "deposit",
            "to_account_id": f"  {str(cash['id']).upper()}  ",
            "amount": 6,
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["to_account_id"] == str(cash["id"]).lower()

    missing = await ac.post(
        "/api/v1/accounting/transfers",
        headers=admin,
        json={"kind": "deposit", "to_account_id": str(uuid4()), "amount": 5},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
