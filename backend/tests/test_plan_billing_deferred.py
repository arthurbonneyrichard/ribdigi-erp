"""Stage 1 B5 — plan_code is metadata; billing deferred (ADR-002 / BR-1.3)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_plan_change_is_metadata_only_no_payment(client, db_session):
    ac, seed = client
    headers = await _super(ac, seed)

    me = await ac.get("/api/v1/tenants/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()["data"]
    assert body["billing_deferred"] is True
    assert body["billing_provider"] is None
    assert "trial" in body["plan_codes"]

    bad = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"plan_code": "platinum-paid"},
    )
    assert bad.status_code == 400, bad.text

    changed = await ac.patch(
        "/api/v1/tenants/me",
        headers=headers,
        json={"plan_code": "growth"},
    )
    assert changed.status_code == 200, changed.text
    data = changed.json()
    assert "billing deferred" in (data.get("message") or "").lower()
    assert data["data"]["plan_code"] == "growth"
    assert data["data"]["billing_deferred"] is True
    assert data["data"].get("payment_processed") is not True
    assert "payment_success" not in data["data"]

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "plan_code_changed",
            )
        )
    ).scalars().all()
    assert audits, "expected plan_code_changed audit"
    details = audits[-1].details or {}
    assert details.get("to") == "growth"
    assert details.get("billing_deferred") is True
    assert details.get("payment_processed") is False
