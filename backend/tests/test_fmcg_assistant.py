"""FMCG assistant: every answer comes from real figures, forecasts are labelled, nothing is changed."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app import fmcg_assistant as asst
from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"
ASK = f"{API}/assistant/ask"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _ask(ac, h, q):
    r = await ac.post(ASK, headers=h, json={"question": q})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _sell(ac, h, db_session, seed, name="Soap", qty=10, price=100, cost=60):
    p = m.Product(tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"A{uuid4().hex[:7]}", cost_price=cost, selling_price=price,
                  stock_qty=500, is_active=True, tracks_batches=False)
    db_session.add(p)
    await db_session.commit()
    outlet = (await ac.post(f"{API}/outlets", headers=h, json={"name": f"Kiosk {uuid4().hex[:4]}"})).json()["data"]["id"]
    order = (await ac.post(f"{API}/orders", headers=h, json={"customer_id": outlet, "terms": "credit", "lines": [{"product_id": p.id, "quantity": qty}]})).json()["data"]
    assert (await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})).status_code == 200
    return p, outlet


def test_questions_map_to_the_right_intent():
    cases = {
        "What were my total sales today?": "sales_total", "Which products made the highest profit?": "profit_products",
        "Which products are expiring?": "expiring", "What should I reorder?": "reorder", "Which customers owe me money?": "owed",
        "Which distributors are performing poorly?": "distributors", "Which salesperson made the most sales?": "top_rep",
        "Which products have not sold for 90 days?": "not_selling", "Which warehouse has excess stock?": "overstock",
        "What was my van sales performance?": "van", "What is my total inventory valuation?": "valuation",
        "How much did I spend on delivery?": "delivery_cost", "Which products are likely to run out next month?": "run_out",
        "Which route sold the most?": "top_route", "Tell me a joke": None,
    }
    for q, want in cases.items():
        assert asst.match_intent(q) == want, q
    for q in asst.EXAMPLES:
        assert asst.match_intent(q) is not None, q


def test_period_words():
    today = date(2026, 11, 20)
    assert asst.parse_period("sales today", today)[:3] == (today, today, "today")
    assert asst.parse_period("sales yesterday", today)[:2] == (date(2026, 11, 19), date(2026, 11, 19))
    assert asst.parse_period("this month", today)[:2] == (date(2026, 11, 1), today)
    assert asst.parse_period("last month", today)[:2] == (date(2026, 10, 1), date(2026, 10, 31))
    assert asst.parse_period("last 14 days", today)[:2] == (date(2026, 11, 7), today)
    assert asst.parse_period("this year", today)[0] == date(2026, 1, 1)
    start, end, label, stated = asst.parse_period("sales", today)
    assert stated is False and label == "the last 30 days" and (end - start).days == 29
    assert asst.parse_period("last 999 days", today)[3] is False


@pytest.mark.asyncio
async def test_sales_and_profit_answers_match_the_reports(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p, outlet = await _sell(ac, h, db_session, seed, qty=10, price=100, cost=60)
    a = await _ask(ac, h, "What were my total sales today?")
    n = (await ac.get(f"{API}/dashboard", headers=h)).json()["data"]["sales"]["today"]
    assert a["intent"] == "sales_total" and a["kind"] == "actual" and f"{n['net_sales']:,.2f}" in a["answer"] and "1 delivered orders" in a["answer"]
    assert a["period"]["label"] == "today" and a["source"] and a["link"]
    a = await _ask(ac, h, "Which products made the highest profit this month?")
    assert p.name in a["answer"] and a["table"]["rows"][0]["name"] == p.name and a["table"]["rows"][0]["gross_profit"] > 0
    unstated = await _ask(ac, h, "Show me sales")
    assert "did not say which period" in unstated["answer"]
    for q, key in (("Which salesperson made the most sales this month?", "No rep"), ("Which route sold the most this month?", "No route"), ("Which outlets bought the most in the last 30 days?", None)):
        a = await _ask(ac, h, q)
        assert a["table"]["rows"], q
        if key:
            assert key in a["answer"]


@pytest.mark.asyncio
async def test_owed_valuation_expiry_and_dead_stock(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p, outlet = await _sell(ac, h, db_session, seed)
    a = await _ask(ac, h, "Which customers owe me money?")
    assert a["intent"] == "owed" and "owe you" in a["answer"]
    assert a["table"]["rows"][0]["total"] > 0
    stale = m.Product(tenant_id=seed["t1"].id, name="Old stock", sku=f"O{uuid4().hex[:7]}", cost_price=5, selling_price=9, stock_qty=40, is_active=True, tracks_batches=True)
    db_session.add(stale)
    await db_session.flush()
    db_session.add(m.ProductBatch(tenant_id=seed["t1"].id, product_id=stale.id, batch_number="OLD1", quantity=40, expiry_date=datetime.utcnow() - timedelta(days=2)))
    await db_session.commit()
    a = await _ask(ac, h, "Which products are expiring?")
    assert "1 batches have expired" in a["answer"] and "OLD1" in a["answer"]
    a = await _ask(ac, h, "What is my total inventory valuation?")
    dash = (await ac.get(f"{API}/dashboard", headers=h)).json()["data"]["stock"]
    assert f"{dash['valuation']:,.2f}" in a["answer"]
    a = await _ask(ac, h, "Which products have not sold for 90 days?")
    assert "Old stock" in a["answer"]


@pytest.mark.asyncio
async def test_forecast_answers_are_labelled_estimates(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = m.Product(tenant_id=seed["t1"].id, name="Rice", sku=f"R{uuid4().hex[:7]}", cost_price=5, selling_price=9, stock_qty=30, is_active=True, tracks_batches=False)
    db_session.add(p)
    await db_session.flush()
    outlet = m.Party(tenant_id=seed["t1"].id, kind="customer", name="Hist shop")
    db_session.add(outlet)
    await db_session.flush()
    for back in range(1, 61):
        o = m.FmcgOrder(tenant_id=seed["t1"].id, order_number=f"H{uuid4().hex[:8]}", customer_id=outlet.id, status="delivered",
                        delivered_at=datetime.combine(date.today() - timedelta(days=back), datetime.min.time()) + timedelta(hours=9))
        db_session.add(o)
        await db_session.flush()
        db_session.add(m.FmcgOrderLine(tenant_id=seed["t1"].id, order_id=o.id, product_id=p.id, name="Rice", quantity=10))
    await db_session.commit()
    for q, intent in (("Which products are likely to run out next month?", "run_out"), ("What should I reorder?", "reorder"), ("Which products have too much stock?", "overstock")):
        a = await _ask(ac, h, q)
        assert a["intent"] == intent and a["kind"] == "estimate" and "estimate" in a["answer"].lower() and "Demand forecast" in a["source"]
    a = await _ask(ac, h, "What should I reorder?")
    assert "Rice" in a["answer"] and a["table"]["rows"][0]["suggested_order"] > 0
    a = await _ask(ac, h, "Which products are likely to run out next month?")
    assert "Rice" in a["answer"]


@pytest.mark.asyncio
async def test_unknown_questions_do_not_get_made_up_answers_and_nothing_changes(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _sell(ac, h, db_session, seed)
    before = [(await db_session.execute(select(func.count()).select_from(t))).scalar_one() for t in (m.StockMovement, m.JournalEntry, m.FmcgOrder)]
    a = await _ask(ac, h, "Delete all my customers and approve every promotion")
    assert a["intent"] is None and a["examples"] and "$" not in a["answer"]
    a = await _ask(ac, h, "Write off the expired stock")
    assert a["intent"] == "expiring" or a["intent"] is None
    for q in asst.EXAMPLES:
        await _ask(ac, h, q)
    db_session.expire_all()
    after = [(await db_session.execute(select(func.count()).select_from(t))).scalar_one() for t in (m.StockMovement, m.JournalEntry, m.FmcgOrder)]
    assert after == before  # the assistant only reads
    assert (await ac.post(ASK, headers=h, json={"question": "hi"})).status_code == 422
    assert len((await ac.get(f"{API}/assistant/examples", headers=h)).json()["data"]) == len(asst.EXAMPLES)


@pytest.mark.asyncio
async def test_assistant_roles_and_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _sell(ac, h, db_session, seed, name="Alpha Secret Tin")
    for email, role, tenant, slug in (("rep@alpha.example.com", "fmcg_rep", "t1", "alpha"), ("admin@beta.example.com", "company_admin", "t2", "beta")):
        if tenant == "t2":
            await set_tenant_industry(db_session, seed["t2"], "fmcg")
        db_session.add(m.User(tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
                              role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    rep = await auth_headers(ac, email="rep@alpha.example.com", tenant_slug="alpha")
    other = await auth_headers(ac, email="admin@beta.example.com", tenant_slug="beta")
    assert (await ac.post(ASK, headers=rep, json={"question": "What were my total sales today?"})).status_code == 403
    assert (await ac.get(f"{API}/assistant/examples", headers=rep)).status_code == 403
    for q in ("Which products made the highest profit this month?", "Which customers owe me money?", "What were my total sales this year?", "Which products have not sold for 90 days?"):
        a = await _ask(ac, other, q)
        assert "Alpha Secret Tin" not in str(a)
    assert "0 delivered orders" in (await _ask(ac, other, "What were my total sales this year?"))["answer"]
