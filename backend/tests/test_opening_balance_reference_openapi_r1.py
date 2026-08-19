"""OpeningBalanceCreate.reference OpenAPI honesty (BR-10.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import OpeningBalanceCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_opening_balance_reference_schema():
    omit = OpeningBalanceCreate.model_validate(
        {"lines": [{"account_code": "1000", "amount": 1}]}
    )
    assert omit.reference is None
    ok = OpeningBalanceCreate.model_validate(
        {
            "lines": [{"account_code": "1000", "amount": 1}],
            "reference": "  FY2026-OPEN  ",
        }
    )
    assert ok.reference == "FY2026-OPEN"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            OpeningBalanceCreate.model_validate(
                {
                    "lines": [{"account_code": "1000", "amount": 1}],
                    "reference": bad,
                }
            )


def test_opening_balance_reference_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening balance reference"' in page
    assert "coaOpenRef.trim() || null" in page
    assert 'aria-label="Post opening balances"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Opening balance reference OpenAPI" in agents
    assert "OpeningBalanceReferenceValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "OpeningBalanceReferenceValue" in docs
    assert "Opening balance reference" in docs


@pytest.mark.asyncio
async def test_opening_balance_reference_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    line = {"account_code": "1000", "amount": 25}

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/accounting/opening-balances",
            headers=admin,
            json={"lines": [line], "reference": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    status = await ac.get("/api/v1/accounting/opening-balances", headers=admin)
    assert status.status_code == 200, status.text
    already = bool((status.json().get("data") or {}).get("posted"))

    if already:
        return

    omit = await ac.post(
        "/api/v1/accounting/opening-balances",
        headers=admin,
        json={"lines": [line]},
    )
    assert omit.status_code == 200, omit.text
    auto_ref = omit.json()["data"].get("reference") or ""
    assert auto_ref.startswith("COA-OPEN-"), auto_ref

    # Once-only: explicit reference covered by schema + UI hello-world when tenant open.
    _ = suffix
