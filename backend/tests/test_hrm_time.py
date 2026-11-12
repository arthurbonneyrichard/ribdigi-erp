"""HRM time: daily sheet arithmetic, QR codes, overtime pay, clocking at sites, corrections,
overtime into payroll, and ZKTeco links (terminal push and BioTime pull, simulated)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select

from app import hrm_biometric, hrm_time
from app import models as m
from tests.conftest import auth_headers
from tests.test_hrm_desk import _admin, _even, _person

UTC = ZoneInfo("UTC")


def _at(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time())


# --- Pure ----------------------------------------------------------------------------------


def test_day_sheet_late_early_overtime():
    day = date(2026, 11, 2)
    window = hrm_time.shift_window("08:00", "17:00", day, UTC)
    late = hrm_time.compute_day(
        events=[("in", _at(day, "08:25")), ("out", _at(day, "16:30"))], window=window, break_minutes=60,
        grace_minutes=10, hours_per_day=8, on_leave=False, now=_at(day, "20:00"),
    )
    assert (late.status, late.late_minutes, late.early_minutes, late.worked_minutes, late.overtime_minutes) == ("late", 25, 30, 425, 0)
    long = hrm_time.compute_day(
        events=[("in", _at(day, "07:55")), ("out", _at(day, "19:00"))], window=window, break_minutes=60,
        grace_minutes=10, hours_per_day=8, on_leave=False, now=_at(day, "20:00"),
    )
    assert (long.status, long.late_minutes, long.overtime_minutes) == ("present", 0, 125)  # 605 worked - 480 expected
    absent = hrm_time.compute_day(events=[], window=window, break_minutes=60, grace_minutes=10, hours_per_day=8, on_leave=False, now=_at(day, "09:00"))
    assert absent.status == "absent"
    leave = hrm_time.compute_day(events=[], window=window, break_minutes=60, grace_minutes=10, hours_per_day=8, on_leave=True, now=_at(day, "09:00"))
    assert leave.status == "on_leave"


def test_night_shift_crosses_midnight():
    day = date(2026, 11, 2)
    start, end = hrm_time.shift_window("22:00", "06:00", day, UTC)
    assert end - start == timedelta(hours=8)
    sheet = hrm_time.compute_day(
        events=[("in", _at(day, "21:58")), ("out", _at(day + timedelta(days=1), "06:00"))], window=(start, end),
        break_minutes=0, grace_minutes=5, hours_per_day=8, on_leave=False, now=_at(day + timedelta(days=1), "07:00"),
    )
    assert sheet.worked_minutes == 482 and sheet.overtime_minutes == 2 and sheet.status == "present"


def test_qr_code_changes_and_stays_valid_one_window():
    now = datetime(2026, 11, 2, 9, 0, 0)
    code = hrm_time.qr_code("secret", now)
    assert hrm_time.qr_valid("secret", code, now + timedelta(minutes=4))
    assert hrm_time.qr_valid("secret", code, now + timedelta(minutes=6))  # previous window still accepted
    assert not hrm_time.qr_valid("secret", code, now + timedelta(minutes=12))
    assert not hrm_time.qr_valid("other", code, now)


def test_overtime_pay_decimal():
    # 3,520 basic / (22 days x 8 h) = 20.0000 an hour; 90 minutes at 1.5 = 45.00
    hourly, amount = hrm_time.overtime_pay(Decimal("3520"), 22, Decimal("8"), Decimal("1.5"), 90)
    assert hourly == Decimal("20.0000") and amount == Decimal("45.00")


# --- API -----------------------------------------------------------------------------------

pytestmark_async = pytest.mark.asyncio


async def _staff(ac, h, email):
    r = await ac.post(
        "/api/v1/users", headers=h,
        json={"email": email, "full_name": email.split("@")[0].title(), "password": "SecurePass123!", "role": "hrm_employee"},
    )
    assert r.status_code == 200, r.text
    return await auth_headers(ac, email=email, tenant_slug="alpha")


@pytestmark_async
async def test_clock_needs_a_site_when_switched_on(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    await _person(ac, h, email="clock@alpha.example.com")
    staff = await _staff(ac, h, "clock@alpha.example.com")
    site = (await ac.post("/api/v1/hrm/sites", headers=h, json={"name": "Osu shop", "latitude": 5.556, "longitude": -0.1969, "radius_m": 100})).json()["data"]
    assert (await ac.patch("/api/v1/hrm/settings", headers=h, json={"clock_needs_site": True})).status_code == 200

    far = await ac.post("/api/v1/hrm/me/clock", headers=staff, json={"kind": "in", "latitude": 5.60, "longitude": -0.20, "accuracy_m": 15})
    assert far.status_code == 422
    rough = await ac.post("/api/v1/hrm/me/clock", headers=staff, json={"kind": "in", "latitude": 5.556, "longitude": -0.1969, "accuracy_m": 900})
    assert rough.status_code == 422
    near = await ac.post("/api/v1/hrm/me/clock", headers=staff, json={"kind": "in", "latitude": 5.5561, "longitude": -0.1969, "accuracy_m": 12})
    assert near.status_code == 200, near.text
    assert near.json()["data"]["site_id"] == site["id"]
    twice = await ac.post("/api/v1/hrm/me/clock", headers=staff, json={"kind": "in", "latitude": 5.5561, "longitude": -0.1969, "accuracy_m": 12})
    assert twice.status_code == 409

    qr = (await ac.get(f"/api/v1/hrm/sites/{site['id']}/qr", headers=h)).json()["data"]["code"]
    bad_qr = await ac.post("/api/v1/hrm/me/clock", headers=staff, json={"kind": "out", "qr_code": "ABCDEFGH"})
    assert bad_qr.status_code == 422
    out = await ac.post("/api/v1/hrm/me/clock", headers=staff, json={"kind": "out", "qr_code": qr})
    assert out.status_code == 200 and out.json()["data"]["source"] == "qr"
    assert (await ac.get(f"/api/v1/hrm/sites/{site['id']}/qr", headers=staff)).status_code == 403


@pytestmark_async
async def test_roster_sheet_correction_and_overtime_into_payroll(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, basic=3520, allowances=0, email="ot@alpha.example.com")
    staff = await _staff(ac, h, "ot@alpha.example.com")
    shift = (await ac.post("/api/v1/hrm/shifts", headers=h, json={"name": "Day", "starts_at": "08:00", "ends_at": "17:00", "break_minutes": 60})).json()["data"]
    day = date(2026, 10, 5)  # a Monday
    r = await ac.post(
        "/api/v1/hrm/roster", headers=h,
        json={"employee_ids": [person["id"]], "start": "2026-10-05", "end": "2026-10-09", "shift_id": shift["id"]},
    )
    assert r.json()["data"]["days"] == 5
    # HR enters Monday: in 08:30 (late), out 19:00 (overtime 90).
    rec = await ac.post(
        "/api/v1/hrm/time/record", headers=h,
        json={"employee_id": person["id"], "day": day.isoformat(), "in_at": "2026-10-05T08:30:00", "out_at": "2026-10-05T19:00:00", "note": "Terminal was down"},
    )
    assert rec.status_code == 200, rec.text
    board = {row["employee_id"]: row for row in (await ac.get(f"/api/v1/hrm/time/day?day={day}", headers=h)).json()["data"]}
    mine = board[person["id"]]
    assert (mine["status"], mine["late_minutes"], mine["overtime_minutes"]) == ("late", 30, 90)

    # Tuesday: staff forgot to clock; asks for a correction; HR approves.
    ask = await ac.post(
        "/api/v1/hrm/me/clock-corrections", headers=staff,
        json={"day": "2026-10-06", "in_at": "2026-10-06T08:00:00", "out_at": "2026-10-06T17:30:00", "reason": "Forgot to clock"},
    )
    assert ask.status_code == 200, ask.text
    own = await ac.post(f"/api/v1/hrm/time/corrections/{ask.json()['data']['id']}/decide", headers=staff, json={"approve": True})
    assert own.status_code == 403
    ok = await ac.post(f"/api/v1/hrm/time/corrections/{ask.json()['data']['id']}/decide", headers=h, json={"approve": True})
    assert ok.status_code == 200

    month = {row["employee_id"]: row for row in (await ac.get("/api/v1/hrm/time/month?period=2026-10", headers=h)).json()["data"]}
    assert month[person["id"]]["overtime_minutes"] == 120  # 90 + 30
    assert month[person["id"]]["absent_days"] == 3  # Wed-Fri rostered, nothing clocked
    too_much = await ac.post("/api/v1/hrm/time/overtime", headers=h, json={"employee_id": person["id"], "period": "2026-10", "minutes": 500})
    assert too_much.status_code == 422
    approved = await ac.post("/api/v1/hrm/time/overtime", headers=h, json={"employee_id": person["id"], "period": "2026-10", "minutes": 120})
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["amount"] == 60.0  # 20/h x 1.5 x 2 h

    run = (await ac.post("/api/v1/hrm/payroll", headers=h, json={"period": "2026-10"})).json()["data"]
    slip = run["slips"][0]
    assert slip["overtime"] == 60 and slip["gross"] == 3580
    assert slip["ssnit_employee"] == round(3520 * 0.055, 2)  # overtime adds no SSNIT
    assert (await ac.post(f"/api/v1/hrm/payroll/{run['id']}/approve", headers=h)).status_code == 200
    again = await ac.post("/api/v1/hrm/time/overtime", headers=h, json={"employee_id": person["id"], "period": "2026-10", "minutes": 60})
    assert again.status_code == 409
    await _even(ac, h)


@pytestmark_async
async def test_zkteco_terminal_push(client, db_session):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, biometric_id="1007")
    clash = await ac.post("/api/v1/hrm/employees", headers=h, json={"full_name": "Twin", "hired_on": "2024-01-01", "biometric_id": "1007"})
    assert clash.status_code == 409
    link = await ac.post("/api/v1/hrm/biometric", headers=h, json={"kind": "device", "name": "Front door", "device_serial": "CQZ7232060123"})
    assert link.status_code == 200, link.text

    unknown = await ac.get("/iclock/cdata?SN=NOTOURS&options=all")
    assert unknown.status_code == 404
    hello = await ac.get("/iclock/cdata?SN=CQZ7232060123&options=all")
    assert hello.status_code == 200 and "GET OPTION FROM: CQZ7232060123" in hello.text
    lines = "1007\t2026-10-05 08:02:11\t0\t1\t0\t0\n1007\t2026-10-05 17:05:40\t1\t1\t0\t0\n9999\t2026-10-05 08:00:00\t0\t1\n"
    up = await ac.post("/iclock/cdata?SN=CQZ7232060123&table=ATTLOG", content=lines)
    assert up.status_code == 200 and up.text.startswith("OK")
    again = await ac.post("/iclock/cdata?SN=CQZ7232060123&table=ATTLOG", content=lines)
    assert again.status_code == 200
    rows = (await db_session.execute(select(m.HrmClockEvent).where(m.HrmClockEvent.employee_id == person["id"]))).scalars().all()
    assert sorted(r.kind for r in rows) == ["in", "out"]  # stored once, unknown PIN ignored
    assert all(r.source == "biometric" for r in rows)
    assert (await ac.get("/iclock/getrequest?SN=CQZ7232060123")).text == "OK"


@pytestmark_async
async def test_biotime_pull_with_simulated_server(client, db_session, monkeypatch):
    ac, seed = client
    h = await _admin(ac, seed, db_session)
    person = await _person(ac, h, biometric_id="55")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/jwt-api-token-auth/":
            body = json.loads(request.content)
            assert body == {"username": "api", "password": "s3cret"}
            return httpx.Response(200, json={"token": "abc"})
        if request.url.path == "/iclock/api/transactions/":
            seen["auth"] = request.headers.get("authorization")
            page = int(request.url.params.get("page", "1"))
            data = (
                [{"id": 1, "emp_code": "55", "punch_time": "2026-11-02 08:01:00", "punch_state": "0"}]
                if page == 1
                else [{"id": 2, "emp_code": "55", "punch_time": "2026-11-02 17:00:00", "punch_state": "1"}]
            )
            return httpx.Response(200, json={"count": 2, "next": "more" if page == 1 else None, "data": data})
        return httpx.Response(404)

    monkeypatch.setattr(hrm_biometric, "transport", httpx.MockTransport(handler))
    bad = await ac.post("/api/v1/hrm/biometric", headers=h, json={"kind": "biotime", "name": "BioTime", "base_url": "http://169.254.169.254", "username": "api", "password": "x"})
    assert bad.status_code == 422
    link = (
        await ac.post("/api/v1/hrm/biometric", headers=h, json={"kind": "biotime", "name": "BioTime", "base_url": "https://biotime.example.com", "username": "api", "password": "s3cret"})
    ).json()["data"]
    assert "password" not in link and link["has_password"] is True
    synced = await ac.post(f"/api/v1/hrm/biometric/{link['id']}/sync", headers=h)
    assert synced.status_code == 200, synced.text
    assert synced.json()["data"]["counts"] == {"stored": 2}
    assert seen["auth"] == "JWT abc"
    again = await ac.post(f"/api/v1/hrm/biometric/{link['id']}/sync", headers=h)
    assert again.json()["data"]["counts"] == {"duplicate": 2}
    rows = (await db_session.execute(select(m.HrmClockEvent).where(m.HrmClockEvent.employee_id == person["id"]))).scalars().all()
    assert len(rows) == 2
