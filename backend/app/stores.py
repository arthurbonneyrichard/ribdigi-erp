"""Multi-store operations and inter-store stock transfers."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import allocate_unlocated_stock, apply_warehouse_stock_change, get_or_create_warehouse_stock

TRANSFER_EDITABLE = {"draft"}
TRANSFER_SUBMITTABLE = {"draft"}
TRANSFER_APPROVABLE = frozenset({"requested"})
TRANSFER_SHIPPABLE = frozenset({"requested"})
TRANSFER_RECEIVABLE = {"in_transit"}
TRANSFER_CANCELLABLE = {"draft", "requested", "in_transit"}
TRANSFER_ADMIN_ROLES = frozenset({"company_admin", "super_admin"})
TRANSFER_MANAGER_ROLES = frozenset({"store_manager"}) | TRANSFER_ADMIN_ROLES

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def normalize_operating_hours(value: dict | None) -> dict | None:
    """Validate weekly hours map; return normalized dict or None.

    Schema StoreOperatingHours / StoreDayHours rejects unknown days and bad
    HH:MM → 422; keep allow-list + time defense-in-depth here.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="operating_hours must be an object")
    if not value:
        return None
    unknown = set(value.keys()) - set(WEEKDAYS)
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid operating_hours day keys: {sorted(unknown)}",
        )
    cleaned: dict[str, dict] = {}
    for day in WEEKDAYS:
        if day not in value:
            continue
        entry = value[day]
        if entry is None:
            continue
        if not isinstance(entry, dict):
            raise HTTPException(status_code=400, detail=f"operating_hours.{day} must be an object")
        closed = bool(entry.get("closed"))
        if closed:
            cleaned[day] = {"closed": True}
            continue
        open_t = str(entry.get("open") or "").strip()
        close_t = str(entry.get("close") or "").strip()
        if not _TIME_RE.fullmatch(open_t) or not _TIME_RE.fullmatch(close_t):
            raise HTTPException(
                status_code=400,
                detail=f"operating_hours.{day} requires open/close as HH:MM (24h)",
            )
        if open_t >= close_t:
            raise HTTPException(
                status_code=400,
                detail=f"operating_hours.{day} open must be before close",
            )
        cleaned[day] = {"open": open_t, "close": close_t, "closed": False}
    return cleaned or None


def serialize_store(row: m.Store, *, drawer: dict | None = None) -> dict:
    data = {
        "id": row.id,
        "name": row.name,
        "code": row.code,
        "address": row.address,
        "phone": row.phone,
        "manager_id": row.manager_id,
        "branch_id": getattr(row, "branch_id", None),
        "is_active": bool(row.is_active),
        "operating_hours": getattr(row, "operating_hours", None),
    }
    if drawer:
        data.update({k: v for k, v in drawer.items() if k != "source"})
    return data


async def next_transfer_number(db: AsyncSession, tenant_id: str) -> str:
    from app.doc_numbers import next_stock_transfer_number

    return await next_stock_transfer_number(db, tenant_id)


async def get_store(db: AsyncSession, tenant_id: str, store_id: str) -> m.Store:
    store = (
        await db.execute(
            select(m.Store).where(m.Store.id == store_id, m.Store.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


async def require_active_store(db: AsyncSession, tenant_id: str, store_id: str) -> m.Store:
    """Resolve store for new POS/sales/expense assignment; inactive stores cannot be newly used."""
    store = await get_store(db, tenant_id, store_id)
    if not bool(store.is_active):
        raise HTTPException(status_code=400, detail="Store is inactive")
    return store


async def warehouse_for_store(db: AsyncSession, tenant_id: str, store_id: str) -> m.Warehouse:
    wh = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == store_id,
            )
        )
    ).scalar_one_or_none()
    if wh:
        return wh
    store = await get_store(db, tenant_id, store_id)
    wh = m.Warehouse(
        tenant_id=tenant_id,
        store_id=store.id,
        name=f"{store.name} Warehouse",
        code=f"WH-{store.code}",
    )
    db.add(wh)
    await db.flush()
    return wh


