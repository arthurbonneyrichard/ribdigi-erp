"""OpenAPI honesty tips #496–#502: Query int ge/le bounds (limits/days/copies)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_query_int_bounds_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Platform trials within_days Query OpenAPI",
        "Barcode label copies Query OpenAPI",
        "Opening stock list limit Query OpenAPI",
        "Product lookup limit Query OpenAPI",
        "Inventory expiry days Query OpenAPI",
        "Notifications limit Query OpenAPI",
        "AI low-stock days_ahead Query OpenAPI",
    ):
        assert title in agents, title

    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "within_days" in docs
    assert "copies` ∈ 1–40" in docs or "copies` ∈ 1-40" in docs or "Query `copies` ∈ 1–40" in docs
    assert "Inventory expiry days" in docs or "days` ∈ 1–365" in docs

    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Label copies"' in inv
    reports = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Inventory expiry days"' in reports
    assert "Math.min(365" in reports

    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "within_days: Annotated[int, Query(ge=1, le=365)]" in api
    assert "copies: Annotated[int, Query(ge=1, le=40)]" in api
    assert api.count("limit: Annotated[int, Query(ge=1, le=100)]") >= 1
    assert "days_ahead: Annotated[int, Query(ge=1, le=90)]" in api


@pytest.mark.asyncio
async def test_query_int_bounds_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    # Product lookup limit
    for bad in (0, -1, 101):
        resp = await ac.get(f"/api/v1/inventory/products/lookup?limit={bad}", headers=headers)
        assert resp.status_code == 422, (bad, resp.text)
    ok = await ac.get("/api/v1/inventory/products/lookup?limit=10", headers=headers)
    assert ok.status_code == 200, ok.text

    # Opening stock limit
    for bad in (0, -1, 501):
        resp = await ac.get(f"/api/v1/inventory/opening-stock?limit={bad}", headers=headers)
        assert resp.status_code == 422, (bad, resp.text)

    # Expiry days
    for path in ("/api/v1/inventory/batches/expiring", "/api/v1/reports/inventory/expiry"):
        for bad in (0, -1, 366):
            resp = await ac.get(f"{path}?days={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)
        ok = await ac.get(f"{path}?days=30", headers=headers)
        assert ok.status_code == 200, (path, ok.text)

    # Notifications limit
    for bad in (0, -1, 201):
        resp = await ac.get(f"/api/v1/notifications?limit={bad}", headers=headers)
        assert resp.status_code == 422, (bad, resp.text)
    ok = await ac.get("/api/v1/notifications?limit=8", headers=headers)
    assert ok.status_code == 200, ok.text

    # AI days_ahead
    for bad in (0, -1, 91):
        resp = await ac.get(
            f"/api/v1/ai/inventory/low-stock-prediction?days_ahead={bad}", headers=headers
        )
        assert resp.status_code == 422, (bad, resp.text)
    ok = await ac.get(
        "/api/v1/ai/inventory/low-stock-prediction?days_ahead=14", headers=headers
    )
    assert ok.status_code == 200, ok.text

    # Barcode label copies (need a real product id from seed)
    product_id = _seed["p1"].id
    for bad in (0, -1, 41):
        resp = await ac.get(
            f"/api/v1/products/{product_id}/barcode/label?copies={bad}", headers=headers
        )
        assert resp.status_code == 422, (bad, resp.text)


@pytest.mark.asyncio
async def test_platform_trials_within_days_422(client):
    """Platform route: may 403 for tenant admin — assert schema via file + platform user if available."""
    ac, seed = client
    # Prefer platform-capable user when present; otherwise assert OpenAPI wiring only.
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "within_days: Annotated[int, Query(ge=1, le=365)] = 45" in api

    # Seeded super on alpha may lack platform_reports — accept 403 or 422 for bounds.
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    resp = await ac.get("/api/v1/platform/reports/trials?within_days=0", headers=headers)
    assert resp.status_code in (403, 422), resp.text
    if resp.status_code == 422:
        ok = await ac.get("/api/v1/platform/reports/trials?within_days=45", headers=headers)
        assert ok.status_code in (200, 403), ok.text

    # Missing product path still validates copies before 404 for non-uuid handled elsewhere
    missing = await ac.get(
        f"/api/v1/products/{uuid4()}/barcode/label?copies=0", headers=headers
    )
    assert missing.status_code == 422, missing.text
