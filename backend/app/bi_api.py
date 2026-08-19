"""API routes for Smart Business Intelligence (Layer 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.bi_defaults import FORMULA_DOCS
from app.bi_service import BusinessIntelligenceService
from app.db import get_db
from app.security import require_permission

router = APIRouter(prefix="/business-insights", tags=["business-insights"])


class SettingsPatch(BaseModel):
    slow_moving_days: int | None = None
    dead_stock_days: int | None = None
    expiry_warning_days: list[int] | None = None
    safety_stock_days: int | None = None
    default_lead_time_days: int | None = None
    sales_decline_warning_pct: float | None = None
    sales_growth_opportunity_pct: float | None = None
    expense_increase_warning_pct: float | None = None
    expense_to_sales_warning_pct: float | None = None
    credit_overdue_attention_days: int | None = None
    credit_concentration_warning_pct: float | None = None
    sales_anomaly_pct: float | None = None
    large_discount_pct: float | None = None
    health_weights: dict[str, float] | None = None


def _svc(db: AsyncSession, claims: dict) -> BusinessIntelligenceService:
    return BusinessIntelligenceService(db, claims)


@router.get("/overview")
async def bi_overview(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db, claims).build_bundle()


@router.get("/attention")
async def bi_attention(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    bundle = await _svc(db, claims).build_bundle()
    return {
        "items": bundle["attention"],
        "health": bundle["health"],
        "generated_at": bundle["generated_at"],
        "external_ai_required": False,
    }


@router.get("/sales")
async def bi_sales(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    bundle = await _svc(db, claims).build_bundle()
    return {
        "sales": bundle["sales"],
        "top_products": bundle["top_products"],
        "locations": bundle["locations"],
        "insights": [i for i in bundle["insights"] if i["category"] == "sales"],
    }


@router.get("/inventory")
async def bi_inventory(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    bundle = await _svc(db, claims).build_bundle()
    return {
        "inventory": bundle["inventory"],
        "expiry": bundle["expiry"],
        "slow_dead": bundle["slow_dead"],
        "reorder_recommendations": bundle["reorder_recommendations"],
        "insights": [
            i
            for i in bundle["insights"]
            if i["category"] in ("inventory", "expiry")
        ],
    }


@router.get("/credit")
async def bi_credit(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db, claims)
    if not svc.can_read_credit():
        raise HTTPException(status_code=403, detail="credit:read required")
    bundle = await svc.build_bundle()
    return {
        "credit": bundle["credit"],
        "insights": [i for i in bundle["insights"] if i["category"] == "credit"],
    }


@router.get("/expenses")
async def bi_expenses(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    bundle = await _svc(db, claims).build_bundle()
    return {
        "expenses": bundle["expenses"],
        "insights": [i for i in bundle["insights"] if i["category"] == "expenses"],
    }


@router.get("/profit")
async def bi_profit(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc = _svc(db, claims)
    if not svc.can_read_financial():
        raise HTTPException(status_code=403, detail="accounting:read or reports:read required")
    bundle = await svc.build_bundle()
    return {
        "profit": bundle["profit"],
        "insights": [i for i in bundle["insights"] if i["category"] == "profit"],
    }


@router.get("/opportunities")
async def bi_opportunities(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    bundle = await _svc(db, claims).build_bundle()
    return {"items": bundle["opportunities"]}


@router.get("/health-score")
async def bi_health(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    bundle = await _svc(db, claims).build_bundle()
    return bundle["health"]


@router.get("/history")
async def bi_history(
    status: str | None = None,
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    return {"items": await _svc(db, claims).list_history(status=status)}


@router.post("/{insight_id}/acknowledge")
async def bi_acknowledge(
    insight_id: str,
    claims=Depends(require_permission("business_insights", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await _svc(db, claims).acknowledge(insight_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    return row


@router.post("/{insight_id}/dismiss")
async def bi_dismiss(
    insight_id: str,
    claims=Depends(require_permission("business_insights", "write")),
    db: AsyncSession = Depends(get_db),
):
    row = await _svc(db, claims).dismiss(insight_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    return row


@router.get("/settings")
async def bi_get_settings(
    claims=Depends(require_permission("business_insights", "read")),
    db: AsyncSession = Depends(get_db),
):
    return {"settings": await _svc(db, claims).load_settings(), "formulas": FORMULA_DOCS}


@router.put("/settings")
async def bi_put_settings(
    body: SettingsPatch,
    claims=Depends(require_permission("business_insights", "write")),
    db: AsyncSession = Depends(get_db),
):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    settings = await _svc(db, claims).save_settings(patch)
    return {"settings": settings}


@router.get("/formulas")
async def bi_formulas(
    claims=Depends(require_permission("business_insights", "read")),
    _db: AsyncSession = Depends(get_db),
):
    return {"formulas": FORMULA_DOCS, "external_ai": False}
