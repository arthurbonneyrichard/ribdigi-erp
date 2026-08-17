"""GET stock-transfer manage status Query OpenAPI + Inventory/Multi-Store filters."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.reports import TRANSFER_REPORT_STATUSES
from app.schemas import TransferReportStatusValue
from app.stores import create_store
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_transfer_manage_status_reuses_report_literal():
    lit = TransferReportStatusValue.__args__[0]
    assert set(lit.__args__) == set(TRANSFER_REPORT_STATUSES)
    adapter = TypeAdapter(TransferReportStatusValue)
    assert adapter.validate_python("  Requested ") == "requested"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")


def test_transfer_manage_status_ui_and_docs():
    inv = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    stores = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    for page in (inv, stores):
        assert "transferManageFilter" in page
        assert "managedTransfers" in page
        assert 'aria-label="Stock transfer status filter"' in page
        assert 'value="draft"' in page
        assert 'value="requested"' in page
        assert 'value="in_transit"' in page
        assert 'value="received"' in page
        assert 'value="cancelled"' in page
        assert "No stock transfers for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Transfer manage status Query OpenAPI" in agents
    assert "transferManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "transferManageFilter" in docs
    assert "GET /inventory/stock-transfers" in docs
    assert "GET /stores/transfers" in docs


@pytest.mark.asyncio
async def test_transfer_manage_status_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for path in (
        "/api/v1/inventory/stock-transfers",
        "/api/v1/stores/transfers",
    ):
        blank = await ac.get(f"{path}?status=", headers=headers)
        assert blank.status_code == 422, blank.text

        bad = await ac.get(f"{path}?status=open", headers=headers)
        assert bad.status_code == 422, bad.text

    from_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Manage Status Xfer From", code="MSXF"
    )
    to_store = await create_store(
        db_session, tenant_id=seed["t1"].id, name="Manage Status Xfer To", code="MSXT"
    )
    await db_session.flush()
    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == from_store.id,
            )
        )
    ).scalar_one()
    to_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == seed["t1"].id,
                m.Warehouse.store_id == to_store.id,
            )
        )
    ).scalar_one()
    await apply_stock_change(
        db_session,
        tenant_id=seed["t1"].id,
        product_id=seed["p1"].id,
        quantity_delta=5,
        movement_type="stock_in",
        user_id=seed["mgr1"].id,
        warehouse_id=from_wh.id,
    )
    await db_session.commit()

    created = await ac.post(
        "/api/v1/inventory/stock-transfers",
        headers=headers,
        json={
            "from_warehouse_id": from_wh.id,
            "to_warehouse_id": to_wh.id,
            "submit": False,
            "items": [{"product_id": seed["p1"].id, "quantity": 1}],
        },
    )
    assert created.status_code == 200, created.text
    tid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    for path in (
        "/api/v1/inventory/stock-transfers",
        "/api/v1/stores/transfers",
    ):
        draft = await ac.get(f"{path}?status=Draft", headers=headers)
        assert draft.status_code == 200, draft.text
        rows = draft.json()["data"]
        assert any(r["id"] == tid for r in rows)
        assert all(r["status"] == "draft" for r in rows)

        cancelled = await ac.get(f"{path}?status=cancelled", headers=headers)
        assert cancelled.status_code == 200, cancelled.text
        assert all(r["status"] == "cancelled" for r in cancelled.json()["data"])
        assert not any(r["id"] == tid for r in cancelled.json()["data"])

        omit = await ac.get(path, headers=headers)
        assert omit.status_code == 200, omit.text
        assert any(r["id"] == tid for r in omit.json()["data"])
