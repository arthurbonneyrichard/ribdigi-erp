"""Gym equipment assets: purchase details and straight-line depreciation."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import gym_assets
from app import models as m
from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin


def test_depreciation_is_straight_line_by_full_months_and_stops_at_zero():
    bought = date(2025, 1, 15)
    assert gym_assets.months_between(bought, date(2025, 2, 14)) == 0  # not a full month yet
    assert gym_assets.months_between(bought, date(2025, 2, 15)) == 1
    assert gym_assets.book_value(1200, 12, bought, date(2025, 7, 15)) == (600.0, 600.0)
    assert gym_assets.book_value(1200, 12, bought, date(2030, 1, 1)) == (1200.0, 0.0)  # never below zero
    assert gym_assets.book_value(1000, 3, bought, bought) == (0.0, 1000.0)


@pytest.mark.asyncio
async def test_asset_details_report_totals_and_warranty(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    eq = (await ac.post("/api/v1/gym/equipment", headers=h, json={"name": "Treadmill"})).json()["data"]
    retired = (await ac.post("/api/v1/gym/equipment", headers=h, json={"name": "Old bike"})).json()["data"]
    url = f"/api/v1/gym/equipment/{eq['id']}/asset"
    bought = (date.today() - timedelta(days=95)).isoformat()
    assert (await ac.post(url, headers=h, json={"purchase_date": (date.today() + timedelta(days=1)).isoformat(), "purchase_cost": 100, "useful_life_months": 12})).status_code == 422
    assert (await ac.post(url, headers=h, json={"purchase_date": bought, "purchase_cost": 0, "useful_life_months": 12})).status_code == 422
    assert (await ac.post(url, headers=h, json={"purchase_date": bought, "purchase_cost": 100, "useful_life_months": 12, "warranty_until": (date.today() - timedelta(days=200)).isoformat()})).status_code == 422
    ok = await ac.post(url, headers=h, json={"purchase_date": bought, "purchase_cost": 1200, "useful_life_months": 12, "warranty_until": (date.today() + timedelta(days=30)).isoformat(), "supplier_name": "Fit Supplies"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["under_warranty"] is True
    # an item that is retired is listed but left out of the totals
    await ac.post(f"/api/v1/gym/equipment/{retired['id']}/asset", headers=h, json={"purchase_date": bought, "purchase_cost": 500, "useful_life_months": 24})
    row = await db_session.get(m.GymEquipment, retired["id"])
    row.status = "retired"
    await db_session.commit()
    rep = (await ac.get("/api/v1/gym/reports/equipment-assets", headers=h)).json()["data"]
    assert rep["total_cost"] == 1200.0 and rep["total_depreciation"] + rep["total_book_value"] == 1200.0
    assert len(rep["items"]) == 2 and "Nothing is posted" in rep["note"]
    later = (await ac.get(f"/api/v1/gym/reports/equipment-assets?as_of={(date.today() + timedelta(days=800)).isoformat()}", headers=h)).json()["data"]
    assert later["total_book_value"] == 0.0


@pytest.mark.asyncio
async def test_assets_are_tenant_scoped_gym_only_and_manager_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    theirs = m.GymEquipment(tenant_id=seed["t2"].id, name="Theirs", status="available")
    db_session.add(theirs)
    await db_session.commit()
    body = {"purchase_date": date.today().isoformat(), "purchase_cost": 10, "useful_life_months": 12}
    assert (await ac.post(f"/api/v1/gym/equipment/{theirs.id}/asset", headers=h, json=body)).status_code == 404
    assert (await ac.get("/api/v1/gym/reports/equipment-assets", headers=h)).json()["data"]["items"] == []
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/gym/reports/equipment-assets", headers=h)).status_code == 403
