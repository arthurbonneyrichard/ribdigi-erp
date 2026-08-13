"""Warehouse setup helpers (BR-2.4)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

WAREHOUSE_TYPES = frozenset({"retail", "bulk", "cold_storage", "other"})


def serialize_warehouse(row: m.Warehouse) -> dict:
    cap = getattr(row, "capacity", None)
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "store_id": row.store_id,
        "name": row.name,
        "code": row.code,
        "warehouse_type": getattr(row, "warehouse_type", None) or "retail",
        "manager_id": getattr(row, "manager_id", None),
        "address": getattr(row, "address", None),
        "capacity": float(cap) if cap is not None else None,
    }


def _normalize_type(value: str | None) -> str:
    wt = (value or "retail").strip().lower()
    if wt not in WAREHOUSE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid warehouse_type; expected one of {sorted(WAREHOUSE_TYPES)}",
        )
    return wt


async def _assert_tenant_user(db: AsyncSession, tenant_id: str, user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in tenant")
    return user.id


async def _assert_store(db: AsyncSession, tenant_id: str, store_id: str | None) -> str | None:
    if not store_id:
        return None
    store = (
        await db.execute(
            select(m.Store).where(m.Store.id == store_id, m.Store.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store.id


async def get_warehouse(db: AsyncSession, tenant_id: str, warehouse_id: str) -> m.Warehouse:
    row = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.id == warehouse_id, m.Warehouse.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    return row


async def create_warehouse(
    db: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    code: str,
    store_id: str | None = None,
    warehouse_type: str | None = "retail",
    manager_id: str | None = None,
    address: str | None = None,
    capacity: float | None = None,
) -> m.Warehouse:
    code_clean = (code or "").strip().upper()
    if not code_clean:
        raise HTTPException(status_code=400, detail="code is required")
    name_clean = (name or "").strip()
    if not name_clean:
        raise HTTPException(status_code=400, detail="name is required")
    existing = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id, m.Warehouse.code == code_clean
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Warehouse code already in use")
    if capacity is not None and capacity < 0:
        raise HTTPException(status_code=400, detail="capacity must be >= 0")
    row = m.Warehouse(
        tenant_id=tenant_id,
        name=name_clean,
        code=code_clean,
        store_id=await _assert_store(db, tenant_id, store_id),
        warehouse_type=_normalize_type(warehouse_type),
        manager_id=await _assert_tenant_user(db, tenant_id, manager_id),
        address=(address or "").strip() or None,
        capacity=capacity,
    )
    db.add(row)
    await db.flush()
    return row


async def update_warehouse(
    db: AsyncSession,
    *,
    tenant_id: str,
    warehouse_id: str,
    name: str | None = None,
    store_id: str | None = None,
    clear_store: bool = False,
    warehouse_type: str | None = None,
    manager_id: str | None = None,
    clear_manager: bool = False,
    address: str | None = None,
    capacity: float | None = None,
    clear_capacity: bool = False,
) -> m.Warehouse:
    row = await get_warehouse(db, tenant_id, warehouse_id)
    if name is not None:
        name_clean = name.strip()
        if not name_clean:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        row.name = name_clean
    if clear_store:
        row.store_id = None
    elif store_id is not None:
        row.store_id = await _assert_store(db, tenant_id, store_id)
    if warehouse_type is not None:
        row.warehouse_type = _normalize_type(warehouse_type)
    if clear_manager:
        row.manager_id = None
    elif manager_id is not None:
        row.manager_id = await _assert_tenant_user(db, tenant_id, manager_id)
    if address is not None:
        row.address = address.strip() or None
    if clear_capacity:
        row.capacity = None
    elif capacity is not None:
        if capacity < 0:
            raise HTTPException(status_code=400, detail="capacity must be >= 0")
        row.capacity = capacity
    await db.flush()
    return row
