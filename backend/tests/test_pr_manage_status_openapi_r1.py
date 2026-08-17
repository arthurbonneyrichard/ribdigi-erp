"""GET /purchasing/requests status Query OpenAPI + Purchasing Requests filter (BR-6.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.purchase_requests import PR_MANAGE_STATUSES
from app.schemas import PurchaseRequestStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pr_manage_status_literal_covers_lifecycle():
    lit = PurchaseRequestStatusValue.__args__[0]
    assert set(lit.__args__) == set(PR_MANAGE_STATUSES)
    adapter = TypeAdapter(PurchaseRequestStatusValue)
    assert adapter.validate_python("  Pending ") == "pending"
    assert adapter.validate_python("Converted") == "converted"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")


def test_pr_manage_status_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "prManageFilter" in page
    assert "managedRequests" in page
    assert 'aria-label="Purchase request status filter"' in page
    for value in ("draft", "pending", "approved", "rejected", "converted"):
        assert f'value="{value}"' in page
    assert "No purchase requests for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PR manage status Query OpenAPI" in agents
    assert "prManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "prManageFilter" in docs
    assert "GET /purchasing/requests" in docs


@pytest.mark.asyncio
async def test_pr_manage_status_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/purchasing/requests?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/purchasing/requests?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    for status in sorted(PR_MANAGE_STATUSES):
        ok = await ac.get(f"/api/v1/purchasing/requests?status={status}", headers=headers)
        assert ok.status_code == 200, ok.text
        assert all(r["status"] == status for r in ok.json()["data"])

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=headers,
        json={
            "department": "Ops",
            "notes": "prManageFilter hello-world",
            "items": [{"product_id": seed["p1"].id, "quantity": 2}],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    draft = await ac.get("/api/v1/purchasing/requests?status=Draft", headers=headers)
    assert draft.status_code == 200, draft.text
    rows = draft.json()["data"]
    assert any(r["id"] == rid for r in rows)
    assert all(r["status"] == "draft" for r in rows)

    rejected = await ac.get("/api/v1/purchasing/requests?status=rejected", headers=headers)
    assert rejected.status_code == 200, rejected.text
    assert all(r["status"] == "rejected" for r in rejected.json()["data"])
    assert not any(r["id"] == rid for r in rejected.json()["data"])

    omit = await ac.get("/api/v1/purchasing/requests", headers=headers)
    assert omit.status_code == 200, omit.text
    assert any(r["id"] == rid for r in omit.json()["data"])
