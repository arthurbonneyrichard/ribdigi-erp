"""POS store→warehouse pick when an older link left two warehouses on one store."""

import pytest

from app import models as m
from app import stores as stores_svc


async def _store(db, tenant_id: str, code: str) -> m.Store:
    store = m.Store(tenant_id=tenant_id, name=f"Store {code}", code=code)
    db.add(store)
    await db.flush()
    return store


@pytest.mark.asyncio
async def test_two_linked_warehouses_prefers_store_default(db_session, seeded):
    tid = seeded["t1"].id
    store = await _store(db_session, tid, "MAIN")
    # "WH-BACK" sorts before "WH-MAIN"; the store's own default must still win.
    db_session.add_all([
        m.Warehouse(tenant_id=tid, store_id=store.id, name="Back Store", code="WH-BACK"),
        m.Warehouse(tenant_id=tid, store_id=store.id, name="Main Store Warehouse", code="WH-MAIN"),
    ])
    await db_session.flush()

    wh = await stores_svc.warehouse_for_store(db_session, tid, store.id)
    assert wh.code == "WH-MAIN"


@pytest.mark.asyncio
async def test_two_linked_warehouses_prefers_active(db_session, seeded):
    tid = seeded["t1"].id
    store = await _store(db_session, tid, "EAST")
    db_session.add_all([
        m.Warehouse(tenant_id=tid, store_id=store.id, name="Old", code="WH-EAST", is_active=False),
        m.Warehouse(tenant_id=tid, store_id=store.id, name="New", code="WH-EAST-2"),
    ])
    await db_session.flush()

    wh = await stores_svc.warehouse_for_store(db_session, tid, store.id)
    assert wh.code == "WH-EAST-2"


@pytest.mark.asyncio
async def test_single_linked_warehouse_is_returned(db_session, seeded):
    tid = seeded["t1"].id
    store = await _store(db_session, tid, "WEST")
    db_session.add(m.Warehouse(tenant_id=tid, store_id=store.id, name="Only", code="WH-ANY"))
    await db_session.flush()

    wh = await stores_svc.warehouse_for_store(db_session, tid, store.id)
    assert wh.code == "WH-ANY"
