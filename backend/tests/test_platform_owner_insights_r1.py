"""Owner insights: monthly trends, last active, and the console wiring."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pyotp
import pytest

from app import models as m
from app import platform_reports as reports
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_last_month_keys_cross_the_year_and_end_on_this_month():
    keys = reports._last_month_keys(datetime(2026, 2, 15))
    assert len(keys) == 12
    assert keys[0] == "2025-03"
    assert keys[-2:] == ["2026-01", "2026-02"]


def test_console_shows_the_owner_insights():
    overview = (ROOT / "frontend/app/(dashboard)/platform/page.tsx").read_text(encoding="utf-8")
    tenants = (ROOT / "frontend/app/(dashboard)/platform/tenants/page.tsx").read_text(encoding="utf-8")
    report = (ROOT / "frontend/app/(dashboard)/platform/reports/page.tsx").read_text(encoding="utf-8")
    assert "/platform/health" in overview
    assert "System health" in overview
    assert "paid_revenue_by_month" in overview
    assert "isQuiet" in overview and "isQuiet" in tenants
    assert "last_active_at" in tenants
    assert "new_companies_by_month" in report


async def _owner(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


@pytest.mark.asyncio
async def test_trends_keep_currencies_apart_and_count_paid_invoices_only(client, seeded, db_session):
    ac, seed = client
    headers = await _owner(ac, seed)
    tenant = seed["t2"]
    account = m.TenantBillingAccount(tenant_id=tenant.id, billing_status="active")
    db_session.add(account)
    await db_session.flush()
    now = datetime.utcnow()

    def invoice(amount, currency, status, paid_at):
        return m.TenantBillingInvoice(
            tenant_id=tenant.id,
            account_id=account.id,
            idempotency_key=uuid4().hex,
            amount=amount,
            currency=currency,
            status=status,
            period_start=now,
            period_end=now + timedelta(days=30),
            paid_at=paid_at,
        )

    db_session.add_all(
        [
            invoice(100, "GHS", "paid", now),
            invoice(50.5, "GHS", "paid", now),
            invoice(20, "USD", "paid", now),
            invoice(999, "GHS", "open", None),
            invoice(777, "GHS", "paid", now - timedelta(days=500)),
        ]
    )
    await db_session.commit()

    res = await ac.get("/api/v1/platform/reports/summary", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()["data"]
    months = body["paid_revenue_by_month"]
    assert set(months) == {"GHS", "USD"}
    assert len(months["GHS"]) == 12
    assert months["GHS"][-1] == {"month": now.strftime("%Y-%m"), "amount": 150.5}
    assert months["USD"][-1]["amount"] == 20
    assert sum(row["amount"] for row in months["GHS"]) == 150.5
    assert len(body["new_companies_by_month"]) == 12


@pytest.mark.asyncio
async def test_directory_reports_last_active_from_the_newest_session(client, seeded, db_session):
    ac, seed = client
    headers = await _owner(ac, seed)
    tenant = seed["t2"]
    user = m.User(
        tenant_id=tenant.id,
        email=f"quiet-{uuid4().hex[:8]}@example.com",
        full_name="Quiet Person",
        password_hash="x",
        role="cashier",
    )
    db_session.add(user)
    await db_session.flush()
    newest = datetime(2026, 3, 4, 5, 6, 7)
    for created in (datetime(2026, 1, 1), newest):
        db_session.add(
            m.AuthSession(
                tenant_id=tenant.id,
                user_id=user.id,
                refresh_token_hash=uuid4().hex,
                jti=uuid4().hex,
                expires_at=created + timedelta(days=14),
                created_at=created,
            )
        )
    await db_session.commit()

    res = await ac.get("/api/v1/platform/directory", headers=headers)
    assert res.status_code == 200, res.text
    row = next(item for item in res.json()["data"] if item["id"] == tenant.id)
    assert row["last_active_at"].startswith("2026-03-04T05:06:07")
    # Platform staff stay out of company usage and no business figures appear.
    assert "total_sales" not in row and "stock_value" not in row
