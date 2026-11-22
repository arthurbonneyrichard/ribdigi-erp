"""FMCG optional manufacturing: recipes, production orders, costing, wastage, tracing, switch."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

X = "/api/v1/fmcg/manufacturing"


async def _admin(ac, seed, db_session, on=True):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    if on:
        assert (await ac.put(f"{X}/settings", headers=h, json={"enabled": True})).status_code == 200
    return h


async def _user(ac, db_session, seed, email, role, tenant="t1", slug="alpha"):
    db_session.add(m.User(tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
                          role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug=slug)


async def _p(db_session, seed, name, stock=0, cost=0, batches=False):
    p = m.Product(tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"K{uuid4().hex[:7]}", cost_price=cost,
                  selling_price=9, stock_qty=stock, is_active=True, tracks_batches=batches)
    db_session.add(p)
    await db_session.commit()
    return p.id


async def _recipe(ac, h, db_session, seed, shelf=None):
    juice = await _p(db_session, seed, "Juice", batches=True)
    sugar = await _p(db_session, seed, "Sugar", stock=100, cost=4)
    bottle = await _p(db_session, seed, "Bottle", stock=200, cost=1)
    body = {"product_id": juice, "name": "Juice 10", "output_qty": 10, "lines": [
        {"component_id": sugar, "quantity": 2, "wastage_pct": 10}, {"component_id": bottle, "quantity": 10}]}
    if shelf:
        body["shelf_life_days"] = shelf
    r = await ac.post(f"{X}/boms", headers=h, json=body)
    assert r.status_code == 200, r.text
    return r.json()["data"], juice, sugar, bottle


async def _order(ac, h, bom, qty=100):
    r = await ac.post(f"{X}/orders", headers=h, json={"bom_id": bom["id"], "planned_qty": qty})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _stock(db_session, pid):
    db_session.expire_all()
    p = await db_session.get(m.Product, pid)
    return float(p.stock_qty), float(p.cost_price)


@pytest.mark.asyncio
async def test_module_is_off_until_switched_on(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session, on=False)
    assert (await ac.get(f"{X}/settings", headers=h)).json()["data"]["enabled"] is False
    for call in (ac.get(f"{X}/boms", headers=h), ac.get(f"{X}/orders", headers=h), ac.get(f"{X}/report", headers=h)):
        r = await call
        assert r.status_code == 409 and r.json()["detail"]["code"] == "MODULE_OFF"
    p = await _p(db_session, seed, "X")
    assert (await ac.post(f"{X}/boms", headers=h, json={"product_id": p, "name": "Recipe", "lines": [{"component_id": p, "quantity": 1}]})).status_code == 409
    await ac.put(f"{X}/settings", headers=h, json={"enabled": True})
    assert (await ac.get(f"{X}/boms", headers=h)).status_code == 200


@pytest.mark.asyncio
async def test_recipe_rules_and_standard_cost(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    bom, juice, sugar, bottle = await _recipe(ac, h, db_session, seed)
    assert bom["standard_material_cost"] == round(2 * 1.1 * 4 + 10 * 1, 2) and bom["standard_unit_cost"] == round((8.8 + 10) / 10, 4)
    bad = [
        {"product_id": juice, "name": "Self", "lines": [{"component_id": juice, "quantity": 1}]},
        {"product_id": juice, "name": "Empty", "lines": []},
        {"product_id": juice, "name": "Dup", "lines": [{"component_id": sugar, "quantity": 1}, {"component_id": sugar, "quantity": 2}]},
    ]
    for body in bad:
        assert (await ac.post(f"{X}/boms", headers=h, json=body)).status_code == 422
    assert (await ac.post(f"{X}/boms", headers=h, json={"product_id": juice, "name": "Ghost", "lines": [{"component_id": str(uuid4()), "quantity": 1}]})).status_code == 404
    r = await ac.put(f"{X}/boms/{bom['id']}", headers=h, json={"name": "Juice 20", "output_qty": 20, "lines": [{"component_id": sugar, "quantity": 4}]})
    assert r.status_code == 200 and r.json()["data"]["output_qty"] == 20 and len(r.json()["data"]["lines"]) == 1
    await _order(ac, h, bom)
    r = await ac.put(f"{X}/boms/{bom['id']}", headers=h, json={"name": "Changed", "output_qty": 5, "lines": [{"component_id": sugar, "quantity": 1}]})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "RECIPE_IN_USE"
    assert (await ac.patch(f"{X}/boms/{bom['id']}", headers=h, json={"is_active": False})).json()["data"]["is_active"] is False
    assert (await ac.post(f"{X}/orders", headers=h, json={"bom_id": bom["id"], "planned_qty": 10})).status_code == 409


@pytest.mark.asyncio
async def test_start_checks_materials(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    bom, juice, sugar, bottle = await _recipe(ac, h, db_session, seed)
    big = await _order(ac, h, bom, qty=1000)  # needs 220 sugar, 1000 bottles
    check = (await ac.get(f"{X}/orders/{big['id']}/check", headers=h)).json()["data"]
    assert check["enough"] is False and {r["short_by"] for r in check["materials"]} == {120.0, 800.0}
    r = await ac.post(f"{X}/orders/{big['id']}/start", headers=h)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "MATERIALS_SHORT"
    ok = await _order(ac, h, bom, qty=100)
    assert (await ac.post(f"{X}/orders/{ok['id']}/complete", headers=h, json={"produced_qty": 100})).status_code == 409  # not started
    assert (await ac.post(f"{X}/orders/{ok['id']}/start", headers=h)).json()["data"]["status"] == "in_progress"
    assert (await ac.post(f"{X}/orders/{ok['id']}/start", headers=h)).status_code == 409


@pytest.mark.asyncio
async def test_completion_moves_stock_costs_and_books_overhead(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    bom, juice, sugar, bottle = await _recipe(ac, h, db_session, seed, shelf=180)
    o = await _order(ac, h, bom, qty=100)
    await ac.post(f"{X}/orders/{o['id']}/start", headers=h)
    r = await ac.post(f"{X}/orders/{o['id']}/complete", headers=h, json={
        "produced_qty": 100, "overheads": [{"kind": "labour", "amount": 40, "pay_method": "cash"}, {"kind": "power", "amount": 20, "pay_method": "payable"}]})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["status"] == "completed" and d["material_cost"] == 188 and d["overhead_cost"] == 60 and d["unit_cost"] == 2.48
    assert d["batch_number"] == d["order_number"] and d["expiry_date"] == (date.today() + timedelta(days=180)).isoformat()
    assert d["wastage_cost"] == 0
    assert await _stock(db_session, sugar) == (78.0, 4.0) and await _stock(db_session, bottle) == (100.0, 1.0)
    assert await _stock(db_session, juice) == (100.0, 2.48)
    batch = (await db_session.execute(m.ProductBatch.__table__.select().where(m.ProductBatch.product_id == juice))).first()
    assert float(batch.quantity) == 100 and batch.batch_number == d["order_number"]
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2) and tb["total_debit"] >= 60
    assert (await ac.post(f"{X}/orders/{o['id']}/complete", headers=h, json={"produced_qty": 100})).status_code == 409


@pytest.mark.asyncio
async def test_wastage_weighted_cost_trace_and_qc_hold(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    bom, juice, sugar, bottle = await _recipe(ac, h, db_session, seed)
    s_batch = m.ProductBatch(tenant_id=seed["t1"].id, product_id=sugar, batch_number="SUG-1", quantity=100, expiry_date=datetime.utcnow() + timedelta(days=200))
    db_session.add(s_batch)
    await db_session.commit()
    # Existing finished stock at another cost makes the new cost a weighted average.
    prod = await db_session.get(m.Product, juice)
    prod.stock_qty, prod.cost_price = 100, 2.0
    await db_session.commit()
    o = await _order(ac, h, bom, qty=100)
    await ac.post(f"{X}/orders/{o['id']}/start", headers=h)
    r = await ac.post(f"{X}/orders/{o['id']}/complete", headers=h, json={
        "produced_qty": 100, "batch_number": "JUICE-A1", "hold_for_qc": True,
        "materials": [{"component_id": sugar, "actual_qty": 25}], "overheads": [{"kind": "labour", "amount": 60, "pay_method": "bank_transfer"}]})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["material_cost"] == 200 and d["unit_cost"] == 2.6  # (25 x 4 + 100 x 1 + 60) / 100
    assert await _stock(db_session, juice) == (200.0, 2.3)  # (100 x 2.00 + 100 x 2.60) / 200
    sug = [x for x in d["materials"] if x["component_id"] == sugar][0]
    assert sug["standard"] == 22 and sug["actual"] == 25 and sug["variance"] == 3
    assert d["wastage_cost"] == 12 and d["wastage_pct"] == 6.4
    assert d["trace"] == [{"component": sug["component"], "batch_number": "SUG-1", "quantity": 25.0}] or any(t["batch_number"] == "SUG-1" for t in d["trace"])
    assert d["held_for_qc"] is True
    held = (await ac.get("/api/v1/fmcg/batches?status=held", headers=h)).json()["data"]["batches"]
    assert [b["batch_number"] for b in held] == ["JUICE-A1"]
    rep = (await ac.get(f"{X}/report", headers=h)).json()["data"]
    assert rep["orders"][0]["yield_pct"] == 100.0 and rep["by_product"][0]["average_unit_cost"] == 2.6


@pytest.mark.asyncio
async def test_completion_validation_and_cancel(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    bom, juice, sugar, bottle = await _recipe(ac, h, db_session, seed)
    o = await _order(ac, h, bom, qty=100)
    await ac.post(f"{X}/orders/{o['id']}/start", headers=h)
    for body in ({"produced_qty": 100, "materials": [{"component_id": str(uuid4()), "actual_qty": 1}]},
                 {"produced_qty": 100, "materials": [{"component_id": sugar, "actual_qty": 500}]}):
        assert (await ac.post(f"{X}/orders/{o['id']}/complete", headers=h, json=body)).status_code in (409, 422)
    assert (await ac.post(f"{X}/orders/{o['id']}/complete", headers=h, json={"produced_qty": 100, "overheads": [{"kind": "tea", "amount": 5, "pay_method": "cash"}]})).status_code == 422
    # A failed completion leaves stock untouched.
    assert await _stock(db_session, sugar) == (100.0, 4.0) and (await _stock(db_session, juice))[0] == 0
    assert (await ac.post(f"{X}/orders/{o['id']}/cancel", headers=h, json={"reason": "!"})).status_code == 422
    assert (await ac.post(f"{X}/orders/{o['id']}/cancel", headers=h, json={"reason": "Machine broke down"})).json()["data"]["status"] == "cancelled"
    assert (await ac.post(f"{X}/orders/{o['id']}/start", headers=h)).status_code == 409
    assert len((await ac.get(f"{X}/orders?status=cancelled", headers=h)).json()["data"]) == 1


@pytest.mark.asyncio
async def test_manufacturing_roles_and_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    bom, juice, sugar, bottle = await _recipe(ac, h, db_session, seed)
    o = await _order(ac, h, bom)
    rep = await _user(ac, db_session, seed, "rep@alpha.example.com", "fmcg_rep")
    assert (await ac.get(f"{X}/boms", headers=rep)).status_code == 403
    assert (await ac.put(f"{X}/settings", headers=rep, json={"enabled": False})).status_code == 403
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    other = await _user(ac, db_session, seed, "admin@beta.example.com", "company_admin", tenant="t2", slug="beta")
    assert (await ac.get(f"{X}/settings", headers=other)).json()["data"]["enabled"] is False  # the switch is per company
    await ac.put(f"{X}/settings", headers=other, json={"enabled": True})
    assert (await ac.get(f"{X}/orders/{o['id']}", headers=other)).status_code == 404
    assert (await ac.post(f"{X}/orders/{o['id']}/start", headers=other)).status_code == 404
    assert (await ac.post(f"{X}/orders", headers=other, json={"bom_id": bom["id"], "planned_qty": 5})).status_code == 404
    assert (await ac.put(f"{X}/boms/{bom['id']}", headers=other, json={"name": "Stolen", "lines": [{"component_id": sugar, "quantity": 1}]})).status_code == 404
    assert (await ac.get(f"{X}/boms", headers=other)).json()["data"] == []
