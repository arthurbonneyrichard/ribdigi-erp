"""People signals for HR: plain rules over the desk's own records, no AI model.

Each signal says what was seen and why it matters, so HR can talk to the person. None is a
judgement and none carries a score or pay figures. Rules (all over the company's own data):

- Short absences: Bradford factor (spells² × days) of sick leave in the last 12 months at or
  over 200 (a common threshold for a conversation, not a policy).
- Late often: 5 or more late days last month on the clock.
- Long hours: more than 20 hours of overtime clocked last month.
- Leave piling up: from October, half or more of this year's annual leave still not taken.
- No review: active a year or more and no finished review in the last 12 months.
- Policy not accepted: a company policy that needs accepting, still not accepted after 14 days.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

BRADFORD_FLAG = 200
LATE_DAYS_FLAG = 5
OVERTIME_HOURS_FLAG = 20


def bradford(spells: int, days: int) -> int:
    return int(spells) * int(spells) * int(days)


def _last_month(today: date) -> str:
    first = today.replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y-%m")


async def signals(db: AsyncSession, tenant_id: str, today: date | None = None) -> list[dict]:
    from app import hrm

    today = today or date.today()
    people = await hrm.list_employees(db, tenant_id)
    out: list[dict] = []

    def add(person, kind: str, title: str, why: str, link: str) -> None:
        out.append({"employee_id": person.id, "name": person.full_name, "kind": kind, "title": title, "why": why, "link": link})

    year_ago = today - timedelta(days=365)
    for person in people:
        sick = (
            await db.execute(
                select(m.HrmLeaveRequest.days).where(
                    m.HrmLeaveRequest.employee_id == person.id, m.HrmLeaveRequest.leave_type == "sick",
                    m.HrmLeaveRequest.status == "approved", m.HrmLeaveRequest.starts_on >= year_ago,
                )
            )
        ).scalars().all()
        score = bradford(len(sick), sum(int(d or 0) for d in sick))
        if score >= BRADFORD_FLAG:
            add(
                person, "absence", "Frequent short absences",
                f"{len(sick)} spells of sick leave ({sum(int(d or 0) for d in sick)} days) in 12 months. Many short spells often point to something worth a kind conversation.",
                "/hrm?tab=leave",
            )
        if today.month >= 10:
            bal = await hrm.leave_balance(db, tenant_id, person.id, year=today.year)
            if bal["entitled"] > 0 and bal["left"] * 2 >= bal["entitled"]:
                add(
                    person, "leave", "Leave piling up",
                    f"{bal['left']} of {bal['entitled']} annual leave days not taken this year. Plan time off, or carry over or pay out within the rules.",
                    "/hrm?tab=leave",
                )
        if person.hired_on and person.hired_on <= today - timedelta(days=365):
            reviewed = (
                await db.execute(
                    select(func.count()).select_from(m.HrmReview).where(
                        m.HrmReview.employee_id == person.id, m.HrmReview.status == "done",
                        m.HrmReview.completed_at >= datetime.combine(year_ago, datetime.min.time()),
                    )
                )
            ).scalar_one()
            if not reviewed:
                add(person, "review", "No review this year", "Here a year or more with no finished review in the last 12 months.", "/hrm?tab=reviews")

    # Clock signals only when the company uses the clock at all last month.
    period = _last_month(today)
    first = datetime.strptime(period + "-01", "%Y-%m-%d")
    uses_clock = (
        await db.execute(
            select(m.HrmClockEvent.id)
            .where(m.HrmClockEvent.tenant_id == tenant_id, m.HrmClockEvent.at >= first, m.HrmClockEvent.at < datetime.combine(today.replace(day=1), datetime.min.time()))
            .limit(1)
        )
    ).first()
    if uses_clock:
        from app import hrm_time

        by_id = {p.id: p for p in people}
        for row in await hrm_time.month_summary(db, tenant_id, period):
            person = by_id.get(row["employee_id"])
            if person is None:
                continue
            if row["late_days"] >= LATE_DAYS_FLAG:
                add(person, "late", "Late often", f"Late on {row['late_days']} days in {period}. Check the shift times still suit them.", "/hrm?tab=attendance")
            if row["overtime_minutes"] > OVERTIME_HOURS_FLAG * 60:
                add(
                    person, "hours", "Long hours",
                    f"{round(row['overtime_minutes'] / 60)} hours over their shifts in {period}. Long hours for weeks wear people down.",
                    "/hrm?tab=attendance",
                )

    # Policies not accepted after two weeks.
    from app import hrm_documents

    for doc in await hrm_documents.company_wide(db, tenant_id, active_only=True):
        if not doc.needs_ack or not doc.created_at or doc.created_at > datetime.utcnow() - timedelta(days=14):
            continue
        for row in await hrm_documents.outstanding(db, tenant_id, doc.id):
            if not row["accepted_at"]:
                person = await db.get(m.HrmEmployee, row["employee_id"])
                if person is not None:
                    add(person, "policy", "Policy not accepted", f"Has not accepted “{doc.title}” after two weeks.", "/hrm?tab=people")
    order = {"absence": 0, "hours": 1, "late": 2, "leave": 3, "review": 4, "policy": 5}
    return sorted(out, key=lambda s: (order.get(s["kind"], 9), s["name"] or ""))
