"""Stage 130 C1 — cheques CSV export."""

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
async def test_cheques_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    db_session.add_all(
        [
            m.Cheque(
                tenant_id=seed["t1"].id,
                direction="received",
                status="pending",
                cheque_number="CHQ-130-P",
                amount=100.0,
                bank_name="Stage130 Bank",
                party_id=seed["party1"].id,
                notes="Stage130 pending",
            ),
            m.Cheque(
                tenant_id=seed["t1"].id,
                direction="issued",
                status="cleared",
                cheque_number="CHQ-130-C",
                amount=50.0,
                bank_name="Stage130 Bank",
                notes="Stage130 cleared",
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/accounting/cheques/export?status=pending", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "cheque_number" in header and "status" in header and "direction" in header
    assert "CHQ-130-P" in exported.text
    assert "CHQ-130-C" not in exported.text

    by_dir = await ac.get(
        "/api/v1/accounting/cheques/export?direction=issued", headers=headers
    )
    assert by_dir.status_code == 200, by_dir.text
    assert "CHQ-130-C" in by_dir.text
    assert "CHQ-130-P" not in by_dir.text


def test_accounting_cheques_export_ui_c1():
    page = (ROOT / "frontend/app/accounting/page.tsx").read_text(encoding="utf-8")
    assert "Stage 130" in page
    assert "/accounting/cheques/export" in page
    assert "Export cheques CSV" in page
