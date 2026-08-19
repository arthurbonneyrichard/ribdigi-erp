"""Stage 120 X1 — expenses CSV export."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_expenses_export_csv(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    # Ensure at least one expense exists for export content
    created = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "category": "Supplies",
            "amount": 12.5,
            "description": "Stage 120 export sample",
            "payment_method": "cash",
            "payee": "Office Mart",
        },
    )
    assert created.status_code == 200, created.text

    exported = await ac.get("/api/v1/expenses/export", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    assert "expense_date" in text.splitlines()[0]
    assert "Office Mart" in text or "Stage 120 export sample" in text


def test_expenses_page_export_button_x1():
    page = (ROOT / "frontend/app/expenses/page.tsx").read_text(encoding="utf-8")
    assert "Stage 120" in page
    assert "/expenses/export" in page
    assert "Export expenses CSV" in page
    svc = (ROOT / "backend/app/expense_export.py").read_text(encoding="utf-8")
    assert "export_expenses_csv" in svc
