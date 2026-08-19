"""Stage 160 P1 — accounting profit-loss CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_accounting_profit_loss_export_csv(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    exported = await ac.get("/api/v1/accounting/profit-loss/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "net_profit" in header
    assert "account_id" in header or "code" in header
    assert "revenue" in header or "gross_profit" in header


def test_accounting_profit_loss_export_ui_p1():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 160" in page
    assert "/accounting/profit-loss/export" in page
    assert "Export profit-loss CSV" in page
