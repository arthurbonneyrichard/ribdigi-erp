"""CashTransferCreate.reference OpenAPI honesty (BR-10.3)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import CashTransferCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_cash_transfer_reference_schema():
    omit = CashTransferCreate.model_validate({"amount": 10})
    assert omit.reference is None
    ok = CashTransferCreate.model_validate({"amount": 10, "reference": "  TILL-BANK  "})
    assert ok.reference == "TILL-BANK"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            CashTransferCreate.model_validate({"amount": 10, "reference": bad})


def test_cash_transfer_reference_ui_and_docs():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Cash transfer reference"' in page
    assert "xferRef.trim() || null" in page
    assert 'aria-label="Post cash transfer"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Cash transfer reference OpenAPI" in agents
    assert "CashTransferReferenceValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CashTransferReferenceValue" in docs
    assert "Cash transfer reference" in docs


@pytest.mark.asyncio
async def test_cash_transfer_reference_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=admin)
    assert liq.status_code == 200, liq.text
    by_code = {a["code"]: a for a in liq.json()["data"]}
    cash = by_code["1000"]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/accounting/transfers",
            headers=admin,
            json={
                "kind": "deposit",
                "to_account_id": cash["id"],
                "amount": 5,
                "reference": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/accounting/transfers",
        headers=admin,
        json={"kind": "deposit", "to_account_id": cash["id"], "amount": 5},
    )
    assert omit.status_code == 200, omit.text
    auto_ref = omit.json()["data"].get("reference") or ""
    assert auto_ref.startswith("XFER-"), auto_ref

    ok = await ac.post(
        "/api/v1/accounting/transfers",
        headers=admin,
        json={
            "kind": "deposit",
            "to_account_id": cash["id"],
            "amount": 7.5,
            "reference": f"  TIP150-{suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["reference"] == f"TIP150-{suffix}"
