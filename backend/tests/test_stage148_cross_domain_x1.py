"""Stage 148 X1 — AI cross-domain analysis CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_cross_domain_analysis_export_csv(client):
    ac, _seed = client
    headers = await _mgr(ac)

    exported = await ac.get("/api/v1/ai/cross-domain/analysis/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "row_type" in header and "total_sales" in header and "signal_kind" in header
    assert "summary" in text


def test_cross_domain_analysis_export_ui_x1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 148" in page
    assert "/ai/cross-domain/analysis/export" in page
    assert "Export cross-domain CSV" in page
    assert 'id="cross-domain"' in page
