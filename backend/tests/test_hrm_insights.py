"""People signals from plain rules."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app import hrm_insights
from app import models as m
from tests.test_hrm_desk import _admin, _person

pytestmark = pytest.mark.asyncio


def test_bradford():
    assert hrm_insights.bradford(5, 5) == 125
    assert hrm_insights.bradford(10, 10) == 1000


async def test_signals_explain_themselves(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    tid = seed["t1"].id
    ama = await _person(ac, h, full_name="Ama Often", hired_on="2020-01-06")
    await _person(ac, h, full_name="Kofi Fine", hired_on=(date.today() - timedelta(days=30)).isoformat())
    start = date.today() - timedelta(days=200)
    for i in range(6):
        day = start + timedelta(days=14 * i)
        db_session.add(m.HrmLeaveRequest(tenant_id=tid, employee_id=ama["id"], leave_type="sick", starts_on=day, ends_on=day, days=1, status="approved", stage="hr"))
    await db_session.commit()
    rows = (await ac.get("/api/v1/hrm/insights", headers=h)).json()["data"]
    mine = {r["kind"] for r in rows if r["name"] == "Ama Often"}
    assert "absence" in mine and "review" in mine  # 6 spells x 6 days = 216; here since 2020, never reviewed
    assert not [r for r in rows if r["name"] == "Kofi Fine" and r["kind"] in ("absence", "review")]
    assert all("GH" not in r["why"] for r in rows)
