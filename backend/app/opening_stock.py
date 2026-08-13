"""Opening stock entry (BR-5.2) — initialize on-hand qty for go-live / fiscal year."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.catalog import stock_in_with_batch


async def post_opening_stock(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    lines: list[dict],
    post_journal: bool = True,
    reference: str | None = None,
    notes: str | None = None,
) -> dict:
    if not lines:
        raise HTTPException(status_code=400, detail="Opening stock requires at least one line")

    entry_id = str(uuid.uuid4())
    ref_label = (reference or "").strip() or f"OS-{datetime.utcnow():%Y%m%d%H%M%S}"
    results: list[dict] = []
    inventory_value = 0.0

    for raw in lines:
        product_id = raw.get("product_id")
        if not product_id:
            raise HTTPException(status_code=400, detail="Each line needs product_id")
        qty = float(raw.get("quantity") or 0)
        if qty <= 0:
            raise HTTPException(status_code=400, detail="quantity must be positive")

        parts = [p for p in (notes, raw.get("notes")) if p]
        line_notes = "; ".join(parts) if parts else None

        moved = await stock_in_with_batch(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            product_id=product_id,
            quantity=qty,
            unit_id=raw.get("unit_id"),
            notes=line_notes,
            warehouse_id=raw.get("warehouse_id"),
            variant_id=raw.get("variant_id"),
            batch_number=raw.get("batch_number"),
            manufacturing_date=raw.get("manufacturing_date"),
            expiry_date=raw.get("expiry_date"),
            movement_type="opening_stock",
            reference_type="opening_stock",
            reference_id=entry_id,
        )
        unit_cost = raw.get("unit_cost")
        if unit_cost is None:
            unit_cost = float(moved.get("cost_price") or 0)
        else:
            unit_cost = float(unit_cost)
            if unit_cost < 0:
                raise HTTPException(status_code=400, detail="unit_cost cannot be negative")
        line_value = round(float(moved["quantity_base"]) * unit_cost, 2)
        inventory_value += line_value
        results.append(
            {
                **moved,
                "unit_cost": unit_cost,
                "line_value": line_value,
            }
        )

    journal = None
    if post_journal and inventory_value > 0:
        from app.accounting import post_opening_stock_journal

        journal = await post_opening_stock_journal(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            entry_id=entry_id,
            reference=ref_label,
            inventory_value=inventory_value,
            description=notes or f"Opening stock {ref_label}",
        )

    db.add(
        m.AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action="opening_stock_posted",
            entity="opening_stock",
            entity_id=entry_id,
            details={
                "reference": ref_label,
                "line_count": len(results),
                "inventory_value": round(inventory_value, 2),
                "journal_id": journal.id if journal else None,
                "post_journal": post_journal,
            },
        )
    )

    return {
        "id": entry_id,
        "reference": ref_label,
        "line_count": len(results),
        "inventory_value": round(inventory_value, 2),
        "journal_id": journal.id if journal else None,
        "journal_number": journal.entry_number if journal else None,
        "lines": results,
    }


async def list_opening_stock_movements(
    db: AsyncSession, tenant_id: str, *, limit: int = 100
) -> list[dict]:
    rows = (
        await db.execute(
            select(m.StockMovement)
            .where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.movement_type == "opening_stock",
            )
            .order_by(m.StockMovement.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "product_id": r.product_id,
            "warehouse_id": r.warehouse_id,
            "variant_id": r.variant_id,
            "batch_id": r.batch_id,
            "quantity": float(r.quantity),
            "quantity_before": float(r.quantity_before),
            "quantity_after": float(r.quantity_after),
            "reference_id": r.reference_id,
            "notes": r.notes,
            "created_by": r.created_by,
            "created_at": r.created_at,
        }
        for r in rows
    ]
