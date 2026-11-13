"""HRM time routes: shifts, roster, sites and QR codes, clocking, the daily sheet, clock
corrections, overtime, and ZKTeco BioTime / terminal links. `hrm.job` area "attendance"
covers HR officers; overtime approval needs "payroll" (an HR manager). Staff use /me/clock."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm as svc
from app import hrm_biometric as bio
from app import hrm_time as time_svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hrm", tags=["hrm"])
# ZKTeco terminals call these at the server root, with no login (see hrm_biometric).
device_router = APIRouter(tags=["hrm-devices"])

HHMM = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
Period = Annotated[str, Field(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class ShiftBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=2, max_length=80)]
    starts_at: HHMM
    ends_at: HHMM
    break_minutes: Annotated[int, Field(ge=0, le=240)] = 0
    grace_minutes: Annotated[int, Field(ge=0, le=120)] = 10


class RosterBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_ids: list[UuidIdValue] = Field(min_length=1, max_length=500)
    start: date
    end: date
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=lambda: [0, 1, 2, 3, 4], min_length=1, max_length=7)
    # None takes the people off the roster on those days.
    shift_id: UuidIdValue | None = None


class SiteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=2, max_length=120)]
    latitude: Annotated[float, Field(ge=-90, le=90)] | None = None
    longitude: Annotated[float, Field(ge=-180, le=180)] | None = None
    radius_m: Annotated[int, Field(ge=20, le=5000)] = 150


class ClockBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["in", "out"]
    latitude: Annotated[float, Field(ge=-90, le=90)] | None = None
    longitude: Annotated[float, Field(ge=-180, le=180)] | None = None
    accuracy_m: Annotated[float, Field(ge=0, le=100000)] | None = None
    qr_code: Annotated[str, Field(min_length=8, max_length=8)] | None = None


class HrRecordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: UuidIdValue
    day: date
    in_at: datetime | None = None
    out_at: datetime | None = None
    note: Annotated[str, Field(min_length=3, max_length=255)]


class CorrectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    day: date
    in_at: datetime | None = None
    out_at: datetime | None = None
    reason: Annotated[str, Field(min_length=3, max_length=255)]


class DecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool
    note: Annotated[str, Field(min_length=1, max_length=255)] | None = None


class OvertimeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: UuidIdValue
    period: Period
    minutes: Annotated[int, Field(ge=1, le=60 * 24 * 31)]


class LinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["biotime", "device"]
    name: Annotated[str, Field(min_length=2, max_length=120)]
    base_url: Annotated[str, Field(min_length=8, max_length=255)] | None = None
    username: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    password: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    device_serial: Annotated[str, Field(min_length=4, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")] | None = None
    site_id: UuidIdValue | None = None


def _r():
    return Depends(require_permission("hrm", "read"))


def _w():
    return Depends(require_permission("hrm", "write"))


# --- Shifts, roster, sites -----------------------------------------------------------------


@router.get("/shifts")
async def shifts(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    return _env([time_svc.serialize_shift(r) for r in await time_svc.list_shifts(db, claims["tenant_id"])])


@router.post("/shifts")
async def shift_add(payload: ShiftBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    row = await time_svc.add_shift(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(time_svc.serialize_shift(row), "Shift saved")


@router.post("/shifts/{shift_id}/retire")
async def shift_retire(shift_id: UuidIdValue, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    row = await time_svc.retire_shift(db, claims["tenant_id"], shift_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(time_svc.serialize_shift(row), "Shift switched off")


@router.get("/roster")
async def roster(start: date, end: date, claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    return _env(await time_svc.roster_between(db, claims["tenant_id"], start, end))


@router.post("/roster")
async def roster_set(payload: RosterBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    n = await time_svc.set_roster(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"days": n}, f"Roster saved for {n} person-day(s)")


@router.get("/sites")
async def sites(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    return _env([time_svc.serialize_site(r) for r in await time_svc.list_sites(db, claims["tenant_id"])])


@router.post("/sites")
async def site_add(payload: SiteBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    row = await time_svc.add_site(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(time_svc.serialize_site(row), "Site saved")


@router.get("/sites/{site_id}/qr")
async def site_qr(site_id: UuidIdValue, claims=_r(), db: AsyncSession = Depends(get_db)):
    """The code to show on a screen at the site. It changes every five minutes."""
    svc.job(claims, "attendance")
    return _env(await time_svc.site_qr(db, claims["tenant_id"], site_id))


# --- Clocking ------------------------------------------------------------------------------


@router.post("/me/clock")
async def my_clock(payload: ClockBody, request: Request, claims=_w(), db: AsyncSession = Depends(get_db)):
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    row = await time_svc.clock(
        db, claims["tenant_id"], me, payload, user_id=claims.get("sub"), device=request.headers.get("user-agent")
    )
    await db.commit()
    return _env(time_svc.serialize_event(row), "Clocked in" if row.kind == "in" else "Clocked out")


@router.get("/me/time")
async def my_time(claims=_r(), db: AsyncSession = Depends(get_db)):
    tid = claims["tenant_id"]
    me = await svc.employee_for_user(db, tid, claims.get("sub"))
    today = date.today()
    last = await time_svc._last_event(db, me.id)
    return _env(
        {
            "today": await time_svc.sheet_for(db, tid, me, today),
            "clocked_in": bool(last and last.kind == "in" and (datetime.utcnow() - last.at).total_seconds() < 20 * 3600),
            "roster": [r for r in await time_svc.roster_between(db, tid, today, date.fromordinal(today.toordinal() + 13)) if r["employee_id"] == me.id],
            "corrections": [await time_svc.serialize_correction(db, r) for r in await time_svc.list_corrections(db, tid, employee_id=me.id)][:10],
        }
    )


@router.post("/me/clock-corrections")
async def my_correction(payload: CorrectionBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    row = await time_svc.request_correction(db, claims["tenant_id"], me, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await time_svc.serialize_correction(db, row), "Sent to HR")


@router.get("/time/day")
async def time_day(day: date, claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    return _env(await time_svc.day_board(db, claims["tenant_id"], day))


@router.post("/time/record")
async def time_record(payload: HrRecordBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    await time_svc.hr_record(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(None, "Times saved")


@router.get("/time/corrections")
async def time_corrections(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    rows = await time_svc.list_corrections(db, claims["tenant_id"])
    return _env([await time_svc.serialize_correction(db, r) for r in rows])


@router.post("/time/corrections/{correction_id}/decide")
async def time_correction_decide(correction_id: UuidIdValue, payload: DecideBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    row = await time_svc.decide_correction(
        db, claims["tenant_id"], correction_id, approve=payload.approve, note=payload.note, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(await time_svc.serialize_correction(db, row), "Saved")


@router.get("/time/month")
async def time_month(period: Annotated[str, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")], claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    rows = await time_svc.month_summary(db, claims["tenant_id"], period)
    if not svc.sees_pay(claims):
        for row in rows:
            if row.get("overtime_approved"):
                row["overtime_approved"].pop("amount", None)
    return _env(rows)


@router.post("/time/overtime")
async def time_overtime(payload: OvertimeBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    row = await time_svc.approve_overtime(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"minutes": row.minutes, "amount": float(row.amount), "period": row.period}, "Overtime approved for that month's payroll")


# --- ZKTeco links --------------------------------------------------------------------------


@router.get("/biometric")
async def links(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    return _env([bio.serialize_link(r) for r in await bio.list_links(db, claims["tenant_id"])])


@router.post("/biometric")
async def link_add(payload: LinkBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")  # it stores a password and feeds pay
    row = await bio.add_link(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(bio.serialize_link(row), "Linked")


@router.post("/biometric/{link_id}/off")
async def link_off(link_id: UuidIdValue, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    row = await bio.unlink(db, claims["tenant_id"], link_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(bio.serialize_link(row), "Switched off")


@router.post("/biometric/{link_id}/sync")
async def link_sync(link_id: UuidIdValue, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    body = await bio.sync_biotime(db, claims["tenant_id"], link_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(body, body["result"])


@router.post("/biometric/{link_id}/check")
async def link_check(link_id: UuidIdValue, claims=_w(), db: AsyncSession = Depends(get_db)):
    """Setup check: signs in / reads without storing punches; lists PIN mismatches."""
    svc.job(claims, "attendance")
    body = await bio.check(db, claims["tenant_id"], link_id)
    return _env(body, body.get("status", ""))


# --- Terminal push (no login: the terminal is found by its serial number) ------------------


@device_router.get("/iclock/cdata", response_class=PlainTextResponse)
async def zk_handshake(SN: str = "", db: AsyncSession = Depends(get_db)):  # noqa: N803 - ZKTeco's name
    link = await bio.device_for(db, SN)
    await db.commit()
    if link is None:
        return PlainTextResponse("UNKNOWN DEVICE", status_code=404)
    return PlainTextResponse(bio.handshake_text(link.device_serial))


@device_router.post("/iclock/cdata", response_class=PlainTextResponse)
async def zk_upload(request: Request, SN: str = "", table: str = "", db: AsyncSession = Depends(get_db)):  # noqa: N803
    link = await bio.device_for(db, SN)
    if link is None:
        return PlainTextResponse("UNKNOWN DEVICE", status_code=404)
    raw = (await request.body())[:1_000_000].decode("utf-8", errors="replace")
    stored = 0
    if table.upper() == "ATTLOG":
        counts = await bio.push_attlog(db, link, raw)
        stored = sum(counts.values())
    await db.commit()
    # The terminal moves on when it reads OK; other tables (user info, photos) are not used.
    return PlainTextResponse(f"OK: {stored}")


@device_router.get("/iclock/getrequest", response_class=PlainTextResponse)
async def zk_poll(SN: str = "", db: AsyncSession = Depends(get_db)):  # noqa: N803
    link = await bio.device_for(db, SN)
    await db.commit()
    return PlainTextResponse("OK" if link is not None else "UNKNOWN DEVICE", status_code=200 if link else 404)


@device_router.post("/iclock/devicecmd", response_class=PlainTextResponse)
async def zk_cmd_reply(SN: str = ""):  # noqa: N803
    return PlainTextResponse("OK")
