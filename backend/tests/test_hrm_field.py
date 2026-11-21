"""FMCG field workforce view: field jobs, targets, visits, sales against target."""

from __future__ import annotations

from datetime import datetime

import pytest

from app import models as m
from tests.test_hrm_commission import _setup
from tests.test_hrm_desk import _admin, _person

pytestmark = pytest.mark.asyncio
B = "/api/v1/hrm"


async def test_field_workforce_month(client, db_session):
    ac, seed = client
    h, user, person = await _setup(ac, seed, db_session, "fmcg")
    tid = seed["t1"].id
    outlet = m.Party(tenant_id=tid, kind="customer", name="Outlet", status="active", credit_limit=0)
    terr = m.FmcgTerritory(tenant_id=tid, code="N1", name="North", daily_visit_target=6)
    db_session.add_all([outlet, terr])
    await db_session.flush()
    db_session.add(m.FmcgTerritoryRep(tenant_id=tid, territory_id=terr.id, user_id=user["id"]))
    db_session.add(m.FmcgOrder(
        tenant_id=tid, order_number="FO-9", customer_id=outlet.id, status="delivered", subtotal=2000, discount=0, tax=0,
        total=2000, paid=0, returned=0, cost_of_goods=0, delivered_at=datetime(2026, 10, 12), created_by=user["id"],
    ))
    db_session.add(m.FmcgVisit(tenant_id=tid, outlet_id=outlet.id, user_id=user["id"], checked_in_at=datetime(2026, 10, 12, 9, 0)))
    for d in (12, 13):
        db_session.add(m.HrmAttendance(tenant_id=tid, employee_id=person["id"], day=datetime(2026, 10, d).date(), status="present"))
    await db_session.commit()

    assert (await ac.put(f"{B}/employees/{person['id']}/field-profile", headers=h, json={"field_role": "pilot"})).status_code == 422
    ok = await ac.put(f"{B}/employees/{person['id']}/field-profile", headers=h, json={"field_role": "van_sales", "monthly_sales_target": 4000})
    assert ok.status_code == 200, ok.text
    data = (await ac.get(f"{B}/field-workforce?period=2026-10", headers=h)).json()["data"]
    row = data["staff"][0]
    assert row["field_role"] == "van_sales" and row["territories"] == ["North"]
    assert row["days_present"] == 2 and row["visits_month"] == 1 and row["visit_target"] == 12
    assert row["net_sales"] == 2000 and row["sales_target"] == 4000 and row["achievement_pct"] == 50.0
    assert row["commission"] == 100  # 5% of 2000
    assert data["by_role"] == {"van_sales": 1}


async def test_field_view_is_fmcg_only_and_hides_commission_from_officers(client, db_session):
    ac, seed = client
    h, user, person = await _setup(ac, seed, db_session, "fmcg")
    await ac.put(f"{B}/employees/{person['id']}/field-profile", headers=h, json={"field_role": "rep"})
    from tests.test_hrm_people import _user

    officer = await _user(ac, h, "offf@alpha.example.com", "fmcg_manager")
    row = (await ac.get(f"{B}/field-workforce?period=2026-10", headers=officer)).json()["data"]["staff"][0]
    assert "commission" not in row
    rep = await _user(ac, h, "rep77@alpha.example.com", "fmcg_rep")
    assert (await ac.get(f"{B}/field-workforce", headers=rep)).status_code == 403
    assert (await ac.put(f"{B}/employees/{person['id']}/field-profile", headers=rep, json={"field_role": "rep"})).status_code == 403

    # a retail company has no field workforce
    from tests.conftest import auth_headers, set_tenant_industry

    await set_tenant_industry(db_session, seed["t1"], "retail")
    retail = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get(f"{B}/field-workforce", headers=retail)).status_code == 403
