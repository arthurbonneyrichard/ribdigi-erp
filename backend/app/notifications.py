"""In-app notifications, preferences, and alert helpers."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

DEFAULT_PREFERENCES = {
    "low_stock": {"dashboard": True, "email": False, "sms": False},
    "expense_approval": {"dashboard": True, "email": False, "sms": False},
    "shift_variance": {"dashboard": True, "email": False, "sms": False},
    "credit_limit": {"dashboard": True, "email": False, "sms": False},
    "purchase_received": {"dashboard": True, "email": False, "sms": False},
    "payment_due": {"dashboard": True, "email": True, "sms": False},
    "quotation_expiry": {"dashboard": True, "email": True, "sms": False},
    "recurring_expense": {"dashboard": True, "email": True, "sms": False},
    "transfer": {"dashboard": True, "email": False, "sms": False},
    "billing": {"dashboard": True, "email": True, "sms": False},
    "system": {"dashboard": True, "email": False, "sms": False},
}

VALID_CATEGORIES = set(DEFAULT_PREFERENCES.keys())


def merge_preferences(raw: dict | None) -> dict:
    merged = {k: dict(v) for k, v in DEFAULT_PREFERENCES.items()}
    if not raw:
        return merged
    for key, channels in raw.items():
        if key in merged and isinstance(channels, dict):
            merged[key] = {**merged[key], **channels}
    return merged


def serialize_notification(note: m.Notification) -> dict:
    return {
        "id": note.id,
        "user_id": note.user_id,
        "category": note.category or "system",
        "title": note.title,
        "message": note.message,
        "status": note.status,
        "entity_type": note.entity_type,
        "entity_id": note.entity_id,
        "created_at": note.created_at,
    }


async def get_preferences(db: AsyncSession, tenant_id: str, user_id: str) -> dict:
    row = (
        await db.execute(
            select(m.NotificationPreference).where(
                m.NotificationPreference.tenant_id == tenant_id,
                m.NotificationPreference.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    return merge_preferences(row.preferences if row else None)


async def update_preferences(
    db: AsyncSession, tenant_id: str, user_id: str, preferences: dict
) -> dict:
    merged = merge_preferences(preferences)
    row = (
        await db.execute(
            select(m.NotificationPreference).where(
                m.NotificationPreference.tenant_id == tenant_id,
                m.NotificationPreference.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        row = m.NotificationPreference(
            tenant_id=tenant_id,
            user_id=user_id,
            preferences=merged,
        )
        db.add(row)
    else:
        row.preferences = merged
        row.updated_at = datetime.utcnow()
    await db.flush()
    return merged


async def channel_enabled(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    category: str,
    channel: str = "dashboard",
) -> bool:
    if not user_id:
        return True
    prefs = await get_preferences(db, tenant_id, user_id)
    cat = prefs.get(category) or prefs.get("system") or {}
    return bool(cat.get(channel, True))


async def create_notification(
    db: AsyncSession,
    *,
    tenant_id: str,
    title: str,
    message: str,
    category: str = "system",
    user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> m.Notification | None:
    category = category if category in VALID_CATEGORIES else "system"
    if user_id and not await channel_enabled(
        db, tenant_id=tenant_id, user_id=user_id, category=category, channel="dashboard"
    ):
        return None
    note = m.Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        category=category,
        title=title,
        message=message,
        status="unread",
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(note)
    await db.flush()

    # Best-effort email + SMS channels (do not fail the notification write)
    try:
        from app import emailer
        from app import sms as sms_svc

        async def _recipients_for_channel(channel: str) -> list[m.User]:
            if user_id:
                if await channel_enabled(
                    db, tenant_id=tenant_id, user_id=user_id, category=category, channel=channel
                ):
                    user = await db.get(m.User, user_id)
                    return [user] if user else []
                return []
            admins = (
                await db.execute(
                    select(m.User).where(
                        m.User.tenant_id == tenant_id,
                        m.User.is_active == True,  # noqa: E712
                        m.User.role.in_(["company_admin", "super_admin"]),
                    )
                )
            ).scalars().all()
            out: list[m.User] = []
            for admin in admins:
                if await channel_enabled(
                    db, tenant_id=tenant_id, user_id=admin.id, category=category, channel=channel
                ):
                    out.append(admin)
            return out

        for admin in await _recipients_for_channel("email"):
            if admin.email:
                await emailer.send_notification_email(
                    to=admin.email, title=title, message=message, category=category
                )
        for admin in await _recipients_for_channel("sms"):
            phone = getattr(admin, "phone", None)
            if phone:
                await sms_svc.send_notification_sms(to=phone, title=title, message=message)
    except Exception:
        pass

    return note


async def list_notifications(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None = None,
    status: str | None = None,
    category: str | None = None,
    limit: int = 100,
) -> list[m.Notification]:
    stmt = select(m.Notification).where(m.Notification.tenant_id == tenant_id)
    if user_id:
        stmt = stmt.where(
            or_(m.Notification.user_id == user_id, m.Notification.user_id.is_(None))
        )
    if status:
        stmt = stmt.where(m.Notification.status == status)
    if category:
        stmt = stmt.where(m.Notification.category == category)
    # Keep last ~90 days
    cutoff = datetime.utcnow() - timedelta(days=90)
    stmt = stmt.where(m.Notification.created_at >= cutoff)
    stmt = stmt.order_by(m.Notification.created_at.desc()).limit(limit)
    return (await db.execute(stmt)).scalars().all()


async def unread_count(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> int:
    rows = await list_notifications(
        db, tenant_id=tenant_id, user_id=user_id, status="unread", limit=500
    )
    return len(rows)


async def mark_read(
    db: AsyncSession, *, tenant_id: str, notification_id: str, user_id: str | None = None
) -> m.Notification:
    note = (
        await db.execute(
            select(m.Notification).where(
                m.Notification.id == notification_id,
                m.Notification.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Notification not found")
    if user_id and note.user_id and note.user_id != user_id:
        raise HTTPException(status_code=403, detail="Notification belongs to another user")
    note.status = "read"
    await db.flush()
    return note


async def mark_all_read(db: AsyncSession, *, tenant_id: str, user_id: str | None = None) -> int:
    rows = await list_notifications(
        db, tenant_id=tenant_id, user_id=user_id, status="unread", limit=500
    )
    for note in rows:
        note.status = "read"
    await db.flush()
    return len(rows)


async def notify_low_stock_if_needed(
    db: AsyncSession,
    *,
    tenant_id: str,
    product: m.Product,
) -> m.Notification | None:
    stock = float(product.stock_qty or 0)
    reorder = float(product.reorder_level or 0)
    if stock > reorder:
        return None
    # Avoid duplicate unread low-stock alerts for same product
    existing = (
        await db.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "low_stock",
                m.Notification.entity_id == product.id,
                m.Notification.status == "unread",
            )
        )
    ).scalar_one_or_none()
    if existing:
        return None
    return await create_notification(
        db,
        tenant_id=tenant_id,
        category="low_stock",
        title="Low Stock",
        message=f"{product.name} ({product.sku}) is at {stock} (reorder {reorder}).",
        entity_type="product",
        entity_id=product.id,
    )


async def notify_warehouse_low_stock_if_needed(
    db: AsyncSession,
    *,
    tenant_id: str,
    product: m.Product,
    stock: m.WarehouseStock,
) -> m.Notification | None:
    qty = float(stock.quantity or 0)
    reorder = float(getattr(stock, "reorder_level", 0) or 0)
    if reorder <= 0 or qty > reorder:
        return None
    entity_id = f"{stock.warehouse_id}:{product.id}"
    existing = (
        await db.execute(
            select(m.Notification).where(
                m.Notification.tenant_id == tenant_id,
                m.Notification.category == "low_stock",
                m.Notification.entity_type == "warehouse_stock",
                m.Notification.entity_id == entity_id,
                m.Notification.status == "unread",
            )
        )
    ).scalar_one_or_none()
    if existing:
        return None
    wh = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.id == stock.warehouse_id, m.Warehouse.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    loc = wh.code if wh else stock.warehouse_id[:8]
    suggested = float(getattr(stock, "reorder_qty", 0) or 0) or max(round(reorder - qty, 3), 0)
    return await create_notification(
        db,
        tenant_id=tenant_id,
        category="low_stock",
        title="Store/warehouse low stock",
        message=(
            f"{product.name} ({product.sku}) at {loc}: {qty} "
            f"(reorder {reorder}; suggest order {suggested})."
        ),
        entity_type="warehouse_stock",
        entity_id=entity_id,
    )


async def scan_low_stock(db: AsyncSession, tenant_id: str) -> int:
    """Create unread low-stock notifications for products and warehouse policies."""
    products = (
        await db.execute(select(m.Product).where(m.Product.tenant_id == tenant_id))
    ).scalars().all()
    created = 0
    for product in products:
        note = await notify_low_stock_if_needed(db, tenant_id=tenant_id, product=product)
        if note:
            created += 1

    rows = (
        await db.execute(
            select(m.WarehouseStock, m.Product)
            .join(m.Product, m.Product.id == m.WarehouseStock.product_id)
            .where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.reorder_level > 0,
            )
        )
    ).all()
    for stock, product in rows:
        note = await notify_warehouse_low_stock_if_needed(
            db, tenant_id=tenant_id, product=product, stock=stock
        )
        if note:
            created += 1
    return created


async def scan_payment_due(db: AsyncSession, tenant_id: str, within_days: int = 3) -> int:
    now = datetime.utcnow()
    horizon = now + timedelta(days=within_days)
    invoices = (
        await db.execute(
            select(m.SalesInvoice).where(
                m.SalesInvoice.tenant_id == tenant_id,
                m.SalesInvoice.status.in_(["posted", "partial"]),
                m.SalesInvoice.due_date.is_not(None),
                m.SalesInvoice.due_date <= horizon,
            )
        )
    ).scalars().all()
    created = 0
    for inv in invoices:
        due = max(float(inv.total_amount) - float(inv.paid_amount or 0), 0)
        if due <= 0:
            continue
        existing = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.tenant_id == tenant_id,
                    m.Notification.category == "payment_due",
                    m.Notification.entity_id == inv.id,
                    m.Notification.status == "unread",
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        await create_notification(
            db,
            tenant_id=tenant_id,
            category="payment_due",
            title="Payment Due",
            message=(
                f"Invoice {inv.invoice_number} has {due:.2f} due "
                f"by {inv.due_date.date().isoformat()}."
            ),
            entity_type="sales_invoice",
            entity_id=inv.id,
        )
        created += 1
    return created


async def scan_quotation_expiry(
    db: AsyncSession, tenant_id: str, within_days: int = 1
) -> dict[str, int]:
    """Remind before quotation validity ends; mark past-due draft/sent quotes expired.

    USER_MANUAL: remind 1 day before quotation expiry (BR-7.2).
    """
    now = datetime.utcnow()
    horizon = now + timedelta(days=max(0, int(within_days)))
    quotes = (
        await db.execute(
            select(m.SalesQuotation).where(
                m.SalesQuotation.tenant_id == tenant_id,
                m.SalesQuotation.status.in_(["draft", "sent"]),
                m.SalesQuotation.valid_until.is_not(None),
            )
        )
    ).scalars().all()
    reminded = 0
    expired = 0
    for quote in quotes:
        valid_until = quote.valid_until
        if valid_until is None:
            continue
        if valid_until < now:
            quote.status = "expired"
            expired += 1
            existing = (
                await db.execute(
                    select(m.Notification).where(
                        m.Notification.tenant_id == tenant_id,
                        m.Notification.category == "quotation_expiry",
                        m.Notification.entity_id == quote.id,
                        m.Notification.status == "unread",
                    )
                )
            ).scalar_one_or_none()
            if existing:
                continue
            await create_notification(
                db,
                tenant_id=tenant_id,
                category="quotation_expiry",
                title="Quotation Expired",
                message=(
                    f"Quotation {quote.quotation_number} expired on "
                    f"{valid_until.date().isoformat()}."
                ),
                entity_type="sales_quotation",
                entity_id=quote.id,
            )
            reminded += 1
            continue
        if valid_until > horizon:
            continue
        existing = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.tenant_id == tenant_id,
                    m.Notification.category == "quotation_expiry",
                    m.Notification.entity_id == quote.id,
                    m.Notification.status == "unread",
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        await create_notification(
            db,
            tenant_id=tenant_id,
            category="quotation_expiry",
            title="Quotation Expiring Soon",
            message=(
                f"Quotation {quote.quotation_number} expires on "
                f"{valid_until.date().isoformat()}."
            ),
            entity_type="sales_quotation",
            entity_id=quote.id,
        )
        reminded += 1
    await db.flush()
    return {"reminded": reminded, "expired": expired}


async def scan_recurring_expense_upcoming(
    db: AsyncSession, tenant_id: str, within_days: int = 1
) -> dict[str, int]:
    """Notify before recurring expenses auto-generate (BR-9.5)."""
    now = datetime.utcnow()
    horizon = now + timedelta(days=max(0, int(within_days)))
    rows = (
        await db.execute(
            select(m.RecurringExpense).where(
                m.RecurringExpense.tenant_id == tenant_id,
                m.RecurringExpense.is_active == True,  # noqa: E712
                m.RecurringExpense.next_run_at <= horizon,
            )
        )
    ).scalars().all()
    reminded = 0
    for row in rows:
        if row.end_date and row.end_date < now:
            continue
        if row.skip_next:
            continue
        if row.last_notified_for is not None and row.last_notified_for == row.next_run_at:
            continue
        existing = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.tenant_id == tenant_id,
                    m.Notification.category == "recurring_expense",
                    m.Notification.entity_id == row.id,
                    m.Notification.status == "unread",
                )
            )
        ).scalar_one_or_none()
        if existing:
            row.last_notified_for = row.next_run_at
            continue
        amount = float(row.next_amount) if row.next_amount is not None else float(row.amount)
        label = (row.next_description if row.next_description is not None else row.description) or row.category
        due = row.next_run_at.date().isoformat() if row.next_run_at else "soon"
        title = (
            "Recurring Expense Due"
            if row.next_run_at and row.next_run_at <= now
            else "Recurring Expense Upcoming"
        )
        await create_notification(
            db,
            tenant_id=tenant_id,
            category="recurring_expense",
            title=title,
            message=(
                f"{label} ({amount:.2f}) is scheduled for {due} "
                f"({row.frequency}). Skip or modify the next occurrence if needed."
            ),
            entity_type="recurring_expense",
            entity_id=row.id,
        )
        row.last_notified_for = row.next_run_at
        reminded += 1
    await db.flush()
    return {"reminded": reminded}
