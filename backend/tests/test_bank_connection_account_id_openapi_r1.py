"""BankConnectionCreate.account_id ∈ UuidIdValue OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import BankConnectionCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_bank_connection_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = BankConnectionCreate.model_validate({"account_id": f"  {_VALID}  "})
    assert ok.account_id == _VALID.lower()
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "acct_001", "a b"):
        with pytest.raises(ValidationError):
            BankConnectionCreate.model_validate({"account_id": bad})
    with pytest.raises(ValidationError):
        BankConnectionCreate.model_validate({})


def test_bank_connection_account_id_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Reconcile liquid account"' in page
    assert 'aria-label="Connect bank account"' in page
    assert "account_id: reconAccountId.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Bank connection account_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /accounting/bank-connections" in docs
    assert "Reconcile liquid account" in docs


@pytest.mark.asyncio
async def test_bank_connection_account_id_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            "/api/v1/accounting/bank-connections",
            headers=headers,
            json={"account_id": bad, "provider": "mock"},
        )
        assert resp.status_code == 422, (bad, resp.text)

    suffix = uuid4().hex[:6]
    created = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": f"BC{suffix}",
            "name": f"Tip269 Bank {suffix}",
            "account_type": "asset",
            "liquid_kind": "bank",
            "bank_name": "Tip269 Bank",
        },
    )
    assert created.status_code == 200, created.text
    acct_id = created.json()["data"]["id"]

    ok = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={
            "account_id": f"  {str(acct_id).upper()}  ",
            "provider": "mock",
            "display_name": "Tip269 connection",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["account_id"] == str(acct_id).lower()

    missing = await ac.post(
        "/api/v1/accounting/bank-connections",
        headers=headers,
        json={"account_id": str(uuid4()), "provider": "mock"},
    )
    assert missing.status_code in (400, 404), missing.text
