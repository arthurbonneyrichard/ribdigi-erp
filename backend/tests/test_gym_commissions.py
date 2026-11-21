"""Gym trainer commissions: accrue once per completed session, report, mark paid."""

from __future__ import annotations

from datetime import date

import pytest

from tests.conftest import auth_headers, set_tenant_industry
from tests.test_gym_desk import _admin, _open
from tests.test_gym_stage1 import _active, _soon, _trainer


@pytest.mark.asyncio
async def test_commission_accrues_once_per_completed_session_and_can_be_paid(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _open(ac, h)
    trainer, member = await _trainer(ac, h), await _active(ac, h)  # session price 80
    assert (await ac.post(f"/api/v1/gym/trainers/{trainer['id']}/commission", headers=h, json={"commission_pct": 150})).status_code == 422
    assert (await ac.post(f"/api/v1/gym/trainers/{trainer['id']}/commission", headers=h, json={"commission_pct": 25})).status_code == 200
    s = (await ac.post("/api/v1/gym/training-sessions", headers=h, json={"trainer_id": trainer["id"], "member_id": member["id"], "starts_at": _soon(3), "minutes": 60})).json()["data"]
    cancelled = (await ac.post("/api/v1/gym/training-sessions", headers=h, json={"trainer_id": trainer["id"], "member_id": member["id"], "starts_at": _soon(6), "minutes": 60})).json()["data"]
    await ac.post(f"/api/v1/gym/training-sessions/{cancelled['id']}", headers=h, json={"status": "cancelled"})
    assert (await ac.post(f"/api/v1/gym/training-sessions/{s['id']}", headers=h, json={"status": "completed"})).status_code == 200
    assert (await ac.post(f"/api/v1/gym/training-sessions/{s['id']}", headers=h, json={"status": "completed"})).status_code == 409
    rep = (await ac.get("/api/v1/gym/reports/commissions", headers=h)).json()["data"]
    assert rep["total_accrued"] == 20.0 and rep["trainers"][0]["sessions"] == 1  # 25% of 80, cancelled earns nothing
    today = date.today().isoformat()
    body = {"trainer_id": trainer["id"], "start_date": today, "end_date": today, "reference": "PAY-NOV-01"}
    paid = await ac.post("/api/v1/gym/commissions/pay", headers=h, json=body)
    assert paid.status_code == 200 and paid.json()["data"]["paid"] == 20.0
    assert (await ac.post("/api/v1/gym/commissions/pay", headers=h, json=body)).status_code == 409
    rep = (await ac.get("/api/v1/gym/reports/commissions", headers=h)).json()["data"]
    assert rep["total_accrued"] == 0 and rep["total_paid"] == 20.0


@pytest.mark.asyncio
async def test_commissions_are_manager_only_and_gym_only(client, seeded, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await set_tenant_industry(db_session, seed["t1"], "bakery")
    h = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    assert (await ac.get("/api/v1/gym/reports/commissions", headers=h)).status_code == 403
