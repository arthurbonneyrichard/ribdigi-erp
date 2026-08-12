"""Stage 132 T1 — stock-transfer list status honesty + CSV."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_stock_transfers_status_filter_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    wh_a = m.Warehouse(
        tenant_id=seed["t1"].id, code="WH-132-A", name="Stage132 A", is_default=True
    )
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id, code="WH-132-B", name="Stage132 B", is_default=False
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    draft = m.StockTransfer(
        tenant_id=seed["t1"].id,
        transfer_number="XFER-132-DRAFT",
        from_warehouse_id=wh_a.id,
        to_warehouse_id=wh_b.id,
        status="draft",
        notes="Stage132 draft",
    )
    received = m.StockTransfer(
        tenant_id=seed["t1"].id,
        transfer_number="XFER-132-RECV",
        from_warehouse_id=wh_a.id,
        to_warehouse_id=wh_b.id,
        status="received",
        notes="Stage132 received",
    )
    db_session.add_all([draft, received])
    await db_session.commit()

    drafts = await ac.get(
        "/api/v1/inventory/stock-transfers?status=draft", headers=headers
    )
    assert drafts.status_code == 200, drafts.text
    rows = drafts.json()["data"]
    assert any(r.get("transfer_number") == "XFER-132-DRAFT" for r in rows)
    assert all(r.get("status") == "draft" for r in rows)
    assert not any(r.get("transfer_number") == "XFER-132-RECV" for r in rows)

    exported = await ac.get(
        "/api/v1/inventory/stock-transfers/export?status=received", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "transfer_number" in header and "status" in header
    assert "items" not in header
    assert "XFER-132-RECV" in exported.text
    assert "XFER-132-DRAFT" not in exported.text


def test_shell_and_stock_transfers_t1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "transfer_status=draft" in shell
    assert "transfer_status=requested" in shell
    assert "transfer_status=in_transit" in shell
    assert "transfer_status=received" in shell
    assert "transfer_status=cancelled" in shell
    assert "Draft Warehouse Transfers" in shell
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert "Stage 132" in page
    assert "transferStatusFilter" in page
    assert "/inventory/stock-transfers/export" in page
    assert "Export transfers CSV" in page
