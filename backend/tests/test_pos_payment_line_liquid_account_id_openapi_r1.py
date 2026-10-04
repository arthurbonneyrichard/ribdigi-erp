"""PosPaymentLine.liquid_account_id ∈ UuidIdValue OpenAPI honesty (BR-8.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import PosPaymentLine, PosSaleCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ITEMS = [{"product_id": "11111111-2222-3333-4444-555555555555", "quantity": 1}]


def test_pos_payment_line_liquid_account_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = PosPaymentLine.model_validate({"amount": 1})
    assert omit.liquid_account_id is None
    ok = PosPaymentLine.model_validate(
        {"amount": 1, "liquid_account_id": f"  {_VALID}  "}
    )
    assert ok.liquid_account_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        with pytest.raises(ValidationError):
            PosPaymentLine.model_validate({"amount": 1, "liquid_account_id": bad})
    with pytest.raises(ValidationError):
        PosSaleCreate.model_validate(
            {
                "items": _ITEMS,
                "payments": [{"amount": 1, "liquid_account_id": "acct_001"}],
            }
        )


def test_pos_payment_line_liquid_account_id_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "POS payment line liquid_account_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PosPaymentLine.liquid_account_id" in docs


@pytest.mark.asyncio
async def test_pos_payment_line_liquid_account_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {"product_id": seed["p1"].id, "quantity": 1}

    cur = await ac.get("/api/v1/pos/sessions/current", headers=headers)
    if not (cur.status_code == 200 and (cur.json().get("data") or {}).get("session_id")):
        opened = await ac.post(
            "/api/v1/pos/sessions/open",
            headers=headers,
            json={"opening_cash": 0},
        )
        assert opened.status_code == 200, opened.text
        session_id = opened.json()["data"].get("session_id") or opened.json()["data"]["id"]
    else:
        session_id = cur.json()["data"]["session_id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "acct_001"):
        resp = await ac.post(
            "/api/v1/pos/sales",
            headers=headers,
            json={
                "session_id": session_id,
                "items": [item],
                "total": 1,
                "status": "completed",
                "payments": [
                    {"payment_method": "cash", "amount": 1, "liquid_account_id": bad}
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/pos/sales",
        headers=headers,
        json={
            "session_id": session_id,
            "items": [item],
            "total": 1,
            "status": "completed",
            "payments": [
                {
                    "payment_method": "cash",
                    "amount": 1,
                    "liquid_account_id": f"  {str(uuid4()).upper()}  ",
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
