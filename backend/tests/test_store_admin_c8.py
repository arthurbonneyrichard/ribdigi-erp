"""Stage 1 C8 — store manager, linked warehouse, operating hours."""

from __future__ import annotations

import pytest

from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_store_list_includes_warehouse_and_manager_hours(client):
    ac, seed = client
    headers = await _mgr(ac)

    created = await ac.post(
        "/api/v1/stores",
        headers=headers,
        json={
            "code": "C8ST",
            "name": "C8 Store",
            "manager_id": seed["mgr1"].id,
            "operating_hours": {"mon": "08:00-17:00", "fri": "09:00-13:00", "note": "Closed Sun"},
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["manager_id"] == seed["mgr1"].id
    assert data["warehouse_id"]
    assert data["warehouse_code"]
    assert data["operating_hours"]["mon"] == "08:00-17:00"

    listed = await ac.get("/api/v1/stores", headers=headers)
    assert listed.status_code == 200, listed.text
    row = next(s for s in listed.json()["data"] if s["id"] == data["id"])
    assert row["warehouse_id"] == data["warehouse_id"]
    assert row["manager_id"] == seed["mgr1"].id

    patched = await ac.patch(
        f"/api/v1/stores/{data['id']}",
        headers=headers,
        json={
            "manager_id": seed["u1"].id,
            "operating_hours": {"tue": "10:00-16:00"},
            "is_active": True,
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["manager_id"] == seed["u1"].id
    assert patched.json()["data"]["operating_hours"]["tue"] == "10:00-16:00"
    assert patched.json()["data"]["warehouse_id"] == data["warehouse_id"]

    foreign = await ac.patch(
        f"/api/v1/stores/{data['id']}",
        headers=headers,
        json={"manager_id": seed["u2"].id},
    )
    assert foreign.status_code == 404, foreign.text
