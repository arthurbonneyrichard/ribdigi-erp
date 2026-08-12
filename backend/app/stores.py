"""Multi-store operations and inter-store stock transfers."""

from __future__ import annotations

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


async def next_transfer_number(db: AsyncSession, tenant_id: str) -> str:
    count = len(
        (
            await db.execute(select(m.StockTransfer.id).where(m.StockTransfer.tenant_id == tenant_id))
        ).scalars().all()
    )
    return f"TR-{datetime.utcnow():%Y%m%d}-{count + 1:04d}"


async def get_store(db: AsyncSession, tenant_id: str, store_id: str) -> m.Store:
    store = (
        await db.execute(
            select(m.Store).where(m.Store.id == store_id, m.Store.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
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
) -> m.Store:
    if branch_id:
        from app import org_units as org_units_svc

        branch = await org_units_svc.get_branch(db, tenant_id, branch_id)
        if not branch.is_active:
            raise HTTPException(status_code=400, detail="Branch is inactive")
        branch_id = branch.id
    store = m.Store(
        tenant_id=tenant_id,
        name=name,
        code=code.strip().upper(),
        address=address,
        phone=phone,
        manager_id=manager_id,
        branch_id=branch_id,
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
    fully_approved = bool(
        getattr(transfer, "source_approved_by", None)
        and getattr(transfer, "dest_approved_by", None)
    )
    can_ship = transfer.status == "requested" and fully_approved
    awaiting = None
    if transfer.status == "requested" and not fully_approved:
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
    from_store_id: str,
    to_store_id: str,
    items: list[dict],
    notes: str | None = None,
    submit: bool = False,
) -> m.StockTransfer:
    if from_store_id == to_store_id:
        raise HTTPException(status_code=400, detail="Source and destination stores must differ")
    if not items:
        raise HTTPException(status_code=400, detail="Transfer requires at least one item")

    await get_store(db, tenant_id, from_store_id)
    await get_store(db, tenant_id, to_store_id)
    from_wh = await warehouse_for_store(db, tenant_id, from_store_id)
    to_wh = await warehouse_for_store(db, tenant_id, to_store_id)

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
        approval_steps_required=2,
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
    transfer.approval_steps_required = 2
    transfer.source_approved_by = None
    transfer.source_approved_at = None
    transfer.dest_approved_by = None
    transfer.dest_approved_at = None
    transfer.rejected_by = None
    transfer.rejection_reason = None
    await db.flush()
    return transfer


def _transfer_fully_approved(transfer: m.StockTransfer) -> bool:
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
        transfer.approval_step = 2
        from app.notifications import create_notification

        await create_notification(
            db,
            tenant_id=tenant_id,
            category="transfer",
            title="Transfer needs destination approval",
            message=f"Transfer {transfer.transfer_number} passed source approval.",
            entity_type="stock_transfer",
            entity_id=transfer.id,
        )
    elif not transfer.dest_approved_by:
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
        transfer.approval_step = int(transfer.approval_steps_required or 2)
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
    transfer.status = "cancelled"
    transfer.rejected_by = user_id
    transfer.rejection_reason = (reason or "").strip() or None
    await db.flush()
    return transfer


async def ship_transfer(
    db: AsyncSession, *, tenant_id: str, user_id: str, transfer_id: str
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_SHIPPABLE:
        raise HTTPException(status_code=409, detail=f"Cannot ship transfer in status {transfer.status}")
    if not _transfer_fully_approved(transfer):
        raise HTTPException(
            status_code=409,
            detail="Transfer requires source and destination manager approval before shipping",
        )
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
    db: AsyncSession, *, tenant_id: str, user_id: str, transfer_id: str
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_CANCELLABLE:
        raise HTTPException(status_code=409, detail=f"Cannot cancel transfer in status {transfer.status}")

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
                    notes=f"Cancelled {transfer.transfer_number}",
                    created_by=user_id,
                )
            )

    transfer.status = "cancelled"
    await db.flush()
    return transfer
