"""Stage 139 B1 — expense budgets CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app.expenses import ensure_default_categories
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_budgets_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)
    await ensure_default_categories(db_session, seed["t1"].id)
    await db_session.commit()

    listed = await ac.get("/api/v1/expenses/categories", headers=headers)
    assert listed.status_code == 200, listed.text
    rent = next(c for c in listed.json()["data"] if c["code"] == "RENT")
    patched = await ac.patch(
        f"/api/v1/expenses/categories/{rent['id']}",
        headers=headers,
        json={"budget_amount": 1500},
    )
    assert patched.status_code == 200, patched.text

    exported = await ac.get("/api/v1/expenses/budgets/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "budget_amount" in header
    assert "spent" in header and "variance" in header
    assert "utilization_pct" in header
    assert "RENT" in text
    assert "1500" in text or "1500.00" in text


def test_budgets_export_ui_b1():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Stage 139" in page
    assert "/expenses/budgets/export" in page
    assert "Export budgets CSV" in page
