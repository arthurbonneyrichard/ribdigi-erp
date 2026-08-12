"""Stage 129 N1 — notifications CSV export."""

from __future__ import annotations

from pathlib import Path

import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_notifications_export_csv(client, db_session):
    ac, seed = client
    headers = await auth_headers(
        ac, email="mgr@alpha.example.com", tenant_slug="alpha"
    )

    db_session.add_all(
        [
            m.Notification(
                tenant_id=seed["t1"].id,
                user_id=seed["mgr1"].id,
                category="system",
                title="Stage129 Unread",
                message="Unread body",
                status="unread",
            ),
            m.Notification(
                tenant_id=seed["t1"].id,
                user_id=seed["mgr1"].id,
                category="system",
                title="Stage129 Read",
                message="Read body",
                status="read",
            ),
        ]
    )
    await db_session.commit()

    exported = await ac.get(
        "/api/v1/notifications/export?status=unread", headers=headers
    )
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    header = exported.text.splitlines()[0]
    assert "title" in header and "status" in header and "group" in header
    assert "Stage129 Unread" in exported.text
    assert "Stage129 Read" not in exported.text

    all_csv = await ac.get("/api/v1/notifications/export?status=all", headers=headers)
    assert all_csv.status_code == 200, all_csv.text
    assert "Stage129 Unread" in all_csv.text
    assert "Stage129 Read" in all_csv.text


def test_notifications_export_ui_n1():
    page = (ROOT / "frontend/app/notifications/page.tsx").read_text(encoding="utf-8")
    assert "Stage 129" in page
    assert "/notifications/export" in page
    assert "Export notifications CSV" in page
