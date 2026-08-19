"""Stage 1 C9 — warehouse admin create/update with audit."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


@pytest.mark.asyncio
async def test_warehouse_admin_create_update_and_list(client, db_session):
    ac, seed = client
    headers = await _mgr(ac)

    created = await ac.post(
        "/api/v1/warehouses",
        headers=headers,
        json={
            "code": "C9WH",
            "name": "C9 Cold Room",
            "warehouse_type": "cold",
            "manager_id": seed["mgr1"].id,
            "address": "Cold lane",
            "capacity": 120,
        },
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["warehouse_type"] == "cold"
    assert data["manager_id"] == seed["mgr1"].id
    assert float(data["capacity"]) == 120

    listed = await ac.get("/api/v1/warehouses", headers=headers)
    assert listed.status_code == 200
    assert any(w["id"] == data["id"] for w in listed.json()["data"])

    updated = await ac.patch(
        f"/api/v1/warehouses/{data['id']}",
        headers=headers,
        json={"name": "C9 Cold Room 2", "is_active": False, "capacity": 150},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["name"] == "C9 Cold Room 2"
    assert updated.json()["data"]["is_active"] is False
    assert float(updated.json()["data"]["capacity"]) == 150

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.entity_id == data["id"],
                m.AuditLog.action.in_(["warehouse_created", "warehouse_updated"]),
            )
        )
    ).scalars().all()
    actions = {a.action for a in audits}
    assert "warehouse_created" in actions
    assert "warehouse_updated" in actions
