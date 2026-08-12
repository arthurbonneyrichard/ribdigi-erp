"""Stage 130 P1 — POS session status honesty + CSV."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_pos_sessions_status_filter_and_export(client, db_session):
    ac, seed = client
    headers = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )

    db_session.add_all(
        [
            m.PosSession(
                tenant_id=seed["t1"].id,
                user_id=seed["u1"].id,
                session_number="POS-130-OPEN",
                status="open",
                opening_cash=100,
            ),
            m.PosSession(
                tenant_id=seed["t1"].id,
                user_id=seed["u1"].id,
                session_number="POS-130-CLOSED",
                status="closed",
                opening_cash=50,
                total_sales=20,
                sale_count=1,
            ),
        ]
    )
    await db_session.commit()

    opened = await ac.get("/api/v1/pos/sessions?status=open", headers=headers)
    assert opened.status_code == 200, opened.text
    rows = opened.json()["data"]
    assert any(r.get("session_number") == "POS-130-OPEN" for r in rows)
    assert all(r.get("status") == "open" for r in rows)
    assert not any(r.get("session_number") == "POS-130-CLOSED" for r in rows)

    closed = await ac.get("/api/v1/pos/sessions?status=closed", headers=headers)
    assert closed.status_code == 200, closed.text
    crows = closed.json()["data"]
    assert any(r.get("session_number") == "POS-130-CLOSED" for r in crows)
    assert all(r.get("status") == "closed" for r in crows)

    exported = await ac.get("/api/v1/pos/sessions/export?status=closed", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "session_number" in header and "status" in header
    assert "POS-130-CLOSED" in exported.text
    assert "POS-130-OPEN" not in exported.text


def test_shell_and_pos_sessions_p1():
    shell = (ROOT / "frontend/components/Shell.tsx").read_text(encoding="utf-8")
    assert "pos_session_status=open" in shell
    assert "pos_session_status=closed" in shell
    assert "Open POS Sessions" in shell
    assert "Closed POS Sessions" in shell
    page = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "Stage 130" in page
    assert "posSessionStatusFilter" in page
    assert "/pos/sessions/export" in page
