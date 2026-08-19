"""Stage 147 E1 — AI expense analysis CSV export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_expense_analysis_export_csv(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)
    expense = m.Expense(
        tenant_id=seed["t1"].id,
        category="Supplies",
        description="Stage 147 expense analysis seed",
        amount=125.5,
        status="approved",
        expense_date=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db_session.add(expense)
    await db_session.commit()

    exported = await ac.get("/api/v1/ai/expenses/analysis/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "total_approved" in header
    assert "summary" in text
    assert "125.5" in text or "125.50" in text


def test_expense_analysis_export_ui_e1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 147" in page
    assert "/ai/expenses/analysis/export" in page
    assert "Export expense analysis CSV" in page
    assert 'id="expense-analysis"' in page
