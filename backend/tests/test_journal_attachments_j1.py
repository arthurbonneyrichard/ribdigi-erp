"""Stage 9 J1: journal supporting document upload/download/delete (BR-10.2)."""

from __future__ import annotations

import io

import pyotp
import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_journal_attachment_upload_download_delete(client, db_session, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id
    await accounting_svc.ensure_default_accounts(db_session, tenant_id)
    await db_session.commit()

    posted = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "J1 supporting doc",
            "lines": [
                {"account_code": "6000", "debit": 15, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 15},
            ],
        },
    )
    assert posted.status_code == 200, posted.text
    entry = posted.json()["data"]
    entry_id = entry["id"]
    assert entry["has_attachment"] is False
    assert entry.get("attachment_url") in (None, "")

    upload = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment",
        headers=headers,
        files={"file": ("support.pdf", io.BytesIO(b"%PDF-1.4 journal"), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text
    data = upload.json()["data"]
    assert data["has_attachment"] is True
    assert data["uploaded"]["filename"] == "support.pdf"
    assert data["attachment_url"]

    listed = await ac.get("/api/v1/accounting/journal-entries", headers=headers)
    assert listed.status_code == 200
    row = next(r for r in listed.json()["data"] if r["id"] == entry_id)
    assert row["has_attachment"] is True

    download = await ac.get(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment", headers=headers
    )
    assert download.status_code == 200
    assert download.content.startswith(b"%PDF")

    removed = await ac.delete(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment", headers=headers
    )
    assert removed.status_code == 200
    assert removed.json()["data"]["has_attachment"] is False

    missing = await ac.get(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment", headers=headers
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_journal_attachment_tenant_isolation(client, db_session, tmp_path, monkeypatch):
    from app import storage as storage_svc

    monkeypatch.setattr(storage_svc.settings, "MEDIA_DIR", str(tmp_path))
    ac, seed = client
    headers = await _super(ac, seed)
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)
    await db_session.commit()

    posted = await ac.post(
        "/api/v1/accounting/journal-entries",
        headers=headers,
        json={
            "description": "J1 isolation",
            "lines": [
                {"account_code": "6000", "debit": 5, "credit": 0},
                {"account_code": "1000", "debit": 0, "credit": 5},
            ],
        },
    )
    assert posted.status_code == 200, posted.text
    entry_id = posted.json()["data"]["id"]

    upload = await ac.post(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment",
        headers=headers,
        files={"file": ("a.pdf", io.BytesIO(b"%PDF-1.4 a"), "application/pdf")},
    )
    assert upload.status_code == 200, upload.text

    other = await auth_headers(ac, email="cashier@beta.example.com", tenant_slug="beta")
    cross = await ac.get(
        f"/api/v1/accounting/journal-entries/{entry_id}/attachment", headers=other
    )
    assert cross.status_code in (403, 404)
