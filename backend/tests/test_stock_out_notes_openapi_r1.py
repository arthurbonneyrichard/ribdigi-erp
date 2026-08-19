"""StockOut.notes OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import StockOut
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_out_notes_schema():
    omit = StockOut.model_validate(
        {"product_id": "p1", "quantity": 1, "reference_type": "internal"}
    )
    assert omit.notes is None
    nullish = StockOut.model_validate(
        {
            "product_id": "p1",
            "quantity": 1,
            "reference_type": "internal",
            "notes": None,
        }
    )
    assert nullish.notes is None
    ok = StockOut.model_validate(
        {
            "product_id": "p1",
            "quantity": 1,
            "reference_type": "internal",
            "notes": "  Issued to kitchen  ",
        }
    )
    assert ok.notes == "Issued to kitchen"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StockOut.model_validate(
                {
                    "product_id": "p1",
                    "quantity": 1,
                    "reference_type": "internal",
                    "notes": bad,
                }
            )


def test_stock_out_notes_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-out notes"' in page
    assert "outNotes.trim() || null" in page
    assert 'aria-label="Post stock out"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock-out notes OpenAPI" in agents
    assert "StockOutNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockOutNotesValue" in docs
    assert "Stock-out notes" in docs


@pytest.mark.asyncio
async def test_stock_out_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/inventory/stock-out",
            headers=admin,
            json={
                "product_id": product_id,
                "quantity": 1,
                "reference_type": "internal",
                "notes": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=admin,
        json={
            "product_id": product_id,
            "quantity": 1,
            "reference_type": "internal",
        },
    )
    assert omit.status_code == 200, omit.text

    ok = await ac.post(
        "/api/v1/inventory/stock-out",
        headers=admin,
        json={
            "product_id": product_id,
            "quantity": 1,
            "reference_type": "internal",
            "notes": f"  Tip159 notes {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text

    hist = await ac.get(
        "/api/v1/inventory/movements",
        headers=admin,
        params={"movement_type": "stock_out"},
    )
    assert hist.status_code == 200, hist.text
    payload = hist.json().get("data") or {}
    rows = payload.get("movements") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        rows = []
    hit = [
        m
        for m in rows
        if (m.get("notes") or "") == f"Tip159 notes {suffix}"
    ]
    assert hit, hist.json()
