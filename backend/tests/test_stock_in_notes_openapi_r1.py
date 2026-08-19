"""StockMove.notes OpenAPI honesty (BR-5.2) — stock-in."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import StockMove
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_in_notes_schema():
    omit = StockMove.model_validate({"product_id": "p1", "quantity": 1})
    assert omit.notes is None
    nullish = StockMove.model_validate(
        {"product_id": "p1", "quantity": 1, "notes": None}
    )
    assert nullish.notes is None
    ok = StockMove.model_validate(
        {"product_id": "p1", "quantity": 1, "notes": "  Received from PO  "}
    )
    assert ok.notes == "Received from PO"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StockMove.model_validate(
                {"product_id": "p1", "quantity": 1, "notes": bad}
            )


def test_stock_in_notes_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock-in notes"' in page
    assert "stockNotes.trim() || null" in page
    assert 'aria-label="Receive batch"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock-in notes OpenAPI" in agents
    assert "StockInNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockInNotesValue" in docs
    assert "Stock-in notes" in docs


@pytest.mark.asyncio
async def test_stock_in_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    product_id = seed["p1"].id
    batch = f"TIP160-{suffix}"

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/inventory/stock-in",
            headers=admin,
            json={
                "product_id": product_id,
                "quantity": 1,
                "batch_number": batch,
                "notes": bad,
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={
            "product_id": product_id,
            "quantity": 1,
            "batch_number": f"{batch}-omit",
        },
    )
    assert omit.status_code == 200, omit.text

    ok = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={
            "product_id": product_id,
            "quantity": 1,
            "batch_number": f"{batch}-ok",
            "notes": f"  Tip160 notes {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text

    hist = await ac.get(
        "/api/v1/inventory/movements",
        headers=admin,
        params={"movement_type": "stock_in"},
    )
    assert hist.status_code == 200, hist.text
    payload = hist.json().get("data") or {}
    rows = payload.get("movements") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        rows = []
    hit = [
        m
        for m in rows
        if (m.get("notes") or "") == f"Tip160 notes {suffix}"
    ]
    assert hit, hist.json()
