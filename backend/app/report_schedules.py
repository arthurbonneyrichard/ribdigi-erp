"""Scheduled report email delivery."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.report_export import EXPORTABLE, EXPORT_FORMATS, export_report

FREQUENCIES = frozenset({"daily", "weekly"})


def serialize_schedule(row: m.ReportSchedule) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "report_type": row.report_type,
        "format": row.format,
        "frequency": row.frequency,
        "weekday": row.weekday,
        "hour_utc": int(row.hour_utc or 0),
        "recipients": list(row.recipients or []),
        "enabled": bool(row.enabled),
        "last_run_at": row.last_run_at,
        "last_error": row.last_error,
        "created_by": row.created_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _normalize_recipients(raw: list[str] | str | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(";", ",").split(",")]
    else:
        parts = [str(p).strip() for p in raw]
    out = [p for p in parts if p and "@" in p]
    # de-dupe preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for email in out:
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(email)
    return unique


async def list_schedules(
    db: AsyncSession,
    tenant_id: str,
    *,
    enabled: bool | None = None,
) -> list[m.ReportSchedule]:
    """Stage 127 S1 — optional enabled filter for honest schedule lists."""
    stmt = select(m.ReportSchedule).where(m.ReportSchedule.tenant_id == tenant_id)
    if enabled is not None:
        stmt = stmt.where(m.ReportSchedule.enabled.is_(bool(enabled)))
    return list(
        (await db.execute(stmt.order_by(m.ReportSchedule.created_at.desc())))
        .scalars()
        .all()
    )


async def get_schedule(db: AsyncSession, tenant_id: str, schedule_id: str) -> m.ReportSchedule:
    row = (
        await db.execute(
            select(m.ReportSchedule).where(
                m.ReportSchedule.id == schedule_id,
                m.ReportSchedule.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    return row


async def create_schedule(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    name: str,
    report_type: str,
    format: str = "xlsx",
    frequency: str = "daily",
    weekday: int | None = None,
    hour_utc: int = 6,
    recipients: list[str] | str | None = None,
    enabled: bool = True,
) -> m.ReportSchedule:
    name = (name or "").strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="name is required")
    if report_type not in EXPORTABLE:
        raise HTTPException(status_code=400, detail=f"report_type must be one of {sorted(EXPORTABLE)}")
    fmt = (format or "xlsx").lower()
    if fmt not in EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"format must be one of {sorted(EXPORT_FORMATS)}")
    freq = (frequency or "daily").lower()
    if freq not in FREQUENCIES:
        raise HTTPException(status_code=400, detail="frequency must be daily or weekly")
    if freq == "weekly":
        if weekday is None or weekday < 0 or weekday > 6:
            raise HTTPException(status_code=400, detail="weekday 0-6 required for weekly schedules")
    hour = int(hour_utc)
    if hour < 0 or hour > 23:
        raise HTTPException(status_code=400, detail="hour_utc must be 0-23")
    emails = _normalize_recipients(recipients)
    if not emails:
        raise HTTPException(status_code=400, detail="At least one valid recipient email is required")

    row = m.ReportSchedule(
        tenant_id=tenant_id,
        name=name,
        report_type=report_type,
        format=fmt,
        frequency=freq,
        weekday=weekday if freq == "weekly" else None,
        hour_utc=hour,
        recipients=emails,
        enabled=bool(enabled),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def update_schedule(
    db: AsyncSession,
    tenant_id: str,
    schedule_id: str,
    *,
    name: str | None = None,
    report_type: str | None = None,
    format: str | None = None,
    frequency: str | None = None,
    weekday: int | None = None,
    hour_utc: int | None = None,
    recipients: list[str] | str | None = None,
    enabled: bool | None = None,
) -> m.ReportSchedule:
    row = await get_schedule(db, tenant_id, schedule_id)
    if name is not None:
        name = name.strip()
        if len(name) < 2:
            raise HTTPException(status_code=400, detail="name is required")
        row.name = name
    if report_type is not None:
        if report_type not in EXPORTABLE:
            raise HTTPException(status_code=400, detail=f"report_type must be one of {sorted(EXPORTABLE)}")
        row.report_type = report_type
    if format is not None:
        fmt = format.lower()
        if fmt not in EXPORT_FORMATS:
            raise HTTPException(status_code=400, detail=f"format must be one of {sorted(EXPORT_FORMATS)}")
        row.format = fmt
    if frequency is not None:
        freq = frequency.lower()
        if freq not in FREQUENCIES:
            raise HTTPException(status_code=400, detail="frequency must be daily or weekly")
        row.frequency = freq
        if freq == "daily":
            row.weekday = None
    if weekday is not None:
        if weekday < 0 or weekday > 6:
            raise HTTPException(status_code=400, detail="weekday must be 0-6")
        row.weekday = weekday
    if hour_utc is not None:
        hour = int(hour_utc)
        if hour < 0 or hour > 23:
            raise HTTPException(status_code=400, detail="hour_utc must be 0-23")
        row.hour_utc = hour
    if recipients is not None:
        emails = _normalize_recipients(recipients)
        if not emails:
            raise HTTPException(status_code=400, detail="At least one valid recipient email is required")
        row.recipients = emails
    if enabled is not None:
        row.enabled = bool(enabled)
    if row.frequency == "weekly" and row.weekday is None:
        raise HTTPException(status_code=400, detail="weekday 0-6 required for weekly schedules")
    row.updated_at = datetime.utcnow()
    await db.flush()
    return row


async def delete_schedule(db: AsyncSession, tenant_id: str, schedule_id: str) -> None:
    row = await get_schedule(db, tenant_id, schedule_id)
    await db.delete(row)
    await db.flush()


def is_schedule_due(row: m.ReportSchedule, *, now: datetime | None = None) -> tuple[bool, str]:
    now = now or datetime.utcnow()
    if not row.enabled:
        return False, "disabled"
    if row.frequency == "weekly" and row.weekday is not None and now.weekday() != int(row.weekday):
        return False, "wrong_weekday"
    if now.hour < int(row.hour_utc or 0):
        return False, "before_hour"
    if row.last_run_at:
        gap = timedelta(days=7 if row.frequency == "weekly" else 1)
        if now - row.last_run_at < gap:
            return False, "already_ran"
    return True, "due"


async def run_schedule(
    db: AsyncSession,
    *,
    tenant_id: str,
    schedule: m.ReportSchedule,
    force: bool = False,
) -> dict:
    from app import emailer

    due, reason = is_schedule_due(schedule)
    if not force and not due:
        return {"ran": False, "reason": reason, "schedule_id": schedule.id}

    recipients = list(schedule.recipients or [])
    if not recipients:
        schedule.last_error = "No recipients"
        await db.flush()
        return {"ran": False, "reason": "no_recipients", "schedule_id": schedule.id}

    try:
        content, media, filename = await export_report(
            db,
            tenant_id,
            schedule.report_type,
            schedule.format,
        )
        subject = f"RIBDIGI report: {schedule.name} ({schedule.report_type})"
        text = (
            f"Attached is your scheduled {schedule.report_type} report "
            f"({schedule.format}) generated at {datetime.utcnow().isoformat()}Z.\n"
        )
        result = await emailer.send_email(
            to=recipients,
            subject=subject,
            text_body=text,
            html_body=f"<p>{text}</p>",
            attachments=[
                {
                    "filename": filename,
                    "content": content,
                    "content_type": media,
                }
            ],
        )
        if not result.sent:
            schedule.last_error = result.error or f"Email not sent ({result.mode})"
            await db.flush()
            return {
                "ran": False,
                "reason": "email_failed",
                "schedule_id": schedule.id,
                "mode": result.mode,
                "error": schedule.last_error,
            }
        schedule.last_run_at = datetime.utcnow()
        schedule.last_error = None
        schedule.updated_at = datetime.utcnow()
        await db.flush()
        return {
            "ran": True,
            "reason": "sent",
            "schedule_id": schedule.id,
            "to": recipients,
            "mode": result.mode,
            "filename": filename,
        }
    except Exception as exc:  # noqa: BLE001
        schedule.last_error = str(exc)[:500]
        await db.flush()
        return {
            "ran": False,
            "reason": "error",
            "schedule_id": schedule.id,
            "error": schedule.last_error,
        }


async def run_due_schedules_for_tenant(db: AsyncSession, tenant_id: str) -> dict:
    rows = await list_schedules(db, tenant_id)
    results = []
    for row in rows:
        if not row.enabled:
            continue
        outcome = await run_schedule(db, tenant_id=tenant_id, schedule=row, force=False)
        results.append(outcome)
    return {"tenant_id": tenant_id, "checked": len(rows), "results": results}
