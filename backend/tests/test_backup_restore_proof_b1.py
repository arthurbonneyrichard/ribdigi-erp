"""Stage 5 B1: logical backup restore proof + verify endpoint."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    headers["X-Workspace-Kind"] = "tenant"
    return headers


@pytest.mark.asyncio
async def test_backup_restore_drill_with_proof(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))

    headers = await _admin(ac, seed)
    headers["X-Workspace-Kind"] = "tenant"
    product = seed["p1"]
    original_name = product.name
    original_stock = float(product.stock_qty)

    created = await ac.post("/api/v1/backup", headers=headers, json={"notes": "b1-drill"})
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]
    assert created.json()["data"]["checksum_sha256"]

    # Simulate data loss / corruption after backup
    product.name = "CORRUPTED WIDGET"
    product.stock_qty = 0
    await db_session.commit()

    dry = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": True},
    )
    assert dry.status_code == 200, dry.text
    dry_body = dry.json()["data"]
    assert dry_body["valid"] is True
    assert dry_body["dry_run"] is True
    assert dry_body["applied"] is False
    assert dry_body["record_counts"]["products"] >= 1

    blocked = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": False, "confirm": True, "confirm_text": "YES"},
    )
    assert blocked.status_code == 400

    applied = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": False, "confirm": True, "confirm_text": "RESTORE"},
    )
    assert applied.status_code == 200, applied.text
    report = applied.json()["data"]
    assert report["applied"] is True
    assert report["dry_run"] is False
    assert report["proof"]["ok"] is True
    assert report["proof"]["checked"] >= 1
    assert report["proof"]["mismatch_count"] == 0

    await db_session.refresh(product)
    assert product.name == original_name
    assert float(product.stock_qty) == original_stock

    verify = await ac.post(
        f"/api/v1/backup/{backup_id}/verify",
        headers=headers,
        json={"sample_limit": 50},
    )
    assert verify.status_code == 200, verify.text
    vdata = verify.json()["data"]
    assert vdata["proof"]["ok"] is True
    assert vdata["checksum_sha256"]

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.module == "backup",
                m.AuditLog.entity_id == backup_id,
                m.AuditLog.action.in_(
                    ("restore_dry_run", "restore_apply", "restore_verify")
                ),
            )
        )
    ).scalars().all()
    actions = {row.action for row in audits}
    assert "restore_dry_run" in actions
    assert "restore_apply" in actions
    assert "restore_verify" in actions


@pytest.mark.asyncio
async def test_verify_detects_drift_before_restore(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))

    headers = await _admin(ac, seed)
    headers["X-Workspace-Kind"] = "tenant"
    created = await ac.post("/api/v1/backup", headers=headers, json={})
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]

    seed["p1"].name = "Drifted Name"
    await db_session.commit()

    verify = await ac.post(f"/api/v1/backup/{backup_id}/verify", headers=headers, json={})
    assert verify.status_code == 200, verify.text
    proof = verify.json()["data"]["proof"]
    assert proof["ok"] is False
    assert proof["mismatch_count"] >= 1
    assert any(m.get("field") == "name" for m in proof["mismatches"])
