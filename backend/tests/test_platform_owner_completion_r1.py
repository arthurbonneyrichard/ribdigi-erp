"""Software owner dashboard: settings, CSV export, paid revenue summary, tenant search."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]

_SECRET_WORDS = ("secret", "token", "key", "password", "webhook", "hint")


async def _owner(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def _walk_keys(value, found=None):
    found = [] if found is None else found
    if isinstance(value, dict):
        for key, inner in value.items():
            found.append(str(key).lower())
            _walk_keys(inner, found)
    elif isinstance(value, list):
        for inner in value:
            _walk_keys(inner, found)
    return found


@pytest.mark.asyncio
async def test_platform_settings_owner_read_only_no_secrets(client):
    ac, seed = client
    headers = await _owner(ac, seed)
    res = await ac.get("/api/v1/platform/settings", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    for key in (
        "trial_days",
        "grace_days",
        "billing_grace_days",
        "billing_reminder_days",
        "billing_max_attempts",
        "billing",
        "live_charges",
        "auth",
        "services",
        "backup",
        "audit",
        "deploy",
    ):
        assert key in data, key
    assert isinstance(data["live_charges"], bool)
    assert data["live_charges"] is False  # test env never has a live, tested gateway
    assert isinstance(data["billing_reminder_days"], list)
    assert data["editable"] is False
    assert data["source"] == "environment"
    assert isinstance(data["auth"]["login_2fa_enabled"], bool)
    assert isinstance(data["services"]["rate_limit_enabled"], bool)
    assert isinstance(data["backup"]["encryption_configured"], bool)
    assert data["deploy"]["app_env"]
    for key in _walk_keys(data):
        assert not any(word in key for word in _SECRET_WORDS), key


@pytest.mark.asyncio
async def test_platform_settings_denied_for_non_owner_platform_role(client):
    ac, seed = client
    owner = await _owner(ac, seed)
    created = await ac.post(
        "/api/v1/platform/staff",
        headers=owner,
        json={
            "email": "finance-settings@alpha.example.com",
            "full_name": "Platform Finance",
            "password": "SecurePass123!",
            "role": "platform_finance",
        },
    )
    assert created.status_code == 200, created.text
    verified = await ac.post(
        f"/api/v1/platform/staff/{created.json()['data']['id']}/verify-email", headers=owner
    )
    assert verified.status_code == 200, verified.text
    finance = await auth_headers(
        ac, email="finance-settings@alpha.example.com", tenant_slug="alpha"
    )
    denied = await ac.get("/api/v1/platform/settings", headers=finance)
    assert denied.status_code == 403, denied.text

    tenant_admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    denied = await ac.get("/api/v1/platform/settings", headers=tenant_admin)
    assert denied.status_code == 403, denied.text


@pytest.mark.asyncio
@pytest.mark.parametrize("report", ["summary", "subscriptions", "packages", "trials"])
async def test_platform_reports_export_csv(client, report):
    ac, seed = client
    headers = await _owner(ac, seed)
    res = await ac.get(f"/api/v1/platform/reports/export?report={report}", headers=headers)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    disposition = res.headers["content-disposition"]
    assert "attachment" in disposition and f"platform-{report}-" in disposition
    assert disposition.endswith('.csv"')
    lines = [line for line in res.text.splitlines() if line.strip()]
    assert lines, "CSV must at least carry a header row"
    if report == "packages":
        assert lines[0].startswith("package_code")
        assert any("professional" in line for line in lines[1:])
    if report == "subscriptions":
        assert "company_name" in lines[0]
        assert any("Alpha Co" in line for line in lines[1:])


@pytest.mark.asyncio
async def test_platform_reports_export_rejects_unknown_report(client):
    ac, seed = client
    headers = await _owner(ac, seed)
    for bad in ("", "tenants", "SUMMARY!", "../x"):
        res = await ac.get(f"/api/v1/platform/reports/export?report={bad}", headers=headers)
        assert res.status_code == 422, (bad, res.text)
    res = await ac.get(
        "/api/v1/platform/reports/export?report=trials&within_days=0", headers=headers
    )
    assert res.status_code == 422, res.text


@pytest.mark.asyncio
async def test_platform_summary_paid_revenue_from_paid_invoices_only(client, db_session):
    ac, seed = client
    headers = await _owner(ac, seed)

    before = (await ac.get("/api/v1/platform/reports/summary", headers=headers)).json()["data"]
    assert before["paid_invoice_count"] == 0
    assert before["paid_revenue_by_currency"] == {}
    assert before["active_billing_accounts"] == 0
    assert before["attention_count"] == 0

    now = datetime.utcnow()
    acct1 = m.TenantBillingAccount(tenant_id=seed["t1"].id, billing_status="active")
    acct2 = m.TenantBillingAccount(tenant_id=seed["t2"].id, billing_status="past_due")
    db_session.add_all([acct1, acct2])
    await db_session.flush()

    def invoice(account, tenant, key, amount, currency, status):
        return m.TenantBillingInvoice(
            tenant_id=tenant.id,
            account_id=account.id,
            idempotency_key=key,
            amount=amount,
            currency=currency,
            status=status,
            period_start=now,
            period_end=now + timedelta(days=30),
            paid_at=now if status == "paid" else None,
        )

    db_session.add_all(
        [
            invoice(acct1, seed["t1"], "paid-ghs-1", 150.50, "GHS", "paid"),
            invoice(acct1, seed["t1"], "paid-ghs-2", 49.50, "GHS", "paid"),
            invoice(acct1, seed["t1"], "paid-usd-1", 20, "USD", "paid"),
            invoice(acct2, seed["t2"], "open-ghs-1", 999, "GHS", "open"),
            invoice(acct2, seed["t2"], "failed-ghs-1", 888, "GHS", "failed"),
        ]
    )
    await db_session.commit()

    res = await ac.get("/api/v1/platform/reports/summary", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["paid_invoice_count"] == 3
    # Per currency, never summed across currencies, open/failed invoices excluded.
    assert data["paid_revenue_by_currency"] == {"GHS": 200.0, "USD": 20.0}
    assert all(isinstance(v, float) for v in data["paid_revenue_by_currency"].values())
    assert data["active_billing_accounts"] == 1
    assert data["attention_count"] == 1
    assert "mrr" not in {key.lower() for key in data}

    csv_res = await ac.get("/api/v1/platform/reports/export?report=summary", headers=headers)
    assert csv_res.status_code == 200, csv_res.text
    assert "paid_invoice_count" in csv_res.text


@pytest.mark.asyncio
async def test_tenants_list_q_filter(client):
    ac, seed = client
    headers = await _owner(ac, seed)

    all_rows = (await ac.get("/api/v1/tenants", headers=headers)).json()["data"]
    assert {"alpha", "beta"} <= {row["slug"] for row in all_rows}

    by_name = await ac.get("/api/v1/tenants?q=alpha co", headers=headers)
    assert by_name.status_code == 200, by_name.text
    assert [row["slug"] for row in by_name.json()["data"]] == ["alpha"]

    by_slug = await ac.get("/api/v1/tenants?q=BET", headers=headers)
    assert by_slug.status_code == 200, by_slug.text
    assert [row["slug"] for row in by_slug.json()["data"]] == ["beta"]

    none = await ac.get("/api/v1/tenants?q=zzz-no-such", headers=headers)
    assert none.status_code == 200 and none.json()["data"] == []

    # LIKE wildcards are literal, not "match everything".
    wild = await ac.get("/api/v1/tenants?q=%25", headers=headers)
    assert wild.status_code == 200 and wild.json()["data"] == []

    combined = await ac.get("/api/v1/tenants?q=co&status=active&industry=retail", headers=headers)
    assert combined.status_code == 200, combined.text
    assert {row["slug"] for row in combined.json()["data"]} >= {"alpha", "beta"}

    other = await ac.get("/api/v1/tenants?q=alpha&industry=hotel", headers=headers)
    assert other.status_code == 200 and other.json()["data"] == []

    bad = await ac.get("/api/v1/tenants?industry=not-an-industry", headers=headers)
    assert bad.status_code == 422, bad.text


def test_owner_dashboard_ui_smoke():
    settings = (ROOT / "frontend/app/(dashboard)/platform/settings/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "/platform/settings" in settings
    assert "Platform settings" in settings
    assert 'href="/platform/billing"' in settings
    assert 'href="/security"' in settings
    assert 'href="/jobs"' in settings
    assert 'href="/platform/reports"' in settings
    assert "Read-only" in settings
    assert "Billing gateway" in settings
    assert "Security & access" in settings
    assert "System services" in settings
    assert "Backup & audit" in settings
    assert "Deploy identity" in settings
    assert "<input" not in settings  # read-only page

    nav = (ROOT / "frontend/lib/tenantNav.ts").read_text(encoding="utf-8")
    assert "['Settings', '/platform/settings', 'platform']" in nav

    reports = (ROOT / "frontend/app/(dashboard)/platform/reports/page.tsx").read_text(
        encoding="utf-8"
    )
    assert "/platform/reports/export?report=" in reports
    for label in (
        "Export platform summary CSV",
        "Export platform subscriptions CSV",
        "Export platform packages CSV",
        "Export platform trials CSV",
    ):
        assert f'aria-label="{label}"' in reports, label

    console = (ROOT / "frontend/app/(dashboard)/platform/page.tsx").read_text(encoding="utf-8")
    assert "paid_revenue_by_currency" in console
    assert "paid_invoice_count" in console
    assert "active_billing_accounts" in console
    assert "attention_count" in console

    tenants = (ROOT / "frontend/app/(dashboard)/platform/tenants/page.tsx").read_text(
        encoding="utf-8"
    )
    assert 'aria-label="Search tenants"' in tenants
