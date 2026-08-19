"""PurchaseRequestCreate.required_date OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseRequestCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pr_required_date_schema():
    base = {"items": [{"product_id": "p1", "quantity": 1}]}
    omit = PurchaseRequestCreate.model_validate(base)
    assert omit.required_date is None
    ok = PurchaseRequestCreate.model_validate({**base, "required_date": " 2026-08-14 "})
    assert ok.required_date == "2026-08-14"
    iso = PurchaseRequestCreate.model_validate(
        {**base, "required_date": "2026-08-20T12:00:00"}
    )
    assert iso.required_date == "2026-08-20T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            PurchaseRequestCreate.model_validate({**base, "required_date": bad})


def test_pr_required_date_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase request required date"' in page
    assert "prRequiredDate.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PR required_date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Purchase request required date" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_pr_required_date_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {"product_id": seed["p1"].id, "quantity": 2}

    for bad in ("", "not-a-date", "01/02/2024"):
        resp = await ac.post(
            "/api/v1/purchasing/requests",
            headers=headers,
            json={
                "required_date": bad,
                "items": [item],
                "notes": f"bad date {uuid4().hex[:6]}",
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "required_date": "2026-08-14",
            "items": [item],
            "notes": "pr required_date OpenAPI hello-world",
        },
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert str(data.get("required_date") or "").startswith("2026-08-14")

    omit = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "items": [item],
            "notes": "omit required_date",
        },
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"].get("required_date") in (None, "")
