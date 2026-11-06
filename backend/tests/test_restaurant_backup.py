"""A restaurant comes back from a company backup: its tables, menu, orders and till."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app import backup as backup_svc
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_restaurant_till_shift import _dish, _paid_order


def test_a_company_backup_carries_the_whole_restaurant():
    covered = {model for _name, model in backup_svc.DATASET_SPECS}
    restaurant_models = {
        mapper.class_ for mapper in m.Base.registry.mappers if mapper.class_.__name__.startswith("Restaurant")
    }
    assert restaurant_models <= covered, sorted(c.__name__ for c in restaurant_models - covered)


def test_tables_are_restored_after_the_tables_they_point_at():
    """Restore inserts in list order, so a row must never come before the row it needs."""
    order = {model.__table__.name: index for index, (_name, model) in enumerate(backup_svc.DATASET_SPECS)}
    for name, index in order.items():
        table = m.Base.metadata.tables[name]
        for fk in table.foreign_keys:
            parent = fk.column.table.name
            if parent in order and parent != name and name.startswith("restaurant_"):
                assert order[parent] < index, f"{name} is restored before {parent}"


@pytest.mark.asyncio
async def test_a_restaurant_comes_back_from_a_restore(client, db_session):
    ac, seed = client
    await set_tenant_industry(db_session, seed["t1"], "restaurant")
    admin = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    dish = await _dish(ac, admin, "Jollof", 40)
    opened = await ac.post("/api/v1/restaurant/till/shift/open", headers=admin, json={"opening_cash": 100})
    assert opened.status_code == 200, opened.text
    paid = await _paid_order(ac, admin, dish["id"], "cash")

    payload, counts = await backup_svc.collect_tenant_payload(db_session, seed["t1"].id)
    assert counts["restaurant_orders"] >= 1
    assert counts["restaurant_order_lines"] >= 1
    assert counts["restaurant_till_shifts"] >= 1

    order = await db_session.get(m.RestaurantOrder, paid["id"])
    kept_total = float(order.total_amount)
    order.total_amount = 1
    line = (
        await db_session.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
    ).scalars().first()
    await db_session.delete(line)
    await db_session.commit()

    report = await backup_svc.apply_restore(db_session, seed["t1"].id, json.loads(json.dumps(payload, default=str)))
    await db_session.commit()
    assert report["applied"] is True
    assert report["proof"]["ok"] is True
    await db_session.refresh(order)
    assert float(order.total_amount) == kept_total
    lines = (
        await db_session.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
    ).scalars().all()
    assert len(lines) == 1
