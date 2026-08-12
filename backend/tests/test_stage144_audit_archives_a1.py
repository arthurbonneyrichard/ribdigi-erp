"""Stage 144 A1 — audit cold archives CSV export."""

from __future__ import annotations

from datetime import datetime
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
async def test_audit_archives_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    tenant_id = seed["t1"].id

    row = m.AuditColdArchive(
        tenant_id=tenant_id,
        storage_key=f"audit/{tenant_id}/stage144.jsonl.gz",
        sha256="a" * 64,
        event_count=3,
        from_created_at=datetime.utcnow(),
        to_created_at=datetime.utcnow(),
        byte_size=128,
        created_by=seed["super"].id,
    )
    db_session.add(row)
    await db_session.commit()

    exported = await ac.get("/api/v1/audit-logs/archives/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "storage_key" in header and "sha256" in header and "event_count" in header
    assert row.id in text
    assert "stage144.jsonl.gz" in text
    assert "3" in text


def test_audit_archives_export_ui_a1():
    page = (ROOT / "frontend/app/audit/page.tsx").read_text(encoding="utf-8")
    assert "Stage 144" in page
    assert "/audit-logs/archives/export" in page
    assert "Export archives CSV" in page
