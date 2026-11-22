"""FMCG proof of delivery, quality inspection and complaint routes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_orders as orders
from app import fmcg_quality as svc
from app.db import get_db
from app.schemas import NonNegativeQtyValue, PositiveQtyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg", tags=["fmcg"])

Name = Annotated[str, Field(min_length=2, max_length=150)]
Short = Annotated[str, Field(min_length=3, max_length=500)]
Long = Annotated[str, Field(min_length=3, max_length=2000)]
Image = Annotated[str, Field(max_length=1_200_000)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class PodBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_name: Name
    signature: Image | None = None
    photo: Image | None = None
    latitude: Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)] | None = None
    longitude: Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)] | None = None
    accuracy_m: Annotated[float, Field(ge=0, le=100000, allow_inf_nan=False)] | None = None
    notes: Short | None = None


class InspectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UuidIdValue
    batch_id: UuidIdValue | None = None
    supplier_id: UuidIdValue | None = None
    sample_size: NonNegativeQtyValue = 0
    packaging_ok: bool | None = None
    label_ok: bool | None = None
    expiry_ok: bool | None = None
    temperature_c: Annotated[float, Field(ge=-80, le=80, allow_inf_nan=False)] | None = None
    certificate_ref: Annotated[str, Field(min_length=2, max_length=120)] | None = None
    notes: Annotated[str, Field(min_length=3, max_length=1000)] | None = None
    hold_until_decided: bool = False


class DecideBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result: Literal["pass", "fail", "conditional"]
    note: Annotated[str, Field(min_length=3, max_length=1000)] | None = None
    rejected_qty: NonNegativeQtyValue = 0


class ComplaintBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: UuidIdValue | None = None
    order_id: UuidIdValue | None = None
    product_id: UuidIdValue | None = None
    batch_id: UuidIdValue | None = None
    category: Literal["quality", "damaged", "short", "wrong", "expiry", "other"]
    description: Long


class ComplaintStatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["investigating", "resolved", "rejected"]
    resolution: Long | None = None


@router.post("/orders/{order_id}/pod")
async def pod_capture(
    order_id: UuidIdValue, payload: PodBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "deliver")
    data = await svc.record_pod(
        db, tenant_id=claims["tenant_id"], order_id=order_id, recipient_name=payload.recipient_name,
        signature=payload.signature, photo=payload.photo, latitude=payload.latitude, longitude=payload.longitude,
        accuracy_m=payload.accuracy_m, notes=payload.notes, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Proof of delivery saved")


@router.get("/orders/{order_id}/pod")
async def pod_get(
    order_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "deliver")
    return _env(await svc.get_pod(db, tenant_id=claims["tenant_id"], order_id=order_id))


@router.get("/pod/missing")
async def pod_missing(
    days: Annotated[int, Query(ge=1, le=365)] = 30,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "deliver")
    return _env(await svc.missing_pod(db, tenant_id=claims["tenant_id"], days=days))


@router.get("/quality/inspections")
async def qc_list(
    status: Literal["pending", "passed", "failed", "conditional"] | None = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "quality")
    return _env(await svc.list_inspections(db, tenant_id=claims["tenant_id"], status=status))


@router.post("/quality/inspections")
async def qc_open(
    payload: InspectionBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "quality")
    data = await svc.create_inspection(
        db, tenant_id=claims["tenant_id"], product_id=payload.product_id, batch_id=payload.batch_id,
        supplier_id=payload.supplier_id, sample_size=payload.sample_size, packaging_ok=payload.packaging_ok,
        label_ok=payload.label_ok, expiry_ok=payload.expiry_ok, temperature_c=payload.temperature_c,
        certificate_ref=payload.certificate_ref, notes=payload.notes,
        hold_until_decided=payload.hold_until_decided, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Inspection opened")


@router.post("/quality/inspections/{inspection_id}/decide")
async def qc_decide(
    inspection_id: UuidIdValue, payload: DecideBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "quality")
    data = await svc.decide_inspection(
        db, tenant_id=claims["tenant_id"], inspection_id=inspection_id, result=payload.result,
        note=payload.note, rejected_qty=payload.rejected_qty, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Decision saved")


@router.get("/quality/suppliers")
async def qc_suppliers(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "quality")
    return _env(await svc.supplier_quality(db, tenant_id=claims["tenant_id"]))


@router.get("/complaints")
async def complaints_list(
    status: Literal["open", "investigating", "resolved", "rejected"] | None = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "complaints")
    return _env(await svc.list_complaints(db, tenant_id=claims["tenant_id"], status=status))


@router.post("/complaints")
async def complaint_open(
    payload: ComplaintBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "complaints")
    data = await svc.create_complaint(
        db, tenant_id=claims["tenant_id"], customer_id=payload.customer_id, order_id=payload.order_id,
        product_id=payload.product_id, batch_id=payload.batch_id, category=payload.category,
        description=payload.description, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Complaint logged")


@router.post("/complaints/{complaint_id}/status")
async def complaint_status(
    complaint_id: UuidIdValue, payload: ComplaintStatusBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "quality")
    data = await svc.set_complaint_status(
        db, tenant_id=claims["tenant_id"], complaint_id=complaint_id, status=payload.status,
        resolution=payload.resolution, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Updated")
