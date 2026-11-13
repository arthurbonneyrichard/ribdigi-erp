"""Measurable goals (KPIs) and 360 feedback on performance reviews.

- A review goal may carry a target and a unit ("Sales 50000 GHS", "Complaints 0"). While the
  review is open, the person or HR records the actual so far. Scores stay the reviewer's call.
- 360 feedback: HR asks colleagues (not the person) for a 1-5 rating and two comments. Each
  colleague answers once under My HR. Answers are shown without names to everyone, including
  HR, and only once two or more have answered; HR sees who still has to answer, not who said what.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json, optional_honest_narrative

MIN_ANSWERS = 2


async def _people():
    from app import hrm_people

    return hrm_people


async def record_progress(db: AsyncSession, tenant_id: str, review_id: str, *, index: int, actual, me: m.HrmEmployee | None, as_hr: bool, user_id) -> m.HrmReview:
    people = await _people()
    row = await people._owned(db, m.HrmReview, tenant_id, review_id, "Review")
    if not as_hr and (me is None or row.employee_id != me.id):
        raise HTTPException(status_code=404, detail="Review not found")
    if row.status == "done":
        raise HTTPException(status_code=409, detail="This review is finished")
    goals = [dict(g) for g in (row.goals or [])]
    if not 0 <= index < len(goals):
        raise HTTPException(status_code=422, detail="No such goal on this review")
    if goals[index].get("target") is None:
        raise HTTPException(status_code=422, detail="This goal has no target to measure against")
    goals[index]["actual"] = str(Decimal(str(actual)))
    goals[index]["actual_at"] = datetime.utcnow().isoformat()
    row.goals = goals
    await db.flush()
    await people._audit(db, tenant_id, user_id, "hrm_goal_progress", "hrm_review", row.id, {"goal": index, "actual": goals[index]["actual"]})
    return row


def progress_percent(goal: dict) -> float | None:
    target, actual = goal.get("target"), goal.get("actual")
    if target in (None, "") or actual in (None, ""):
        return None
    t = Decimal(str(target))
    if t == 0:
        return None
    return money_json((Decimal(str(actual)) / t * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


async def ask(db: AsyncSession, tenant_id: str, review_id: str, employee_ids: list[str], *, user_id) -> int:
    from app import hrm, hrm_notify

    people = await _people()
    row = await people._owned(db, m.HrmReview, tenant_id, review_id, "Review")
    if row.status == "done":
        raise HTTPException(status_code=409, detail="This review is finished")
    subject = await db.get(m.HrmEmployee, row.employee_id)
    added = 0
    for eid in dict.fromkeys(employee_ids):
        if eid == row.employee_id:
            raise HTTPException(status_code=422, detail="The person reviewed cannot give feedback on themselves here; that is their own view")
        colleague = await hrm._employee(db, tenant_id, eid)
        exists = (
            await db.execute(select(m.HrmFeedback.id).where(m.HrmFeedback.review_id == row.id, m.HrmFeedback.from_employee_id == colleague.id))
        ).first()
        if exists:
            continue
        fb = m.HrmFeedback(tenant_id=tenant_id, review_id=row.id, from_employee_id=colleague.id, status="asked", asked_by=user_id)
        db.add(fb)
        await db.flush()
        added += 1
        await hrm_notify.to_person(
            db, tenant_id, colleague, "Feedback asked",
            f"Please give feedback on {subject.full_name if subject else 'a colleague'} ({row.cycle}) under My HR.",
            entity_type="hrm_feedback", entity_id=fb.id,
        )
    await people._audit(db, tenant_id, user_id, "hrm_feedback_asked", "hrm_review", row.id, {"colleagues": added})
    return added


async def my_requests(db: AsyncSession, tenant_id: str, me: m.HrmEmployee) -> list[dict]:
    rows = (
        await db.execute(
            select(m.HrmFeedback, m.HrmReview)
            .join(m.HrmReview, m.HrmReview.id == m.HrmFeedback.review_id)
            .where(m.HrmFeedback.tenant_id == tenant_id, m.HrmFeedback.from_employee_id == me.id)
            .order_by(m.HrmFeedback.created_at.desc())
        )
    ).all()
    out = []
    for fb, review in rows:
        subject = await db.get(m.HrmEmployee, review.employee_id)
        out.append(
            {
                "id": fb.id, "about": subject.full_name if subject else None, "cycle": review.cycle, "status": fb.status,
                "open": fb.status == "asked" and review.status != "done",
                "goals": [g.get("title") for g in (review.goals or [])],
            }
        )
    return out


async def give(db: AsyncSession, tenant_id: str, feedback_id: str, me: m.HrmEmployee, payload, *, user_id) -> m.HrmFeedback:
    people = await _people()
    fb = await db.get(m.HrmFeedback, feedback_id)
    if fb is None or fb.tenant_id != tenant_id or fb.from_employee_id != me.id:
        raise HTTPException(status_code=404, detail="Feedback request not found")
    review = await db.get(m.HrmReview, fb.review_id)
    if fb.status != "asked" or review is None or review.status == "done":
        raise HTTPException(status_code=409, detail="This feedback is closed")
    fb.rating = payload.rating
    fb.strengths = optional_honest_narrative(payload.strengths, label="what they do well", max_length=2000)
    fb.improve = optional_honest_narrative(payload.improve, label="what could be better", max_length=2000)
    if not fb.strengths and not fb.improve:
        raise HTTPException(status_code=422, detail="Write at least one comment")
    fb.status = "given"
    fb.given_at = datetime.utcnow()
    await db.flush()
    await people._audit(db, tenant_id, user_id, "hrm_feedback_given", "hrm_review", review.id, {})
    return fb


async def summary(db: AsyncSession, review_id: str, *, with_waiting: bool = False) -> dict:
    rows = list((await db.execute(select(m.HrmFeedback).where(m.HrmFeedback.review_id == review_id))).scalars())
    given = [r for r in rows if r.status == "given"]
    ratings = [int(r.rating) for r in given if r.rating]
    waiting = []
    if with_waiting:
        for r in rows:
            if r.status == "asked":
                person = await db.get(m.HrmEmployee, r.from_employee_id)
                waiting.append(person.full_name if person else "")
    return {
        "waiting_on": sorted(waiting),
        "asked": len(rows), "given": len(given),
        "average": round(sum(ratings) / len(ratings), 2) if len(ratings) >= MIN_ANSWERS else None,
        # No names: who said what is not shown, to anyone. With fewer than two answers the one
        # answer would give its writer away, so nothing is shown until a second arrives.
        "comments": (
            [{"strengths": r.strengths, "improve": r.improve, "rating": r.rating} for r in sorted(given, key=lambda r: r.strengths or "")]
            if len(given) >= MIN_ANSWERS else []
        ),
    }
