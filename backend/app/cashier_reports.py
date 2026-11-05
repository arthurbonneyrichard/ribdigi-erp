"""Cashier performance: who sold what, and who gave discounts, refunds and voids.

Retail reads till sales (transactions) and returns. Restaurant reads restaurant_orders.
Each desk has its own query so neither reads the other's tables. The sensitive-activity
counts on both come from the audit log, which records the cashier at the till.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json

RETAIL_ACTIVITY = {
    "pos_discount": "Discount given",
    "drawer_open": "Drawer opened",
    "credit_limit_override": "Credit limit overridden",
    "sales_return_posted": "Refund or return",
    "pos_sale_handover": "Sale handed over",
    "pos_cashier_switched": "Took over the till",
    "pos_unlock_failed": "Wrong passcode",
}
RESTAURANT_ACTIVITY = {
    "restaurant_order_voided": "Order voided",
    "restaurant_order_cancelled": "Order cancelled",
    "restaurant_order_refunded": "Order refunded",
    "pos_sale_handover": "Sale handed over",
    "pos_cashier_switched": "Took over the till",
    "pos_unlock_failed": "Wrong passcode",
}
MAX_TRANSACTIONS = 500


def period_key(moment: datetime, period: str) -> str:
    if period == "month":
        return moment.strftime("%Y-%m")
    if period == "week":
        return (moment - timedelta(days=moment.weekday())).strftime("%Y-%m-%d")
    return moment.strftime("%Y-%m-%d")


def _window(stmt, column, from_date: datetime | None, to_date: datetime | None):
    if from_date is not None:
        stmt = stmt.where(column >= from_date)
    if to_date is not None:
        stmt = stmt.where(column <= to_date)
    return stmt


def _money(value) -> float:
    return money_json(round(float(value or 0), 2))


async def _names(db: AsyncSession, tenant_id: str, ids: set[str]) -> dict[str, str]:
    clean = {i for i in ids if i}
    if not clean:
        return {}
    rows = await db.execute(
        select(m.User.id, m.User.full_name).where(m.User.tenant_id == tenant_id, m.User.id.in_(clean))
    )
    return {row[0]: row[1] for row in rows.all()}


async def _terminal_labels(db: AsyncSession, tenant_id: str, device_ids: set[str]) -> dict[str, str]:
    clean = {i for i in device_ids if i}
    if not clean:
        return {}
    rows = await db.execute(
        select(m.PosDevice.device_id, m.PosDevice.label).where(
            m.PosDevice.tenant_id == tenant_id, m.PosDevice.device_id.in_(clean)
        )
    )
    return {device: label for device, label in rows.all() if label}


def _terminal_name(device_id: str | None, labels: dict[str, str]) -> str | None:
    if not device_id:
        return None
    return labels.get(device_id) or f"Till {device_id[-6:]}"


async def _activity(
    db: AsyncSession,
    tenant_id: str,
    *,
    actions: dict[str, str],
    from_date: datetime | None,
    to_date: datetime | None,
    cashier_id: str | None,
    limit: int | None = None,
) -> list[m.AuditLog]:
    stmt = select(m.AuditLog).where(m.AuditLog.tenant_id == tenant_id, m.AuditLog.action.in_(tuple(actions)))
    stmt = _window(stmt, m.AuditLog.created_at, from_date, to_date)
    if cashier_id:
        stmt = stmt.where(m.AuditLog.user_id == cashier_id)
    stmt = stmt.order_by(m.AuditLog.created_at.desc())
    if limit:
        stmt = stmt.limit(limit)
    return list((await db.execute(stmt)).scalars())


def _blank_row(cashier_id: str) -> dict:
    return {
        "cashier_id": cashier_id,
        "sale_count": 0,
        "sales_total": 0.0,
        "discounts": 0.0,
        "refund_count": 0,
        "refunds_total": 0.0,
        "void_count": 0,
        "by_payment": defaultdict(float),
        "activity": defaultdict(int),
    }


def _finish(
    rows: dict[str, dict],
    periods: dict[tuple[str, str], dict],
    names: dict[str, str],
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    period: str,
    labels: dict[str, str],
) -> dict:
    cashiers = []
    for row in rows.values():
        count = row["sale_count"]
        cashiers.append(
            {
                "cashier_id": row["cashier_id"],
                "name": names.get(row["cashier_id"]) or "Unknown cashier",
                "sale_count": count,
                "sales_total": _money(row["sales_total"]),
                "avg_sale": _money(row["sales_total"] / count) if count else 0.0,
                "discounts": _money(row["discounts"]),
                "refund_count": row["refund_count"],
                "refunds_total": _money(row["refunds_total"]),
                "void_count": row["void_count"],
                "by_payment": {k: _money(v) for k, v in sorted(row["by_payment"].items())},
                "activity": [
                    {"action": action, "label": labels.get(action, action), "count": count_}
                    for action, count_ in sorted(row["activity"].items())
                ],
            }
        )
    cashiers.sort(key=lambda r: (-r["sales_total"], r["name"].casefold()))
    series = [
        {
            "period": key[0],
            "cashier_id": key[1],
            "name": names.get(key[1]) or "Unknown cashier",
            "sale_count": value["sale_count"],
            "sales_total": _money(value["sales_total"]),
        }
        for key, value in sorted(periods.items())
    ]
    return {
        "from": from_date.date().isoformat() if from_date else None,
        "to": to_date.date().isoformat() if to_date else None,
        "period": period,
        "cashiers": cashiers,
        "periods": series,
        "totals": {
            "sale_count": sum(r["sale_count"] for r in cashiers),
            "sales_total": _money(sum(r["sales_total"] for r in cashiers)),
            "discounts": _money(sum(r["discounts"] for r in cashiers)),
            "refunds_total": _money(sum(r["refunds_total"] for r in cashiers)),
            "void_count": sum(r["void_count"] for r in cashiers),
        },
    }


# ---------- retail ----------


async def _retail_sales(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    store_id: str | None,
    store_ids: list[str] | None,
) -> list[tuple[m.Transaction, m.PosSession | None]]:
    stmt = (
        select(m.Transaction, m.PosSession)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
            m.Transaction.status == "completed",
        )
    )
    stmt = _window(stmt, m.Transaction.created_at, from_date, to_date)
    if store_id:
        stmt = stmt.where(m.PosSession.store_id == store_id)
    elif store_ids is not None:
        stmt = stmt.where(m.PosSession.store_id.in_(store_ids))
    rows = await db.execute(stmt.order_by(m.Transaction.created_at.desc()))
    return [(tx, session) for tx, session in rows.all()]


def _retail_cashier(tx: m.Transaction, session: m.PosSession | None) -> str:
    payload = tx.payload if isinstance(tx.payload, dict) else {}
    return str(payload.get("cashier_user_id") or (session.user_id if session else "") or "")


async def retail_performance(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    period: str = "day",
    cashier_id: str | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> dict:
    rows: dict[str, dict] = {}
    periods: dict[tuple[str, str], dict] = defaultdict(lambda: {"sale_count": 0, "sales_total": 0.0})
    for tx, session in await _retail_sales(
        db, tenant_id, from_date=from_date, to_date=to_date, store_id=store_id, store_ids=store_ids
    ):
        who = _retail_cashier(tx, session)
        if not who or (cashier_id and who != cashier_id):
            continue
        payload = tx.payload if isinstance(tx.payload, dict) else {}
        row = rows.setdefault(who, _blank_row(who))
        total = float(tx.total or 0)
        row["sale_count"] += 1
        row["sales_total"] += total
        row["discounts"] += float(payload.get("discount_amount") or 0) + float(payload.get("line_discounts") or 0)
        row["by_payment"][str(payload.get("payment_method") or "cash")] += total
        bucket = periods[(period_key(tx.created_at, period), who)]
        bucket["sale_count"] += 1
        bucket["sales_total"] += total
    returns = select(m.SalesReturn).where(
        m.SalesReturn.tenant_id == tenant_id,
        m.SalesReturn.status == "posted",
        m.SalesReturn.transaction_id.is_not(None),
    )
    returns = _window(returns, m.SalesReturn.created_at, from_date, to_date)
    if store_id:
        returns = returns.where(m.SalesReturn.store_id == store_id)
    elif store_ids is not None:
        returns = returns.where(m.SalesReturn.store_id.in_(store_ids))
    for ret in (await db.execute(returns)).scalars():
        who = str(ret.created_by or "")
        if not who or (cashier_id and who != cashier_id):
            continue
        row = rows.setdefault(who, _blank_row(who))
        row["refund_count"] += 1
        row["refunds_total"] += float(ret.total_amount or 0)
    for log in await _activity(
        db, tenant_id, actions=RETAIL_ACTIVITY, from_date=from_date, to_date=to_date, cashier_id=cashier_id
    ):
        who = str(log.user_id or "")
        if who in rows or (who and not store_id and store_ids is None):
            rows.setdefault(who, _blank_row(who))["activity"][log.action] += 1
    names = await _names(db, tenant_id, set(rows))
    return _finish(
        rows, periods, names, from_date=from_date, to_date=to_date, period=period, labels=RETAIL_ACTIVITY
    )


def _activity_rows(logs: list[m.AuditLog], names: dict[str, str], labels: dict[str, str]) -> list[dict]:
    out = []
    for log in logs:
        details = log.details if isinstance(log.details, dict) else {}
        out.append(
            {
                "at": log.created_at.isoformat() + "Z" if log.created_at else None,
                "cashier_id": log.user_id,
                "name": names.get(str(log.user_id or "")) or "Unknown cashier",
                "action": log.action,
                "label": labels.get(log.action, log.action),
                "reference": details.get("reference"),
                "amount": details.get("total"),
                "terminal": details.get("device_id"),
            }
        )
    return out


async def retail_transactions(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    cashier_id: str | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
    limit: int = 200,
) -> dict:
    picked = []
    for tx, session in await _retail_sales(
        db, tenant_id, from_date=from_date, to_date=to_date, store_id=store_id, store_ids=store_ids
    ):
        who = _retail_cashier(tx, session)
        if cashier_id and who != cashier_id:
            continue
        picked.append((tx, who))
        if len(picked) >= limit:
            break
    payloads = [tx.payload if isinstance(tx.payload, dict) else {} for tx, _who in picked]
    logs = await _activity(
        db, tenant_id, actions=RETAIL_ACTIVITY, from_date=from_date, to_date=to_date,
        cashier_id=cashier_id, limit=limit,
    )
    names = await _names(
        db,
        tenant_id,
        {who for _tx, who in picked}
        | {str(p.get("started_by_user_id") or "") for p in payloads}
        | {str(log.user_id or "") for log in logs},
    )
    labels = await _terminal_labels(db, tenant_id, {str(p.get("device_id") or "") for p in payloads})
    rows = []
    for (tx, who), payload in zip(picked, payloads):
        starter = str(payload.get("started_by_user_id") or "")
        rows.append(
            {
                "id": tx.id,
                "reference": tx.reference,
                "at": tx.created_at.isoformat() + "Z" if tx.created_at else None,
                "cashier_id": who,
                "name": payload.get("cashier_name") or names.get(who) or "Unknown cashier",
                "terminal": _terminal_name(payload.get("device_id"), labels),
                "total": _money(tx.total),
                "payment_method": payload.get("payment_method"),
                "discount": _money(
                    float(payload.get("discount_amount") or 0) + float(payload.get("line_discounts") or 0)
                ),
                "started_by": names.get(starter) if starter else None,
            }
        )
    return {"transactions": rows, "activity": _activity_rows(logs, names, RETAIL_ACTIVITY)}


# ---------- restaurant ----------


async def _restaurant_paid(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    store_id: str | None,
    store_ids: list[str] | None,
) -> list[m.RestaurantOrder]:
    stmt = select(m.RestaurantOrder).where(
        m.RestaurantOrder.tenant_id == tenant_id,
        m.RestaurantOrder.status.in_(("completed", "refunded")),
    )
    stmt = _window(stmt, m.RestaurantOrder.completed_at, from_date, to_date)
    if store_id:
        stmt = stmt.where(m.RestaurantOrder.store_id == store_id)
    elif store_ids is not None:
        stmt = stmt.where(m.RestaurantOrder.store_id.in_(store_ids))
    return list((await db.execute(stmt.order_by(m.RestaurantOrder.completed_at.desc()))).scalars())


def _restaurant_cashier(order: m.RestaurantOrder) -> str:
    return str(order.completed_by or order.created_by or "")


async def restaurant_performance(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    period: str = "day",
    cashier_id: str | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> dict:
    rows: dict[str, dict] = {}
    periods: dict[tuple[str, str], dict] = defaultdict(lambda: {"sale_count": 0, "sales_total": 0.0})
    for order in await _restaurant_paid(
        db, tenant_id, from_date=from_date, to_date=to_date, store_id=store_id, store_ids=store_ids
    ):
        who = _restaurant_cashier(order)
        if not who or (cashier_id and who != cashier_id):
            continue
        row = rows.setdefault(who, _blank_row(who))
        total = float(order.total_amount or 0)
        row["sale_count"] += 1
        row["sales_total"] += total
        row["by_payment"][str(order.payment_method or "cash")] += total
        bucket = periods[(period_key(order.completed_at or order.created_at, period), who)]
        bucket["sale_count"] += 1
        bucket["sales_total"] += total
    for log in await _activity(
        db, tenant_id, actions=RESTAURANT_ACTIVITY, from_date=from_date, to_date=to_date, cashier_id=cashier_id
    ):
        who = str(log.user_id or "")
        if not who:
            continue
        details = log.details if isinstance(log.details, dict) else {}
        row = rows.setdefault(who, _blank_row(who))
        row["activity"][log.action] += 1
        if log.action == "restaurant_order_voided":
            row["void_count"] += 1
        elif log.action == "restaurant_order_refunded":
            row["refund_count"] += 1
            row["refunds_total"] += float(details.get("total") or 0)
    names = await _names(db, tenant_id, set(rows))
    return _finish(
        rows, periods, names, from_date=from_date, to_date=to_date, period=period, labels=RESTAURANT_ACTIVITY
    )


async def restaurant_transactions(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None,
    to_date: datetime | None,
    cashier_id: str | None = None,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
    limit: int = 200,
) -> dict:
    orders = [
        order
        for order in await _restaurant_paid(
            db, tenant_id, from_date=from_date, to_date=to_date, store_id=store_id, store_ids=store_ids
        )
        if not cashier_id or _restaurant_cashier(order) == cashier_id
    ][:limit]
    logs = await _activity(
        db, tenant_id, actions=RESTAURANT_ACTIVITY, from_date=from_date, to_date=to_date,
        cashier_id=cashier_id, limit=limit,
    )
    names = await _names(
        db,
        tenant_id,
        {_restaurant_cashier(o) for o in orders}
        | {str(o.created_by or "") for o in orders}
        | {str(log.user_id or "") for log in logs},
    )
    labels = await _terminal_labels(db, tenant_id, {str(o.completed_device_id or "") for o in orders})
    rows = []
    for order in orders:
        who = _restaurant_cashier(order)
        opened_by = str(order.created_by or "")
        moment = order.completed_at or order.created_at
        rows.append(
            {
                "id": order.id,
                "reference": order.order_number,
                "at": moment.isoformat() + "Z" if moment else None,
                "cashier_id": who,
                "name": names.get(who) or "Unknown cashier",
                "terminal": _terminal_name(order.completed_device_id, labels),
                "total": _money(order.total_amount),
                "payment_method": order.payment_method,
                "status": order.status,
                "started_by": names.get(opened_by) if opened_by and opened_by != who else None,
            }
        )
    return {"transactions": rows, "activity": _activity_rows(logs, names, RESTAURANT_ACTIVITY)}
