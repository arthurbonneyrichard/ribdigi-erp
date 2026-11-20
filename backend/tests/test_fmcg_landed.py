"""FMCG import shipments: landed cost allocation, accounting, rules."""

from __future__ import annotations

import random
from uuid import uuid4

import pytest

from app import fmcg_landed
from app import models as m
from app.rbac import permissions_for_role
from app.security import hash_password
from tests.conftest import auth_headers, set_tenant_industry

S = "/api/v1/fmcg/shipments"


async def _admin(ac, seed, db_session):
    await set_tenant_industry(db_session, seed["t1"], "fmcg")
    return await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")


async def _user(ac, db_session, seed, email, role, tenant="t1", slug="alpha"):
    db_session.add(m.User(tenant_id=seed[tenant].id, email=email, full_name=role, password_hash=hash_password("SecurePass123!"),
                          role=role, email_verified=True, permissions=permissions_for_role(role), totp_enabled=False))
    await db_session.commit()
    return await auth_headers(ac, email=email, tenant_slug=slug)


async def _product(db_session, seed, stock, cost=10, name="Tin"):
    p = m.Product(tenant_id=seed["t1"].id, name=f"{name} {uuid4().hex[:4]}", sku=f"L{uuid4().hex[:7]}", cost_price=cost,
                  selling_price=30, stock_qty=stock, is_active=True, tracks_batches=False)
    db_session.add(p)
    await db_session.commit()
    return p.id


async def _ship(ac, h, **extra):
    r = await ac.post(S, headers=h, json={"reference": "BL-1001", **extra})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _line(ac, h, sid, pid, qty, value):
    r = await ac.post(f"{S}/{sid}/lines", headers=h, json={"product_id": pid, "quantity": qty, "goods_value": value})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _cost(ac, h, sid, kind, amount, method="cash"):
    r = await ac.post(f"{S}/{sid}/costs", headers=h, json={"kind": kind, "amount": amount, "pay_method": method})
    assert r.status_code == 200, r.text
    return r.json()["data"]


async def _cost_of(db_session, pid):
    db_session.expire_all()
    return float((await db_session.get(m.Product, pid)).cost_price)


def test_spread_is_exact_to_the_cent():
    rnd = random.Random(7)
    for _ in range(500):
        total = rnd.randint(1, 10_000_000)
        weights = [rnd.random() * 1000 for _ in range(rnd.randint(1, 9))]
        parts = fmcg_landed.spread(total, weights)
        assert sum(parts) == total and all(p >= 0 for p in parts)
    assert fmcg_landed.spread(100, [0, 0, 0]) == [34, 33, 33]
    assert fmcg_landed.spread(0, [1, 2]) == [0, 0]


@pytest.mark.asyncio
async def test_costs_are_spread_by_value_and_lift_product_cost(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, b = await _product(db_session, seed, 100), await _product(db_session, seed, 50)
    ship = await _ship(ac, h)
    await _line(ac, h, ship["id"], a, 100, 1000)
    await _line(ac, h, ship["id"], b, 50, 500)
    await _cost(ac, h, ship["id"], "freight", 150, "cash")
    d = await _cost(ac, h, ship["id"], "customs_duty", 150, "payable")
    assert d["total_costs"] == 300 and d["uplift_pct"] == 20.0
    preview = {l["product_id"]: l for l in d["lines"]}
    assert preview[a]["allocated"] == 200 and preview[b]["allocated"] == 100 and preview[a]["landed_unit_cost"] == 12.0
    assert await _cost_of(db_session, a) == 10  # a preview changes nothing
    r = await ac.post(f"{S}/{ship['id']}/allocate", headers=h)
    assert r.status_code == 200, r.text
    done = r.json()["data"]
    assert done["status"] == "allocated" and done["allocated_at"]
    assert await _cost_of(db_session, a) == 12.0 and await _cost_of(db_session, b) == 12.0
    line_a = [l for l in done["lines"] if l["product_id"] == a][0]
    assert line_a["to_stock"] == 200 and line_a["to_cost_of_goods"] == 0 and line_a["cost_before"] == 10 and line_a["cost_after"] == 12
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2) and tb["total_debit"] >= 300
    # Allocated once, and frozen.
    assert (await ac.post(f"{S}/{ship['id']}/allocate", headers=h)).status_code == 409
    assert (await ac.post(f"{S}/{ship['id']}/costs", headers=h, json={"kind": "port", "amount": 5, "pay_method": "cash"})).status_code == 409
    assert (await ac.post(f"{S}/{ship['id']}/cancel", headers=h)).status_code == 409
    assert await _cost_of(db_session, a) == 12.0


@pytest.mark.asyncio
async def test_units_already_sold_take_their_share_to_cost_of_goods(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed, stock=40)  # 100 received, 60 already sold
    ship = await _ship(ac, h)
    await _line(ac, h, ship["id"], p, 100, 1000)
    await _cost(ac, h, ship["id"], "freight", 200, "bank_transfer")
    done = (await ac.post(f"{S}/{ship['id']}/allocate", headers=h)).json()["data"]
    line = done["lines"][0]
    assert line["allocated"] == 200 and line["to_stock"] == 80 and line["to_cost_of_goods"] == 120
    assert await _cost_of(db_session, p) == 12.0  # 10 + 80 / 40 units on hand
    tb = (await ac.get("/api/v1/accounting/trial-balance", headers=h)).json()["data"]
    assert round(tb["total_debit"], 2) == round(tb["total_credit"], 2)


