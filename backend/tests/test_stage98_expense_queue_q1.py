"""Stage 98 Q1 — Expense approval queue honesty."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_expenses_status_ui_and_approval_matrix_anchor():
    expenses = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "filterStatus" in expenses or "setStatusFilter" in expenses
    assert "Filter expenses by status" in expenses
    assert 'id="approval-matrix"' in expenses
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Pending Expenses" in shell
    assert "/expenses?status=pending" in shell
    assert "#approval-matrix" in shell


def test_expenses_status_param_in_api():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert 'status must be pending, approved, or rejected' in api
    assert "pending_expenses" in api


@pytest.mark.asyncio
async def test_expenses_status_filter_api(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    bad = await ac.get("/api/v1/expenses?status=bogus", headers=headers)
    assert bad.status_code == 400

    pending = await ac.get("/api/v1/expenses?status=pending", headers=headers)
    assert pending.status_code == 200, pending.text
    for row in pending.json().get("data") or []:
        assert row["status"] == "pending"

    dash = await ac.get("/api/v1/dashboard", headers=headers)
    assert dash.status_code == 200
    links = dash.json()["data"].get("kpi_links") or {}
    assert links.get("pending_expenses") == "/expenses?status=pending"
