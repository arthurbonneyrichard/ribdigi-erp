"""Stage 23 B1 — Logical DR drill automation evidence (commercial MVP gate).

Proves the quarterly logical restore drill path end-to-end, writes a durable
evidence artifact, and confirms foreign-tenant backup ids cannot be restored.
WAL / pg_dump / S3 PITR remain deferred post-MVP (packaging elsewhere).
"""

from __future__ import annotations

import json
from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import backup as backup_svc
from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = Path("/opt/cursor/artifacts/dr")
EVIDENCE_FILE = EVIDENCE_DIR / "stage23_b1_logical_drill.json"
READINESS = ROOT / "PRODUCTION_READINESS.md"
RUNBOOK = ROOT / "docs" / "DR_LOGICAL_BACKUP_RUNBOOK.md"


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
async def test_logical_dr_drill_end_to_end_with_evidence(
    client, db_session, tmp_path, monkeypatch
):
    """Create → corrupt → dry-run → guard → apply RESTORE → verify → evidence JSON."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    headers = await _admin(ac, seed)
    product = seed["p1"]
    original_name = product.name
    original_stock = float(product.stock_qty)

    created = await ac.post(
        "/api/v1/backup", headers=headers, json={"notes": "stage23-b1-drill"}
    )
    assert created.status_code == 200, created.text
    backup = created.json()["data"]
    backup_id = backup["id"]
    checksum = backup["checksum_sha256"]
    assert checksum

    product.name = "STAGE23_DR_CORRUPTED"
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
    assert report["proof"]["ok"] is True
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
    assert vdata["checksum_sha256"] == checksum

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
    assert actions >= {"restore_dry_run", "restore_apply", "restore_verify"}

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    evidence = {
        "stage": "23",
        "workstream": "B1",
        "evidence": "logical_dr_drill",
        "passed": True,
        "backup_id": backup_id,
        "checksum_sha256": checksum,
        "dry_run_valid": dry_body["valid"],
        "apply_proof_ok": report["proof"]["ok"],
        "verify_proof_ok": vdata["proof"]["ok"],
        "audit_actions": sorted(actions),
        "wal_pitr_deferred": True,
        "operator_pitr_drill_executed": False,
    }
    EVIDENCE_FILE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    loaded = json.loads(EVIDENCE_FILE.read_text(encoding="utf-8"))
    assert loaded["passed"] is True
    assert loaded["workstream"] == "B1"
    assert loaded["wal_pitr_deferred"] is True
    assert loaded["operator_pitr_drill_executed"] is False


@pytest.mark.asyncio
async def test_foreign_tenant_backup_restore_and_verify_404(
    client, db_session, tmp_path, monkeypatch
):
    """Alpha operator cannot restore/verify a Beta tenant backup id."""
    ac, seed = client
    _patch_backup_dir(monkeypatch, tmp_path)
    foreign = await backup_svc.create_backup(
        db_session,
        tenant_id=seed["t2"].id,
        user_id=None,
        notes="beta-foreign-drill",
    )
    await db_session.commit()

    headers = await _admin(ac, seed)
    for path, body in (
        (f"/api/v1/backup/{foreign.id}/restore", {"dry_run": True}),
        (f"/api/v1/backup/{foreign.id}/verify", {}),
        (f"/api/v1/backup/{foreign.id}/download", None),
    ):
        if body is None:
            resp = await ac.get(path, headers=headers)
        else:
            resp = await ac.post(path, headers=headers, json=body)
        assert resp.status_code == 404, (path, resp.text)


def test_dr_gate_runbook_cites_stage23_b1() -> None:
    readiness = READINESS.read_text(encoding="utf-8")
    runbook = RUNBOOK.read_text(encoding="utf-8")

    assert "- [x] Disaster recovery drill passes." in readiness
    assert "Stage 23 B1" in readiness
    assert "test_logical_dr_drill_b1.py" in readiness
    assert "WAL" in readiness or "PITR" in readiness
    assert (
        "- [ ] Point-in-time recovery/WAL strategy complete." in readiness
        or (
            "- [x] Point-in-time recovery/WAL strategy complete." in readiness
            and "Stage 26 W1" in readiness
        )
    )

    assert "Stage 23 B1" in runbook
    assert "stage23_b1_logical_drill.json" in runbook
    assert "test_logical_dr_drill_b1.py" in runbook
    assert "WAL" in runbook or "PITR" in runbook
