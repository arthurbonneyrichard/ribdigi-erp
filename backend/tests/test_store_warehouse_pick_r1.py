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


async def _admin_headers(ac, seed):
    import pyotp

    from tests.conftest import auth_headers

    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code)


@pytest.mark.asyncio
async def test_own_warehouse_replaces_unused_store_default(client):
    """A new store gets WH-<code>; linking the owner's own warehouse replaces it while it is unused."""
    ac, seed = client
    admin = await _admin_headers(ac, seed)
    store = await ac.post("/api/v1/stores", headers=admin, json={"code": "RPL", "name": "Replace Store"})
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]
    own = await ac.post("/api/v1/warehouses", headers=admin, json={"code": "RPL-MAIN", "name": "Back room", "store_id": store_id})
    assert own.status_code == 200, own.text
    whs = (await ac.get("/api/v1/warehouses", headers=admin)).json()["data"]
    linked = [w["code"] for w in whs if w.get("store_id") == store_id]
    assert linked == ["RPL-MAIN"]


@pytest.mark.asyncio
async def test_second_warehouse_blocked_when_default_holds_stock(client):
    ac, seed = client
    admin = await _admin_headers(ac, seed)
    store = await ac.post("/api/v1/stores", headers=admin, json={"code": "BLK", "name": "Block Store"})
    assert store.status_code == 200, store.text
    store_id = store.json()["data"]["id"]
    default = next(w for w in (await ac.get("/api/v1/warehouses", headers=admin)).json()["data"] if w.get("store_id") == store_id)
    stocked = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=admin,
        json={"product_id": seed["p1"].id, "quantity": 3, "warehouse_id": default["id"]},
    )
    assert stocked.status_code == 200, stocked.text
    second = await ac.post("/api/v1/warehouses", headers=admin, json={"code": "BLK-2", "name": "Second", "store_id": store_id})
    assert second.status_code == 400, second.text
