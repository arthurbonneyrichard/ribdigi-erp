"""HRM routes for people work: recruitment, reviews, training, contracts, cases, assets,
claims and notices. The `hrm` permission and industry gate come from require_permission;
`hrm.job` limits each HR role (officers do people admin; reviews, claims, cases, offers
and hiring need an HR manager; staff use the /me routes for their own)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm as svc
from app import hrm_people as people
from app.db import get_db
from app.schemas import E164PhoneValue, NonNegativeMoneyValue, PartyNameValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hrm", tags=["hrm"])

Text = Annotated[str, Field(min_length=2, max_length=4000)]
Short = Annotated[str, Field(min_length=2, max_length=160)]
PayMethod = Literal["bank_transfer", "cash", "mobile_money", "cheque"]
Money = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _w():
    return Depends(require_permission("hrm", "write"))


def _r():
    return Depends(require_permission("hrm", "read"))


# --- Bodies --------------------------------------------------------------------------------


class VacancyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Short
    department: Short | None = None
    openings: Annotated[int, Field(ge=1, le=500)] = 1
    description: Text | None = None
    closes_on: date | None = None


class CandidateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: PartyNameValue
    email: EmailStr | None = None
    phone: E164PhoneValue | None = None
    notes: Text | None = None


class MoveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["screening", "interview", "offer", "rejected", "withdrawn", "hired"]
    interview_at: datetime | None = None
    score: Annotated[int, Field(ge=0, le=100)] | None = None
    offered_basic: NonNegativeMoneyValue | None = None
    note: Annotated[str, Field(min_length=1, max_length=1000)] | None = None


class HireBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    starts_on: date
    allowances: NonNegativeMoneyValue = 0
    probation_months: Annotated[int, Field(ge=0, le=24)] = 0
    manager_id: UuidIdValue | None = None


class Goal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Short
    weight: Annotated[int, Field(ge=1, le=100)]
    # Optional KPI: a number to reach and what it is counted in.
    target: Annotated[Decimal, Field(max_digits=16, decimal_places=2)] | None = None
    unit: Annotated[str, Field(min_length=1, max_length=30)] | None = None


class ProgressBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: Annotated[int, Field(ge=0, le=11)]
    actual: Annotated[Decimal, Field(max_digits=16, decimal_places=2)]


class AskFeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_ids: list[UuidIdValue] = Field(min_length=1, max_length=20)


class GiveFeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Annotated[int, Field(ge=1, le=5)]
    strengths: Annotated[str, Field(max_length=2000)] | None = None
    improve: Annotated[str, Field(max_length=2000)] | None = None


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: UuidIdValue
    cycle: Annotated[str, Field(min_length=2, max_length=60)]
    goals: list[Goal] = Field(min_length=1, max_length=12)


class ScoreBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scores: list[Annotated[int, Field(ge=1, le=5)]] = Field(min_length=1, max_length=12)
    comment: Text | None = None


class TrainingBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Short
    provider: Short | None = None
    mandatory: bool = False
    valid_months: Annotated[int, Field(ge=1, le=120)] | None = None


class TrainingRecordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    training_id: UuidIdValue
    employee_id: UuidIdValue
    completed_on: date
    result: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    certificate_ref: Annotated[str, Field(min_length=1, max_length=120)] | None = None


class ContractBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: UuidIdValue
    kind: Literal["permanent", "fixed_term", "casual", "probation"]
    starts_on: date
    ends_on: date | None = None
    probation_ends_on: date | None = None
    reference: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    notes: Text | None = None


class CaseBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: UuidIdValue
    kind: Literal["disciplinary", "grievance"]
    subject: Short
    details: Text


class CaseUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hearing_at: datetime | None = None
    employee_response: Text | None = None
    close: bool = False
    outcome: str | None = None
    outcome_note: Text | None = None


class GrievanceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: Short
    details: Text


class AssetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    employee_id: UuidIdValue
    item: Short
    kind: Literal["laptop", "phone", "uniform", "vehicle", "tool", "other"] = "other"
    serial: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    issued_on: date
    condition: Annotated[str, Field(min_length=2, max_length=120)] | None = None


class AssetReturnBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    returned_on: date
    condition: Annotated[str, Field(min_length=2, max_length=120)]


class ClaimBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spent_on: date
    description: Short
    amount: Money
    receipt_ref: Annotated[str, Field(min_length=1, max_length=120)] | None = None


class StaffClaimBody(ClaimBody):
    employee_id: UuidIdValue


class ClaimDecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approve: bool
    method: PayMethod | None = None
    note: Annotated[str, Field(min_length=1, max_length=255)] | None = None


class NoticeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["announcement", "policy"]
    title: Short
    body: Annotated[str, Field(min_length=2, max_length=20000)]


# --- Recruitment ---------------------------------------------------------------------------


@router.get("/vacancies")
async def vacancies(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "recruitment")
    return _env(await people.list_vacancies(db, claims["tenant_id"]))


@router.post("/vacancies")
async def vacancy_add(payload: VacancyBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "recruitment")
    row = await people.add_vacancy(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(people.serialize_vacancy(row), "Vacancy opened")


@router.post("/vacancies/{vacancy_id}/close")
async def vacancy_close(vacancy_id: UuidIdValue, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "recruitment")
    row = await people.close_vacancy(db, claims["tenant_id"], vacancy_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(people.serialize_vacancy(row), "Vacancy closed")


@router.get("/vacancies/{vacancy_id}/candidates")
async def candidates(vacancy_id: UuidIdValue, claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "recruitment")
    rows = await people.list_candidates(db, claims["tenant_id"], vacancy_id)
    sees_pay = svc.sees_pay(claims)
    out = [people.serialize_candidate(r) for r in rows]
    if not sees_pay:
        for row in out:
            row.pop("offered_basic", None)
    return _env(out)


@router.post("/vacancies/{vacancy_id}/candidates")
async def candidate_add(vacancy_id: UuidIdValue, payload: CandidateBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "recruitment")
    row = await people.add_candidate(db, claims["tenant_id"], vacancy_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(people.serialize_candidate(row), "Candidate added")


@router.post("/candidates/{candidate_id}/move")
async def candidate_move(candidate_id: UuidIdValue, payload: MoveBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    # An offer names a salary, so it needs someone who sees pay.
    svc.job(claims, "payroll" if payload.stage == "offer" or payload.offered_basic is not None else "recruitment")
    row = await people.move_candidate(db, claims["tenant_id"], candidate_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(people.serialize_candidate(row), "Candidate moved")


@router.post("/candidates/{candidate_id}/hire")
async def candidate_hire(candidate_id: UuidIdValue, payload: HireBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    employee = await people.hire(db, claims["tenant_id"], candidate_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.serialize_employee(employee), "Hired: their staff record is ready")


# --- Reviews -------------------------------------------------------------------------------


@router.get("/reviews")
async def reviews(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "reviews")
    return _env([await people.serialize_review(db, r, as_hr=True) for r in await people.list_reviews(db, claims["tenant_id"])])


@router.post("/reviews")
async def review_start(payload: ReviewBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "reviews")
    row = await people.start_review(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_review(db, row), "Review started")


@router.post("/reviews/{review_id}/complete")
async def review_complete(review_id: UuidIdValue, payload: ScoreBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "reviews")
    row = await people.complete_review(db, claims["tenant_id"], review_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_review(db, row), "Review finished")


@router.post("/reviews/{review_id}/progress")
async def review_progress(review_id: UuidIdValue, payload: ProgressBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "reviews")
    from app import hrm_feedback

    row = await hrm_feedback.record_progress(db, claims["tenant_id"], review_id, index=payload.goal, actual=payload.actual, me=None, as_hr=True, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_review(db, row, as_hr=True), "Progress saved")


@router.post("/me/reviews/{review_id}/progress")
async def my_review_progress(review_id: UuidIdValue, payload: ProgressBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "self")
    from app import hrm_feedback

    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    row = await hrm_feedback.record_progress(db, claims["tenant_id"], review_id, index=payload.goal, actual=payload.actual, me=me, as_hr=False, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_review(db, row), "Progress saved")


@router.post("/reviews/{review_id}/feedback")
async def review_ask_feedback(review_id: UuidIdValue, payload: AskFeedbackBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "reviews")
    from app import hrm_feedback

    added = await hrm_feedback.ask(db, claims["tenant_id"], review_id, payload.employee_ids, user_id=claims.get("sub"))
    await db.commit()
    return _env({"asked": added}, f"Asked {added} colleague(s)")


@router.get("/me/feedback")
async def my_feedback_requests(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "self")
    from app import hrm_feedback

    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    return _env(await hrm_feedback.my_requests(db, claims["tenant_id"], me))


@router.post("/me/feedback/{feedback_id}")
async def give_feedback(feedback_id: UuidIdValue, payload: GiveFeedbackBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "self")
    from app import hrm_feedback

    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    await hrm_feedback.give(db, claims["tenant_id"], feedback_id, me, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env({"given": True}, "Thank you. Your feedback is shown without your name.")


@router.post("/me/reviews/{review_id}/self")
async def review_self(review_id: UuidIdValue, payload: ScoreBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    row = await people.self_assess(db, claims["tenant_id"], review_id, me, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_review(db, row), "Your view is sent")


# --- Training ------------------------------------------------------------------------------


@router.get("/trainings")
async def trainings(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "training")
    tid = claims["tenant_id"]
    return _env(
        {
            "courses": [people.serialize_training(r) for r in await people.list_trainings(db, tid)],
            "records": [await people.serialize_record(db, r) for r in await people.list_records(db, tid)],
            "gaps": await people.training_gaps(db, tid),
        }
    )


@router.post("/trainings")
async def training_add(payload: TrainingBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "training")
    row = await people.add_training(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(people.serialize_training(row), "Course added")


@router.post("/training-records")
async def training_record(payload: TrainingRecordBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "training")
    row = await people.record_training(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_record(db, row), "Training recorded")


# --- Contracts -----------------------------------------------------------------------------


@router.get("/contracts")
async def contracts(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "contracts")
    tid = claims["tenant_id"]
    return _env(
        {
            "contracts": [await people.serialize_contract(db, r) for r in await people.list_contracts(db, tid)],
            "alerts": await people.contract_alerts(db, tid),
        }
    )


@router.post("/contracts")
async def contract_add(payload: ContractBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "contracts")
    row = await people.add_contract(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_contract(db, row), "Contract saved")


@router.post("/contracts/{contract_id}/confirm")
async def contract_confirm(contract_id: UuidIdValue, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "contracts")
    row = await people.confirm_probation(db, claims["tenant_id"], contract_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_contract(db, row), "Probation confirmed")


# --- Cases ---------------------------------------------------------------------------------


@router.get("/cases")
async def cases(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "cases")
    return _env([await people.serialize_case(db, r) for r in await people.list_cases(db, claims["tenant_id"])])


@router.post("/cases")
async def case_open(payload: CaseBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "cases")
    row = await people.open_case(
        db, claims["tenant_id"], employee_id=payload.employee_id, kind=payload.kind,
        subject=payload.subject, details=payload.details, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(await people.serialize_case(db, row), "Case opened")


@router.patch("/cases/{case_id}")
async def case_update(case_id: UuidIdValue, payload: CaseUpdateBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "cases")
    row = await people.update_case(db, claims["tenant_id"], case_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_case(db, row), "Case closed" if payload.close else "Case updated")


@router.post("/me/grievances")
async def my_grievance(payload: GrievanceBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    row = await people.open_case(
        db, claims["tenant_id"], employee_id=me.id, kind="grievance",
        subject=payload.subject, details=payload.details, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(await people.serialize_case(db, row, full=False), "Sent to HR in confidence")


# --- Assets --------------------------------------------------------------------------------


@router.get("/assets")
async def assets(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "assets")
    return _env([await people.serialize_asset(db, r) for r in await people.list_assets(db, claims["tenant_id"])])


@router.post("/assets")
async def asset_issue(payload: AssetBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "assets")
    row = await people.issue_asset(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_asset(db, row), "Item issued")


@router.post("/assets/{asset_id}/return")
async def asset_return(asset_id: UuidIdValue, payload: AssetReturnBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "assets")
    row = await people.return_asset(db, claims["tenant_id"], asset_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_asset(db, row), "Item handed back")


# --- Claims --------------------------------------------------------------------------------


@router.get("/claims")
async def claims_list(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "claims")
    return _env([await people.serialize_claim(db, r) for r in await people.list_claims(db, claims["tenant_id"])])


@router.post("/claims")
async def claim_for_staff(payload: StaffClaimBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "claims")
    employee = await svc._employee(db, claims["tenant_id"], payload.employee_id)
    row = await people.add_claim(db, claims["tenant_id"], employee, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_claim(db, row), "Claim recorded")


@router.post("/claims/{claim_id}/decide")
async def claim_decide(claim_id: UuidIdValue, payload: ClaimDecideBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "claims")
    row = await people.decide_claim(db, claims["tenant_id"], claim_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_claim(db, row), "Paid back" if payload.approve else "Turned down")


@router.post("/me/claims")
async def my_claim(payload: ClaimBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    row = await people.add_claim(db, claims["tenant_id"], me, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await people.serialize_claim(db, row), "Claim sent")


# --- Notices -------------------------------------------------------------------------------


@router.get("/notices")
async def notices(claims=_r(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "notices")
    return _env([people.serialize_notice(r) for r in await people.list_notices(db, claims["tenant_id"])])


@router.post("/notices")
async def notice_add(payload: NoticeBody, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "notices")
    row = await people.add_notice(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(people.serialize_notice(row), "Posted")


@router.post("/notices/{notice_id}/retire")
async def notice_retire(notice_id: UuidIdValue, claims=_w(), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "notices")
    row = await people.retire_notice(db, claims["tenant_id"], notice_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(people.serialize_notice(row), "Taken down")


# --- My file -------------------------------------------------------------------------------


@router.get("/me/more")
async def my_more(claims=_r(), db: AsyncSession = Depends(get_db)):
    """Everything else on my own file: reviews, training, kit, claims, my grievances, notices."""
    tid = claims["tenant_id"]
    me = await svc.employee_for_user(db, tid, claims.get("sub"))
    my_cases = [c for c in await people.list_cases(db, tid) if c.employee_id == me.id]
    return _env(
        {
            "reviews": [await people.serialize_review(db, r) for r in await people.list_reviews(db, tid, employee_id=me.id)],
            "training": [await people.serialize_record(db, r) for r in await people.list_records(db, tid, employee_id=me.id)],
            "assets": [await people.serialize_asset(db, r) for r in await people.list_assets(db, tid, employee_id=me.id) if not r.returned_on],
            "claims": [await people.serialize_claim(db, r) for r in await people.list_claims(db, tid, employee_id=me.id)],
            # Staff see that a case exists and how it ended, not HR's notes.
            "cases": [await people.serialize_case(db, c, full=False) for c in my_cases],
            "contracts": [await people.serialize_contract(db, r) for r in await people.list_contracts(db, tid, employee_id=me.id)],
            "notices": [people.serialize_notice(r) for r in await people.list_notices(db, tid, active_only=True)],
        }
    )
