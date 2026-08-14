"""Multi-store operations and inter-store stock transfers."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.inventory import allocate_unlocated_stock, apply_warehouse_stock_change, get_or_create_warehouse_stock

TRANSFER_EDITABLE = {"draft"}
TRANSFER_SUBMITTABLE = {"draft"}
TRANSFER_SHIPPABLE = {"requested", "draft"}
TRANSFER_RECEIVABLE = {"in_transit"}
TRANSFER_CANCELLABLE = {"draft", "requested", "in_transit"}
TRANSFER_HISTORY_SCOPES = frozenset({"all", "inter_store", "warehouse"})


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
    operating_hours: dict | None = None,
    company_id: str | None = None,
) -> m.Store:
    if manager_id:
        manager = (
            await db.execute(
                select(m.User).where(m.User.id == manager_id, m.User.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager user not found")
    store = m.Store(
        tenant_id=tenant_id,
        company_id=company_id,
        name=name,
        code=code.strip().upper(),
        address=address,
        phone=phone,
        manager_id=manager_id,
        branch_id=branch_id,
        operating_hours=operating_hours,
        is_active=True,
    )
    db.add(store)
    await db.flush()
    db.add(
        m.Warehouse(
            tenant_id=tenant_id,
            company_id=company_id,
            store_id=store.id,
            name=f"{store.name} Warehouse",
            code=f"WH-{store.code}",
            warehouse_type="retail",
            is_active=True,
        )
    )
    await db.flush()
    return store


def serialize_store(store: m.Store) -> dict:
    return {
        "id": store.id,
        "name": store.name,
        "code": store.code,
        "address": store.address,
        "phone": store.phone,
        "manager_id": store.manager_id,
        "branch_id": store.branch_id,
        "operating_hours": getattr(store, "operating_hours", None),
        "is_active": bool(store.is_active),
    }


async def serialize_store_detail(db: AsyncSession, store: m.Store) -> dict:
    """Store payload including linked warehouse (created with the store)."""
    data = serialize_store(store)
    wh = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == store.tenant_id,
                m.Warehouse.store_id == store.id,
            )
        )
    ).scalar_one_or_none()
    data["warehouse_id"] = wh.id if wh else None
    data["warehouse_code"] = wh.code if wh else None
    data["warehouse_name"] = wh.name if wh else None
    return data


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
    operating_hours: dict | None = None,
    is_active: bool | None = None,
) -> m.Store:
    store = await get_store(db, tenant_id, store_id)
    if name is not None:
        clean = name.strip()
        if len(clean) < 2:
            raise HTTPException(status_code=400, detail="name must be at least 2 characters")
        store.name = clean
    if address is not None:
        store.address = address.strip() or None
    if phone is not None:
        store.phone = phone.strip() or None
    if clear_manager:
        store.manager_id = None
    elif manager_id is not None:
        manager = (
            await db.execute(
                select(m.User).where(m.User.id == manager_id, m.User.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager user not found")
        store.manager_id = manager_id
    if clear_branch:
        store.branch_id = None
    elif branch_id is not None:
        store.branch_id = branch_id
    if operating_hours is not None:
        if operating_hours and not isinstance(operating_hours, dict):
            raise HTTPException(status_code=400, detail="operating_hours must be an object")
        store.operating_hours = operating_hours or None
    if is_active is not None:
        store.is_active = bool(is_active)
    await db.flush()
    return store


def serialize_warehouse(row: m.Warehouse) -> dict:
    return {
        "id": row.id,
        "store_id": row.store_id,
        "name": row.name,
        "code": row.code,
        "warehouse_type": getattr(row, "warehouse_type", None) or "retail",
        "manager_id": getattr(row, "manager_id", None),
        "address": getattr(row, "address", None),
        "capacity": float(row.capacity) if getattr(row, "capacity", None) is not None else None,
        "is_active": bool(getattr(row, "is_active", True)),
    }


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
    is_active: bool | None = None,
) -> m.Warehouse:
    row = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.id == warehouse_id,
                m.Warehouse.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Warehouse not found")
    if name is not None:
        clean = name.strip()
        if len(clean) < 2:
            raise HTTPException(status_code=400, detail="name must be at least 2 characters")
        row.name = clean
    if clear_store:
        row.store_id = None
    elif store_id is not None:
        await get_store(db, tenant_id, store_id)
        row.store_id = store_id
    if warehouse_type is not None:
        wtype = warehouse_type.strip().lower()
        if wtype not in {"retail", "main", "cold", "bulk", "transit"}:
            raise HTTPException(
                status_code=400,
                detail="warehouse_type must be one of: retail, main, cold, bulk, transit",
            )
        row.warehouse_type = wtype
    if clear_manager:
        row.manager_id = None
    elif manager_id is not None:
        manager = (
            await db.execute(
                select(m.User).where(m.User.id == manager_id, m.User.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager user not found")
        row.manager_id = manager_id
    if address is not None:
        row.address = address.strip() or None
    if capacity is not None:
        if float(capacity) < 0:
            raise HTTPException(status_code=400, detail="capacity must be >= 0")
        row.capacity = float(capacity)
    if is_active is not None:
        row.is_active = bool(is_active)
    await db.flush()
    return row


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


async def store_sales(
    db: AsyncSession,
    tenant_id: str,
    store_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    recent_limit: int = 50,
) -> dict:
    """Store-specific sales summary + recent invoice/POS lines (BR-13.1)."""
    store = await get_store(db, tenant_id, store_id)
    limit = max(1, min(int(recent_limit or 50), 200))

    inv_stmt = select(m.SalesInvoice).where(
        m.SalesInvoice.tenant_id == tenant_id,
        m.SalesInvoice.store_id == store_id,
        m.SalesInvoice.status.in_(["posted", "partial", "paid", "sent", "overdue"]),
    )
    if from_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at >= from_date)
    if to_date:
        inv_stmt = inv_stmt.where(m.SalesInvoice.posted_at <= to_date)
    invoices = (await db.execute(inv_stmt.order_by(m.SalesInvoice.posted_at.desc()))).scalars().all()

    pos_stmt = (
        select(m.Transaction, m.PosSession)
        .join(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
            m.PosSession.store_id == store_id,
        )
    )
    if from_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at >= from_date)
    if to_date:
        pos_stmt = pos_stmt.where(m.Transaction.created_at <= to_date)
    pos_rows = (await db.execute(pos_stmt.order_by(m.Transaction.created_at.desc()))).all()

    invoice_revenue = 0.0
    invoice_tax = 0.0
    for inv in invoices:
        invoice_revenue += float(inv.total_amount or 0)
        invoice_tax += float(inv.tax_amount or 0)

    pos_revenue = 0.0
    pos_tax = 0.0
    for tx, _session in pos_rows:
        pos_revenue += float(tx.total or 0)
        pos_tax += float(tx.tax or 0)

    sale_count = len(invoices) + len(pos_rows)
    revenue = round(invoice_revenue + pos_revenue, 2)
    tax = round(invoice_tax + pos_tax, 2)

    recent: list[dict] = []
    for inv in invoices:
        recent.append(
            {
                "source": "invoice",
                "id": inv.id,
                "number": inv.invoice_number,
                "total": float(inv.total_amount or 0),
                "tax": float(inv.tax_amount or 0),
                "status": inv.status,
                "occurred_at": inv.posted_at or inv.created_at,
            }
        )
    for tx, _session in pos_rows:
        recent.append(
            {
                "source": "pos",
                "id": tx.id,
                "number": tx.reference or tx.id[:8],
                "total": float(tx.total or 0),
                "tax": float(tx.tax or 0),
                "status": "completed",
                "occurred_at": tx.created_at,
            }
        )
    recent.sort(key=lambda r: r["occurred_at"] or datetime.min, reverse=True)
    recent = recent[:limit]

    return {
        "store": {
            "id": store.id,
            "code": store.code,
            "name": store.name,
            "is_active": bool(getattr(store, "is_active", True)),
        },
        "from_date": from_date,
        "to_date": to_date,
        "summary": {
            "invoice_count": len(invoices),
            "invoice_revenue": round(invoice_revenue, 2),
            "invoice_tax": round(invoice_tax, 2),
            "pos_count": len(pos_rows),
            "pos_revenue": round(pos_revenue, 2),
            "pos_tax": round(pos_tax, 2),
            "sale_count": sale_count,
            "revenue": revenue,
            "tax": tax,
            "avg_ticket": round(revenue / sale_count, 2) if sale_count else 0.0,
        },
        "recent": recent,
    }


async def set_store_reorder_policy(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str,
    product_id: str,
    reorder_level: float,
    reorder_qty: float = 0,
    minimum_stock: float = 0,
) -> dict:
    from app.inventory import compute_stock_status

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
    row.minimum_stock = max(float(minimum_stock or 0), 0)
    row.reorder_level = max(float(reorder_level or 0), 0)
    row.reorder_qty = max(float(reorder_qty or 0), 0)
    await db.flush()
    qty = float(row.quantity or 0)
    minimum = float(row.minimum_stock or 0)
    reorder = float(row.reorder_level or 0)
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "quantity": qty,
        "minimum_stock": minimum,
        "reorder_level": reorder,
        "reorder_qty": float(row.reorder_qty or 0),
        "stock_status": compute_stock_status(qty, minimum, reorder),
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
    from_manager_id = None
    to_manager_id = None
    if transfer.from_store_id:
        from_store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.id == transfer.from_store_id,
                    m.Store.tenant_id == transfer.tenant_id,
                )
            )
        ).scalar_one_or_none()
        from_manager_id = getattr(from_store, "manager_id", None) if from_store else None
    if transfer.to_store_id:
        to_store = (
            await db.execute(
                select(m.Store).where(
                    m.Store.id == transfer.to_store_id,
                    m.Store.tenant_id == transfer.tenant_id,
                )
            )
        ).scalar_one_or_none()
        to_manager_id = getattr(to_store, "manager_id", None) if to_store else None
    return {
        "id": transfer.id,
        "transfer_number": transfer.transfer_number,
        "from_store_id": transfer.from_store_id,
        "to_store_id": transfer.to_store_id,
        "from_warehouse_id": transfer.from_warehouse_id,
        "to_warehouse_id": transfer.to_warehouse_id,
        "from_store_manager_id": from_manager_id,
        "to_store_manager_id": to_manager_id,
        "status": transfer.status,
        "notes": transfer.notes,
        "created_by": transfer.created_by,
        "shipped_by": transfer.shipped_by,
        "received_by": transfer.received_by,
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


async def list_transfers_filtered(
    db: AsyncSession,
    tenant_id: str,
    *,
    status: str | None = None,
    store_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    scope: str = "all",
    limit: int = 100,
) -> list[m.StockTransfer]:
    """Filtered stock transfer list (inter-store + warehouse) for ops and reports."""
    scope_key = (scope or "all").strip().lower()
    if scope_key not in TRANSFER_HISTORY_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"scope must be one of: {sorted(TRANSFER_HISTORY_SCOPES)}",
        )
    lim = max(1, min(int(limit or 100), 500))
    stmt = select(m.StockTransfer).where(m.StockTransfer.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(m.StockTransfer.status == status.strip().lower())
    if store_id:
        stmt = stmt.where(
            or_(
                m.StockTransfer.from_store_id == store_id,
                m.StockTransfer.to_store_id == store_id,
            )
        )
    if from_date:
        stmt = stmt.where(m.StockTransfer.created_at >= from_date)
    if to_date:
        stmt = stmt.where(m.StockTransfer.created_at <= to_date)
    if scope_key == "inter_store":
        stmt = stmt.where(
            m.StockTransfer.from_store_id.is_not(None),
            m.StockTransfer.to_store_id.is_not(None),
        )
    elif scope_key == "warehouse":
        stmt = stmt.where(
            or_(
                m.StockTransfer.from_store_id.is_(None),
                m.StockTransfer.to_store_id.is_(None),
            )
        )
    stmt = stmt.order_by(m.StockTransfer.created_at.desc()).limit(lim)
    return list((await db.execute(stmt)).scalars().all())


async def transfer_history(
    db: AsyncSession,
    tenant_id: str,
    *,
    status: str | None = None,
    store_id: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    scope: str = "all",
    limit: int = 200,
) -> dict:
    """Consolidated transfer history report (BR-13.2) — Stage 16 M2."""
    rows = await list_transfers_filtered(
        db,
        tenant_id,
        status=status,
        store_id=store_id,
        from_date=from_date,
        to_date=to_date,
        scope=scope,
        limit=limit,
    )
    transfers = [await serialize_transfer(db, t) for t in rows]
    by_status: dict[str, int] = {}
    qty_requested = 0.0
    qty_shipped = 0.0
    qty_received = 0.0
    for t in transfers:
        by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        for item in t.get("items") or []:
            qty_requested += float(item.get("quantity") or 0)
            qty_shipped += float(item.get("shipped_qty") or 0)
            qty_received += float(item.get("received_qty") or 0)
    return {
        "scope": (scope or "all").strip().lower(),
        "status": status,
        "store_id": store_id,
        "count": len(transfers),
        "by_status": by_status,
        "total_qty_requested": round(qty_requested, 3),
        "total_qty_shipped": round(qty_shipped, 3),
        "total_qty_received": round(qty_received, 3),
        "transfers": transfers,
    }


async def _add_transfer_items(
    db: AsyncSession, *, tenant_id: str, transfer_id: str, items: list[dict]
) -> None:
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
                transfer_id=transfer_id,
                product_id=product_id,
                quantity=qty,
            )
        )
    await db.flush()


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
    )
    db.add(transfer)
    await db.flush()
    await _add_transfer_items(db, tenant_id=tenant_id, transfer_id=transfer.id, items=items)
    return transfer


async def create_warehouse_transfer(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    from_warehouse_id: str,
    to_warehouse_id: str,
    items: list[dict],
    notes: str | None = None,
    submit: bool = False,
) -> m.StockTransfer:
    """Inter-warehouse transfer (Stage 2); stores optional/null."""
    from app.inventory import get_warehouse

    if from_warehouse_id == to_warehouse_id:
        raise HTTPException(status_code=400, detail="Source and destination warehouse must differ")
    if not items:
        raise HTTPException(status_code=400, detail="Transfer requires at least one item")

    from_wh = await get_warehouse(db, tenant_id, from_warehouse_id)
    to_wh = await get_warehouse(db, tenant_id, to_warehouse_id)

    transfer = m.StockTransfer(
        tenant_id=tenant_id,
        transfer_number=await next_transfer_number(db, tenant_id),
        from_store_id=from_wh.store_id,
        to_store_id=to_wh.store_id,
        from_warehouse_id=from_wh.id,
        to_warehouse_id=to_wh.id,
        status="requested" if submit else "draft",
        notes=notes,
        created_by=user_id,
    )
    db.add(transfer)
    await db.flush()
    await _add_transfer_items(db, tenant_id=tenant_id, transfer_id=transfer.id, items=items)
    return transfer


async def submit_transfer(db: AsyncSession, *, tenant_id: str, transfer_id: str) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_SUBMITTABLE:
        raise HTTPException(status_code=409, detail=f"Cannot submit transfer in status {transfer.status}")
    transfer.status = "requested"
    await db.flush()
    return transfer


async def assert_inter_store_manager_action(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    transfer: m.StockTransfer,
    action: str,
) -> None:
    """BR-13.2: ship = source manager; receive = destination manager.

    Warehouse-only transfers (null store id for the action side) skip this gate.
    When a store has no manager assigned, any ``stores``/inventory write may act.
    When a manager is assigned, only that user — or company_admin/super_admin with
    audit ``transfer_manager_override`` — may act.
    """
    if action not in {"ship", "receive"}:
        raise ValueError(f"Unsupported transfer action: {action}")

    store_id = transfer.from_store_id if action == "ship" else transfer.to_store_id
    if not store_id:
        return

    store = await get_store(db, tenant_id, store_id)
    manager_id = getattr(store, "manager_id", None)
    if not manager_id:
        return
    if user_id == manager_id:
        return

    if role in {"company_admin", "super_admin"}:
        from app import audit as audit_svc

        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="transfer_manager_override",
            entity="stock_transfer",
            entity_id=transfer.id,
            module="stores",
            details={
                "transfer_action": action,
                "store_id": store_id,
                "store_code": store.code,
                "expected_manager_id": manager_id,
                "transfer_number": transfer.transfer_number,
            },
        )
        return

    code = "TRANSFER_SHIP_FORBIDDEN" if action == "ship" else "TRANSFER_RECEIVE_FORBIDDEN"
    raise HTTPException(
        status_code=403,
        detail={
            "code": code,
            "message": (
                "Only the source store manager may ship this transfer"
                if action == "ship"
                else "Only the destination store manager may receive this transfer"
            ),
            "store_id": store_id,
            "manager_id": manager_id,
        },
    )


async def ship_transfer(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    transfer_id: str,
    role: str = "company_admin",
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_SHIPPABLE:
        raise HTTPException(status_code=409, detail=f"Cannot ship transfer in status {transfer.status}")
    await assert_inter_store_manager_action(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        transfer=transfer,
        action="ship",
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
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    transfer_id: str,
    role: str = "company_admin",
) -> m.StockTransfer:
    transfer = await get_transfer(db, tenant_id, transfer_id)
    if transfer.status not in TRANSFER_RECEIVABLE:
        raise HTTPException(status_code=409, detail=f"Cannot receive transfer in status {transfer.status}")
    await assert_inter_store_manager_action(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        role=role,
        transfer=transfer,
        action="receive",
    )
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
