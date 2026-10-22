"""Isolated logical backup/restore: tenant ownership, queued POS sales, failed apply.

Uses the pytest sqlite database only. Does not touch a production database.
Offline sync events are outside DATASET_SPECS so a restore cannot delete or rewind
the queue. A failed apply raises before commit, so the request session rolls back.
"""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import func, select

from app import backup as backup_svc
from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _patch_backup_dir(monkeypatch, tmp_path):
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))


@pytest.mark.asyncio
async def test_restore_keeps_other_tenant_and_queued_sales(
    client, db_session, tmp_path, monkeypatch
):
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)
    t1 = seed["t1"].id
    t2 = seed["t2"].id
    product = seed["p1"]
    beta = seed["p2"]
    original_name = product.name
    original_stock = float(product.stock_qty)
    beta_name = beta.name
    beta_stock = float(beta.stock_qty)
    company_name = seed["t1"].company_name
    other_company = seed["t2"].company_name

    store = m.Store(tenant_id=t1, name="Alpha Main", code="AMAIN", is_active=True)
    other_store = m.Store(tenant_id=t2, name="Beta Main", code="BMAIN", is_active=True)
    db_session.add_all([store, other_store])
    await db_session.flush()
    warehouse = m.Warehouse(
        tenant_id=t1,
        store_id=store.id,
        name="Alpha WH",
        code="AWH",
        is_active=True,
    )
    db_session.add(warehouse)
    await db_session.commit()

    sale = m.Transaction(
        tenant_id=t1,
        tx_type="pos_sale",
        reference="POS-RESTORE-1",
        subtotal=4,
        tax=0,
        total=4,
        status="completed",
        payload={"items": [{"sku": "A-1", "qty": 2}]},
    )
    db_session.add(sale)
    await db_session.flush()
    payment = m.PosPayment(
        tenant_id=t1,
        sale_id=sale.id,
        payment_method="mobile_money",
        amount=4,
        reference="MOMO-REF-1",
    )
    movement = m.StockMovement(
        tenant_id=t1,
        product_id=product.id,
        movement_type="stock_out",
        quantity=2,
        quantity_before=10,
        quantity_after=8,
        reference_type="pos_sale",
        reference_id=sale.id,
    )
    audit = m.AuditLog(
        tenant_id=t1,
        module="pos",
        action="sale_recorded",
        entity="transaction",
        entity_id=sale.id,
        details={"total": 4},
    )
    queued = m.OfflineSyncEvent(
        tenant_id=t1,
        user_id=seed["super"].id,
        device_id="dev-restore",
        client_request_id="queue-before-restore",
        result="conflict",
        conflict_code="PRICE_CONFLICT",
        details={"queued": "before"},
    )
    db_session.add_all([payment, movement, audit, queued])
    await db_session.commit()

    beta_audits_before = (
        await db_session.execute(
            select(func.count()).select_from(m.AuditLog).where(m.AuditLog.tenant_id == t2)
        )
    ).scalar_one()

    created = await ac.post(
        "/api/v1/backup", headers=headers, json={"notes": "isolation restore drill"}
    )
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]

    preview = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": True},
    )
    assert preview.status_code == 200, preview.text
    validated = preview.json()["data"]
    assert validated["valid"] is True
    assert validated["applied"] is False
    assert validated["source_tenant_id"] == t1
    assert validated["company_name"] == company_name
    assert validated["record_counts"]["stores"] >= 1
    assert validated["record_counts"]["transactions"] >= 1

    product.name = "CORRUPTED_NAME"
    product.stock_qty = 0
    sale.total = 99
    payment.amount = 99
    movement.quantity = 99
    store.name = "CORRUPT_STORE"
    warehouse.name = "CORRUPT_WH"
    warehouse.store_id = None
    queued.details = {"queued": "still-local"}
    later = m.OfflineSyncEvent(
        tenant_id=t1,
        user_id=seed["super"].id,
        device_id="dev-restore",
        client_request_id="queue-after-backup",
        result="conflict",
        conflict_code="PRICE_CONFLICT",
        details={"queued": "after"},
    )
    db_session.add(later)
    await db_session.commit()

    applied = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": False, "confirm": True, "confirm_text": "RESTORE"},
    )
    assert applied.status_code == 200, applied.text
    report = applied.json()["data"]
    assert report["applied"] is True
    assert report["proof"]["ok"] is True
    assert report["source_tenant_id"] == t1

    await db_session.refresh(product)
    await db_session.refresh(beta)
    await db_session.refresh(sale)
    await db_session.refresh(payment)
    await db_session.refresh(movement)
    await db_session.refresh(queued)
    await db_session.refresh(later)
    await db_session.refresh(audit)
    await db_session.refresh(seed["inv2"])
    await db_session.refresh(store)
    await db_session.refresh(other_store)
    await db_session.refresh(warehouse)
    await db_session.refresh(seed["t1"])
    await db_session.refresh(seed["t2"])

    assert product.name == original_name
    assert float(product.stock_qty) == original_stock
    assert product.tenant_id == t1
    assert beta.name == beta_name
    assert float(beta.stock_qty) == beta_stock
    assert beta.tenant_id == t2
    assert seed["inv2"].invoice_number == "INV-B-1"
    assert seed["inv2"].tenant_id == t2
    assert float(sale.total) == 4
    assert sale.tenant_id == t1
    assert sale.reference == "POS-RESTORE-1"
    assert payment.tenant_id == t1
    assert payment.sale_id == sale.id
    assert payment.payment_method == "mobile_money"
    assert float(payment.amount) == 4
    assert movement.tenant_id == t1
    assert movement.product_id == product.id
    assert float(movement.quantity) == 2
    assert audit.action == "sale_recorded"
    assert audit.tenant_id == t1
    assert queued.client_request_id == "queue-before-restore"
    assert queued.details == {"queued": "still-local"}
    assert queued.tenant_id == t1
    assert later.client_request_id == "queue-after-backup"
    assert later.details == {"queued": "after"}
    assert later.tenant_id == t1
    assert store.name == "Alpha Main"
    assert store.code == "AMAIN"
    assert store.tenant_id == t1
    assert store.is_active is True
    assert warehouse.name == "Alpha WH"
    assert warehouse.tenant_id == t1
    assert warehouse.store_id == store.id
    assert other_store.name == "Beta Main"
    assert other_store.tenant_id == t2
    assert seed["t1"].company_name == company_name
    assert seed["t1"].id == t1
    assert seed["t2"].company_name == other_company
    assert seed["t2"].id == t2

    verified = await ac.post(
        f"/api/v1/backup/{backup_id}/verify",
        headers=headers,
        json={"sample_limit": 100},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["data"]["proof"]["ok"] is True

    beta_audits_after = (
        await db_session.execute(
            select(func.count()).select_from(m.AuditLog).where(m.AuditLog.tenant_id == t2)
        )
    ).scalar_one()
    assert beta_audits_after == beta_audits_before

    conflicts = await ac.get("/api/v1/pos/offline/conflicts", headers=headers)
    assert conflicts.status_code == 200, conflicts.text
    ids = {row["client_request_id"] for row in conflicts.json()["data"]}
    assert "queue-before-restore" in ids
    assert "queue-after-backup" in ids

    resolved = await ac.post(
        f"/api/v1/pos/offline/conflicts/{queued.id}/resolve",
        headers=headers,
        json={"action": "dismiss", "note": "Keep the queued sale"},
    )
    assert resolved.status_code == 200, resolved.text
    await db_session.refresh(queued)
    assert queued.resolution == "dismiss"
    assert queued.client_request_id == "queue-before-restore"
    assert queued.tenant_id == t1


@pytest.mark.asyncio
async def test_failed_restore_does_not_commit_partial_writes(
    client, db_session, tmp_path, monkeypatch
):
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)
    product = seed["p1"]
    beta = seed["p2"]
    store = m.Store(tenant_id=seed["t1"].id, name="Alpha Main", code="AMAIN", is_active=True)
    db_session.add(store)
    await db_session.commit()

    created = await ac.post(
        "/api/v1/backup", headers=headers, json={"notes": "failed restore drill"}
    )
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]

    product.name = "CORRUPT_BEFORE_FAILED_RESTORE"
    store.name = "CORRUPT_STORE_BEFORE_FAIL"
    await db_session.commit()

    async def _fail_after_partial(db, tenant_id, payload, sample_limit=100):
        row = await db.get(m.Product, product.id)
        shop = await db.get(m.Store, store.id)
        assert row is not None and shop is not None
        row.name = "PARTIAL_RESTORE"
        shop.name = "PARTIAL_STORE"
        await db.flush()
        return {
            "ok": False,
            "checked": 1,
            "mismatch_count": 1,
            "mismatches": [{"error": "forced"}],
            "by_dataset": {},
            "sample_limit": sample_limit,
            "mode": "forced_failure",
        }

    monkeypatch.setattr(backup_svc, "prove_restore_integrity", _fail_after_partial)

    failed = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": False, "confirm": True, "confirm_text": "RESTORE"},
    )
    assert failed.status_code == 409, failed.text

    await db_session.refresh(product)
    await db_session.refresh(beta)
    await db_session.refresh(store)
    assert product.name == "CORRUPT_BEFORE_FAILED_RESTORE"
    assert product.name != "PARTIAL_RESTORE"
    assert store.name == "CORRUPT_STORE_BEFORE_FAIL"
    assert store.name != "PARTIAL_STORE"
    assert store.tenant_id == seed["t1"].id
    assert beta.name == "Beta Widget"
    assert beta.tenant_id == seed["t2"].id
