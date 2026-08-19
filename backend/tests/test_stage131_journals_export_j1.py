"""Stage 131 J1 — journal entry header CSV export."""

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
async def test_journals_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    db_session.add_all(
        [
            m.JournalEntry(
                tenant_id=seed["t1"].id,
                entry_number="JE-131-POSTED",
                description="Stage131 posted",
                status="posted",
                total_debit=10.0,
                total_credit=10.0,
            ),
            m.JournalEntry(
                tenant_id=seed["t1"].id,
                entry_number="JE-131-UNPOSTED",
                description="Stage131 unposted",
                status="unposted",
                total_debit=5.0,
                total_credit=5.0,
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/accounting/journal-entries/export?status=posted", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "entry_number" in header and "status" in header
    assert "lines" not in header
    assert "JE-131-POSTED" in exported.text
    assert "JE-131-UNPOSTED" not in exported.text

    unposted = await ac.get(
        "/api/v1/accounting/journal-entries/export?status=unposted", headers=headers
    )
    assert unposted.status_code == 200, unposted.text
    assert "JE-131-UNPOSTED" in unposted.text
    assert "JE-131-POSTED" not in unposted.text


def test_accounting_journals_export_ui_j1():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 131" in page
    assert "/accounting/journal-entries/export" in page
    assert "Export journals CSV" in page
