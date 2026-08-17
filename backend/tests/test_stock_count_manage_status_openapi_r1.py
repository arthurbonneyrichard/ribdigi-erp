"""GET /inventory/stock-counts status Query OpenAPI + Inventory Counts filter (BR-5.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app import models as m
from app.schemas import StockCountReportStatusValue
from app.stock_counts import COUNT_STATUSES
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_count_manage_status_reuses_report_literal():
    lit = StockCountReportStatusValue.__args__[0]
    assert set(lit.__args__) == set(COUNT_STATUSES)
    adapter = TypeAdapter(StockCountReportStatusValue)
    assert adapter.validate_python("  Draft ") == "draft"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")


def test_stock_count_manage_status_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "countManageFilter" in page
    assert "managedCounts" in page
    assert 'aria-label="Stock count status filter"' in page
    assert 'value="draft"' in page
    assert 'value="completed"' in page
    assert 'value="cancelled"' in page
    assert "No stock counts for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock count manage status Query OpenAPI" in agents
    assert "countManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "countManageFilter" in docs
    assert "GET /inventory/stock-counts" in docs


@pytest.mark.asyncio
async def test_stock_count_manage_status_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/inventory/stock-counts?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/inventory/stock-counts?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Manage Status Count Store", code="MSC"
    )
    await db_session.flush()
    wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one()
    await db_session.commit()

    created = await ac.post(
        "/api/v1/inventory/stock-counts",
        headers=headers,
        json={"warehouse_id": wh.id, "product_ids": [seed["p1"].id]},
    )
    assert created.status_code == 200, created.text
    count_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    draft = await ac.get("/api/v1/inventory/stock-counts?status=Draft", headers=headers)
    assert draft.status_code == 200, draft.text
    rows = draft.json()["data"]
    assert any(r["id"] == count_id for r in rows)
    assert all(r["status"] == "draft" for r in rows)

    completed = await ac.get(
        "/api/v1/inventory/stock-counts?status=completed", headers=headers
    )
    assert completed.status_code == 200, completed.text
    assert all(r["status"] == "completed" for r in completed.json()["data"])
    assert not any(r["id"] == count_id for r in completed.json()["data"])

    omit = await ac.get("/api/v1/inventory/stock-counts", headers=headers)
    assert omit.status_code == 200, omit.text
    assert any(r["id"] == count_id for r in omit.json()["data"])
