"""Stage 135 T1 — stores transfer list status honesty + CSV."""

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
async def test_stores_transfers_status_filter_and_export(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    wh_a = m.Warehouse(
        tenant_id=seed["t1"].id, code="WH-135-A", name="Stage135 A"
    )
    wh_b = m.Warehouse(
        tenant_id=seed["t1"].id, code="WH-135-B", name="Stage135 B"
    )
    db_session.add_all([wh_a, wh_b])
    await db_session.flush()

    store_a = m.Store(
        tenant_id=seed["t1"].id,
        code="ST-135-A",
        name="Stage135 Store A",
    )
    store_b = m.Store(
        tenant_id=seed["t1"].id,
        code="ST-135-B",
        name="Stage135 Store B",
    )
    db_session.add_all([store_a, store_b])
    await db_session.flush()

    draft = m.StockTransfer(
        tenant_id=seed["t1"].id,
        transfer_number="XFER-135-DRAFT",
        from_store_id=store_a.id,
        to_store_id=store_b.id,
        from_warehouse_id=wh_a.id,
        to_warehouse_id=wh_b.id,
        status="draft",
        notes="Stage135 draft",
    )
    received = m.StockTransfer(
        tenant_id=seed["t1"].id,
        transfer_number="XFER-135-RECV",
        from_store_id=store_a.id,
        to_store_id=store_b.id,
        from_warehouse_id=wh_a.id,
        to_warehouse_id=wh_b.id,
        status="received",
        notes="Stage135 received",
    )
    db_session.add_all([draft, received])
    await db_session.commit()

    drafts = await ac.get(
        "/api/v1/stores/transfers?status=draft", headers=headers
    )
    assert drafts.status_code == 200, drafts.text
    rows = drafts.json()["data"]
    assert any(r.get("transfer_number") == "XFER-135-DRAFT" for r in rows)
    assert all(r.get("status") == "draft" for r in rows)
    assert not any(r.get("transfer_number") == "XFER-135-RECV" for r in rows)

    exported = await ac.get(
        "/api/v1/stores/transfers/export?status=received", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "transfer_number" in header and "status" in header
    assert "items" not in header
    assert "XFER-135-RECV" in exported.text
    assert "XFER-135-DRAFT" not in exported.text


def test_shell_and_stores_transfers_t1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "transfer_status=draft" in shell
    assert "transfer_status=requested" in shell
    assert "transfer_status=in_transit" in shell
    assert "transfer_status=received" in shell
    assert "transfer_status=cancelled" in shell
    assert "Draft Inter-store Transfers" in shell
    page = (ROOT / "frontend/app/stores/page.tsx").read_text(encoding="utf-8")
    assert "Stage 135" in page
    assert "transferStatusFilter" in page
    assert "/stores/transfers/export" in page
    assert "Export transfers CSV" in page
