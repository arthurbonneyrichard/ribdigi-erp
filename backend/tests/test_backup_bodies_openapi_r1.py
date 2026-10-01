"""Backup create/verify/restore typed bodies OpenAPI (BR-16)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import ValidationError

from app.schemas import BackupCreateBody, BackupRestoreBody, BackupVerifyBody
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_backup_bodies_schema_forbid():
    assert BackupCreateBody.model_validate({}).notes is None
    assert BackupCreateBody.model_validate({"notes": "manual"}).notes == "manual"
    with pytest.raises(ValidationError):
        BackupCreateBody.model_validate({"notes": "x", "extra": 1})

    assert BackupVerifyBody.model_validate({}).sample_limit == 100
    assert BackupVerifyBody.model_validate({"sample_limit": 50}).sample_limit == 50
    with pytest.raises(ValidationError):
        BackupVerifyBody.model_validate({"sample_limit": 0})
    with pytest.raises(ValidationError):
        BackupVerifyBody.model_validate({"sample_limit": 501})
    with pytest.raises(ValidationError):
        BackupVerifyBody.model_validate({"sample_limit": 10, "foo": True})

    dry = BackupRestoreBody.model_validate({"dry_run": True})
    assert dry.dry_run is True and dry.confirm is False
    ok = BackupRestoreBody.model_validate(
        {"dry_run": False, "confirm": True, "confirm_text": "RESTORE"}
    )
    assert ok.confirm_text == "RESTORE"
    with pytest.raises(ValidationError):
        BackupRestoreBody.model_validate(
            {"dry_run": False, "confirm": True, "confirm_text": "YES"}
        )
    with pytest.raises(ValidationError):
        BackupRestoreBody.model_validate({"dry_run": False, "confirm": True})
    with pytest.raises(ValidationError):
        BackupRestoreBody.model_validate({"dry_run": True, "extra": 1})


def test_backup_bodies_ui_and_docs():
    page = (ROOT / "frontend/app/(dashboard)/backup/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Create backup now"' in page
    assert 'aria-label="Backup dry-run restore"' in page
    assert 'aria-label="Apply backup restore"' in page
    assert 'aria-label="Restore confirmation text"' in page
    assert 'id="restore"' in page
    assert "confirm_text" in page and "RESTORE" in page
    assert "Restore apply: platform ops" not in page
    assert "{false ?" not in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Backup create/verify/restore bodies OpenAPI" in agents
    assert "BackupCreateBody" in agents
    docs = (ROOT / "docs/DR_LOGICAL_BACKUP_RUNBOOK.md").read_text(encoding="utf-8")
    assert "BackupCreateBody" in docs
    assert "BackupVerifyBody" in docs
    assert "BackupRestoreBody" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_backup_bodies_api_unknown_422(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    unknown_create = await ac.post(
        "/api/v1/backup", headers=headers, json={"notes": "x", "foo": 1}
    )
    assert unknown_create.status_code == 422, unknown_create.text

    created = await ac.post(
        "/api/v1/backup", headers=headers, json={"notes": "openapi probe"}
    )
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]

    bad_verify = await ac.post(
        f"/api/v1/backup/{backup_id}/verify",
        headers=headers,
        json={"sample_limit": 999},
    )
    assert bad_verify.status_code == 422, bad_verify.text

    unknown_verify = await ac.post(
        f"/api/v1/backup/{backup_id}/verify",
        headers=headers,
        json={"sample_limit": 10, "extra": True},
    )
    assert unknown_verify.status_code == 422, unknown_verify.text

    ok_verify = await ac.post(
        f"/api/v1/backup/{backup_id}/verify",
        headers=headers,
        json={"sample_limit": 25},
    )
    assert ok_verify.status_code == 200, ok_verify.text

    bad_restore = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": False, "confirm": True, "confirm_text": "YES"},
    )
    assert bad_restore.status_code == 422, bad_restore.text

    omit_text = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": False, "confirm": True},
    )
    assert omit_text.status_code == 422, omit_text.text

    unknown_restore = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": True, "extra": 1},
    )
    assert unknown_restore.status_code == 422, unknown_restore.text

    dry = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": True, "confirm": False},
    )
    assert dry.status_code == 200, dry.text
    assert dry.json()["data"].get("dry_run") is True or dry.json()["data"].get("valid") is not None


@pytest.mark.asyncio
async def test_company_admin_restore_apply_and_cashier_forbidden(
    client, db_session, tmp_path, monkeypatch
):
    """Tenant company_admin may upsert their own .ribbak; cashiers cannot hit restore."""
    ac, seed = client
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))

    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    created = await ac.post("/api/v1/backup", headers=admin, json={"notes": "restore-ui-wire"})
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]
    product = seed["p1"]
    original = product.name
    product.name = "RESTORE_CORRUPTED"
    await db_session.commit()

    cashier = await auth_headers(ac, email="cashier@alpha.example.com", tenant_slug="alpha")
    denied = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=cashier,
        json={"dry_run": True, "confirm": False},
    )
    assert denied.status_code == 403, denied.text

    applied = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=admin,
        json={"dry_run": False, "confirm": True, "confirm_text": "RESTORE"},
    )
    assert applied.status_code == 200, applied.text
    body = applied.json()["data"]
    assert body.get("applied") is True
    assert body.get("dry_run") is False
    assert (body.get("proof") or {}).get("ok") is True

    await db_session.refresh(product)
    assert product.name == original
    assert product.tenant_id == seed["t1"].id
    beta = seed["p2"]
    await db_session.refresh(beta)
    assert beta.name == "Beta Widget"
