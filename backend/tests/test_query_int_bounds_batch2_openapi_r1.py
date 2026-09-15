"""OpenAPI honesty tips #503–#510: remaining Query int ge/le bounds."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_query_int_bounds_batch2_ui_and_docs():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    for title in (
        "Audit logs limit Query OpenAPI",
        "Audit archives limit Query OpenAPI",
        "Audit archive-cold older_than_days Query OpenAPI",
        "Webhook deliveries limit Query OpenAPI",
        "AI queries limit Query OpenAPI",
        "AI security alerts Query OpenAPI",
        "AI report templates limit Query OpenAPI",
        "Sales monthly / export year-month Query OpenAPI",
    ):
        assert title in agents, title

    audit = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Archive cold audit logs"' in audit

    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "limit: Annotated[int, Query(ge=1, le=1000)] = 200" in api
    assert "older_than_days: Annotated[int, Query(ge=1, le=3650)] | None" in api
    assert "min_score: Annotated[int, Query(ge=0, le=100)] | None" in api
    assert "year: Annotated[int, Query(ge=2000, le=2100)] | None" in api
    assert "month: Annotated[int, Query(ge=1, le=12)] | None" in api
    # No remaining bare int Query defaults on routes
    assert "\n    limit: int =" not in api
    assert "\n    year: int |" not in api
    assert "\n    month: int |" not in api
    assert "\n    older_than_days: int |" not in api
    assert "\n    min_score: int |" not in api


@pytest.mark.asyncio
async def test_audit_ai_sales_query_int_bounds_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    for bad in (0, -1, 1001):
        resp = await ac.get(f"/api/v1/audit-logs?limit={bad}", headers=headers)
        assert resp.status_code == 422, (bad, resp.text)
    ok = await ac.get("/api/v1/audit-logs?limit=50", headers=headers)
    assert ok.status_code == 200, ok.text

    for bad in (0, -1, 201):
        resp = await ac.get(f"/api/v1/audit-logs/archives?limit={bad}", headers=headers)
        assert resp.status_code == 422, (bad, resp.text)

    for bad in (0, -1, 3651):
        resp = await ac.post(
            f"/api/v1/audit-logs/archive-cold?older_than_days={bad}",
            headers=headers,
            content=b"{}",
        )
        assert resp.status_code == 422, (bad, resp.text)

    for path in (
        "/api/v1/ai/queries",
        "/api/v1/ai/security/alerts",
        "/api/v1/ai/reports/templates",
    ):
        for bad in (0, -1, 201):
            resp = await ac.get(f"{path}?limit={bad}", headers=headers)
            assert resp.status_code == 422, (path, bad, resp.text)
        ok = await ac.get(f"{path}?limit=10", headers=headers)
        assert ok.status_code == 200, (path, ok.text)

    for bad in (-1, 101):
        resp = await ac.get(f"/api/v1/ai/security/alerts?min_score={bad}", headers=headers)
        assert resp.status_code == 422, (bad, resp.text)
    ok = await ac.get("/api/v1/ai/security/alerts?min_score=50", headers=headers)
    assert ok.status_code == 200, ok.text

    for bad_year in (1999, 2101):
        resp = await ac.get(f"/api/v1/reports/sales/monthly?year={bad_year}", headers=headers)
        assert resp.status_code == 422, (bad_year, resp.text)
    for bad_month in (0, 13):
        resp = await ac.get(f"/api/v1/reports/sales/monthly?month={bad_month}", headers=headers)
        assert resp.status_code == 422, (bad_month, resp.text)
    ok = await ac.get("/api/v1/reports/sales/monthly?year=2026&month=8", headers=headers)
    assert ok.status_code == 200, ok.text

    # Export year/month bounds (report_type required)
    for bad in (0, 13):
        resp = await ac.get(
            f"/api/v1/reports/export?report_type=sales_monthly&month={bad}",
            headers=headers,
        )
        assert resp.status_code == 422, (bad, resp.text)


@pytest.mark.asyncio
async def test_webhook_deliveries_limit_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    wid = uuid4()
    for bad in (0, -1, 201):
        resp = await ac.get(f"/api/v1/webhooks/{wid}/deliveries?limit={bad}", headers=headers)
        # bounds 422 before or with auth; missing webhook may 404 after valid limit
        assert resp.status_code == 422, (bad, resp.text)
    missing = await ac.get(f"/api/v1/webhooks/{wid}/deliveries?limit=30", headers=headers)
    assert missing.status_code in (404, 403), missing.text
