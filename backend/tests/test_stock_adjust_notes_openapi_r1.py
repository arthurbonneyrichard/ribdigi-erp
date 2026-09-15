"""StockAdjust.notes OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import StockAdjust
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_adjust_notes_schema():
    omit = StockAdjust.model_validate({"quantity": -1, "reason": "damage"})
    assert omit.notes is None
    nullish = StockAdjust.model_validate(
        {"quantity": -1, "reason": "damage", "notes": None}
    )
    assert nullish.notes is None
    ok = StockAdjust.model_validate(
        {"quantity": -1, "reason": "damage", "notes": "  Broken carton  "}
    )
    assert ok.notes == "Broken carton"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            StockAdjust.model_validate(
                {"quantity": -1, "reason": "damage", "notes": bad}
            )


def test_stock_adjust_notes_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Stock adjustment notes"' in page
    assert "adjNotes.trim() || null" in page
    assert 'aria-label="Post stock adjustment"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock adjustment notes OpenAPI" in agents
    assert "StockAdjustNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "StockAdjustNotesValue" in docs
    assert "Stock adjustment notes" in docs


@pytest.mark.asyncio
async def test_stock_adjust_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]
    product_id = seed["p1"].id

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            f"/api/v1/inventory/adjust/{product_id}",
            headers=admin,
            json={"quantity": 1, "reason": "found", "notes": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        f"/api/v1/inventory/adjust/{product_id}",
        headers=admin,
        json={"quantity": 1, "reason": "found"},
    )
    assert omit.status_code == 200, omit.text

    ok = await ac.post(
        f"/api/v1/inventory/adjust/{product_id}",
        headers=admin,
        json={
            "quantity": 1,
            "reason": "found",
            "notes": f"  Tip158 notes {suffix}  ",
        },
    )
    assert ok.status_code == 200, ok.text

    hist = await ac.get(
        "/api/v1/inventory/movements",
        headers=admin,
        params={"movement_type": "adjustment", "reason": "found"},
    )
    assert hist.status_code == 200, hist.text
    payload = hist.json().get("data") or {}
    rows = payload.get("movements") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        rows = []
    hit = [
        m
        for m in rows
        if (m.get("notes") or "") == f"Tip158 notes {suffix}"
    ]
    assert hit, hist.json()
