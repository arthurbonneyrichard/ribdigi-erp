"""Tenant onboarding checklist (Stage 6 N2 / Phase 5 UI checklist)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

# Roadmap: Setup company → Add products → Create supplier → (+ stock) → Make first sale
STEP_DEFS: list[dict[str, str]] = [
    {
        "id": "setup_company",
        "title": "Setup company profile",
        "description": "Add phone, address, legal name, or company logo",
        "href": "/company",
    },
    {
        "id": "add_products",
        "title": "Add products",
        "description": "Create at least one product in the catalog",
        "href": "/inventory",
    },
    {
        "id": "create_supplier",
        "title": "Create a supplier",
        "description": "Add a supplier for purchasing",
        "href": "/purchasing",
    },
    {
        "id": "stock_ready",
        "title": "Stock on hand",
        "description": "Record opening stock or receive inventory",
        "href": "/inventory",
    },
    {
        "id": "first_sale",
        "title": "Make first sale",
        "description": "Post a sales invoice or complete a POS sale",
        "href": "/sales",
    },
]

VALID_STEP_IDS = frozenset(s["id"] for s in STEP_DEFS)
DISMISS_THRESHOLD_PCT = 80


def _state(tenant: m.Tenant) -> dict[str, Any]:
    raw = tenant.onboarding_state if isinstance(tenant.onboarding_state, dict) else {}
    skipped = [str(x) for x in (raw.get("skipped") or []) if str(x) in VALID_STEP_IDS]
    return {
        "dismissed_at": raw.get("dismissed_at"),
        "skipped": skipped,
    }


async def _auto_complete(db: AsyncSession, tenant_id: str, tenant: m.Tenant) -> dict[str, bool]:
    company_done = bool(
        (tenant.logo_url or "").strip()
        or (tenant.phone or "").strip()
        or (tenant.legal_name or "").strip()
        or (tenant.address or "").strip()
        or (tenant.email or "").strip()
    )

    product_count = int(
        (
            await db.execute(
                select(func.count()).select_from(m.Product).where(m.Product.tenant_id == tenant_id)
            )
        ).scalar_one()
        or 0
    )

    supplier_count = int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.Party)
                .where(m.Party.tenant_id == tenant_id, m.Party.kind == "supplier")
            )
        ).scalar_one()
        or 0
    )

    stock_product = (
        await db.execute(
            select(m.Product.id)
            .where(m.Product.tenant_id == tenant_id, m.Product.stock_qty > 0)
            .limit(1)
        )
    ).scalar_one_or_none()
    stock_wh = (
        await db.execute(
            select(m.WarehouseStock.id)
            .where(m.WarehouseStock.tenant_id == tenant_id, m.WarehouseStock.quantity > 0)
            .limit(1)
        )
    ).scalar_one_or_none()

    posted_invoice = (
        await db.execute(
            select(m.SalesInvoice.id)
            .where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(("posted", "sent", "partial", "paid", "overdue")),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    pos_sale = (
        await db.execute(
            select(m.Transaction.id).where(m.Transaction.tenant_id == tenant_id).limit(1)
        )
    ).scalar_one_or_none()

    return {
        "setup_company": company_done,
        "add_products": product_count >= 1,
        "create_supplier": supplier_count >= 1,
        "stock_ready": bool(stock_product or stock_wh),
        "first_sale": bool(posted_invoice or pos_sale),
    }


async def build_checklist(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    state = _state(tenant)
    auto = await _auto_complete(db, tenant_id, tenant)
    skipped = set(state["skipped"])
    steps = []
    done_count = 0
    for meta in STEP_DEFS:
        sid = meta["id"]
        auto_done = bool(auto.get(sid))
        is_skipped = sid in skipped
        completed = auto_done or is_skipped
        if completed:
            done_count += 1
        steps.append(
            {
                **meta,
                "completed": completed,
                "auto_completed": auto_done,
                "skipped": is_skipped and not auto_done,
            }
        )
    total = len(STEP_DEFS)
    progress_pct = int(round((done_count / total) * 100)) if total else 100
    dismissed = bool(state.get("dismissed_at"))
    dismissible = progress_pct >= DISMISS_THRESHOLD_PCT
    visible = not dismissed and progress_pct < 100
    return {
        "steps": steps,
        "completed_count": done_count,
        "total_count": total,
        "progress_pct": progress_pct,
        "dismissed": dismissed,
        "dismissed_at": state.get("dismissed_at"),
        "dismissible": dismissible,
        "visible": visible,
        "dismiss_threshold_pct": DISMISS_THRESHOLD_PCT,
    }


def _save_state(tenant: m.Tenant, state: dict) -> None:
    tenant.onboarding_state = {
        "dismissed_at": state.get("dismissed_at"),
        "skipped": [s for s in (state.get("skipped") or []) if s in VALID_STEP_IDS],
    }


async def skip_step(db: AsyncSession, tenant_id: str, step_id: str) -> dict[str, Any]:
    if step_id not in VALID_STEP_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_id}")
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    state = _state(tenant)
    if step_id not in state["skipped"]:
        state["skipped"].append(step_id)
    _save_state(tenant, state)
    await db.flush()
    return await build_checklist(db, tenant_id)


async def unskip_step(db: AsyncSession, tenant_id: str, step_id: str) -> dict[str, Any]:
    if step_id not in VALID_STEP_IDS:
        raise HTTPException(status_code=400, detail=f"Unknown step: {step_id}")
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    state = _state(tenant)
    state["skipped"] = [s for s in state["skipped"] if s != step_id]
    _save_state(tenant, state)
    await db.flush()
    return await build_checklist(db, tenant_id)


async def dismiss(db: AsyncSession, tenant_id: str, *, force: bool = False) -> dict[str, Any]:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    checklist = await build_checklist(db, tenant_id)
    if not force and not checklist["dismissible"] and checklist["progress_pct"] < 100:
        raise HTTPException(
            status_code=400,
            detail=f"Complete at least {DISMISS_THRESHOLD_PCT}% of onboarding before dismissing",
        )
    state = _state(tenant)
    state["dismissed_at"] = datetime.utcnow().isoformat() + "Z"
    _save_state(tenant, state)
    await db.flush()
    return await build_checklist(db, tenant_id)


async def restore(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    state = _state(tenant)
    state["dismissed_at"] = None
    _save_state(tenant, state)
    await db.flush()
    return await build_checklist(db, tenant_id)
