"""Stage 98 R1 — Returns pipeline discoverability."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_shell_and_returns_honesty_ui():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "Sales Returns" in shell
    assert "/sales?tab=returns" in shell
    assert "Purchase Returns" in shell
    assert "/purchasing?tab=returns" in shell
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "returnStatusFilter" in sales
    assert "Post is required before the credit note" in sales
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "returnStatusFilter" in purchasing
    assert "Post is required before the debit note" in purchasing


def test_returns_status_params_in_api():
    api = (ROOT / "backend/app/api.py").read_text(encoding="utf-8")
    assert "async def list_sales_returns" in api
    assert "async def list_purchase_returns" in api
    assert 'status must be draft or posted' in api


@pytest.mark.asyncio
async def test_returns_status_filter_api(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    bad_s = await ac.get("/api/v1/sales/returns?status=bogus", headers=headers)
    assert bad_s.status_code == 400
    bad_p = await ac.get("/api/v1/purchasing/returns?status=bogus", headers=headers)
    assert bad_p.status_code == 400

    sales_draft = await ac.get("/api/v1/sales/returns?status=draft", headers=headers)
    assert sales_draft.status_code == 200, sales_draft.text
    for row in sales_draft.json().get("data") or []:
        assert row["status"] == "draft"

    purch_posted = await ac.get("/api/v1/purchasing/returns?status=posted", headers=headers)
    assert purch_posted.status_code == 200, purch_posted.text
    for row in purch_posted.json().get("data") or []:
        assert row["status"] == "posted"
