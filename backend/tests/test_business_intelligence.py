"""Smart Business Intelligence Layer 1 — unit + API + tenant isolation tests."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select
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


async def _cashier_headers(http, seed) -> dict:
    headers = await auth_headers(
        http, email=seed["u1"].email, tenant_slug="alpha"
    )
    headers["X-Company-ID"] = seed["c1"].id
    headers["X-Workspace-Kind"] = "company"
    return headers


async def _make_p1_out_of_stock(db_session: AsyncSession, seed, *, reorder_level: float = 8):
    p1 = await db_session.get(m.Product, seed["p1"].id)
    p1.stock_qty = 0
    p1.reorder_level = reorder_level
    await db_session.commit()


@pytest.mark.asyncio
async def test_reorder_requests_skips_without_supplier(client, db_session: AsyncSession):
    http, seed = client
    await _make_p1_out_of_stock(db_session, seed)
    headers = await _mgr_headers(http, seed)
    res = await http.post("/api/v1/business-insights/reorder-requests", headers=headers, json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created_count"] == 0
    assert body["external_ai_required"] is False
    reasons = {s["reason"] for s in body["skipped"]}
    assert "no_supplier" in reasons


@pytest.mark.asyncio
async def test_reorder_requests_creates_draft_pr_from_last_supplier(
    client, db_session: AsyncSession
):
    http, seed = client
    await _make_p1_out_of_stock(db_session, seed, reorder_level=8)
    headers = await _mgr_headers(http, seed)

    supplier = await http.post(
        "/api/v1/suppliers", headers=headers, json={"name": "Reorder Supplier"}
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    po = await http.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 4}],
        },
    )
    assert po.status_code == 200, po.text

    overview = await http.get("/api/v1/business-insights/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    recs = overview.json()["reorder_recommendations"]
    match = [r for r in recs if r["product_id"] == seed["p1"].id]
    assert match, recs
    assert match[0]["last_supplier_id"] == supplier_id
    assert match[0]["recommended_reorder_qty"] >= 1

    created = await http.post(
        "/api/v1/business-insights/reorder-requests", headers=headers, json={}
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["created_count"] == 1
    pr = body["created"][0]
    assert pr["status"] == "draft"
    assert pr["supplier_id"] == supplier_id
    assert pr["items"][0]["product_id"] == seed["p1"].id
    assert float(pr["items"][0]["quantity"]) == float(match[0]["recommended_reorder_qty"])

    again = await http.post(
        "/api/v1/business-insights/reorder-requests", headers=headers, json={}
    )
    assert again.status_code == 200, again.text
    assert again.json()["created_count"] == 0
    assert any(s["reason"] == "open_purchase_request" for s in again.json()["skipped"])


@pytest.mark.asyncio
async def test_reorder_requests_fallback_supplier_and_foreign_404(
    client, db_session: AsyncSession
):
    http, seed = client
    await _make_p1_out_of_stock(db_session, seed, reorder_level=5)
    headers = await _mgr_headers(http, seed)

    foreign = await http.post(
        "/api/v1/business-insights/reorder-requests",
        headers=headers,
        json={"supplier_id": seed["supplier2"].id},
    )
    assert foreign.status_code == 404

    local = await http.post(
        "/api/v1/suppliers", headers=headers, json={"name": "Fallback Supplier"}
    )
    assert local.status_code == 200, local.text
    sid = local.json()["data"]["id"]
    ok = await http.post(
        "/api/v1/business-insights/reorder-requests",
        headers=headers,
        json={"supplier_id": sid, "product_ids": [seed["p1"].id]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["created_count"] == 1
    assert ok.json()["created"][0]["supplier_id"] == sid


@pytest.mark.asyncio
async def test_reorder_requests_cashier_forbidden(client):
    http, seed = client
    headers = await _cashier_headers(http, seed)
    res = await http.post("/api/v1/business-insights/reorder-requests", headers=headers, json={})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_bi_critical_notifications_deduped(client, db_session: AsyncSession):
    http, seed = client
    p1 = await db_session.get(m.Product, seed["p1"].id)
    p1.stock_qty = -3
    await db_session.commit()
    tenant_id = seed["t1"].id
    headers = await _mgr_headers(http, seed)

    first = await http.get("/api/v1/business-insights/overview", headers=headers)
    assert first.status_code == 200, first.text
    second = await http.get("/api/v1/business-insights/overview", headers=headers)
    assert second.status_code == 200, second.text

    notes = (
        await db_session.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "business_insight",
                m.Notification.title == "Negative stock detected",
            )
        )
    ).scalars().all()
    assert len(notes) == 1


@pytest.mark.asyncio
async def test_scan_tenant_business_insights_persists(client, db_session: AsyncSession):
    from app.bi_service import scan_tenant_business_insights

    http, seed = client
    tenant_id = seed["t1"].id
    p1 = await db_session.get(m.Product, seed["p1"].id)
    p1.stock_qty = -2
    await db_session.commit()

    result = await scan_tenant_business_insights(db_session, tenant_id)
    assert result["companies"] >= 1

    rows = (
        await db_session.execute(
            select(m.BusinessInsight).where(
                m.BusinessInsight.tenant_id == tenant_id,
                m.BusinessInsight.insight_type == "negative_stock",
            )
        )
    ).scalars().all()
    assert rows
    assert rows[0].priority == "CRITICAL"


@pytest.mark.asyncio
async def test_reorder_subtracts_open_po_incoming(client, db_session: AsyncSession):
    http, seed = client
    await _make_p1_out_of_stock(db_session, seed, reorder_level=8)
    headers = await _mgr_headers(http, seed)

    supplier = await http.post(
        "/api/v1/suppliers", headers=headers, json={"name": "Incoming Supplier"}
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    po = await http.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 8, "unit_price": 4}],
        },
    )
    assert po.status_code == 200, po.text
    sent = await http.post(
        f"/api/v1/purchasing/orders/{po.json()['data']['id']}/send", headers=headers
    )
    assert sent.status_code == 200, sent.text

    overview = await http.get("/api/v1/business-insights/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    recs = [
        r
        for r in overview.json()["reorder_recommendations"]
        if r["product_id"] == seed["p1"].id
    ]
    assert recs == []


def test_bi_ui_history_settings_and_incoming():
    from pathlib import Path

    page_path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "app"
        / "business-insights"
        / "page.tsx"
    )
    if not page_path.exists():
        pytest.skip("frontend tree is not mounted in this test environment")
    page = page_path.read_text(encoding="utf-8")
    assert "Insight history" in page
    assert "Threshold settings" in page
    assert "pending_incoming_qty" in page
    assert "/business-insights/history" in page
    assert "Save thresholds" in page
