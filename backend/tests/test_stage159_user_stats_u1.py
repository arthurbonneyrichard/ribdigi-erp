"""Stage 159 U1 — dashboard user-stats CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_dashboard_user_stats_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/dashboard/user-stats/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "metric" in header and "value" in header
    assert "total_users" in text or "active_users" in text or "recent_logins_7d" in text


def test_dashboard_user_stats_export_ui_u1():
    page = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "Stage 159" in page
    assert "/dashboard/user-stats/export" in page
    assert "Export user-stats CSV" in page
