"""Smart Business Intelligence Layer 1 — unit + API + tenant isolation tests."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.bi_defaults import DEFAULT_SETTINGS, PRIORITY_CRITICAL, PRIORITY_WARNING
from app.bi_metrics import _pct_change
from app.bi_priority import InsightPriorityService
from app.bi_recommendations import RecommendationService
from app.bi_rules import InsightRulesService
from app.bi_service import compute_health_score, merge_settings
from app.rbac import permissions_for_role
from tests.conftest import auth_headers


async def _mgr_headers(http, seed) -> dict:
    headers = await auth_headers(
        http, email=seed["mgr1"].email, tenant_slug="alpha"
    )
    headers["X-Company-ID"] = seed["c1"].id
    headers["X-Workspace-Kind"] = "company"
    return headers


async def _super_headers(http, seed) -> dict:
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        http,
        email=seed["super"].email,
        tenant_slug="alpha",
        totp_code=code,
    )
    headers["X-Company-ID"] = seed["c1"].id
    headers["X-Workspace-Kind"] = "company"
    return headers


def test_pct_change_division_by_zero():
    assert _pct_change(10, 0) is None
    assert _pct_change(0, 0) is None
    assert _pct_change(110, 100) == 10.0
    assert _pct_change(90, 100) == -10.0


def test_merge_settings_defaults():
    merged = merge_settings({"slow_moving_days": 45})
    assert merged["slow_moving_days"] == 45
    assert merged["dead_stock_days"] == DEFAULT_SETTINGS["dead_stock_days"]
    assert "sales" in merged["health_weights"]


def test_priority_assignment():
    p = InsightPriorityService
    assert p.for_negative_stock() == PRIORITY_CRITICAL
    assert p.for_expired() == PRIORITY_CRITICAL
    assert p.for_low_stock() == PRIORITY_WARNING
    assert p.for_near_expiry(days=7) == PRIORITY_WARNING
    assert p.for_sales_growth(pct=20) == "OPPORTUNITY"


def test_recommendation_links():
    rec = RecommendationService.for_insight("low_stock")
    assert "purchase" in rec["text"].lower() or "stock" in rec["text"].lower()
    assert rec["href"].startswith("/")


def test_health_score_transparent():
    sales = {"mom_change_pct": 0}
    inventory = {
        "product_count": 10,
        "low_stock_count": 0,
        "out_of_stock_count": 0,
        "negative_stock_count": 0,
    }
    profit = {"current": {"gross_margin_pct": 40}}
    expenses = {"mom_change_pct": 0, "expense_to_sales_pct": 15}
    credit = {"total_due": 0, "totals": {}}
    h = compute_health_score(
        sales=sales,
        inventory=inventory,
        profit=profit,
        expenses=expenses,
        credit=credit,
        settings=DEFAULT_SETTINGS,
    )
    assert 0 <= h["score"] <= 100
    assert "formula" in h
    assert h["external_ai"] is False


def test_rules_low_stock_and_sales_decline():
    rules = InsightRulesService()
    sales = {
        "this_month": 80,
        "last_month": 100,
        "mom_change_pct": -20,
        "this_week": 10,
        "last_week": 10,
        "wow_change_pct": 0,
        "avg_daily_sales": 2,
        "transaction_count_mtd": 5,
    }
    inventory = {
        "low_stock_count": 3,
        "out_of_stock_count": 1,
        "negative_stock_count": 0,
        "product_count": 10,
    }
    insights = rules.build(
        sales=sales,
        inventory=inventory,
        profit={
            "revenue_change_pct": None,
            "net_profit_change_pct": None,
            "current": {},
            "prior": {},
        },
        expenses={
            "mom_change_pct": 5,
            "this_month": 10,
            "last_month": 9,
            "expense_to_sales_pct": 10,
        },
        purchases={"by_supplier": []},
        credit=None,
        expiry={"expired_count": 0, "windows": {}, "qty_at_risk": 0, "value_at_risk": 0},
        slow_dead={
            "dead_stock_count": 0,
            "slow_moving_count": 0,
            "dead_stock_days": 60,
            "slow_moving_days": 30,
        },
        by_store=[],
        reorder=[],
        top_products=[],
        can_financial=True,
        can_credit=False,
    )
    types = {i["insight_type"] for i in insights}
    assert "sales_decline" in types
    assert "low_stock" in types
    assert "out_of_stock" in types


@pytest.mark.asyncio
async def test_bi_overview_requires_auth(client):
    http, _seed = client
    res = await http.get("/api/v1/business-insights/overview")
    assert res.status_code in (401, 403)


@pytest.mark.asyncio
async def test_bi_overview_manager_ok(client):
    http, seed = client
    headers = await _mgr_headers(http, seed)
    res = await http.get("/api/v1/business-insights/overview", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["external_ai_required"] is False
    assert "health" in body
    assert "attention" in body
    assert "sales" in body
    assert "inventory" in body
    assert body["health"]["score"] >= 0
    assert body["sales"]["filters"]["tenant_id"] == seed["t1"].id


@pytest.mark.asyncio
async def test_bi_tenant_isolation_history(client, db_session: AsyncSession):
    http, seed = client
    db_session.add(
        m.BusinessInsight(
            tenant_id=seed["t2"].id,
            company_id=seed["c2"].id,
            insight_type="low_stock",
            category="inventory",
            priority="WARNING",
            title="Beta secret low stock",
            message="should not leak to alpha",
            status="ACTIVE",
        )
    )
    await db_session.commit()

    headers = await _mgr_headers(http, seed)
    res = await http.get("/api/v1/business-insights/history", headers=headers)
    assert res.status_code == 200, res.text
    titles = [i["title"] for i in res.json()["items"]]
    assert "Beta secret low stock" not in titles


@pytest.mark.asyncio
async def test_bi_beta_admin_separate_tenant(client, db_session: AsyncSession):
    http, seed = client
    u2 = await db_session.get(m.User, seed["u2"].id)
    u2.role = "store_manager"
    u2.permissions = permissions_for_role("store_manager")
    # Update membership permissions too
    from sqlalchemy import select

    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == u2.id
            )
        )
    ).scalar_one()
    mem.role = "store_manager"
    mem.permissions = permissions_for_role("store_manager")
    await db_session.commit()

    headers_a = await _mgr_headers(http, seed)
    res_a = await http.get("/api/v1/business-insights/overview", headers=headers_a)
    assert res_a.status_code == 200

    headers_b = await auth_headers(http, email=seed["u2"].email, tenant_slug="beta")
    headers_b["X-Company-ID"] = seed["c2"].id
    headers_b["X-Workspace-Kind"] = "company"
    res_b = await http.get("/api/v1/business-insights/overview", headers=headers_b)
    assert res_b.status_code == 200, res_b.text
    assert res_a.json()["sales"]["filters"]["tenant_id"] == seed["t1"].id
    assert res_b.json()["sales"]["filters"]["tenant_id"] == seed["t2"].id
    assert (
        res_a.json()["sales"]["filters"]["tenant_id"]
        != res_b.json()["sales"]["filters"]["tenant_id"]
    )


@pytest.mark.asyncio
async def test_bi_cashier_forbidden(client):
    http, seed = client
    headers = await auth_headers(http, email=seed["u1"].email, tenant_slug="alpha")
    res = await http.get("/api/v1/business-insights/overview", headers=headers)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_bi_settings_get_put(client):
    http, seed = client
    headers = await _super_headers(http, seed)
    get_res = await http.get("/api/v1/business-insights/settings", headers=headers)
    assert get_res.status_code == 200
    put_res = await http.put(
        "/api/v1/business-insights/settings",
        headers=headers,
        json={"slow_moving_days": 40, "sales_decline_warning_pct": 12.5},
    )
    assert put_res.status_code == 200, put_res.text
    assert put_res.json()["settings"]["slow_moving_days"] == 40


@pytest.mark.asyncio
async def test_bi_formulas_document_sources(client):
    http, seed = client
    headers = await _mgr_headers(http, seed)
    res = await http.get("/api/v1/business-insights/formulas", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["external_ai"] is False
    assert any(f["metric"] == "business_health_score" for f in body["formulas"])


@pytest.mark.asyncio
async def test_bi_manager_can_read_attention(client):
    http, seed = client
    headers = await _mgr_headers(http, seed)
    res = await http.get("/api/v1/business-insights/attention", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["external_ai_required"] is False


@pytest.mark.asyncio
async def test_bi_acknowledge_and_dismiss(client, db_session: AsyncSession):
    http, seed = client
    row = m.BusinessInsight(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        insight_type="low_stock",
        category="inventory",
        priority="WARNING",
        title="Test low stock",
        message="test",
        status="ACTIVE",
    )
    db_session.add(row)
    await db_session.commit()
    await db_session.refresh(row)

    headers = await _super_headers(http, seed)
    ack = await http.post(
        f"/api/v1/business-insights/{row.id}/acknowledge", headers=headers
    )
    assert ack.status_code == 200, ack.text
    assert ack.json()["status"] == "ACKNOWLEDGED"

    dismiss = await http.post(
        f"/api/v1/business-insights/{row.id}/dismiss", headers=headers
    )
    assert dismiss.status_code == 200, dismiss.text
    assert dismiss.json()["status"] == "DISMISSED"
