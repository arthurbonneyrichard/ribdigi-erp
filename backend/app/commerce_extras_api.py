"""Gift cards, loyalty balances, hospital visits, and checkout payment notices."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import hospital as hospital_svc
from app import loyalty_gift as loyalty_gift_svc
from app import models as m
from app.db import get_db
from app.honesty import money_json
from app.security import require_permission

router = APIRouter(tags=["commerce-extras"])


def _env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


class GiftCardIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: float = Field(gt=0)
    party_id: str | None = None


class LoyaltyAdjust(BaseModel):
    model_config = ConfigDict(extra="forbid")
    delta: float


class PatientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    phone: str | None = None
    notes: str | None = None


class EncounterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: str
    reason: str


class PaymentNoticeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: float = Field(gt=0)
    method: str
    reference: str
    note: str | None = None


@router.post("/gift-cards")
async def issue_gift_card(
    payload: GiftCardIssue,
    claims=Depends(require_permission("pos", "write")),
    db: AsyncSession = Depends(get_db),
):
    from app.industry_dashboard import assert_gift_cards_for_industry

    assert_gift_cards_for_industry(claims)
    row = await loyalty_gift_svc.issue_gift_card(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        amount=payload.amount,
        party_id=payload.party_id,
    )
    await db.commit()
    return _env(loyalty_gift_svc.serialize_card(row), "Gift card issued")


@router.get("/gift-cards")
async def list_gift_cards(
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    """The company's gift cards, newest first (most recent 200)."""
    rows = (
        await db.execute(
            select(m.GiftCard)
            .where(m.GiftCard.tenant_id == claims["tenant_id"])
            .order_by(m.GiftCard.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    return _env([loyalty_gift_svc.serialize_card(r) for r in rows])


@router.get("/gift-cards/{code}")
async def read_gift_card(
    code: str,
    claims=Depends(require_permission("pos", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await loyalty_gift_svc.get_gift_card(db, tenant_id=claims["tenant_id"], code=code)
    return _env(loyalty_gift_svc.serialize_card(row))


@router.post("/customers/{party_id}/loyalty")
async def adjust_customer_loyalty(
    party_id: str,
    payload: LoyaltyAdjust,
    claims=Depends(require_permission("customers", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await loyalty_gift_svc.adjust_loyalty(
        db, tenant_id=claims["tenant_id"], party_id=party_id, delta=payload.delta
    )
    await db.commit()
    return _env({"party_id": row.id, "loyalty_points": money_json(row.loyalty_points or 0)})


@router.get("/customers/{party_id}/loyalty")
async def read_customer_loyalty(
    party_id: str,
    claims=Depends(require_permission("customers", "read")),
    db: AsyncSession = Depends(get_db),
):
    row = await loyalty_gift_svc._customer(db, claims["tenant_id"], party_id)
    return _env({"party_id": row.id, "loyalty_points": money_json(row.loyalty_points or 0)})


@router.post("/hospital/patients")
async def create_hospital_patient(
    payload: PatientCreate,
    claims=Depends(require_permission("hospital", "write")),
    db: AsyncSession = Depends(get_db),
):
    hospital_svc.assert_hospital(claims)
    row = await hospital_svc.create_patient(
        db,
        tenant_id=claims["tenant_id"],
        name=payload.name,
        phone=payload.phone,
        notes=payload.notes,
    )
    await db.commit()
    return _env(hospital_svc.serialize_patient(row), "Patient recorded")


@router.get("/hospital/patients")
async def list_hospital_patients(
    claims=Depends(require_permission("hospital", "read")),
    db: AsyncSession = Depends(get_db),
):
    hospital_svc.assert_hospital(claims)
    rows = await hospital_svc.list_patients(db, claims["tenant_id"])
    return _env([hospital_svc.serialize_patient(r) for r in rows])


@router.post("/hospital/encounters")
async def open_hospital_encounter(
    payload: EncounterCreate,
    claims=Depends(require_permission("hospital", "write")),
    db: AsyncSession = Depends(get_db),
):
    hospital_svc.assert_hospital(claims)
    row = await hospital_svc.open_encounter(
        db,
        tenant_id=claims["tenant_id"],
        patient_id=payload.patient_id,
        reason=payload.reason,
    )
    await db.commit()
    return _env(hospital_svc.serialize_encounter(row), "Visit opened")


@router.post("/hospital/encounters/{encounter_id}/close")
async def close_hospital_encounter(
    encounter_id: str,
    claims=Depends(require_permission("hospital", "write")),
    db: AsyncSession = Depends(get_db),
):
    hospital_svc.assert_hospital(claims)
    row = await hospital_svc.close_encounter(
        db, tenant_id=claims["tenant_id"], encounter_id=encounter_id
    )
    await db.commit()
    return _env(hospital_svc.serialize_encounter(row), "Visit closed")


@router.post("/billing/payment-notices")
async def create_payment_notice(
    payload: PaymentNoticeCreate,
    claims=Depends(require_permission("accounting", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await loyalty_gift_svc.record_payment_notice(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
        note=payload.note,
    )
    await db.commit()
    return _env(
        loyalty_gift_svc.notice_payload(row),
        "Payment notice saved.",
    )


@router.get("/billing/payment-notices")
async def list_payment_notices(
    claims=Depends(require_permission("accounting", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(m.CheckoutPaymentNotice)
            .where(m.CheckoutPaymentNotice.tenant_id == claims["tenant_id"])
            .order_by(m.CheckoutPaymentNotice.created_at.desc())
        )
    ).scalars().all()
    return _env([loyalty_gift_svc.notice_payload(r) for r in rows])
