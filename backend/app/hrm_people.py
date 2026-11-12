"""HRM people work beyond pay: recruitment, performance reviews, training, contracts and
probation, disciplinary cases and grievances, staff assets, expense claims, notices.

Each company's rows stay on its own hrm_* tables. Who may do what is `hrm.job` (officers
run people admin; reviews, claims and confidential cases need an HR manager; staff see
their own). Sensitive decisions are always made by a person: nothing here approves,
disciplines or dismisses on its own.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

STAGES = ("applied", "screening", "interview", "offer", "hired")
CLOSED_STAGES = frozenset({"hired", "rejected", "withdrawn"})
CASE_OUTCOMES = frozenset(
    {"none", "verbal_warning", "written_warning", "final_warning", "suspension", "dismissal", "upheld", "not_upheld"}
)


def _iso(value):
    return value.isoformat() if value else None


async def _hrm():
    from app import hrm

    return hrm


async def _person(db: AsyncSession, tenant_id: str, employee_id: str) -> m.HrmEmployee:
    hrm = await _hrm()
    return await hrm._employee(db, tenant_id, employee_id)


async def _owned(db: AsyncSession, model, tenant_id: str, row_id: str, label: str):
    row = await db.get(model, row_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return row


async def _audit(db, tenant_id, user_id, action, entity, entity_id, details):
    hrm = await _hrm()
    await hrm._audit(db, tenant_id, user_id, action, entity, entity_id, details)


async def _name(db: AsyncSession, employee_id: str | None) -> str | None:
    if not employee_id:
        return None
    row = await db.get(m.HrmEmployee, employee_id)
    return row.full_name if row else None


# --- Recruitment ---------------------------------------------------------------------------


def serialize_vacancy(row: m.HrmVacancy, counts: dict | None = None) -> dict:
    return {
        "id": row.id, "title": row.title, "department": row.department, "openings": row.openings,
        "description": row.description, "status": row.status, "closes_on": _iso(row.closes_on),
        "created_at": _iso(row.created_at), "candidates": counts or {},
    }


async def list_vacancies(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(select(m.HrmVacancy).where(m.HrmVacancy.tenant_id == tenant_id).order_by(m.HrmVacancy.created_at.desc()))
    ).scalars().all()
    out = []
    for row in rows:
        counts = dict(
            (
                await db.execute(
                    select(m.HrmCandidate.stage, func.count())
                    .where(m.HrmCandidate.vacancy_id == row.id)
                    .group_by(m.HrmCandidate.stage)
                )
            ).all()
        )
        out.append(serialize_vacancy(row, counts))
    return out


async def add_vacancy(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmVacancy:
    row = m.HrmVacancy(
        tenant_id=tenant_id,
        title=require_honest_narrative(payload.title, label="job title", max_length=120),
        department=optional_honest_narrative(payload.department, label="department", max_length=120),
        openings=payload.openings,
        description=optional_honest_narrative(payload.description, label="description", max_length=4000),
        closes_on=payload.closes_on,
        status="open",
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_vacancy_opened", "hrm_vacancy", row.id, {"title": row.title})
    return row


async def close_vacancy(db: AsyncSession, tenant_id: str, vacancy_id: str, *, user_id) -> m.HrmVacancy:
    row = await _owned(db, m.HrmVacancy, tenant_id, vacancy_id, "Vacancy")
    row.status = "closed"
    await _audit(db, tenant_id, user_id, "hrm_vacancy_closed", "hrm_vacancy", row.id, {})
    await db.flush()
    return row


def serialize_candidate(row: m.HrmCandidate) -> dict:
    return {
        "id": row.id, "vacancy_id": row.vacancy_id, "full_name": row.full_name, "email": row.email,
        "phone": row.phone, "stage": row.stage, "interview_at": _iso(row.interview_at), "score": row.score,
        "notes": row.notes, "offered_basic": money_json(row.offered_basic) if row.offered_basic is not None else None,
        "employee_id": row.employee_id, "created_at": _iso(row.created_at),
    }


async def list_candidates(db: AsyncSession, tenant_id: str, vacancy_id: str) -> list[m.HrmCandidate]:
    await _owned(db, m.HrmVacancy, tenant_id, vacancy_id, "Vacancy")
    return list(
        (
            await db.execute(
                select(m.HrmCandidate).where(m.HrmCandidate.vacancy_id == vacancy_id).order_by(m.HrmCandidate.created_at)
            )
        ).scalars()
    )


async def add_candidate(db: AsyncSession, tenant_id: str, vacancy_id: str, payload, *, user_id) -> m.HrmCandidate:
    vacancy = await _owned(db, m.HrmVacancy, tenant_id, vacancy_id, "Vacancy")
    if vacancy.status != "open":
        raise HTTPException(status_code=409, detail="This vacancy is closed")
    row = m.HrmCandidate(
        tenant_id=tenant_id, vacancy_id=vacancy.id, full_name=payload.full_name,
        email=str(payload.email).lower() if payload.email else None, phone=payload.phone,
        notes=optional_honest_narrative(payload.notes, label="notes", max_length=4000), created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_candidate_added", "hrm_candidate", row.id, {"vacancy_id": vacancy.id})
    return row


async def move_candidate(db: AsyncSession, tenant_id: str, candidate_id: str, payload, *, user_id) -> m.HrmCandidate:
    """Forward one stage at a time (or straight to rejected / withdrawn). Hiring is its own step."""
    row = await _owned(db, m.HrmCandidate, tenant_id, candidate_id, "Candidate")
    if row.stage in CLOSED_STAGES:
        raise HTTPException(status_code=409, detail=f"This candidate is already {row.stage}")
    target = payload.stage
    if target == "hired":
        raise HTTPException(status_code=422, detail="Use Hire to take someone on")
    if target not in {"rejected", "withdrawn"}:
        now, nxt = STAGES.index(row.stage), STAGES.index(target)
        if nxt != now + 1:
            raise HTTPException(status_code=409, detail=f"From {row.stage} the next stage is {STAGES[now + 1]}")
    if target == "offer" and payload.offered_basic is None:
        raise HTTPException(status_code=422, detail="Enter the basic salary offered")
    row.stage = target
    if payload.interview_at is not None:
        row.interview_at = payload.interview_at
    if payload.score is not None:
        row.score = payload.score
    if payload.offered_basic is not None:
        row.offered_basic = payload.offered_basic
    if payload.note:
        note = optional_honest_narrative(payload.note, label="note", max_length=1000)
        row.notes = "\n".join(x for x in (row.notes, f"[{target}] {note}") if x)
    row.updated_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "hrm_candidate_moved", "hrm_candidate", row.id, {"stage": target})
    await db.flush()
    return row


async def hire(db: AsyncSession, tenant_id: str, candidate_id: str, payload, *, user_id) -> m.HrmEmployee:
    hrm = await _hrm()
    row = await _owned(db, m.HrmCandidate, tenant_id, candidate_id, "Candidate")
    if row.stage != "offer":
        raise HTTPException(status_code=409, detail="Only someone who has been made an offer can be hired")
    vacancy = await db.get(m.HrmVacancy, row.vacancy_id)

    class _NewHire:
        full_name = row.full_name
        phone = row.phone
        email = row.email
        job_title = vacancy.title if vacancy else None
        department = vacancy.department if vacancy else None
        hired_on = payload.starts_on
        basic_salary = row.offered_basic or 0
        allowances = payload.allowances or 0
        ssnit_number = tin = bank_name = bank_account = None
        ghana_card = mobile_money = None
        tier3_percent = 0
        manager_id = payload.manager_id

    employee = await hrm.create_employee(db, tenant_id, _NewHire(), user_id=user_id)
    row.stage = "hired"
    row.employee_id = employee.id
    row.updated_at = datetime.utcnow()
    if payload.probation_months:
        db.add(
            m.HrmContract(
                tenant_id=tenant_id, employee_id=employee.id, kind="probation", starts_on=payload.starts_on,
                probation_ends_on=_add_months(payload.starts_on, payload.probation_months), status="active",
                created_by=user_id,
            )
        )
    if vacancy is not None:
        hired = (
            await db.execute(
                select(func.count()).select_from(m.HrmCandidate).where(
                    m.HrmCandidate.vacancy_id == vacancy.id, m.HrmCandidate.stage == "hired"
                )
            )
        ).scalar_one()
        if int(hired) >= int(vacancy.openings or 1):
            vacancy.status = "filled"
    await _audit(db, tenant_id, user_id, "hrm_candidate_hired", "hrm_candidate", row.id, {"employee_id": employee.id})
    await db.flush()
    return employee


def _add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


# --- Performance reviews -------------------------------------------------------------------


def _overall(goals: list[dict]) -> Decimal | None:
    scored = [g for g in goals if g.get("score") is not None]
    if not scored:
        return None
    weight = sum(Decimal(str(g.get("weight") or 0)) for g in scored)
    if weight <= 0:
        return None
    total = sum(Decimal(str(g["score"])) * Decimal(str(g.get("weight") or 0)) for g in scored)
    return (total / weight).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def serialize_review(db: AsyncSession, row: m.HrmReview) -> dict:
    return {
        "id": row.id, "employee_id": row.employee_id, "employee_name": await _name(db, row.employee_id),
        "cycle": row.cycle, "goals": row.goals, "status": row.status, "self_comment": row.self_comment,
        "reviewer_comment": row.reviewer_comment, "overall": money_json(row.overall) if row.overall is not None else None,
        "completed_at": _iso(row.completed_at), "created_at": _iso(row.created_at),
    }


async def list_reviews(db: AsyncSession, tenant_id: str, *, employee_id: str | None = None) -> list[m.HrmReview]:
    stmt = select(m.HrmReview).where(m.HrmReview.tenant_id == tenant_id).order_by(m.HrmReview.created_at.desc())
    if employee_id:
        stmt = stmt.where(m.HrmReview.employee_id == employee_id)
    return list((await db.execute(stmt)).scalars())


async def start_review(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmReview:
    employee = await _person(db, tenant_id, payload.employee_id)
    goals = [{"title": require_honest_narrative(g.title, label="goal", max_length=200), "weight": int(g.weight), "score": None, "self_score": None} for g in payload.goals]
    if sum(g["weight"] for g in goals) != 100:
        raise HTTPException(status_code=422, detail="Goal weights must add up to 100")
    row = m.HrmReview(
        tenant_id=tenant_id, employee_id=employee.id,
        cycle=require_honest_narrative(payload.cycle, label="review period", max_length=60),
        goals=goals, status="open", created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_review_started", "hrm_review", row.id, {"employee_id": employee.id, "cycle": row.cycle})
    return row


async def self_assess(db: AsyncSession, tenant_id: str, review_id: str, employee: m.HrmEmployee, payload, *, user_id) -> m.HrmReview:
    row = await _owned(db, m.HrmReview, tenant_id, review_id, "Review")
    if row.employee_id != employee.id:
        raise HTTPException(status_code=404, detail="Review not found")
    if row.status != "open":
        raise HTTPException(status_code=409, detail="Your part of this review is done")
    goals = list(row.goals or [])
    if len(payload.scores) != len(goals):
        raise HTTPException(status_code=422, detail="Score every goal")
    row.goals = [{**g, "self_score": int(s)} for g, s in zip(goals, payload.scores)]
    row.self_comment = optional_honest_narrative(payload.comment, label="comment", max_length=4000)
    row.status = "self_done"
    await _audit(db, tenant_id, user_id, "hrm_review_self_done", "hrm_review", row.id, {})
    await db.flush()
    return row


async def complete_review(db: AsyncSession, tenant_id: str, review_id: str, payload, *, user_id) -> m.HrmReview:
    hrm = await _hrm()
    row = await _owned(db, m.HrmReview, tenant_id, review_id, "Review")
    if row.status == "done":
        raise HTTPException(status_code=409, detail="This review is finished")
    me = await hrm._user_employee(db, tenant_id, user_id)
    if me is not None and me.id == row.employee_id:
        raise HTTPException(status_code=403, detail="Someone else must finish your own review")
    goals = list(row.goals or [])
    if len(payload.scores) != len(goals):
        raise HTTPException(status_code=422, detail="Score every goal")
    row.goals = [{**g, "score": int(s)} for g, s in zip(goals, payload.scores)]
    row.overall = _overall(row.goals)
    row.reviewer_comment = optional_honest_narrative(payload.comment, label="comment", max_length=4000)
    row.reviewer_id = user_id
    row.status = "done"
    row.completed_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "hrm_review_done", "hrm_review", row.id, {"overall": money_json(row.overall) if row.overall is not None else None})
    await db.flush()
    return row


# --- Training ------------------------------------------------------------------------------


def serialize_training(row: m.HrmTraining) -> dict:
    return {"id": row.id, "title": row.title, "provider": row.provider, "mandatory": bool(row.mandatory), "valid_months": row.valid_months, "is_active": bool(row.is_active)}


async def list_trainings(db: AsyncSession, tenant_id: str) -> list[m.HrmTraining]:
    return list((await db.execute(select(m.HrmTraining).where(m.HrmTraining.tenant_id == tenant_id).order_by(m.HrmTraining.title))).scalars())


async def add_training(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmTraining:
    row = m.HrmTraining(
        tenant_id=tenant_id, title=require_honest_narrative(payload.title, label="course", max_length=160),
        provider=optional_honest_narrative(payload.provider, label="provider", max_length=160),
        mandatory=bool(payload.mandatory), valid_months=payload.valid_months, is_active=True,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_training_added", "hrm_training", row.id, {"title": row.title})
    return row


async def serialize_record(db: AsyncSession, row: m.HrmTrainingRecord, today: date | None = None) -> dict:
    today = today or date.today()
    course = await db.get(m.HrmTraining, row.training_id)
    state = "valid"
    if row.expires_on and row.expires_on < today:
        state = "expired"
    elif row.expires_on and row.expires_on <= today + timedelta(days=30):
        state = "expiring"
    return {
        "id": row.id, "training_id": row.training_id, "training": course.title if course else None,
        "employee_id": row.employee_id, "employee_name": await _name(db, row.employee_id),
        "completed_on": _iso(row.completed_on), "expires_on": _iso(row.expires_on), "result": row.result,
        "certificate_ref": row.certificate_ref, "state": state,
    }


async def list_records(db: AsyncSession, tenant_id: str, *, employee_id: str | None = None) -> list[m.HrmTrainingRecord]:
    stmt = select(m.HrmTrainingRecord).where(m.HrmTrainingRecord.tenant_id == tenant_id).order_by(m.HrmTrainingRecord.completed_on.desc())
    if employee_id:
        stmt = stmt.where(m.HrmTrainingRecord.employee_id == employee_id)
    return list((await db.execute(stmt)).scalars())


async def record_training(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmTrainingRecord:
    course = await _owned(db, m.HrmTraining, tenant_id, payload.training_id, "Course")
    employee = await _person(db, tenant_id, payload.employee_id)
    if payload.completed_on > date.today():
        raise HTTPException(status_code=422, detail="Record training once it has been done")
    expires = _add_months(payload.completed_on, course.valid_months) if course.valid_months else None
    row = m.HrmTrainingRecord(
        tenant_id=tenant_id, training_id=course.id, employee_id=employee.id, completed_on=payload.completed_on,
        expires_on=expires, result=optional_honest_narrative(payload.result, label="result", max_length=120),
        certificate_ref=optional_honest_narrative(payload.certificate_ref, label="certificate", max_length=120),
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_training_recorded", "hrm_training_record", row.id, {"training_id": course.id, "employee_id": employee.id})
    return row


async def training_gaps(db: AsyncSession, tenant_id: str) -> list[dict]:
    """Mandatory courses each active person has not done, or whose completion has lapsed."""
    hrm = await _hrm()
    today = date.today()
    courses = [c for c in await list_trainings(db, tenant_id) if c.mandatory and c.is_active]
    people = await hrm.list_employees(db, tenant_id, show="active")
    out = []
    for person in people:
        for course in courses:
            latest = (
                await db.execute(
                    select(m.HrmTrainingRecord)
                    .where(m.HrmTrainingRecord.employee_id == person.id, m.HrmTrainingRecord.training_id == course.id)
                    .order_by(m.HrmTrainingRecord.completed_on.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if latest is None:
                out.append({"employee_name": person.full_name, "employee_id": person.id, "training": course.title, "why": "not done"})
            elif latest.expires_on and latest.expires_on < today:
                out.append({"employee_name": person.full_name, "employee_id": person.id, "training": course.title, "why": f"lapsed {latest.expires_on.isoformat()}"})
    return out


# --- Contracts and probation ---------------------------------------------------------------


async def serialize_contract(db: AsyncSession, row: m.HrmContract) -> dict:
    return {
        "id": row.id, "employee_id": row.employee_id, "employee_name": await _name(db, row.employee_id),
        "kind": row.kind, "starts_on": _iso(row.starts_on), "ends_on": _iso(row.ends_on),
        "probation_ends_on": _iso(row.probation_ends_on), "confirmed_on": _iso(row.confirmed_on),
        "reference": row.reference, "notes": row.notes, "status": row.status,
    }


async def list_contracts(db: AsyncSession, tenant_id: str, *, employee_id: str | None = None) -> list[m.HrmContract]:
    stmt = select(m.HrmContract).where(m.HrmContract.tenant_id == tenant_id).order_by(m.HrmContract.starts_on.desc())
    if employee_id:
        stmt = stmt.where(m.HrmContract.employee_id == employee_id)
    return list((await db.execute(stmt)).scalars())


async def add_contract(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmContract:
    employee = await _person(db, tenant_id, payload.employee_id)
    if payload.ends_on and payload.ends_on < payload.starts_on:
        raise HTTPException(status_code=422, detail="The contract ends before it starts")
    if payload.kind == "fixed_term" and not payload.ends_on:
        raise HTTPException(status_code=422, detail="A fixed-term contract needs an end date")
    if payload.probation_ends_on and payload.probation_ends_on < payload.starts_on:
        raise HTTPException(status_code=422, detail="Probation ends before the start")
    row = m.HrmContract(
        tenant_id=tenant_id, employee_id=employee.id, kind=payload.kind, starts_on=payload.starts_on,
        ends_on=payload.ends_on, probation_ends_on=payload.probation_ends_on,
        reference=optional_honest_narrative(payload.reference, label="reference", max_length=120),
        notes=optional_honest_narrative(payload.notes, label="notes", max_length=4000), status="active", created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_contract_added", "hrm_contract", row.id, {"employee_id": employee.id, "kind": row.kind})
    return row


async def confirm_probation(db: AsyncSession, tenant_id: str, contract_id: str, *, user_id) -> m.HrmContract:
    row = await _owned(db, m.HrmContract, tenant_id, contract_id, "Contract")
    if not row.probation_ends_on or row.confirmed_on:
        raise HTTPException(status_code=409, detail="There is no probation waiting to be confirmed")
    row.confirmed_on = date.today()
    await _audit(db, tenant_id, user_id, "hrm_probation_confirmed", "hrm_contract", row.id, {})
    await db.flush()
    return row


async def contract_alerts(db: AsyncSession, tenant_id: str, *, within_days: int = 30) -> dict:
    today = date.today()
    soon = today + timedelta(days=within_days)
    ending = (
        await db.execute(
            select(m.HrmContract).where(
                m.HrmContract.tenant_id == tenant_id, m.HrmContract.status == "active",
                m.HrmContract.ends_on.is_not(None), m.HrmContract.ends_on <= soon,
            )
        )
    ).scalars().all()
    probation = (
        await db.execute(
            select(m.HrmContract).where(
                m.HrmContract.tenant_id == tenant_id, m.HrmContract.status == "active",
                m.HrmContract.probation_ends_on.is_not(None), m.HrmContract.confirmed_on.is_(None),
                m.HrmContract.probation_ends_on <= soon,
            )
        )
    ).scalars().all()
    return {
        "contracts_ending": [await serialize_contract(db, r) for r in ending],
        "probation_due": [await serialize_contract(db, r) for r in probation],
    }


# --- Disciplinary and grievance cases (confidential) ----------------------------------------


async def serialize_case(db: AsyncSession, row: m.HrmCase, *, full: bool = True) -> dict:
    body = {
        "id": row.id, "case_number": row.case_number, "employee_id": row.employee_id,
        "employee_name": await _name(db, row.employee_id), "kind": row.kind, "subject": row.subject,
        "status": row.status, "outcome": row.outcome, "created_at": _iso(row.created_at), "closed_at": _iso(row.closed_at),
    }
    if full:
        body.update(
            {
                "details": row.details, "hearing_at": _iso(row.hearing_at), "outcome_note": row.outcome_note,
                "employee_response": row.employee_response,
            }
        )
    return body


async def list_cases(db: AsyncSession, tenant_id: str) -> list[m.HrmCase]:
    return list((await db.execute(select(m.HrmCase).where(m.HrmCase.tenant_id == tenant_id).order_by(m.HrmCase.created_at.desc()))).scalars())


async def open_case(db: AsyncSession, tenant_id: str, *, employee_id: str, kind: str, subject: str, details: str, user_id) -> m.HrmCase:
    hrm = await _hrm()
    employee = await _person(db, tenant_id, employee_id)
    row = m.HrmCase(
        tenant_id=tenant_id, case_number=await hrm._next_number(db, tenant_id, m.HrmCase, "CASE"),
        employee_id=employee.id, kind=kind,
        subject=require_honest_narrative(subject, label="subject", max_length=160),
        details=require_honest_narrative(details, label="details", max_length=8000),
        status="open", raised_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, f"hrm_{kind}_opened", "hrm_case", row.id, {"case_number": row.case_number})
    return row


async def update_case(db: AsyncSession, tenant_id: str, case_id: str, payload, *, user_id) -> m.HrmCase:
    row = await _owned(db, m.HrmCase, tenant_id, case_id, "Case")
    if row.status == "closed":
        raise HTTPException(status_code=409, detail="This case is closed")
    if payload.hearing_at is not None:
        row.hearing_at = payload.hearing_at
    if payload.employee_response is not None:
        row.employee_response = optional_honest_narrative(payload.employee_response, label="response", max_length=8000)
    if payload.close:
        if payload.outcome not in CASE_OUTCOMES:
            raise HTTPException(status_code=422, detail="Record the outcome to close the case")
        if row.kind == "disciplinary" and payload.outcome in {"upheld", "not_upheld"}:
            raise HTTPException(status_code=422, detail="Choose a disciplinary outcome")
        if row.kind == "grievance" and payload.outcome not in {"upheld", "not_upheld", "none"}:
            raise HTTPException(status_code=422, detail="A grievance is upheld or not upheld")
        row.outcome = payload.outcome
        row.outcome_note = require_honest_narrative(payload.outcome_note, label="outcome note", max_length=8000)
        row.status = "closed"
        row.closed_by = user_id
        row.closed_at = datetime.utcnow()
    await _audit(db, tenant_id, user_id, "hrm_case_updated", "hrm_case", row.id, {"status": row.status, "outcome": row.outcome})
    await db.flush()
    return row


# --- Assets --------------------------------------------------------------------------------


async def serialize_asset(db: AsyncSession, row: m.HrmAsset) -> dict:
    return {
        "id": row.id, "employee_id": row.employee_id, "employee_name": await _name(db, row.employee_id),
        "item": row.item, "kind": row.kind, "serial": row.serial, "issued_on": _iso(row.issued_on),
        "condition_out": row.condition_out, "returned_on": _iso(row.returned_on), "condition_back": row.condition_back,
    }


async def list_assets(db: AsyncSession, tenant_id: str, *, employee_id: str | None = None) -> list[m.HrmAsset]:
    stmt = select(m.HrmAsset).where(m.HrmAsset.tenant_id == tenant_id).order_by(m.HrmAsset.issued_on.desc())
    if employee_id:
        stmt = stmt.where(m.HrmAsset.employee_id == employee_id)
    return list((await db.execute(stmt)).scalars())


async def issue_asset(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmAsset:
    employee = await _person(db, tenant_id, payload.employee_id)
    row = m.HrmAsset(
        tenant_id=tenant_id, employee_id=employee.id,
        item=require_honest_narrative(payload.item, label="item", max_length=160), kind=payload.kind,
        serial=optional_honest_narrative(payload.serial, label="serial", max_length=120), issued_on=payload.issued_on,
        condition_out=optional_honest_narrative(payload.condition, label="condition", max_length=120), created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_asset_issued", "hrm_asset", row.id, {"employee_id": employee.id, "item": row.item})
    return row


async def return_asset(db: AsyncSession, tenant_id: str, asset_id: str, payload, *, user_id) -> m.HrmAsset:
    row = await _owned(db, m.HrmAsset, tenant_id, asset_id, "Item")
    if row.returned_on:
        raise HTTPException(status_code=409, detail="Already handed back")
    if payload.returned_on < row.issued_on:
        raise HTTPException(status_code=422, detail="Returned before it was issued")
    row.returned_on = payload.returned_on
    row.condition_back = require_honest_narrative(payload.condition, label="condition", max_length=120)
    await _audit(db, tenant_id, user_id, "hrm_asset_returned", "hrm_asset", row.id, {"condition": row.condition_back})
    await db.flush()
    return row


# --- Expense claims ------------------------------------------------------------------------


async def serialize_claim(db: AsyncSession, row: m.HrmClaim) -> dict:
    return {
        "id": row.id, "claim_number": row.claim_number, "employee_id": row.employee_id,
        "employee_name": await _name(db, row.employee_id), "spent_on": _iso(row.spent_on), "description": row.description,
        "amount": money_json(row.amount), "receipt_ref": row.receipt_ref, "status": row.status,
        "decision_note": row.decision_note, "decided_at": _iso(row.decided_at), "paid_method": row.paid_method,
    }


async def list_claims(db: AsyncSession, tenant_id: str, *, employee_id: str | None = None) -> list[m.HrmClaim]:
    stmt = select(m.HrmClaim).where(m.HrmClaim.tenant_id == tenant_id).order_by(m.HrmClaim.created_at.desc())
    if employee_id:
        stmt = stmt.where(m.HrmClaim.employee_id == employee_id)
    return list((await db.execute(stmt)).scalars())


async def add_claim(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee, payload, *, user_id) -> m.HrmClaim:
    hrm = await _hrm()
    if payload.spent_on > date.today():
        raise HTTPException(status_code=422, detail="The date spent is in the future")
    row = m.HrmClaim(
        tenant_id=tenant_id, claim_number=await hrm._next_number(db, tenant_id, m.HrmClaim, "CLM"),
        employee_id=employee.id, spent_on=payload.spent_on,
        description=require_honest_narrative(payload.description, label="what it was for", max_length=255),
        amount=payload.amount, receipt_ref=optional_honest_narrative(payload.receipt_ref, label="receipt", max_length=120),
        status="pending", requested_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_claim_made", "hrm_claim", row.id, {"amount": money_json(row.amount)})
    from app import hrm_notify

    await hrm_notify.to_hr(
        db, tenant_id, "Claim to decide", f"{employee.full_name} made claim {row.claim_number}: {row.description}.",
        entity_type="hrm_claim", entity_id=row.id, skip_user=user_id,
    )
    return row


async def decide_claim(db: AsyncSession, tenant_id: str, claim_id: str, payload, *, user_id) -> m.HrmClaim:
    """Approve and pay it back (debit 6000 Operating Expenses, credit cash or bank), or turn it down."""
    hrm = await _hrm()
    row = await _owned(db, m.HrmClaim, tenant_id, claim_id, "Claim")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail=f"This claim is already {row.status}")
    me = await hrm._user_employee(db, tenant_id, user_id)
    if (me is not None and me.id == row.employee_id) or row.requested_by == user_id:
        raise HTTPException(status_code=403, detail="Someone else must decide your own claim")
    row.decided_by = user_id
    row.decided_at = datetime.utcnow()
    row.decision_note = optional_honest_narrative(payload.note, label="note", max_length=255)
    if not payload.approve:
        if not row.decision_note:
            raise HTTPException(status_code=422, detail="Say why it was turned down")
        row.status = "rejected"
        await _audit(db, tenant_id, user_id, "hrm_claim_rejected", "hrm_claim", row.id, {"note": row.decision_note})
        await db.flush()
        await _claim_notice(db, tenant_id, row, f"Claim {row.claim_number} was turned down: {row.decision_note}")
        return row
    if payload.method not in hrm.METHODS:
        raise HTTPException(status_code=422, detail="Choose how it was paid back")
    amount = money_json(row.amount)
    description = f"Staff claim {row.claim_number}: {row.description}"[:255]
    money_account = accounting.pos_debit_account_for_payment_method(payload.method)[0]
    row.journal_entry_id = await hrm._post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": "6000", "debit": amount, "credit": 0, "description": description},
            {"account_code": money_account, "debit": 0, "credit": amount, "description": description},
        ],
        reference=row.claim_number, source="hrm_claim", source_id=row.id,
    )
    row.status = "paid"
    row.paid_method = payload.method
    await _audit(db, tenant_id, user_id, "hrm_claim_paid", "hrm_claim", row.id, {"amount": amount, "method": payload.method})
    await db.flush()
    await _claim_notice(db, tenant_id, row, f"Claim {row.claim_number} was approved and paid back.")
    return row


async def _claim_notice(db, tenant_id, row, words: str) -> None:
    from app import hrm_notify

    await hrm_notify.to_person(
        db, tenant_id, await db.get(m.HrmEmployee, row.employee_id), "Claim decided", words, entity_type="hrm_claim", entity_id=row.id
    )


# --- Notices and policies ------------------------------------------------------------------


def serialize_notice(row: m.HrmNotice) -> dict:
    return {"id": row.id, "kind": row.kind, "title": row.title, "body": row.body, "is_active": bool(row.is_active), "created_at": _iso(row.created_at)}


async def list_notices(db: AsyncSession, tenant_id: str, *, active_only: bool = False) -> list[m.HrmNotice]:
    stmt = select(m.HrmNotice).where(m.HrmNotice.tenant_id == tenant_id).order_by(m.HrmNotice.created_at.desc())
    if active_only:
        stmt = stmt.where(m.HrmNotice.is_active.is_(True))
    return list((await db.execute(stmt)).scalars())


async def add_notice(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmNotice:
    row = m.HrmNotice(
        tenant_id=tenant_id, kind=payload.kind, title=require_honest_narrative(payload.title, label="title", max_length=160),
        body=require_honest_narrative(payload.body, label="text", max_length=20000), is_active=True, created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_notice_posted", "hrm_notice", row.id, {"kind": row.kind, "title": row.title})
    return row


async def retire_notice(db: AsyncSession, tenant_id: str, notice_id: str, *, user_id) -> m.HrmNotice:
    row = await _owned(db, m.HrmNotice, tenant_id, notice_id, "Notice")
    row.is_active = False
    await _audit(db, tenant_id, user_id, "hrm_notice_retired", "hrm_notice", row.id, {})
    await db.flush()
    return row
