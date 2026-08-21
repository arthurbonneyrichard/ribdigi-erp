"""Stage 10 B1: logical backup includes uploaded media bytes + restore round-trip."""

from __future__ import annotations

import hashlib

import pyotp
import pytest

from app import storage as storage_svc
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    headers["X-Workspace-Kind"] = "tenant"
    return headers


@pytest.mark.asyncio
async def test_backup_restore_media_roundtrip(client, db_session, tmp_path, monkeypatch):
    ac, seed = client
    media_dir = tmp_path / "media"
    backup_dir = tmp_path / "backups"
    media_dir.mkdir()
    backup_dir.mkdir()
    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(media_dir))
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(backup_dir))

    headers = await _admin(ac, seed)
    tenant_id = seed["t1"].id
    product_id = seed["p1"].id

    company_headers = {**headers, "X-Workspace-Kind": "company", "X-Company-ID": seed["c1"].id}
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x01\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    uploaded = await ac.post(
        f"/api/v1/products/{product_id}/images",
        headers=company_headers,
        files={"file": ("widget.png", png, "image/png")},
    )
    assert uploaded.status_code == 200, uploaded.text
    storage_key = uploaded.json()["data"]["storage_key"]
    assert storage_key.startswith(f"{tenant_id}/")
    original_sha = hashlib.sha256(png).hexdigest()
    assert storage_svc.read_object(storage_key, tenant_id=tenant_id).data == png

    created = await ac.post(
        "/api/v1/backup", headers=headers, json={"notes": "b1-media"}
    )
    assert created.status_code == 200, created.text
    body = created.json()["data"]
    backup_id = body["id"]
    assert body["record_counts"]["media_objects"] >= 1
    assert body["record_counts"]["media_missing"] == 0

    # Simulate media loss after backup (DB row keys remain)
    assert storage_svc.delete_key(storage_key, tenant_id=tenant_id) is True
    with pytest.raises(Exception):
        storage_svc.read_object(storage_key, tenant_id=tenant_id)

    dry = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": True},
    )
    assert dry.status_code == 200, dry.text
    assert dry.json()["data"]["media_objects"] >= 1

    applied = await ac.post(
        f"/api/v1/backup/{backup_id}/restore",
        headers=headers,
        json={"dry_run": False, "confirm": True, "confirm_text": "RESTORE"},
    )
    assert applied.status_code == 200, applied.text
    report = applied.json()["data"]
    assert report["applied"] is True
    assert report["media"]["media_restored"] >= 1
    assert report["proof"]["ok"] is True
    assert report["proof"]["by_dataset"]["media"]["checked"] >= 1
    assert report["proof"]["by_dataset"]["media"]["mismatches"] == 0

    restored = storage_svc.read_object(storage_key, tenant_id=tenant_id)
    assert hashlib.sha256(restored.data).hexdigest() == original_sha
    assert restored.data == png


@pytest.mark.asyncio
async def test_collect_media_skips_external_urls(tmp_path, monkeypatch):
    from app.backup import collect_media_objects

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    media, counts = collect_media_objects(
        "tenant-a",
        {
            "expenses": [
                {"id": "e1", "attachment_url": "https://cdn.example.com/r.pdf"},
                {"id": "e2", "attachment_url": "tenant-b/expenses/x.pdf"},
            ],
            "products": [{"id": "p1", "image_url": None}],
        },
        tenant_logo_url="https://cdn.example.com/logo.png",
    )
    assert media == {}
    assert counts["media_objects"] == 0
    assert counts["media_keys_referenced"] == 0
