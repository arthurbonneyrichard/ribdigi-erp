"""FMCG territories and outlet visits from the rep's phone location (simulated coordinates)."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from app import fmcg_field
from app import models as m
from tests.conftest import auth_headers
from tests.test_fmcg_selling import _admin, _order, _outlet, _product

F = "/api/v1/fmcg"
SHOP = (5.6037, -0.1870)  # Accra


def _north(metres: float) -> tuple[float, float]:
    return SHOP[0] + metres / 111_320, SHOP[1]


async def _route(ac, h, code=None):
    r = await ac.post(f"{F}/routes", headers=h, json={"code": code or f"R{uuid4().hex[:5]}", "name": "Osu run"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


async def _rep(ac, h, email="rep@alpha.example.com"):
    r = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": email, "full_name": "Kofi Rep", "password": "SecurePass123!", "role": "fmcg_rep"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"], await auth_headers(ac, email=email, tenant_slug="alpha")


async def _field(ac, seed, db_session):
    h = await _admin(ac, seed, db_session)
    route = await _route(ac, h)
    other_route = await _route(ac, h)
    rep_id, rep = await _rep(ac, h)
    terr = await ac.post(
        f"{F}/territories", headers=h,
        json={"code": "osu", "name": "Osu", "daily_visit_target": 20, "route_ids": [route], "rep_user_ids": [rep_id]},
    )
    assert terr.status_code == 200, terr.text
    assert terr.json()["data"]["code"] == "OSU" and terr.json()["data"]["reps"][0]["id"] == rep_id
    mine = await _outlet(ac, h, route_id=route)
    theirs = await _outlet(ac, h, route_id=other_route)
    return h, rep, rep_id, route, mine, theirs


def test_distance_is_metres():
    lat, lon = _north(250)
    assert 245 < fmcg_field.distance_m(lat, lon, *SHOP) < 255


@pytest.mark.asyncio
async def test_rep_sees_and_visits_only_their_territory(client, seeded, db_session):
    ac, seed = client
    h, rep, _rep_id, _route_id, mine, theirs = await _field(ac, seed, db_session)
    outlets = (await ac.get(f"{F}/my-outlets", headers=rep)).json()["data"]
    assert [o["id"] for o in outlets] == [mine]
    assert len((await ac.get(f"{F}/my-outlets", headers=h)).json()["data"]) >= 2
    far = await ac.post(f"{F}/visits/check-in", headers=rep, json={"outlet_id": theirs, "latitude": SHOP[0], "longitude": SHOP[1], "accuracy_m": 10})
    assert far.status_code == 403 and far.json()["detail"]["code"] == "OUTSIDE_TERRITORY"
    # Reps cannot change territories.
    assert (await ac.post(f"{F}/territories", headers=rep, json={"code": "X", "name": "X"})).status_code == 403


@pytest.mark.asyncio
async def test_first_close_fix_maps_the_outlet_and_later_visits_measure_distance(client, seeded, db_session):
    ac, seed = client
    h, rep, _rep_id, _route_id, mine, _theirs = await _field(ac, seed, db_session)
    first = await ac.post(f"{F}/visits/check-in", headers=rep, json={"outlet_id": mine, "latitude": SHOP[0], "longitude": SHOP[1], "accuracy_m": 12})
    assert first.status_code == 200, first.text
    v = first.json()["data"]
    assert v["set_outlet_location"] and v["flags"] == []
    # One open visit at a time.
    assert (await ac.post(f"{F}/visits/check-in", headers=rep, json={"outlet_id": mine})).status_code == 409
    no_reason = await ac.post(f"{F}/visits/{v['id']}/check-out", headers=rep, json={"outcome": "no_order"})
    assert no_reason.status_code == 422
    done = await ac.post(f"{F}/visits/{v['id']}/check-out", headers=rep, json={"outcome": "no_order", "no_order_reason": "has_stock"})
    assert done.status_code == 200 and done.json()["data"]["checked_out"]
    db_session.expire_all()
    party = await db_session.get(m.Party, mine)
    assert abs(float(party.latitude) - SHOP[0]) < 1e-6

    lat, lon = _north(800)
    second = (await ac.post(f"{F}/visits/check-in", headers=rep, json={"outlet_id": mine, "latitude": lat, "longitude": lon, "accuracy_m": 500})).json()["data"]
    assert "far" in second["flags"] and "rough_gps" in second["flags"] and 790 < second["distance_m"] < 810
    assert not second["set_outlet_location"]


@pytest.mark.asyncio
async def test_rough_fix_does_not_map_and_no_gps_is_flagged(client, seeded, db_session):
    ac, seed = client
    h, rep, _rep_id, _route_id, mine, _theirs = await _field(ac, seed, db_session)
    rough = (await ac.post(f"{F}/visits/check-in", headers=rep, json={"outlet_id": mine, "latitude": SHOP[0], "longitude": SHOP[1], "accuracy_m": 120})).json()["data"]
    assert rough["flags"] == ["outlet_unmapped"] and not rough["set_outlet_location"]
    await ac.post(f"{F}/visits/{rough['id']}/check-out", headers=rep, json={"outcome": "closed"})
    blind = (await ac.post(f"{F}/visits/check-in", headers=rep, json={"outlet_id": mine})).json()["data"]
    assert blind["flags"] == ["no_gps"]


@pytest.mark.asyncio
async def test_order_outcome_links_the_booked_order_and_coverage_counts_it(client, seeded, db_session):
    ac, seed = client
    h, rep, rep_id, route, mine, _theirs = await _field(ac, seed, db_session)
    stop = await ac.post(f"{F}/routes/{route}/stops", headers=h, json={"customer_id": mine, "sequence": 1})
    assert stop.status_code == 200, stop.text
    visit = (await ac.post(f"{F}/visits/check-in", headers=rep, json={"outlet_id": mine, "latitude": SHOP[0], "longitude": SHOP[1], "accuracy_m": 8})).json()["data"]
    product = await _product(db_session, seed)
    order = await _order(ac, rep, mine, product, qty=3)
    done = (await ac.post(f"{F}/visits/{visit['id']}/check-out", headers=rep, json={"outcome": "order"})).json()["data"]
    assert done["order_id"] == order["id"] and "order_not_booked" not in done["flags"]

    cov = (await ac.get(f"{F}/coverage", headers=h)).json()["data"]
    row = next(r for r in cov["reps"] if r["user_id"] == rep_id)
    assert row["visits"] == 1 and row["orders"] == 1 and row["strike_rate"] == 100
    route_row = next(r for r in cov["routes"] if r["route_id"] == route)
    assert route_row["planned"] == 1 and route_row["visited"] == 1 and route_row["missed"] == []
    assert (await ac.get(f"{F}/coverage", headers=rep)).status_code == 403
    mine_only = (await ac.get(f"{F}/visits", headers=rep)).json()["data"]
    assert [v["id"] for v in mine_only] == [visit["id"]]

    report = (await ac.get(f"{F}/territories/report?period={datetime.utcnow():%Y-%m}", headers=h)).json()["data"]
    osu = next(t for t in report if t["code"] == "OSU")
    assert osu["outlets"] == 1 and osu["outlets_visited"] == 1 and osu["coverage_pct"] == 100 and osu["visits"] == 1


@pytest.mark.asyncio
async def test_a_route_moves_between_territories(client, seeded, db_session):
    ac, seed = client
    h, _rep, _rep_id, route, _mine, _theirs = await _field(ac, seed, db_session)
    other = await ac.post(f"{F}/territories", headers=h, json={"code": "LAB", "name": "Labadi", "route_ids": [route]})
    assert other.status_code == 200
    rows = {t["code"]: t for t in (await ac.get(f"{F}/territories", headers=h)).json()["data"]}
    assert rows["OSU"]["routes"] == [] and rows["LAB"]["routes"][0]["id"] == route
    assert (await ac.post(f"{F}/territories", headers=h, json={"code": "osu", "name": "Again"})).status_code == 409
