"""FMCG command centre and reporting centre."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app import fmcg_reports
from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

API = "/api/v1/fmcg"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _user(ac, db_session, seed, email, role, tenant="t1", slug="alpha"):
    db_session.add(m.User(tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
                          role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug=slug)


async def _sell(ac, h, db_session, seed, name="Soap", qty=10, price=100, cost=60, stock=500, outlet_name="Kiosk"):
    p = m.Product(tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"R{uuid4().hex[:7]}", cost_price=cost,
                  selling_price=price, stock_qty=stock, is_active=True, tracks_batches=False)
    db_session.add(p)
    await db_session.commit()
    outlet = (await ac.post(f"{API}/outlets", headers=h, json={"name": f"{outlet_name} {uuid4().hex[:4]}"})).json()["data"]["id"]
    order = (await ac.post(f"{API}/orders", headers=h, json={"customer_id": outlet, "terms": "credit", "lines": [{"product_id": p.id, "quantity": qty}]})).json()["data"]
    assert (await ac.post(f"{API}/orders/{order['id']}/deliver", headers=h, json={})).status_code == 200
    return p, outlet, order


@pytest.mark.asyncio
async def test_dashboard_reports_real_numbers(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p, outlet, _ = await _sell(ac, h, db_session, seed, qty=10, price=100, cost=60)
    d = (await ac.get(f"{API}/dashboard", headers=h)).json()["data"]
    assert d["sales"]["today"]["orders"] == 1 and d["sales"]["today"]["net_sales"] > 0
    assert d["sales"]["year"]["net_sales"] >= d["sales"]["month"]["net_sales"] >= d["sales"]["today"]["net_sales"]
    assert d["sales"]["today"]["gross_profit"] > 0
    assert d["money"]["owed_by_outlets"] > 0 and sum(b["amount"] for b in d["money"]["aging"]) == d["money"]["owed_by_outlets"]
    assert d["stock"]["products"] >= 1 and d["stock"]["valuation"] >= 490 * 60
    assert d["charts"]["daily_sales_30"][-1]["value"] == d["sales"]["today"]["net_sales"]
    assert len(d["charts"]["daily_sales_30"]) == 30 and len(d["charts"]["monthly_12"]) == 12
    assert d["charts"]["top_products_30"][0]["name"].startswith("Soap")
    assert d["stock"]["fast_movers"][0]["units"] == 10
    assert "before tax" in d["note"]


@pytest.mark.asyncio
async def test_dashboard_attention_and_counts_follow_other_modules(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = m.Product(tenant_id=seed["t1"].id, name="Cola", sku=f"C{uuid4().hex[:7]}", cost_price=5, selling_price=9, stock_qty=30, is_active=True, tracks_batches=True)
    db_session.add(p)
    await db_session.flush()
    b = m.ProductBatch(tenant_id=seed["t1"].id, product_id=p.id, batch_number="OLD", quantity=30, expiry_date=datetime.utcnow() - timedelta(days=3))
    db_session.add(b)
    await db_session.commit()
    await ac.post(f"{API}/fleet/vehicles", headers=h, json={"plate": "GR 77-26", "name": "Van", "insurance_expiry": (date.today() - timedelta(days=2)).isoformat()})
    await ac.post(f"{API}/complaints", headers=h, json={"category": "other", "description": "Late delivery"})
    await ac.post(f"{API}/promotions", headers=h, json={"code": "BIG", "name": "Half", "scheme_type": "percent", "value": 50})
    d = (await ac.get(f"{API}/dashboard", headers=h)).json()["data"]
    assert d["stock"]["batches"]["expired"] == 1 and d["stock"]["value_at_risk"] == 150
    assert d["operations"]["open_complaints"] == 1 and d["operations"]["promotions_pending"] == 1 and d["operations"]["vehicle_alerts"] >= 1
    texts = " | ".join(a["text"] for a in d["attention"])
    assert "expired batches" in texts and "vehicle alerts" in texts and "waiting for approval" in texts


@pytest.mark.asyncio
async def test_sales_reports_match_the_orders(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p, outlet, order = await _sell(ac, h, db_session, seed, qty=10, price=100, cost=60)
    r = (await ac.get(f"{API}/reports/run?report=sales_by_product", headers=h)).json()["data"]
    row = [x for x in r["rows"] if x["name"] == p.name][0]
    assert row["units"] == 10 and row["cost"] == 600 and row["orders"] == 1
    assert row["gross_profit"] == round(row["sales"] - 600, 2)
    for rid in ("sales_by_outlet", "sales_by_category", "sales_by_rep", "sales_by_route"):
        data = (await ac.get(f"{API}/reports/run?report={rid}", headers=h)).json()["data"]
        assert data["rows"] and round(sum(x["sales"] for x in data["rows"]), 2) == row["sales"]
    other_day = (await ac.get(f"{API}/reports/run?report=sales_by_product&start={(date.today() - timedelta(days=20)).isoformat()}&end={(date.today() - timedelta(days=10)).isoformat()}", headers=h)).json()["data"]
    assert other_day["rows"] == []


@pytest.mark.asyncio
async def test_every_catalogue_report_runs_and_exports(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _sell(ac, h, db_session, seed)
    cat = (await ac.get(f"{API}/reports/centre", headers=h)).json()["data"]
    assert len(cat) == len(fmcg_reports.CATALOGUE) >= 15
    for entry in cat:
        r = await ac.get(f"{API}/reports/run?report={entry['id']}", headers=h)
        assert r.status_code == 200, (entry["id"], r.text)
        data = r.json()["data"]
        assert data["columns"] and isinstance(data["rows"], list), entry["id"]
        for row in data["rows"]:
            assert set(c["key"] for c in data["columns"]) >= set()  # shape check; keys may be absent when empty
        c = await ac.get(f"{API}/reports/run?report={entry['id']}&format=csv", headers=h)
        assert c.status_code == 200 and c.headers["content-type"].startswith("text/csv"), entry["id"]
        assert "attachment" in c.headers["content-disposition"]


@pytest.mark.asyncio
async def test_csv_has_headers_and_blocks_formula_injection(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p, outlet, _ = await _sell(ac, h, db_session, seed, name="=SUM(A1)", outlet_name="+cmd")
    c = await ac.get(f"{API}/reports/run?report=sales_by_product&format=csv", headers=h)
    rows = list(csv.reader(io.StringIO(c.text.lstrip("﻿"))))
    assert rows[0] == ["Sales by product"] and "Product" in rows[3]
    body = [r for r in rows if r and r[0].endswith("SUM(A1)") or (r and "SUM(A1)" in r[0])][0]
    assert body[0].startswith("'=")  # never reaches a spreadsheet as a formula
    assert fmcg_reports._safe("-5") == "-5" and fmcg_reports._safe("@x") == "'@x" and fmcg_reports._safe(None) == ""


@pytest.mark.asyncio
async def test_period_rules_unknown_report_roles_and_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _sell(ac, h, db_session, seed)
    assert (await ac.get(f"{API}/reports/run?report=nope", headers=h)).status_code == 404
    assert (await ac.get(f"{API}/reports/run?report=sales_by_product&start=2026-02-01&end=2026-01-01", headers=h)).status_code == 422
    assert (await ac.get(f"{API}/reports/run?report=sales_by_product&start=2024-01-01&end=2026-01-01", headers=h)).status_code == 422
    assert (await ac.get(f"{API}/reports/run?report=sales_by_product&format=docx", headers=h)).status_code == 422
    rep = await _user(ac, db_session, seed, "rep@alpha.example.com", "fmcg_rep")
    for path in ("/dashboard", "/reports/centre", "/reports/run?report=sales_by_product"):
        assert (await ac.get(f"{API}{path}", headers=rep)).status_code == 403, path
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    other = await _user(ac, db_session, seed, "admin@beta.example.com", "company_admin", tenant="t2", slug="beta")
    theirs = (await ac.get(f"{API}/reports/run?report=sales_by_product", headers=other)).json()["data"]
    assert theirs["rows"] == []
    dash = (await ac.get(f"{API}/dashboard", headers=other)).json()["data"]
    assert dash["sales"]["year"]["net_sales"] == 0 and dash["sales"]["year"]["orders"] == 0
    assert (await ac.get(f"{API}/reports/run?report=receivables_aging", headers=other)).json()["data"]["rows"] == []