async def create_store(
    db: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    code: str,
    address: str | None = None,
    phone: str | None = None,
    manager_id: str | None = None,
    branch_id: str | None = None,
    operating_hours: dict | None = None,
) -> m.Store:
    from app import store_entitlements as store_ent_svc

    # Lock tenant row so concurrent creates cannot both pass the quota check.
    tenant = await store_ent_svc.lock_tenant_for_store_quota(db, tenant_id)
    await store_ent_svc.assert_can_create_store(db, tenant)

    if branch_id:
        from app import org_units as org_units_svc

        branch = await org_units_svc.get_branch(db, tenant_id, branch_id)
        if not branch.is_active:
            raise HTTPException(status_code=400, detail="Branch is inactive")
        branch_id = branch.id
    if manager_id:
        user = (
            await db.execute(
                select(m.User).where(m.User.id == manager_id, m.User.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found in tenant")
    store = m.Store(
        tenant_id=tenant_id,
        name=name,
        code=code.strip().upper(),
        address=address,
        phone=phone,
        manager_id=manager_id,
        branch_id=branch_id,
        operating_hours=normalize_operating_hours(operating_hours),
        is_active=True,
    )
    db.add(store)
    await db.flush()
    db.add(
        m.Warehouse(
            tenant_id=tenant_id,
            store_id=store.id,
            name=f"{store.name} Warehouse",
            code=f"WH-{store.code}",
        )
    )
    await db.flush()
    return store


async def update_store(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    name: str | None = None,
    address: str | None = None,
    phone: str | None = None,
    manager_id: str | None = None,
    clear_manager: bool = False,
    branch_id: str | None = None,
    clear_branch: bool = False,
    is_active: bool | None = None,
    operating_hours: dict | None = None,
    set_operating_hours: bool = False,
) -> m.Store:
    store = await get_store(db, tenant_id, store_id)
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        store.name = cleaned
    if address is not None:
        store.address = address.strip() or None
    if phone is not None:
        # Defense in depth: StoreUpdate E164PhoneValue → 422 on blank/invalid.
        store.phone = phone
    if clear_manager:
        store.manager_id = None
    elif manager_id is not None:
        user = (
            await db.execute(
                select(m.User).where(m.User.id == manager_id, m.User.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found in tenant")
        store.manager_id = manager_id
    if clear_branch:
        store.branch_id = None
    elif branch_id is not None:
        from app import org_units as org_units_svc

        branch = await org_units_svc.get_branch(db, tenant_id, branch_id)
        if not branch.is_active:
            raise HTTPException(status_code=400, detail="Branch is inactive")
        store.branch_id = branch.id
    if is_active is not None:
        from app import store_entitlements as store_ent_svc

        new_active = bool(is_active)
        if new_active and not bool(store.is_active):
            tenant = await store_ent_svc.lock_tenant_for_store_quota(db, tenant_id)
            await store_ent_svc.assert_can_activate_store(db, tenant, store)
        store.is_active = new_active
    if set_operating_hours:
        store.operating_hours = normalize_operating_hours(operating_hours)
    await db.flush()
    return store


async def store_inventory(
    db: AsyncSession,
    tenant_id: str,
    store_id: str,
    *,
    include_zero: bool = False,
) -> list[dict]:
    await get_store(db, tenant_id, store_id)
    wh = await warehouse_for_store(db, tenant_id, store_id)
    stmt = (
        select(m.WarehouseStock, m.Product)
        .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
        .where(
            m.WarehouseStock.tenant_id == tenant_id,
            m.WarehouseStock.warehouse_id == wh.id,
        )
        .order_by(m.Product.name)
    )
    if not include_zero:
        stmt = stmt.where(
            (m.WarehouseStock.quantity > 0)
            | (m.WarehouseStock.reorder_level > 0)
        )
    rows = (await db.execute(stmt)).all()
    out = []
    for stock, product in rows:
        qty = float(stock.quantity or 0)
        reorder = float(getattr(stock, "reorder_level", 0) or 0)
        reorder_qty = float(getattr(stock, "reorder_qty", 0) or 0)
        out.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": qty,
                "reorder_level": reorder,
                "reorder_qty": reorder_qty,
                "below_reorder": reorder > 0 and qty <= reorder,
                "suggested_order_qty": max(reorder_qty, round(reorder - qty, 3))
                if reorder > 0 and qty <= reorder
                else reorder_qty,
                "warehouse_id": wh.id,
                "consolidated_stock": float(product.stock_qty or 0),
            }
        )
    return out


async def set_store_reorder_policy(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    product_id: str,
    reorder_level: float,
    reorder_qty: float = 0,
) -> dict:
    await get_store(db, tenant_id, store_id)
    product = (
        await db.execute(
            select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    wh = await warehouse_for_store(db, tenant_id, store_id)
    row = await get_or_create_warehouse_stock(
        db, tenant_id=tenant_id, warehouse_id=wh.id, product_id=product_id
    )
    row.reorder_level = max(float(reorder_level or 0), 0)
    row.reorder_qty = max(float(reorder_qty or 0), 0)
    await db.flush()
    qty = float(row.quantity or 0)
    reorder = float(row.reorder_level or 0)
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "quantity": qty,
        "reorder_level": reorder,
        "reorder_qty": float(row.reorder_qty or 0),
        "below_reorder": reorder > 0 and qty <= reorder,
        "warehouse_id": wh.id,
        "store_id": store_id,
    }


async def get_transfer(db: AsyncSession, tenant_id: str, transfer_id: str) -> m.StockTransfer:
    row = (
        await db.execute(
            select(m.StockTransfer).where(
                m.StockTransfer.id == transfer_id,
                m.StockTransfer.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return row


async def list_transfers(
    db: AsyncSession,
    tenant_id: str,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[m.StockTransfer]:
    """Manage list for Inventory / Multi-Store transfer tabs (BR-5.2 / BR-13.2)."""
    from app.reports import TRANSFER_REPORT_STATUSES

    stmt = (
        select(m.StockTransfer)
        .where(m.StockTransfer.tenant_id == tenant_id)
        .order_by(m.StockTransfer.created_at.desc())
        .limit(limit)
    )
    if status is not None:
        # Schema TransferReportStatusValue rejects blank/invalid → 422;
        # keep allow-list defense-in-depth (no silent empty filter / blank→all).
        wanted = (status or "").strip().lower()
        if not wanted:
            pass
        elif wanted not in TRANSFER_REPORT_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid transfer status '{wanted}'. "
                    f"Allowed: {sorted(TRANSFER_REPORT_STATUSES)}"
                ),
            )
        else:
            stmt = stmt.where(m.StockTransfer.status == wanted)
    return list((await db.execute(stmt)).scalars().all())


async def list_transfer_items(
    db: AsyncSession, tenant_id: str, transfer_id: str
) -> list[m.StockTransferItem]:
    return (
        await db.execute(
            select(m.StockTransferItem).where(
                m.StockTransferItem.tenant_id == tenant_id,
                m.StockTransferItem.transfer_id == transfer_id,
            )
        )
    ).scalars().all()


async def serialize_transfer(db: AsyncSession, transfer: m.StockTransfer) -> dict:
    items = await list_transfer_items(db, transfer.tenant_id, transfer.id)
    step = int(getattr(transfer, "approval_step", 0) or 0)
    required = int(getattr(transfer, "approval_steps_required", 2) or 2)
    fully_approved = _transfer_fully_approved(transfer)
    can_ship = transfer.status == "requested" and fully_approved
    awaiting = None
    if transfer.status == "requested" and not fully_approved:
        if required <= 1:
            awaiting = "source"
        else:
            awaiting = "source" if step <= 1 else "dest"
    return {
        "id": transfer.id,
        "transfer_number": transfer.transfer_number,
        "from_store_id": transfer.from_store_id,
        "to_store_id": transfer.to_store_id,
        "from_warehouse_id": transfer.from_warehouse_id,
        "to_warehouse_id": transfer.to_warehouse_id,
        "status": transfer.status,
        "notes": transfer.notes,
        "created_by": transfer.created_by,
        "approval_step": step,
        "approval_steps_required": required,
        "awaiting_approval": awaiting,
        "source_approved_by": getattr(transfer, "source_approved_by", None),
        "source_approved_at": getattr(transfer, "source_approved_at", None),
        "dest_approved_by": getattr(transfer, "dest_approved_by", None),
        "dest_approved_at": getattr(transfer, "dest_approved_at", None),
        "rejected_by": getattr(transfer, "rejected_by", None),
        "rejection_reason": getattr(transfer, "rejection_reason", None),
        "fully_approved": fully_approved,
        "can_ship": can_ship,
        "shipped_at": transfer.shipped_at,
        "received_at": transfer.received_at,
        "created_at": transfer.created_at,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "quantity": float(i.quantity),
                "shipped_qty": float(i.shipped_qty or 0),
                "received_qty": float(i.received_qty or 0),
            }
            for i in items
        ],
    }


async def create_transfer(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    items: list[dict],
    from_store_id: str | None = None,
    to_store_id: str | None = None,
    from_warehouse_id: str | None = None,
    to_warehouse_id: str | None = None,
    notes: str | None = None,
    submit: bool = False,
) -> m.StockTransfer:
    if not items:
        raise HTTPException(status_code=400, detail="Transfer requires at least one item")

    from app.warehouses import get_warehouse

    if from_warehouse_id and to_warehouse_id:
        from_wh = await get_warehouse(db, tenant_id, from_warehouse_id)
        to_wh = await get_warehouse(db, tenant_id, to_warehouse_id)
        if from_wh.id == to_wh.id:
            raise HTTPException(
                status_code=400, detail="Source and destination warehouses must differ"
            )
        if not from_wh.store_id or not to_wh.store_id:
            raise HTTPException(
                status_code=400,
                detail="Both warehouses must be linked to a store for transfers",
            )
        from_store_id = from_wh.store_id
        to_store_id = to_wh.store_id
        await get_store(db, tenant_id, from_store_id)
        await get_store(db, tenant_id, to_store_id)
    elif from_store_id and to_store_id:
        if from_store_id == to_store_id:
            raise HTTPException(
                status_code=400, detail="Source and destination stores must differ"
            )
        await get_store(db, tenant_id, from_store_id)
        await get_store(db, tenant_id, to_store_id)
        from_wh = await warehouse_for_store(db, tenant_id, from_store_id)
        to_wh = await warehouse_for_store(db, tenant_id, to_store_id)
    else:
        raise HTTPException(
            status_code=400,
            detail="Provide from_store_id/to_store_id or from_warehouse_id/to_warehouse_id",
        )

    same_store = from_store_id == to_store_id
    steps_required = 1 if same_store else 2

    transfer = m.StockTransfer(
        tenant_id=tenant_id,
        transfer_number=await next_transfer_number(db, tenant_id),
        from_store_id=from_store_id,
        to_store_id=to_store_id,
        from_warehouse_id=from_wh.id,
        to_warehouse_id=to_wh.id,
        status="requested" if submit else "draft",
        notes=notes,
        created_by=user_id,
        approval_step=1 if submit else 0,
        approval_steps_required=steps_required,
    )
    db.add(transfer)
    await db.flush()

    for item in items:
        product_id = item["product_id"]
        qty = float(item["quantity"])
        if qty <= 0:
            raise HTTPException(status_code=400, detail="Transfer quantities must be positive")
        product = (
            await db.execute(
                select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product not found: {product_id}")
        db.add(
            m.StockTransferItem(
                tenant_id=tenant_id,
                transfer_id=transfer.id,
                product_id=product_id,
                quantity=qty,
            )
        )
    await db.flush()
    return transfer


async def submit_transfer(db: AsyncSession, *, tenant_id: str, transfer_id: str) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_SUBMITTABLE:
        raise HTTPException(status_code=409, detail=f"Cannot submit transfer in status {transfer.status}")
    transfer.status = "requested"
    transfer.approval_step = 1
    # keep approval_steps_required (1 for same-store WH, 2 for inter-store)
    if not transfer.approval_steps_required:
        transfer.approval_steps_required = (
            1 if transfer.from_store_id == transfer.to_store_id else 2
        )
    transfer.source_approved_by = None
    transfer.source_approved_at = None
    transfer.dest_approved_by = None
    transfer.dest_approved_at = None
    transfer.rejected_by = None
    transfer.rejection_reason = None
    await db.flush()
    return transfer


def _transfer_fully_approved(transfer: m.StockTransfer) -> bool:
    required = int(getattr(transfer, "approval_steps_required", 2) or 2)
    if required <= 1:
        return bool(transfer.source_approved_by)
    return bool(transfer.source_approved_by and transfer.dest_approved_by)


async def _assert_may_approve_store(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    user_id: str,
    actor_role: str | None,
    step_label: str,
) -> None:
    role = (actor_role or "").strip()
    if role in TRANSFER_ADMIN_ROLES:
        return
    if role not in TRANSFER_MANAGER_ROLES:
        raise HTTPException(
            status_code=403,
            detail=f"{step_label} approval requires store_manager or company_admin",
        )
    store = await get_store(db, tenant_id, store_id)
    if store.manager_id and store.manager_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=f"Only the assigned {step_label} store manager can approve this step",
        )


async def approve_transfer(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    transfer_id: str,
    actor_role: str | None = None,
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_APPROVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot approve transfer in status {transfer.status}")
    if _transfer_fully_approved(transfer):
        raise HTTPException(status_code=409, detail="Transfer already fully approved")

    step = int(transfer.approval_step or 1)
    now = datetime.utcnow()
    required = int(transfer.approval_steps_required or 2)
    if step <= 1 and not transfer.source_approved_by:
        await _assert_may_approve_store(
            db,
            tenant_id=tenant_id,
            store_id=transfer.from_store_id,
            user_id=user_id,
            actor_role=actor_role,
            step_label="source",
        )
        transfer.source_approved_by = user_id
        transfer.source_approved_at = now
        from app.notifications import create_notification

        if required <= 1:
            # Same-store warehouse transfer: single approval unlocks ship
            transfer.approval_step = required
            await create_notification(
                db,
                tenant_id=tenant_id,
                category="transfer",
                title="Transfer approved for shipping",
                message=f"Transfer {transfer.transfer_number} is approved and ready to ship.",
                entity_type="stock_transfer",
                entity_id=transfer.id,
            )
        else:
            transfer.approval_step = 2
            await create_notification(
                db,
                tenant_id=tenant_id,
                category="transfer",
                title="Transfer needs destination approval",
                message=f"Transfer {transfer.transfer_number} passed source approval.",
                entity_type="stock_transfer",
                entity_id=transfer.id,
            )
    elif required > 1 and not transfer.dest_approved_by:
        await _assert_may_approve_store(
            db,
            tenant_id=tenant_id,
            store_id=transfer.to_store_id,
            user_id=user_id,
            actor_role=actor_role,
            step_label="destination",
        )
        if transfer.source_approved_by == user_id and (actor_role or "") not in TRANSFER_ADMIN_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Same manager cannot approve both source and destination steps",
            )
        transfer.dest_approved_by = user_id
        transfer.dest_approved_at = now
        transfer.approval_step = required
        from app.notifications import create_notification

        await create_notification(
            db,
            tenant_id=tenant_id,
            category="transfer",
            title="Transfer approved for shipping",
            message=f"Transfer {transfer.transfer_number} is fully approved and ready to ship.",
            entity_type="stock_transfer",
            entity_id=transfer.id,
        )
    else:
        raise HTTPException(status_code=409, detail="No pending approval step")
    await db.flush()
    return transfer


async def reject_transfer(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    transfer_id: str,
    reason: str | None = None,
    actor_role: str | None = None,
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_APPROVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot reject transfer in status {transfer.status}")
    role = (actor_role or "").strip()
    if role not in TRANSFER_MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Role cannot reject transfers")
    # Either store's manager (or admin) may reject while pending
    if role not in TRANSFER_ADMIN_ROLES:
        from_store = await get_store(db, tenant_id, transfer.from_store_id)
        to_store = await get_store(db, tenant_id, transfer.to_store_id)
        allowed = {from_store.manager_id, to_store.manager_id} - {None}
        if allowed and user_id not in allowed:
            # If neither store has a manager assigned, any store_manager may reject
            if from_store.manager_id or to_store.manager_id:
                raise HTTPException(status_code=403, detail="Not an assigned store manager for this transfer")
    reason_s = (reason or "").strip()
    if not reason_s:
        raise HTTPException(status_code=400, detail="rejection reason is required")
    transfer.status = "cancelled"
    transfer.rejected_by = user_id
    transfer.rejection_reason = reason_s
    await db.flush()
    return transfer


async def ship_transfer(
    db: AsyncSession, *, tenant_id: str, user_id: str, transfer_id: str
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_SHIPPABLE:
        raise HTTPException(status_code=409, detail=f"Cannot ship transfer in status {transfer.status}")
    if not _transfer_fully_approved(transfer):
        required = int(transfer.approval_steps_required or 2)
        detail = (
            "Transfer requires approval before shipping"
            if required <= 1
            else "Transfer requires source and destination manager approval before shipping"
        )
        raise HTTPException(status_code=409, detail=detail)
    items = await list_transfer_items(db, tenant_id, transfer_id)
    for item in items:
        await allocate_unlocated_stock(
            db,
            tenant_id=tenant_id,
            warehouse_id=transfer.from_warehouse_id,
            product_id=item.product_id,
        )
        await apply_warehouse_stock_change(
            db,
            tenant_id=tenant_id,
            warehouse_id=transfer.from_warehouse_id,
            product_id=item.product_id,
            quantity_delta=-float(item.quantity),
        )
        product = await db.get(m.Product, item.product_id)
        before = float(product.stock_qty or 0) if product else 0
        db.add(
            m.StockMovement(
                tenant_id=tenant_id,
                product_id=item.product_id,
                warehouse_id=transfer.from_warehouse_id,
                movement_type="transfer_out",
                quantity=-float(item.quantity),
                quantity_before=before,
                quantity_after=before,
                reference_type="stock_transfer",
                reference_id=transfer.id,
                notes=f"Shipped {transfer.transfer_number}",
                created_by=user_id,
            )
        )
        item.shipped_qty = float(item.quantity)

    transfer.status = "in_transit"
    transfer.shipped_by = user_id
    transfer.shipped_at = datetime.utcnow()
    from app.notifications import create_notification

    await create_notification(
        db,
        tenant_id=tenant_id,
        category="transfer",
        title="Transfer In Transit",
        message=f"Transfer {transfer.transfer_number} shipped and awaits receipt.",
        entity_type="stock_transfer",
        entity_id=transfer.id,
    )
    await db.flush()
    return transfer


async def receive_transfer(
    db: AsyncSession, *, tenant_id: str, user_id: str, transfer_id: str
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_RECEIVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot receive transfer in status {transfer.status}")
    items = await list_transfer_items(db, tenant_id, transfer_id)
    for item in items:
        qty = float(item.shipped_qty or item.quantity)
        await apply_warehouse_stock_change(
            db,
            tenant_id=tenant_id,
            warehouse_id=transfer.to_warehouse_id,
            product_id=item.product_id,
            quantity_delta=qty,
        )
        product = await db.get(m.Product, item.product_id)
        before = float(product.stock_qty or 0) if product else 0
        db.add(
            m.StockMovement(
                tenant_id=tenant_id,
                product_id=item.product_id,
                warehouse_id=transfer.to_warehouse_id,
                movement_type="transfer_in",
                quantity=qty,
                quantity_before=before,
                quantity_after=before,
                reference_type="stock_transfer",
                reference_id=transfer.id,
                notes=f"Received {transfer.transfer_number}",
                created_by=user_id,
            )
        )
        item.received_qty = qty

    transfer.status = "received"
    transfer.received_by = user_id
    transfer.received_at = datetime.utcnow()
    await db.flush()
    return transfer


async def cancel_transfer(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    transfer_id: str,
    reason: str | None = None,
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_CANCELLABLE:
        raise HTTPException(status_code=409, detail=f"Cannot cancel transfer in status {transfer.status}")
    reason_s = (reason or "").strip()
    if not reason_s:
        raise HTTPException(status_code=400, detail="cancel reason is required")

    if transfer.status == "in_transit":
        items = await list_transfer_items(db, tenant_id, transfer_id)
        for item in items:
            qty = float(item.shipped_qty or item.quantity)
            await apply_warehouse_stock_change(
                db,
                tenant_id=tenant_id,
                warehouse_id=transfer.from_warehouse_id,
                product_id=item.product_id,
                quantity_delta=qty,
            )
            product = await db.get(m.Product, item.product_id)
            before = float(product.stock_qty or 0) if product else 0
            db.add(
                m.StockMovement(
                    tenant_id=tenant_id,
                    product_id=item.product_id,
                    warehouse_id=transfer.from_warehouse_id,
                    movement_type="transfer_cancel",
                    quantity=qty,
                    quantity_before=before,
                    quantity_after=before,
                    reference_type="stock_transfer",
                    reference_id=transfer.id,
                    notes=f"Cancelled {transfer.transfer_number}: {reason_s}",
                    created_by=user_id,
                )
            )

    transfer.status = "cancelled"
    transfer.rejected_by = user_id
    transfer.rejection_reason = reason_s
    await db.flush()
    return transfer
