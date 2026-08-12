"""Stage 96 B1 — Dashboard Business Overview fidelity."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_dashboard_profit_ap_kpi_links_b1(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")
    r = await ac.get("/api/v1/dashboard", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert "profit_summary" in data
    assert "income_mtd" in data
    assert "ap_total_due" in data or "ap_outstanding" in data
    links = data.get("kpi_links") or {}
    assert links.get("profit_summary") == "/accounting?tab=ledger#profit-loss"
    # Stage 98 O1 deepened AP links to ?kind=payable; bare /credit remains acceptable historically
    ap_link = links.get("ap_total_due") or links.get("ap_outstanding") or ""
    assert ap_link.startswith("/credit")


def test_dashboard_ui_overview_and_notification_links_b1():
    dash = (ROOT / "frontend/app/dashboard/page.tsx").read_text(encoding="utf-8")
    assert "Business Overview" in dash
    assert "profit_summary" in dash
    assert "ap_total_due" in dash or "Payables" in dash
    assert "notificationHref" in dash
    assert "entity_type" in dash
    views = (ROOT / "backend/app/dashboard_views.py").read_text(encoding="utf-8")
    assert "profit_summary" in views
    assert "ap_total_due" in views
