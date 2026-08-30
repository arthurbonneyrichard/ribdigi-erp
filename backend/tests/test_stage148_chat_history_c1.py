"""Stage 148 C1 — AI chat history CSV export."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac, seed=None):
    """Elevated actor for company-admin happy paths (store_manager catalog writes denied)."""
    if seed is None:
        # backward-compat: some call sites pass only ac — fall back to admin without totp if possible
        return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_chat_history_export_csv(client, db_session):
    ac, seed = client
    headers = await _mgr(ac, seed)
    mgr = seed["mgr1"]
    db_session.add(
        m.AiQuery(
            tenant_id=seed["t1"].id,
            user_id=mgr.id,
            message="What is my top selling product?",
            answer="Alpha Widget leads posted sales this month.",
            intent="top_product",
            payload={"note": "not_exported"},
            created_at=datetime.utcnow(),
        )
    )
    await db_session.commit()

    exported = await ac.get("/api/v1/ai/chat/history/export?limit=50", headers=headers)
    assert exported.status_code == 200, exported.text
    assert "text/csv" in exported.headers.get("content-type", "")
    text = exported.text
    header = text.splitlines()[0]
    assert "message" in header and "answer" in header and "intent" in header
    assert "What is my top selling product?" in text
    assert "Alpha Widget leads posted sales this month." in text
    assert "not_exported" not in text


def test_chat_history_export_ui_c1():
    page = (ROOT / "frontend/app/ai/page.tsx").read_text(encoding="utf-8")
    assert "Stage 148" in page
    assert "/ai/chat/history/export" in page
    assert "Export chat history CSV" in page
    assert 'id="chat"' in page
