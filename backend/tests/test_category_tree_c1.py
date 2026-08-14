"""Category tree hierarchy (BR-5.1)."""

from __future__ import annotations

import pyotp
import pytest

from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_category_tree_list_path_and_depth(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    parent = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "TREE-FOOD", "name": "Tree Food"},
    )
    assert parent.status_code == 200, parent.text
    pid = parent.json()["data"]["id"]
    assert parent.json()["data"]["depth"] == 0
    assert parent.json()["data"]["path"] == "Tree Food"

    child = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "TREE-DRINK", "name": "Soft Drinks", "parent_id": pid},
    )
    assert child.status_code == 200, child.text
    cid = child.json()["data"]["id"]
    assert child.json()["data"]["depth"] == 1
    assert child.json()["data"]["path"] == "Tree Food › Soft Drinks"

    grand = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "TREE-COLA", "name": "Colas", "parent_id": cid},
    )
    assert grand.status_code == 200, grand.text
    gid = grand.json()["data"]["id"]
    assert grand.json()["data"]["path"] == "Tree Food › Soft Drinks › Colas"
    assert grand.json()["data"]["depth"] == 2

    listed = await ac.get("/api/v1/catalog/categories", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()["data"]
    by_id = {r["id"]: r for r in rows}
    assert by_id[gid]["path"] == "Tree Food › Soft Drinks › Colas"
    # Tree order: parent before descendants
    ids = [r["id"] for r in rows]
    assert ids.index(pid) < ids.index(cid) < ids.index(gid)


@pytest.mark.asyncio
async def test_category_reparent_and_cycle_guard(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    a = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "CYC-A", "name": "Cycle A"},
    )
    b = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "CYC-B", "name": "Cycle B", "parent_id": a.json()["data"]["id"]},
    )
    c = await ac.post(
        "/api/v1/catalog/categories",
        headers=headers,
        json={"code": "CYC-C", "name": "Cycle C", "parent_id": b.json()["data"]["id"]},
    )
    assert a.status_code == 200 and b.status_code == 200 and c.status_code == 200
    aid, bid, cid = a.json()["data"]["id"], b.json()["data"]["id"], c.json()["data"]["id"]

    # Cannot parent A under its descendant C
    cycle = await ac.patch(
        f"/api/v1/catalog/categories/{aid}",
        headers=headers,
        json={"parent_id": cid},
    )
    assert cycle.status_code == 400, cycle.text
    assert "cycle" in cycle.text.lower()

    self_parent = await ac.patch(
        f"/api/v1/catalog/categories/{bid}",
        headers=headers,
        json={"parent_id": bid},
    )
    assert self_parent.status_code == 400

    # Valid reparent: move C under A
    ok = await ac.patch(
        f"/api/v1/catalog/categories/{cid}",
        headers=headers,
        json={"parent_id": aid},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["parent_id"] == aid
    assert ok.json()["data"]["path"] == "Cycle A › Cycle C"

    # Clear parent → root
    root = await ac.patch(
        f"/api/v1/catalog/categories/{cid}",
        headers=headers,
        json={"parent_id": None},
    )
    assert root.status_code == 200
    assert root.json()["data"]["parent_id"] is None
    assert root.json()["data"]["depth"] == 0
