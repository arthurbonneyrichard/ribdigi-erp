"""Stage 145 T1 — AI report templates CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_report_templates_export_csv(client):
    ac, seed = client
    headers = await _mgr(ac)

    created = await ac.post(
        "/api/v1/ai/reports/templates",
        headers=headers,
        json={
            "name": "Stage145 Sales",
            "prompt": "Show me monthly sales",
            "format": "csv",
        },
    )
    assert created.status_code == 200, created.text
    tmpl_id = created.json()["data"]["id"]

    exported = await ac.get("/api/v1/ai/reports/templates/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "name" in header and "prompt" in header and "report_type" in header
    assert tmpl_id in text
    assert "Stage145 Sales" in text


def test_report_templates_export_ui_t1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 145" in page
    assert "/ai/reports/templates/export" in page
    assert "Export templates CSV" in page
    assert "report-generator" in page