@pytest.mark.asyncio
async def test_quantity_basis_and_validation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    a, b = await _product(db_session, seed, 10), await _product(db_session, seed, 30)
    ship = await _ship(ac, h, basis="quantity")
    assert (await ac.post(f"{S}/{ship['id']}/allocate", headers=h)).status_code == 409  # nothing to allocate
    await _line(ac, h, ship["id"], a, 10, 900)
    d = await _line(ac, h, ship["id"], b, 30, 100)
    assert (await ac.post(f"{S}/{ship['id']}/allocate", headers=h)).status_code == 409  # still no costs
    d = await _cost(ac, h, ship["id"], "other", 40, "cash")
    split = {l["product_id"]: l["allocated"] for l in d["lines"]}
    assert split == {a: 10.0, b: 30.0}  # by units, not by value
    for bad in ({"kind": "gold", "amount": 5, "pay_method": "cash"}, {"kind": "port", "amount": 0, "pay_method": "cash"},
                {"kind": "port", "amount": 5, "pay_method": "barter"}):
        assert (await ac.post(f"{S}/{ship['id']}/costs", headers=h, json=bad)).status_code == 422
    assert (await ac.post(f"{S}/{ship['id']}/lines", headers=h, json={"product_id": str(uuid4()), "quantity": 1, "goods_value": 1})).status_code == 404
    assert (await ac.post(f"{S}/{ship['id']}/lines", headers=h, json={"product_id": a, "quantity": 0, "goods_value": 1})).status_code == 422
    # Lines and costs can be removed while open; a cancelled shipment does nothing.
    cost_id = d["costs"][0]["id"]
    d = (await ac.delete(f"{S}/{ship['id']}/costs/{cost_id}", headers=h)).json()["data"]
    assert d["costs"] == [] and d["total_costs"] == 0
    d = (await ac.delete(f"{S}/{ship['id']}/lines/{d['lines'][0]['id']}", headers=h)).json()["data"]
    assert len(d["lines"]) == 1
    assert (await ac.post(f"{S}/{ship['id']}/cancel", headers=h)).json()["data"]["status"] == "cancelled"
    assert (await ac.post(f"{S}/{ship['id']}/allocate", headers=h)).status_code == 409
    assert await _cost_of(db_session, a) == 10


@pytest.mark.asyncio
async def test_goods_receipt_fills_the_lines_once(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed, 20)
    sup = m.Party(tenant_id=seed["t1"].id, kind="supplier", name="Overseas Foods")
    db_session.add(sup)
    await db_session.flush()
    po = m.PurchaseOrder(tenant_id=seed["t1"].id, po_number=f"PO{uuid4().hex[:6]}", supplier_id=sup.id, status="received")
    db_session.add(po)
    await db_session.flush()
    poi = m.PurchaseOrderItem(tenant_id=seed["t1"].id, purchase_order_id=po.id, product_id=p, quantity=20, received_qty=20, unit_price=15)
    db_session.add(poi)
    await db_session.flush()
    grn = m.GoodsReceipt(tenant_id=seed["t1"].id, grn_number=f"G{uuid4().hex[:6]}", purchase_order_id=po.id, supplier_id=sup.id)
    db_session.add(grn)
    await db_session.flush()
    db_session.add(m.GoodsReceiptItem(tenant_id=seed["t1"].id, goods_receipt_id=grn.id, po_item_id=poi.id, product_id=p, received_qty=20, accepted_qty=18, rejected_qty=2))
    await db_session.commit()
    ship = await _ship(ac, h, grn_id=grn.id)
    assert ship["supplier"] == "Overseas Foods" and len(ship["lines"]) == 1
    assert ship["lines"][0]["quantity"] == 18 and ship["lines"][0]["goods_value"] == 270  # accepted units at the order price
    again = await ac.post(S, headers=h, json={"grn_id": grn.id})
    assert again.status_code == 409
    assert (await ac.post(S, headers=h, json={"grn_id": str(uuid4())})).status_code == 404
    assert (await ac.post(S, headers=h, json={"supplier_id": str(uuid4())})).status_code == 404


@pytest.mark.asyncio
async def test_shipments_roles_and_tenant_isolation(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    p = await _product(db_session, seed, 10)
    ship = await _ship(ac, h)
    await _line(ac, h, ship["id"], p, 10, 100)
    rep = await _user(ac, db_session, seed, "rep@alpha.example.com", "fmcg_rep")
    assert (await ac.get(S, headers=rep)).status_code == 403
    assert (await ac.post(f"{S}/{ship['id']}/allocate", headers=rep)).status_code == 403
    await set_tenant_industry(db_session, seed["t2"], "fmcg")
    other = await _user(ac, db_session, seed, "admin@beta.example.com", "company_admin", tenant="t2", slug="beta")
    assert (await ac.get(f"{S}/{ship['id']}", headers=other)).status_code == 404
    assert (await ac.post(f"{S}/{ship['id']}/costs", headers=other, json={"kind": "port", "amount": 5, "pay_method": "cash"})).status_code == 404
    assert (await ac.post(f"{S}/{ship['id']}/allocate", headers=other)).status_code == 404
    assert (await ac.post(f"{S}/{ship['id']}/lines", headers=other, json={"product_id": p, "quantity": 1, "goods_value": 1})).status_code == 404
    assert (await ac.get(S, headers=other)).json()["data"] == []
