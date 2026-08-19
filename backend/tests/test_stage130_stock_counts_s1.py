"""Stage 130 S1 — stock-count list status honesty + CSV."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_stock_counts_status_filter_and_export(client, db_session):
    ac, seed = client
    headers = await auth_headers(
        ac, email="mgr@alpha.example.com", tenant_slug="alpha"
    )

    wh = m.Warehouse(
        tenant_id=seed["t1"].id,
        name="Stage130 WH",
        code="WH130",
        is_active=True,
    )
    db_session.add(wh)
    await db_session.flush()

    db_session.add_all(
        [
            m.StockCount(
                tenant_id=seed["t1"].id,
                warehouse_id=wh.id,
                count_number="SC-130-DRAFT",
                status="draft",
                notes="Stage130 draft",
                created_by=seed["mgr1"].id,
            ),
            m.StockCount(
                tenant_id=seed["t1"].id,
                warehouse_id=wh.id,
                count_number="SC-130-DONE",
                status="completed",
                notes="Stage130 completed",
                created_by=seed["mgr1"].id,
                completed_by=seed["mgr1"].id,
            ),
        ]
    )
    await db_session.commit()

    drafts = await ac.get("/api/v1/inventory/stock-counts?status=draft", headers=headers)
    assert drafts.status_code == 200, drafts.text
    rows = drafts.json()["data"]
    assert any(r.get("count_number") == "SC-130-DRAFT" for r in rows)
    assert all(r.get("status") == "draft" for r in rows)
    assert not any(r.get("count_number") == "SC-130-DONE" for r in rows)

    completed = await ac.get(
        "/api/v1/inventory/stock-counts?status=completed", headers=headers
    )
    assert completed.status_code == 200, completed.text
    assert any(r.get("count_number") == "SC-130-DONE" for r in completed.json()["data"])

    exported = await ac.get(
        "/api/v1/inventory/stock-counts/export?status=draft", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "count_number" in header and "status" in header
    assert "SC-130-DRAFT" in exported.text
    assert "SC-130-DONE" not in exported.text
    assert "items" not in header.lower()


def test_shell_and_stock_counts_s1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "count_status=draft" in shell
    assert "count_status=completed" in shell
    assert "Draft Stock Counts" in shell
    assert "Completed Stock Counts" in shell
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 130" in page
    assert "countStatusFilter" in page
    assert "/inventory/stock-counts/export" in page
