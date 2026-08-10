"""Stage 16 M2: transfer history filters, report, export, and Reports UI packaging."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app.inventory import apply_stock_change
from app.rbac import permissions_for_role
from app.report_export import EXPORTABLE, build_report_payload, flatten_report
from app.security import hash_password
from app.stores import create_store, transfer_history
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _beta(ac):
    return await auth_headers(ac, email="mgr@beta.example.com", tenant_slug="beta")


async def _seed_inter_store_transfer(ac, db_session, seed, *, qty: float = 5.0):
    tenant_id = seed["t1"].id
    mgr_from = seed["mgr1"]
    product = m.Product(
        tenant_id=tenant_id,
        name="S16 M2 Transfer SKU",
        sku="S16-M2-XFER",
        cost_price=2,
        selling_price=4,
        stock_qty=0,
    )
    db_session.add(product)
    await db_session.flush()

    mgr_to = m.User(
        tenant_id=tenant_id,
        email="mgr-s16-m2-dest@alpha.example.com",
        full_name="S16 M2 Dest Manager",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(mgr_to)
    await db_session.flush()

    from_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="S16M2S",
        name="S16 M2 Source",
        manager_id=mgr_from.id,
    )
    to_store = await create_store(
        db_session,
        tenant_id=tenant_id,
        code="S16M2D",
        name="S16 M2 Dest",
        manager_id=mgr_to.id,
    )
    await db_session.flush()

    from_wh = (
        await db_session.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == from_store.id,
            )
        )
    ).scalar_one()
    await apply_stock_change(
        db_session,
        tenant_id=tenant_id,
        product_id=product.id,
        quantity_delta=30.0,
        movement_type="stock_in",
        user_id=mgr_from.id,
        warehouse_id=from_wh.id,
    )
    await db_session.commit()

    headers = await _mgr(ac)
    created = await ac.post(
        "/api/v1/stores/transfers",
        headers=headers,
        json={
            "from_store_id": from_store.id,
            "to_store_id": to_store.id,
            "submit": True,
            "items": [{"product_id": product.id, "quantity": qty}],
        },
    )
    assert created.status_code == 200, created.text
    return {
        "headers": headers,
        "transfer": created.json()["data"],
        "from_store_id": from_store.id,
        "to_store_id": to_store.id,
        "product_id": product.id,
        "qty": qty,
    }


@pytest.mark.asyncio
async def test_transfer_list_filters_and_report(client, db_session):
    ac, seed = client
    ctx = await _seed_inter_store_transfer(ac, db_session, seed, qty=6.0)
    headers = ctx["headers"]
    transfer_id = ctx["transfer"]["id"]
    transfer_number = ctx["transfer"]["transfer_number"]

    listed = await ac.get(
        "/api/v1/stores/transfers",
        headers=headers,
        params={"status": "requested", "scope": "inter_store", "store_id": ctx["from_store_id"]},
    )
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert transfer_id in ids

    scoped_out = await ac.get(
        "/api/v1/stores/transfers",
        headers=headers,
        params={"scope": "warehouse"},
    )
    assert scoped_out.status_code == 200, scoped_out.text
    assert transfer_id not in {row["id"] for row in scoped_out.json()["data"]}

    report = await ac.get(
        "/api/v1/reports/transfers",
        headers=headers,
        params={"scope": "inter_store", "status": "requested"},
    )
    assert report.status_code == 200, report.text
    body = report.json()["data"]
    assert body["count"] >= 1
    assert body["by_status"].get("requested", 0) >= 1
    assert body["total_qty_requested"] >= ctx["qty"]
    assert any(t["transfer_number"] == transfer_number for t in body["transfers"])


@pytest.mark.asyncio
async def test_transfer_history_exportable(client, db_session):
    ac, seed = client
    ctx = await _seed_inter_store_transfer(ac, db_session, seed, qty=4.0)
    headers = ctx["headers"]
    tenant_id = seed["t1"].id

    assert "transfer_history" in EXPORTABLE

    exportable = await ac.get("/api/v1/reports/exportable", headers=headers)
    assert exportable.status_code == 200
    assert "transfer_history" in exportable.json()["data"]["types"]

    exported = await ac.get(
        "/api/v1/reports/export",
        headers=headers,
        params={
            "report_type": "transfer_history",
            "format": "csv",
            "scope": "inter_store",
            "status": "requested",
        },
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    assert ctx["transfer"]["transfer_number"] in exported.text

    payload = await build_report_payload(
        db_session, tenant_id, "transfer_history", scope="inter_store", status="requested"
    )
    rows, lines, title = flatten_report("transfer_history", payload)
    assert title == "Transfer History"
    assert rows
    assert any(ctx["transfer"]["transfer_number"] in ln for ln in lines) or rows


@pytest.mark.asyncio
async def test_transfer_history_tenant_isolation(client, db_session):
    ac, seed = client
    ctx = await _seed_inter_store_transfer(ac, db_session, seed, qty=3.0)
    transfer_number = ctx["transfer"]["transfer_number"]

    alpha = await transfer_history(db_session, seed["t1"].id, scope="all", limit=200)
    beta = await transfer_history(db_session, seed["t2"].id, scope="all", limit=200)
    assert any(t["transfer_number"] == transfer_number for t in alpha["transfers"])
    assert not any(t["transfer_number"] == transfer_number for t in beta["transfers"])

    # Beta cashier has inventory/stores visibility constraints; create a beta manager with reports:read.
    beta_mgr = m.User(
        tenant_id=seed["t2"].id,
        email="mgr@beta.example.com",
        full_name="Beta Manager",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    db_session.add(beta_mgr)
    await db_session.commit()

    beta_headers = await _beta(ac)
    beta_http = await ac.get("/api/v1/reports/transfers", headers=beta_headers)
    assert beta_http.status_code == 200, beta_http.text
    assert not any(
        t["transfer_number"] == transfer_number
        for t in beta_http.json()["data"].get("transfers") or []
    )


def test_reports_ui_packages_transfers_tab():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "'transfers'" in page
    assert "/reports/transfers" in page
    assert "transfer_history" in page
    assert "Open Stores" in page


def test_transfer_history_m2_docs():
    plan = (ROOT / "docs/STAGE_16_PLAN.md").read_text(encoding="utf-8")
    assert "| **M2**" in plan
    assert "test_transfer_history_m2.py" in plan
    assert "COMPLETE" in plan
    br = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "Transfer history and reporting" in br
    assert "[x] Transfer history and reporting" in br or "Stage 16 M2" in br
