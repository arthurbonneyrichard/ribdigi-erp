"""Restaurant tips: taken on the bill, held for staff, shared out and paid.

- A tip is added when the bill is paid. It is never sales and never taxed as sales: the money
  (cash, card, Mobile Money) is debited and "Tips Owed to Staff" (2187) is credited.
  Cash tips sit in the drawer, so the shift's expected cash includes them.
- A refund gives back the bill, not the tip. The tip already belongs to staff.
- A manager makes a share-out for a run of days. It takes every tip from bills paid in those
  days that is not already shared, and splits the total:
    by_server  each bill's tip goes to whoever opened the bill (the waiter);
    equal      evenly between the people chosen;
    hours      by hours each chosen person clocked (HR time), so it needs their staff records.
  Leftover pesewas from rounding go one at a time to the biggest shares.
- Someone who gets no share approves it. Then it is paid:
    cash       one payment out of cash, bank or Mobile Money clears 2187;
    payroll    each share rides on that month's payslip as a taxable earning without SSNIT
               (an accountant should confirm this treatment), and approving the payroll
               clears 2187 instead of adding to wages.
- A draft or an approved share-out not yet paid can be cancelled; its tips go back to the pool.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_DOWN, Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.honesty import money_json, optional_honest_narrative

TIPS_ACCOUNT = "2187"
MANAGERS = frozenset({"company_admin", "restaurant_manager", "super_admin"})
METHODS = frozenset({"by_server", "equal", "hours"})
PAY_BY = frozenset({"cash", "payroll"})
PAY_METHODS = frozenset({"cash", "bank_transfer", "mobile_money"})
CENT = Decimal("0.01")
ZERO = Decimal("0")


def D(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def split(total: Decimal, bases: dict[str, Decimal]) -> dict[str, Decimal]:
    """Split total by bases to the pesewa; the shares always add up to the total exactly."""
    weight = sum(bases.values(), ZERO)
    if total <= 0 or weight <= 0:
        return {k: ZERO for k in bases}
    raw = {k: total * b / weight for k, b in bases.items()}
    out = {k: v.quantize(CENT, rounding=ROUND_DOWN) for k, v in raw.items()}
    left = int(((total - sum(out.values(), ZERO)) / CENT).to_integral_value())
    for key in sorted(raw, key=lambda k: (-(raw[k] - out[k]), -bases[k], k))[:left]:
        out[key] += CENT
    return out


def require_manager(claims: dict) -> None:
    if str(claims.get("role") or "") not in MANAGERS:
        raise HTTPException(status_code=403, detail={"code": "TIPS_MANAGER", "message": "Tips are shared out by a manager."})


async def _audit(db, tenant_id, user_id, action, entity_id, details):
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant", action=action,
        entity="restaurant_tip_run", entity_id=entity_id, details=details,
    )


async def _post(db, tenant_id, *, user_id, description, lines, reference, source, source_id) -> str:
    from app import hrm

    return await hrm._post(
        db, tenant_id, user_id=user_id, description=description, lines=lines,
        reference=reference, source=source, source_id=source_id,
    )


# --- On the bill ---------------------------------------------------------------------------


async def record_tip(db: AsyncSession, order: m.RestaurantOrder, tip, *, user_id) -> None:
    """Book a tip given with the bill. Called while the bill is being paid."""
    from app import accounting

    amount = D(tip).quantize(CENT)
    if amount <= 0:
        return
    order.tip_amount = amount
    description = f"Tip on {order.order_number}"
    money_account = accounting.pos_debit_account_for_payment_method(order.payment_method)[0]
    await _post(
        db, order.tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": money_account, "debit": money_json(amount), "credit": 0, "description": description},
            {"account_code": TIPS_ACCOUNT, "debit": 0, "credit": money_json(amount), "description": description},
        ],
        reference=order.order_number, source="restaurant_tip", source_id=order.id,
    )


# --- Share-outs ----------------------------------------------------------------------------


async def _zone(db, tenant_id):
    from app import hrm_time

    return await hrm_time._zone(db, tenant_id)


async def _bounds(db, tenant_id, date_from: date, date_to: date) -> tuple[datetime, datetime]:
    from app import hrm_time

    zone = await _zone(db, tenant_id)
    start, _ = hrm_time.local_day_bounds(date_from, zone)
    _, end = hrm_time.local_day_bounds(date_to, zone)
    return start, end


async def _staff_by_user(db, tenant_id) -> dict[str, m.HrmEmployee]:
    """Staff records matched to sign-ins by email, the same way commission is matched."""
    from app import hrm

    users = {
        (email or "").strip().lower(): uid
        for uid, email in (await db.execute(select(m.User.id, m.User.email).where(m.User.tenant_id == tenant_id))).all()
        if email
    }
    out = {}
    for person in await hrm.list_employees(db, tenant_id, show="all"):
        uid = users.get((person.email or "").strip().lower())
        if uid:
            out[uid] = person
    return out


async def pool(db: AsyncSession, tenant_id: str, date_from: date, date_to: date) -> list[m.RestaurantOrder]:
    start, end = await _bounds(db, tenant_id, date_from, date_to)
    return list(
        (
            await db.execute(
                select(m.RestaurantOrder).where(
                    m.RestaurantOrder.tenant_id == tenant_id,
                    m.RestaurantOrder.status.in_(("completed", "refunded")),
                    m.RestaurantOrder.tip_amount > 0,
                    m.RestaurantOrder.tip_run_id.is_(None),
                    m.RestaurantOrder.completed_at >= start,
                    m.RestaurantOrder.completed_at < end,
                ).order_by(m.RestaurantOrder.completed_at)
            )
        ).scalars().all()
    )


async def unshared(db: AsyncSession, tenant_id: str, date_from: date, date_to: date) -> dict:
    """What is waiting to be shared, and who served it."""
    orders = await pool(db, tenant_id, date_from, date_to)
    names = await _names(db, tenant_id)
    by_server: dict[str, Decimal] = {}
    for o in orders:
        who = o.created_by or o.completed_by or ""
        by_server[who] = by_server.get(who, ZERO) + D(o.tip_amount)
    return {
        "date_from": date_from.isoformat(), "date_to": date_to.isoformat(),
        "total": money_json(sum((D(o.tip_amount) for o in orders), ZERO)), "tips": len(orders),
        "by_server": [{"user_id": k or None, "name": names.get(k) or "Unknown", "amount": money_json(v)} for k, v in by_server.items()],
    }


async def staff(db: AsyncSession, tenant_id: str) -> list[dict]:
    """Active sign-ins who can share tips, with whether they have a staff record (needed for hours and payroll)."""
    linked = await _staff_by_user(db, tenant_id)
    rows = (
        await db.execute(
            select(m.User.id, m.User.full_name, m.User.email, m.User.role)
            .where(m.User.tenant_id == tenant_id, m.User.is_active.is_(True))
            .order_by(m.User.full_name)
        )
    ).all()
    return [
        {"id": uid, "name": name or email, "role": role, "has_staff_record": uid in linked}
        for uid, name, email, role in rows
        if not str(role or "").startswith("platform") and role != "super_admin"
    ]


async def _names(db, tenant_id) -> dict[str, str]:
    rows = (await db.execute(select(m.User.id, m.User.full_name, m.User.email).where(m.User.tenant_id == tenant_id))).all()
    return {uid: name or email for uid, name, email in rows}


async def _hours(db, tenant_id, person: m.HrmEmployee, date_from: date, date_to: date) -> Decimal:
    from app import hrm, hrm_time

    zone = await _zone(db, tenant_id)
    settings = await hrm.get_settings(db, tenant_id)
    minutes = 0
    day = date_from
    while day <= date_to:
        sheet = await hrm_time.sheet_for(db, tenant_id, person, day, zone=zone, settings=settings)
        minutes += int(sheet.get("worked_minutes") or 0)
        day += timedelta(days=1)
    return Decimal(minutes)


async def create_run(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.RestaurantTipRun:
    if payload.date_to < payload.date_from:
        raise HTTPException(status_code=422, detail="The last day is before the first")
    if (payload.date_to - payload.date_from).days > 62:
        raise HTTPException(status_code=422, detail="Share out at most two months at a time")
    if payload.pay_by == "payroll" and not payload.period:
        raise HTTPException(status_code=422, detail="Say which month's payroll pays these tips")
    orders = await pool(db, tenant_id, payload.date_from, payload.date_to)
    if not orders:
        raise HTTPException(status_code=409, detail="There are no unshared tips in those days")
    total = sum((D(o.tip_amount) for o in orders), ZERO)
    staff = await _staff_by_user(db, tenant_id)
    bases: dict[str, Decimal] = {}
    if payload.method == "by_server":
        for o in orders:
            who = o.created_by or o.completed_by
            if not who:
                raise HTTPException(status_code=422, detail=f"Bill {o.order_number} has no server; share these tips another way")
            bases[who] = bases.get(who, ZERO) + D(o.tip_amount)
        amounts = {k: v.quantize(CENT) for k, v in bases.items()}
    else:
        people = list(dict.fromkeys(payload.user_ids))
        if not people:
            raise HTTPException(status_code=422, detail="Choose who shares the tips")
        for uid in people:
            user = await db.get(m.User, uid)
            if user is None or user.tenant_id != tenant_id:
                raise HTTPException(status_code=404, detail="Staff member not found")
        if payload.method == "equal":
            bases = {uid: Decimal(1) for uid in people}
        else:
            missing = [uid for uid in people if uid not in staff]
            if missing:
                names = await _names(db, tenant_id)
                raise HTTPException(
                    status_code=422,
                    detail="Sharing by hours needs a staff record with the same email for: " + ", ".join(names.get(u, u) for u in missing),
                )
            bases = {uid: await _hours(db, tenant_id, staff[uid], payload.date_from, payload.date_to) for uid in people}
            if sum(bases.values(), ZERO) <= 0:
                raise HTTPException(status_code=422, detail="Nobody chosen clocked any time in those days")
        amounts = split(total, bases)
    if payload.pay_by == "payroll":
        missing = [uid for uid, amt in amounts.items() if amt > 0 and uid not in staff]
        if missing:
            names = await _names(db, tenant_id)
            raise HTTPException(
                status_code=422,
                detail="Paying on payroll needs a staff record with the same email for: " + ", ".join(names.get(u, u) for u in missing),
            )
    from app import hrm

    run = m.RestaurantTipRun(
        tenant_id=tenant_id, run_number=await hrm._next_number(db, tenant_id, m.RestaurantTipRun, "TIP"),
        date_from=payload.date_from, date_to=payload.date_to, method=payload.method, pay_by=payload.pay_by,
        period=payload.period if payload.pay_by == "payroll" else None, total=total, tip_count=len(orders),
        status="draft", notes=optional_honest_narrative(payload.notes, label="notes", max_length=500), created_by=user_id,
    )
    db.add(run)
    await db.flush()
    for o in orders:
        o.tip_run_id = run.id
    for uid, amount in amounts.items():
        if amount <= 0:
            continue
        person = staff.get(uid)
        db.add(
            m.RestaurantTipShare(
                tenant_id=tenant_id, run_id=run.id, user_id=uid, employee_id=person.id if person else None,
                basis=bases.get(uid, ZERO), amount=amount,
            )
        )
    await db.flush()
    await _audit(db, tenant_id, user_id, "tip_run_created", run.id, {"total": money_json(total), "method": run.method, "pay_by": run.pay_by})
    return run


async def _run(db, tenant_id, run_id, *, lock=False) -> m.RestaurantTipRun:
    stmt = select(m.RestaurantTipRun).where(m.RestaurantTipRun.id == run_id, m.RestaurantTipRun.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Tip share-out not found")
    return row


async def _shares(db, run_id) -> list[m.RestaurantTipShare]:
    return list((await db.execute(select(m.RestaurantTipShare).where(m.RestaurantTipShare.run_id == run_id))).scalars().all())


async def approve(db: AsyncSession, tenant_id: str, run_id: str, *, user_id) -> m.RestaurantTipRun:
    run = await _run(db, tenant_id, run_id, lock=True)
    if run.status != "draft":
        raise HTTPException(status_code=409, detail=f"This share-out is {run.status}")
    if any(s.user_id == user_id for s in await _shares(db, run.id)):
        raise HTTPException(
            status_code=403,
            detail={"code": "TIPS_SECOND_PERSON", "message": "Someone who gets no share must approve this."},
        )
    run.status, run.approved_by, run.approved_at = "approved", user_id, datetime.utcnow()
    await db.flush()
    await _audit(db, tenant_id, user_id, "tip_run_approved", run.id, {"total": money_json(run.total)})
    return run


async def pay_cash(db: AsyncSession, tenant_id: str, run_id: str, *, method: str, user_id) -> m.RestaurantTipRun:
    from app import accounting

    run = await _run(db, tenant_id, run_id, lock=True)
    if run.pay_by != "cash":
        raise HTTPException(status_code=409, detail="These tips are paid on payroll")
    if run.status != "approved":
        raise HTTPException(status_code=409, detail="Approve the share-out first" if run.status == "draft" else f"This share-out is {run.status}")
    if method not in PAY_METHODS:
        raise HTTPException(status_code=422, detail="Choose how the tips were paid")
    description = f"Tips paid {run.run_number}"
    run.journal_entry_id = await _post(
        db, tenant_id, user_id=user_id, description=description,
        lines=[
            {"account_code": TIPS_ACCOUNT, "debit": money_json(run.total), "credit": 0, "description": description},
            {"account_code": accounting.pos_debit_account_for_payment_method(method)[0], "debit": 0, "credit": money_json(run.total), "description": description},
        ],
        reference=run.run_number, source="restaurant_tip_pay", source_id=run.id,
    )
    for share in await _shares(db, run.id):
        share.status = "paid"
    run.status, run.paid_at, run.paid_method = "paid", datetime.utcnow(), method
    await db.flush()
    await _audit(db, tenant_id, user_id, "tip_run_paid", run.id, {"total": money_json(run.total), "method": method})
    return run


async def cancel(db: AsyncSession, tenant_id: str, run_id: str, *, user_id) -> m.RestaurantTipRun:
    run = await _run(db, tenant_id, run_id, lock=True)
    if run.status not in {"draft", "approved"}:
        raise HTTPException(status_code=409, detail=f"This share-out is {run.status}")
    shares = await _shares(db, run.id)
    if any(s.payroll_run_id for s in shares):
        raise HTTPException(status_code=409, detail="A payroll already holds these tips. Throw that payroll away first.")
    for o in (await db.execute(select(m.RestaurantOrder).where(m.RestaurantOrder.tip_run_id == run.id))).scalars():
        o.tip_run_id = None
    for s in shares:
        s.status = "cancelled"
    run.status = "cancelled"
    await db.flush()
    await _audit(db, tenant_id, user_id, "tip_run_cancelled", run.id, {"total": money_json(run.total)})
    return run


async def serialize_run(db: AsyncSession, run: m.RestaurantTipRun) -> dict:
    names = await _names(db, run.tenant_id)
    return {
        "id": run.id, "run_number": run.run_number, "date_from": run.date_from.isoformat(), "date_to": run.date_to.isoformat(),
        "method": run.method, "pay_by": run.pay_by, "period": run.period, "total": money_json(run.total), "tips": run.tip_count,
        "status": run.status, "notes": run.notes, "paid_method": run.paid_method,
        "created_by": names.get(run.created_by or ""), "approved_by": names.get(run.approved_by or ""),
        "shares": [
            {
                "user_id": s.user_id, "name": names.get(s.user_id), "amount": money_json(s.amount),
                "hours": round(float(s.basis or 0) / 60, 2) if run.method == "hours" else None,
                "status": s.status, "on_payroll": bool(s.payroll_run_id),
            }
            for s in sorted(await _shares(db, run.id), key=lambda s: -float(s.amount or 0))
        ],
    }


async def list_runs(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(select(m.RestaurantTipRun).where(m.RestaurantTipRun.tenant_id == tenant_id).order_by(m.RestaurantTipRun.created_at.desc()).limit(60))
    ).scalars().all()
    return [await serialize_run(db, r) for r in rows]


async def mine(db: AsyncSession, tenant_id: str, user_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.RestaurantTipShare, m.RestaurantTipRun)
            .join(m.RestaurantTipRun, m.RestaurantTipRun.id == m.RestaurantTipShare.run_id)
            .where(m.RestaurantTipShare.tenant_id == tenant_id, m.RestaurantTipShare.user_id == user_id, m.RestaurantTipRun.status != "cancelled")
            .order_by(m.RestaurantTipRun.date_to.desc())
            .limit(60)
        )
    ).all()
    return [
        {
            "run_number": r.run_number, "date_from": r.date_from.isoformat(), "date_to": r.date_to.isoformat(),
            "amount": money_json(s.amount), "status": "paid" if s.status == "paid" else ("waiting for approval" if r.status == "draft" else "to be paid"),
            "pay_by": r.pay_by, "period": r.period,
        }
        for s, r in rows
    ]


# --- Payroll hooks (called from hrm.create_run / delete_run / approve_run) -----------------


async def take(db: AsyncSession, employee_id: str, period: str, payroll_run_id: str) -> Decimal:
    rows = (
        await db.execute(
            select(m.RestaurantTipShare)
            .join(m.RestaurantTipRun, m.RestaurantTipRun.id == m.RestaurantTipShare.run_id)
            .where(
                m.RestaurantTipShare.employee_id == employee_id, m.RestaurantTipShare.payroll_run_id.is_(None),
                m.RestaurantTipShare.status == "pending", m.RestaurantTipRun.status == "approved",
                m.RestaurantTipRun.pay_by == "payroll", m.RestaurantTipRun.period == period,
            )
        )
    ).scalars().all()
    total = ZERO
    for share in rows:
        share.payroll_run_id = payroll_run_id
        total += D(share.amount)
    return total


async def release(db: AsyncSession, payroll_run_id: str) -> None:
    for share in (await db.execute(select(m.RestaurantTipShare).where(m.RestaurantTipShare.payroll_run_id == payroll_run_id))).scalars():
        if share.status == "pending":
            share.payroll_run_id = None


async def settle(db: AsyncSession, payroll_run_id: str) -> None:
    run_ids = set()
    for share in (await db.execute(select(m.RestaurantTipShare).where(m.RestaurantTipShare.payroll_run_id == payroll_run_id))).scalars():
        share.status = "paid"
        run_ids.add(share.run_id)
    await db.flush()
    for run_id in run_ids:
        waiting = (
            await db.execute(
                select(func.count()).select_from(m.RestaurantTipShare).where(
                    m.RestaurantTipShare.run_id == run_id, m.RestaurantTipShare.status == "pending"
                )
            )
        ).scalar_one()
        if not waiting:
            run = await db.get(m.RestaurantTipRun, run_id)
            run.status, run.paid_at, run.paid_method = "paid", datetime.utcnow(), "payroll"
