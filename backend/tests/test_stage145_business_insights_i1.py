"""Stage 145 I1 — business insights CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_business_insights_export_csv(client):
    ac, seed = client
    headers = await _mgr(ac)

    exported = await ac.get("/api/v1/ai/insights/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "kind" in header and "title" in header and "summary" in header
    assert "severity" in header
    # Empty insights still valid (header-only); non-empty should have generated_at column
    assert "generated_at" in header


def test_business_insights_export_ui_i1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 145" in page
    assert "/ai/insights/export" in page
    assert "Export insights CSV" in page
    assert 'id="insights"' in page
