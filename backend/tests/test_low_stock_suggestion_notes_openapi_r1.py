"""LowStockSuggestionsCreate / line notes OpenAPI honesty (BR-6.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import LowStockSuggestionLine, LowStockSuggestionsCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_low_stock_suggestion_notes_schema():
    omit = LowStockSuggestionsCreate.model_validate(
        {"lines": [{"product_id": "p1", "quantity": 1}]}
    )
    assert omit.notes is None
    ok = LowStockSuggestionsCreate.model_validate(
        {
            "lines": [{"product_id": "p1", "quantity": 1}],
            "notes": "  Restock floor  ",
        }
    )
    assert ok.notes == "Restock floor"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            LowStockSuggestionsCreate.model_validate(
                {"lines": [{"product_id": "p1", "quantity": 1}], "notes": bad}
            )

    line_ok = LowStockSuggestionLine.model_validate(
        {"product_id": "p1", "quantity": 2, "notes": "  Bin A  "}
    )
    assert line_ok.notes == "Bin A"
    with pytest.raises(ValidationError):
        LowStockSuggestionLine.model_validate(
            {"product_id": "p1", "quantity": 2, "notes": "!!!!"}
        )


def test_low_stock_suggestion_notes_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Low-stock suggestion notes"' in page
    assert "suggestNotes.trim() || null" in page
    assert 'aria-label="Create draft PR from low-stock suggestions"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Low-stock suggestion notes OpenAPI" in agents
    assert "LowStockSuggestionsCreate" in agents
    assert "PurchaseRequestNotesValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "LowStockSuggestionsCreate" in docs
    assert "Low-stock suggestion notes" in docs


@pytest.mark.asyncio
async def test_low_stock_suggestion_notes_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP187 notes {suffix}"
    item = {"product_id": seed["p1"].id, "quantity": 2}

    for bad in ("", "!!!", "http://evil"):
        resp = await ac.post(
            "/api/v1/purchasing/requests/from-low-stock",
            headers=headers,
            json={"notes": bad, "lines": [item], "include_open": True},
        )
        assert resp.status_code == 422, (bad, resp.text)

    bad_line = await ac.post(
        "/api/v1/purchasing/requests/from-low-stock",
        headers=headers,
        json={
            "include_open": True,
            "lines": [{**item, "notes": "!!!!"}],
        },
    )
    assert bad_line.status_code == 422, bad_line.text

    ok = await ac.post(
        "/api/v1/purchasing/requests/from-low-stock",
        headers=headers,
        json={"notes": f"  {tag}  ", "lines": [item], "include_open": True},
    )
    assert ok.status_code == 200, ok.text
    created = (ok.json().get("data") or {}).get("created") or []
    assert created, ok.json()
    notes_hit = [c for c in created if tag in str(c.get("notes") or "")]
    assert notes_hit, ok.json()
