"""OpeningStockCreate.notes OpenAPI honesty (BR-5.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import OpeningStockCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_opening_stock_notes_schema():
    omit = OpeningStockCreate.model_validate(
        {"lines": [{"product_id": "p1", "quantity": 1}]}
    )
    assert omit.notes is None
    nullish = OpeningStockCreate.model_validate(
        {"lines": [{"product_id": "p1", "quantity": 1}], "notes": None}
    )
    assert nullish.notes is None
    ok = OpeningStockCreate.model_validate(
        {"lines": [{"product_id": "p1", "quantity": 1}], "notes": "  Go-live count  "}
    )
    assert ok.notes == "Go-live count"
    for bad in ("", " ", "!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            OpeningStockCreate.model_validate(
                {"lines": [{"product_id": "p1", "quantity": 1}], "notes": bad}
            )


def test_opening_stock_notes_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Opening stock notes"' in page
    assert "openingNotes.trim() || null" in page
    assert 'aria-label="Post opening stock"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Opening stock notes OpenAPI" in agents
    assert "OpeningStockNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "OpeningStockNotesValue" in docs
    assert "Opening stock notes" in docs


@pytest.mark.asyncio
async def test_opening_stock_notes_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    admin = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    products = await ac.get("/api/v1/products", headers=admin)
    assert products.status_code == 200, products.text
    rows = products.json().get("data") or []
    assert rows, "seed products required"
    product_id = rows[0]["id"]

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/inventory/opening-stock",
            headers=admin,
            json={
                "notes": bad,
                "post_journal": False,
                "lines": [{"product_id": product_id, "quantity": 1}],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=admin,
        json={
            "post_journal": False,
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert omit.status_code == 200, omit.text

    ok = await ac.post(
        "/api/v1/inventory/opening-stock",
        headers=admin,
        json={
            "notes": f"  Tip153 notes {suffix}  ",
            "post_journal": False,
            "lines": [{"product_id": product_id, "quantity": 1}],
            "reference": f"TIP153-{suffix}",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["reference"] == f"TIP153-{suffix}"
    # notes land on movements; confirm list still returns the posted entry
    hist = await ac.get("/api/v1/inventory/opening-stock", headers=admin)
    assert hist.status_code == 200, hist.text
    notes_hit = [
        m
        for m in (hist.json().get("data") or [])
        if (m.get("notes") or "") and f"Tip153 notes {suffix}" in (m.get("notes") or "")
    ]
    assert notes_hit, hist.json()
