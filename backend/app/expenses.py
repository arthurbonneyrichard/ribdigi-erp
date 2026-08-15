"""Expense categories, approval workflow, and recurring expenses."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.doc_numbers import next_expense_number

DEFAULT_CATEGORIES = [
    ("RENT", "Rent"),
    ("UTIL", "Utilities"),
    ("SAL", "Salaries"),
    ("TRANS", "Transportation"),
    ("MKT", "Marketing"),
    ("SUP", "Supplies"),
    ("MISC", "Miscellaneous"),
]

DEFAULT_APPROVAL_THRESHOLD = 100.0
DEFAULT_L2_THRESHOLD = 1000.0
L2_ROLES = frozenset({"company_admin", "super_admin"})
MAX_APPROVAL_LEVELS = 5
DEFAULT_L1_ROLES = ("store_manager", "accountant", "company_admin", "super_admin")


def default_approval_levels(
    *,
    auto_threshold: float = DEFAULT_APPROVAL_THRESHOLD,
    l2_threshold: float = DEFAULT_L2_THRESHOLD,
) -> list[dict]:
    auto_t = float(auto_threshold)
    l2_t = max(float(l2_threshold), auto_t)
    return [
        {
            "step": 1,
            "min_amount": auto_t,
            "roles": list(DEFAULT_L1_ROLES),
            "label": "Manager / accountant",
        },
        {
            "step": 2,
            "min_amount": l2_t,
            "roles": sorted(L2_ROLES),
            "label": "Company admin",
        },
    ]


def normalize_approval_matrix(raw: dict | list | None) -> list[dict]:
    """Validate/normalize levels. Raises HTTPException on bad input."""
    from app.rbac import VALID_ROLES

    if raw is None:
        return default_approval_levels()
    if isinstance(raw, dict):
        levels_in = raw.get("levels")
    else:
        levels_in = raw
    if not isinstance(levels_in, list) or not levels_in:
        raise HTTPException(status_code=400, detail="approval matrix levels must be a non-empty list")
    if len(levels_in) > MAX_APPROVAL_LEVELS:
        raise HTTPException(
            status_code=400,
            detail=f"at most {MAX_APPROVAL_LEVELS} approval levels allowed",
        )

    levels: list[dict] = []
    prev_min: float | None = None
    for i, item in enumerate(levels_in):
        if not isinstance(item, dict):
            raise HTTPException(status_code=400, detail=f"level {i + 1} must be an object")
        try:
            min_amount = float(item.get("min_amount"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"level {i + 1} min_amount is required") from None
        if min_amount <= 0:
            raise HTTPException(status_code=400, detail=f"level {i + 1} min_amount must be positive")
        if prev_min is not None and min_amount <= prev_min:
            raise HTTPException(
                status_code=400,
                detail="level min_amount values must be strictly increasing",
            )
        roles_raw = item.get("roles") or []
        if not isinstance(roles_raw, list) or not roles_raw:
            raise HTTPException(status_code=400, detail=f"level {i + 1} roles must be a non-empty list")
        roles: list[str] = []
        for r in roles_raw:
            role = str(r or "").strip()
            if not role:
                continue
            if role not in VALID_ROLES:
                raise HTTPException(status_code=400, detail=f"unknown role '{role}' in level {i + 1}")
            if role not in roles:
                roles.append(role)
        if not roles:
            raise HTTPException(status_code=400, detail=f"level {i + 1} roles must be a non-empty list")
        label = str(item.get("label") or f"Level {i + 1}").strip() or f"Level {i + 1}"
        levels.append(
            {
                "step": i + 1,
                "min_amount": round(min_amount, 2),
                "roles": roles,
                "label": label,
            }
        )
        prev_min = min_amount
    return levels


def matrix_payload(levels: list[dict]) -> dict:
    return {"levels": levels}


def steps_required_from_matrix(amount: float, levels: list[dict]) -> int:
    """Count levels whose min_amount the expense exceeds (0 = auto-approve)."""
    amt = float(amount)
    return sum(1 for lvl in levels if amt > float(lvl["min_amount"]))


def requires_approval(amount: float, threshold: float) -> bool:
    return float(amount) > float(threshold)


def steps_required_for_amount(amount: float, *, auto_threshold: float, l2_threshold: float) -> int:
    """Legacy 2-threshold helper (kept for tests / back-compat)."""
    levels = default_approval_levels(auto_threshold=auto_threshold, l2_threshold=l2_threshold)
    return steps_required_from_matrix(amount, levels)


def roles_for_step(levels: list[dict], step: int) -> list[str]:
    for lvl in levels:
        if int(lvl["step"]) == int(step):
            return list(lvl["roles"])
    return []


def assert_actor_may_act(*, levels: list[dict], step: int, actor_role: str | None) -> None:
    role = (actor_role or "").strip()
    allowed = roles_for_step(levels, step)
    if not allowed:
        raise HTTPException(status_code=400, detail=f"No approval level configured for step {step}")
    if role not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Level-{step} approval requires one of: {', '.join(allowed)}",
        )


def next_run_date(from_dt: datetime, frequency: str) -> datetime:
    freq = (frequency or "monthly").lower()
    if freq == "daily":
        return from_dt + timedelta(days=1)
    if freq == "weekly":
        return from_dt + timedelta(weeks=1)
    if freq == "yearly":
        return from_dt + timedelta(days=365)
    return from_dt + timedelta(days=30)


RECURRING_FREQUENCIES = frozenset({"daily", "weekly", "monthly", "yearly"})


def serialize_recurring(row: m.RecurringExpense) -> dict:
    return {
        "id": row.id,
        "category": row.category,
        "category_id": row.category_id,
        "description": row.description,
        "amount": float(row.amount),
        "frequency": row.frequency,
        "payment_method": row.payment_method,
        "payee": row.payee,
        "branch_id": getattr(row, "branch_id", None),
        "department_id": getattr(row, "department_id", None),
        "start_date": row.start_date,
        "end_date": row.end_date,
        "next_run_at": row.next_run_at,
        "is_active": row.is_active,
        "created_by": row.created_by,
        "created_at": row.created_at,
    }


async def ensure_default_categories(db: AsyncSession, tenant_id: str) -> None:
    existing = {
        c.code
        for c in (
            await db.execute(select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tenant_id))
        ).scalars().all()
    }
    for code, name in DEFAULT_CATEGORIES:
        if code not in existing:
            db.add(m.ExpenseCategory(tenant_id=tenant_id, code=code, name=name, budget_amount=0))
    await db.flush()


def scale_monthly_budget(budget_monthly: float, period_days: int) -> float:
    """Scale a monthly category budget to an arbitrary reporting window (AI + reports)."""
    days = max(1, int(period_days))
    return float(budget_monthly or 0) * (days / 30.0)


def serialize_category(cat: m.ExpenseCategory, account: m.Account | None = None) -> dict:
    return {
        "id": cat.id,
        "code": cat.code,
        "name": cat.name,
        "budget_amount": float(cat.budget_amount or 0),
        "is_active": bool(cat.is_active),
        "account_id": getattr(cat, "account_id", None),
        "account_code": account.code if account else None,
        "account_name": account.name if account else None,
    }


async def resolve_expense_category_account(
    db: AsyncSession, tenant_id: str, account_id: str | None
) -> m.Account | None:
    """Validate optional GL link: must be a tenant expense-type account."""
    from app.accounting import assert_account_active

    if not account_id:
        return None
    account = (
        await db.execute(
            select(m.Account).where(
                m.Account.id == account_id,
                m.Account.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if (account.account_type or "").lower() != "expense":
        raise HTTPException(
            status_code=400,
            detail="Expense category GL must be an expense-type account",
        )
    assert_account_active(account)
    return account


async def get_category(
    db: AsyncSession, tenant_id: str, category_id: str
) -> m.ExpenseCategory:
    cat = (
        await db.execute(
            select(m.ExpenseCategory).where(
                m.ExpenseCategory.id == category_id,
                m.ExpenseCategory.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Expense category not found")
    return cat


async def update_category(
    db: AsyncSession,
    tenant_id: str,
    category_id: str,
    *,
    name: str | None = None,
    budget_amount: float | None = None,
    is_active: bool | None = None,
    account_id: str | None = None,
    clear_account: bool = False,
) -> m.ExpenseCategory:
    cat = await get_category(db, tenant_id, category_id)
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        cat.name = cleaned
    if budget_amount is not None:
        cat.budget_amount = float(budget_amount)
    if is_active is not None:
        cat.is_active = bool(is_active)
    if clear_account:
        cat.account_id = None
    elif account_id is not None:
        account = await resolve_expense_category_account(db, tenant_id, account_id)
        cat.account_id = account.id if account else None
    await db.flush()
    return cat


def resolve_tenant_levels(tenant: m.Tenant) -> list[dict]:
    raw = getattr(tenant, "expense_approval_matrix", None)
    if raw:
        try:
            return normalize_approval_matrix(raw)
        except HTTPException:
            pass
    auto_t = float(tenant.expense_approval_threshold or DEFAULT_APPROVAL_THRESHOLD)
    l2_t = float(getattr(tenant, "expense_l2_threshold", None) or DEFAULT_L2_THRESHOLD)
    return default_approval_levels(auto_threshold=auto_t, l2_threshold=l2_t)


def settings_from_levels(levels: list[dict]) -> dict:
    auto_t = float(levels[0]["min_amount"]) if levels else DEFAULT_APPROVAL_THRESHOLD
    l2_t = float(levels[1]["min_amount"]) if len(levels) > 1 else max(DEFAULT_L2_THRESHOLD, auto_t)
    return {
        "expense_approval_threshold": auto_t,
        "expense_l2_threshold": l2_t,
        "levels": levels,
        "max_levels": MAX_APPROVAL_LEVELS,
    }


async def get_approval_threshold(db: AsyncSession, tenant_id: str) -> float:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    levels = resolve_tenant_levels(tenant)
    return float(levels[0]["min_amount"]) if levels else DEFAULT_APPROVAL_THRESHOLD


async def get_l2_threshold(db: AsyncSession, tenant_id: str) -> float:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    levels = resolve_tenant_levels(tenant)
    if len(levels) > 1:
        return float(levels[1]["min_amount"])
    return float(getattr(tenant, "expense_l2_threshold", None) or DEFAULT_L2_THRESHOLD)


async def get_approval_settings(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return settings_from_levels(resolve_tenant_levels(tenant))


async def update_approval_settings(
    db: AsyncSession,
    tenant: m.Tenant,
    *,
    expense_approval_threshold: float | None = None,
    expense_l2_threshold: float | None = None,
    levels: list[dict] | None = None,
) -> dict:
    if levels is not None:
        normalized = normalize_approval_matrix({"levels": levels})
    else:
        auto_t = float(
            expense_approval_threshold
            if expense_approval_threshold is not None
            else (tenant.expense_approval_threshold or DEFAULT_APPROVAL_THRESHOLD)
        )
        l2_t = float(
            expense_l2_threshold
            if expense_l2_threshold is not None
            else (getattr(tenant, "expense_l2_threshold", None) or DEFAULT_L2_THRESHOLD)
        )
        if l2_t < auto_t:
            raise HTTPException(
                status_code=400,
                detail="expense_l2_threshold must be >= expense_approval_threshold",
            )
        # Preserve custom roles from existing matrix when only thresholds change
        existing = resolve_tenant_levels(tenant)
        if len(existing) >= 2:
            normalized = [
                {**existing[0], "min_amount": round(auto_t, 2), "step": 1},
                {**existing[1], "min_amount": round(l2_t, 2), "step": 2},
                *[{**lvl, "step": i + 3} for i, lvl in enumerate(existing[2:])],
            ]
            # Re-validate increasing mins if extra levels exist
            try:
                normalized = normalize_approval_matrix({"levels": normalized})
            except HTTPException:
                normalized = default_approval_levels(auto_threshold=auto_t, l2_threshold=l2_t)
        else:
            normalized = default_approval_levels(auto_threshold=auto_t, l2_threshold=l2_t)

    tenant.expense_approval_matrix = matrix_payload(normalized)
    tenant.expense_approval_threshold = float(normalized[0]["min_amount"])
    tenant.expense_l2_threshold = float(
        normalized[1]["min_amount"] if len(normalized) > 1 else normalized[0]["min_amount"]
    )
    await db.flush()
    return settings_from_levels(normalized)


async def list_approval_actions(
    db: AsyncSession, tenant_id: str, expense_id: str
) -> list[m.ExpenseApprovalAction]:
    return list(
        (
            await db.execute(
                select(m.ExpenseApprovalAction)
                .where(
                    m.ExpenseApprovalAction.tenant_id == tenant_id,
                    m.ExpenseApprovalAction.expense_id == expense_id,
                )
                .order_by(m.ExpenseApprovalAction.created_at.asc())
            )
        )
        .scalars()
        .all()
    )


def serialize_approval_action(row: m.ExpenseApprovalAction) -> dict:
    return {
        "id": row.id,
        "expense_id": row.expense_id,
        "step": int(row.step),
        "action": row.action,
        "actor_id": row.actor_id,
        "comment": row.comment,
        "created_at": row.created_at,
    }


def serialize_expense(expense: m.Expense, actions: list[m.ExpenseApprovalAction] | None = None) -> dict:
    step = int(getattr(expense, "approval_step", 1) or 1)
    required = int(getattr(expense, "approval_steps_required", 1) or 1)
    return {
        "id": expense.id,
        "category_id": expense.category_id,
        "category": expense.category,
        "description": expense.description,
        "amount": float(expense.amount),
        "expense_date": expense.expense_date,
        "payment_method": expense.payment_method,
        "liquid_account_id": getattr(expense, "liquid_account_id", None),
        "reference": expense.reference,
        "payee": expense.payee,
        "store_id": expense.store_id,
        "branch_id": getattr(expense, "branch_id", None),
        "department_id": getattr(expense, "department_id", None),
        "status": expense.status,
        "created_by": expense.created_by,
        "approved_by": expense.approved_by,
        "approved_at": expense.approved_at,
        "rejection_reason": expense.rejection_reason,
        "approval_comment": expense.approval_comment,
        "attachment_url": expense.attachment_url,
        "has_attachment": bool(expense.attachment_url),
        "approval_step": step,
        "approval_steps_required": required,
        "awaiting_level": step if expense.status == "pending" else None,
        "approval_actions": [serialize_approval_action(a) for a in (actions or [])],
        "created_at": expense.created_at,
    }


async def serialize_expense_full(db: AsyncSession, expense: m.Expense) -> dict:
    actions = await list_approval_actions(db, expense.tenant_id, expense.id)
    data = serialize_expense(expense, actions)
    if expense.status == "pending":
        settings = await get_approval_settings(db, expense.tenant_id)
        data["awaiting_roles"] = roles_for_step(settings["levels"], int(expense.approval_step or 1))
    else:
        data["awaiting_roles"] = []
    return data


async def resolve_category(
    db: AsyncSession,
    tenant_id: str,
    *,
    category_id: str | None,
    category: str | None,
) -> tuple[str | None, str]:
    if category_id:
        cat = (
            await db.execute(
                select(m.ExpenseCategory).where(
                    m.ExpenseCategory.id == category_id,
                    m.ExpenseCategory.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if not cat:
            raise HTTPException(status_code=404, detail="Expense category not found")
        if not bool(cat.is_active):
            raise HTTPException(status_code=400, detail="Expense category is inactive")
        return cat.id, cat.name
    name = (category or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="category or category_id is required")
    return None, name


async def get_expense(db: AsyncSession, tenant_id: str, expense_id: str) -> m.Expense:
    expense = (
        await db.execute(
            select(m.Expense).where(
                m.Expense.id == expense_id,
                m.Expense.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


async def _record_action(
    db: AsyncSession,
    *,
    tenant_id: str,
    expense_id: str,
    step: int,
    action: str,
    actor_id: str | None,
    comment: str | None = None,
) -> None:
    db.add(
        m.ExpenseApprovalAction(
            tenant_id=tenant_id,
            expense_id=expense_id,
            step=step,
            action=action,
            actor_id=actor_id,
            comment=comment,
        )
    )


async def _resolve_expense_store(
    db: AsyncSession,
    tenant_id: str,
    store_id: str | None,
    *,
    branch_id: str | None = None,
) -> str | None:
    """Validate optional store; optionally ensure it belongs to the selected branch."""
    if not store_id:
        return None
    from app import stores as stores_svc

    store = await stores_svc.require_active_store(db, tenant_id, store_id)
    if branch_id and store.branch_id and store.branch_id != branch_id:
        raise HTTPException(
            status_code=400,
            detail="Store does not belong to the selected branch",
        )
    return store.id


async def create_expense(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    amount: float,
    description: str = "",
    category_id: str | None = None,
    category: str | None = None,
    payment_method: str = "cash",
    liquid_account_id: str | None = None,
    reference: str | None = None,
    payee: str | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
    department_id: str | None = None,
    expense_date: datetime | None = None,
) -> m.Expense:
    await ensure_default_categories(db, tenant_id)
    cat_id, cat_name = await resolve_category(
        db, tenant_id, category_id=category_id, category=category
    )
    from app import org_units as org_units_svc

    resolved_branch, resolved_dept = await org_units_svc.assert_user_org_assignment(
        db,
        tenant_id,
        branch_id=branch_id,
        department_id=department_id,
    )
    resolved_store = await _resolve_expense_store(
        db, tenant_id, store_id, branch_id=resolved_branch
    )
    settings = await get_approval_settings(db, tenant_id)
    levels = settings["levels"]
    auto_t = settings["expense_approval_threshold"]
    steps = steps_required_from_matrix(amount, levels)
    needs_approval = steps > 0

    if liquid_account_id:
        from app.accounting import resolve_settlement_gl

        await resolve_settlement_gl(
            db,
            tenant_id,
            payment_method or "cash",
            liquid_account_id=liquid_account_id,
            outflow=True,
        )

    ref = (reference or "").strip() or None
    if not ref:
        ref = await next_expense_number(db, tenant_id)

    expense = m.Expense(
        tenant_id=tenant_id,
        category_id=cat_id,
        category=cat_name,
        description=description or "",
        amount=round(float(amount), 2),
        expense_date=expense_date or datetime.utcnow(),
        payment_method=payment_method or "cash",
        liquid_account_id=liquid_account_id,
        reference=ref,
        payee=payee,
        store_id=resolved_store,
        branch_id=resolved_branch,
        department_id=resolved_dept,
        status="pending" if needs_approval else "approved",
        created_by=user_id,
        approved_by=None if needs_approval else user_id,
        approved_at=None if needs_approval else datetime.utcnow(),
        approval_comment=None if needs_approval else "Auto-approved under threshold",
        approval_step=1 if needs_approval else 0,
        approval_steps_required=steps if needs_approval else 0,
    )
    db.add(expense)
    await db.flush()

    if needs_approval:
        from app.notifications import create_notification

        await create_notification(
            db,
            tenant_id=tenant_id,
            category="expense_approval",
            title="Expense Approval Required",
            message=(
                f"Expense {cat_name} of {expense.amount:.2f} exceeds approval threshold "
                f"({auto_t:.2f}) and awaits level-1 review"
                + (f" (of {steps} levels)." if steps > 1 else ".")
            ),
            entity_type="expense",
            entity_id=expense.id,
            roles=roles_for_step(levels, 1),
            exclude_user_ids={user_id} if user_id else None,
        )
    else:
        await _record_action(
            db,
            tenant_id=tenant_id,
            expense_id=expense.id,
            step=0,
            action="auto_approve",
            actor_id=user_id,
            comment="Auto-approved under threshold",
        )
        from app.accounting import post_expense_journal

        await post_expense_journal(db, tenant_id=tenant_id, user_id=user_id, expense=expense)
    return expense


async def approve_expense(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    expense_id: str,
    comment: str | None = None,
    actor_role: str | None = None,
) -> m.Expense:
    expense = await get_expense(db, tenant_id, expense_id)
    if expense.status == "approved":
        raise HTTPException(status_code=409, detail="Expense already approved")
    if expense.status == "rejected":
        raise HTTPException(status_code=409, detail="Rejected expenses cannot be approved")
    if expense.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending expenses can be approved")

    if expense.created_by and expense.created_by == user_id and (actor_role or "") not in {
        "super_admin",
    }:
        raise HTTPException(status_code=403, detail="Cannot approve your own expense")

    step = int(expense.approval_step or 1)
    required = int(expense.approval_steps_required or 1)
    settings = await get_approval_settings(db, tenant_id)
    assert_actor_may_act(levels=settings["levels"], step=step, actor_role=actor_role)

    # Same actor cannot approve consecutive steps
    prior = await list_approval_actions(db, tenant_id, expense.id)
    if any(a.action == "approve" and a.actor_id == user_id for a in prior):
        raise HTTPException(status_code=403, detail="You already approved an earlier step on this expense")

    await _record_action(
        db,
        tenant_id=tenant_id,
        expense_id=expense.id,
        step=step,
        action="approve",
        actor_id=user_id,
        comment=comment,
    )

    if step < required:
        expense.approval_step = step + 1
        expense.approval_comment = comment or f"Level {step} approved; awaiting level {step + 1}"
        from app.notifications import create_notification

        next_step = step + 1
        await create_notification(
            db,
            tenant_id=tenant_id,
            category="expense_approval",
            title="Expense Needs Next-Level Approval",
            message=(
                f"Expense {expense.category} of {float(expense.amount):.2f} passed level {step} "
                f"and awaits level {next_step} approval."
            ),
            entity_type="expense",
            entity_id=expense.id,
            roles=roles_for_step(settings["levels"], next_step),
            exclude_user_ids={user_id, expense.created_by} - {None},
        )
        await db.flush()
        return expense

    expense.status = "approved"
    expense.approved_by = user_id
    expense.approved_at = datetime.utcnow()
    expense.approval_comment = comment
    expense.rejection_reason = None
    expense.approval_step = required

    from app.accounting import post_expense_journal

    await post_expense_journal(db, tenant_id=tenant_id, user_id=user_id, expense=expense)
    await db.flush()
    return expense


async def reject_expense(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    expense_id: str,
    reason: str,
    actor_role: str | None = None,
) -> m.Expense:
    if not (reason or "").strip():
        raise HTTPException(status_code=400, detail="rejection reason is required")
    expense = await get_expense(db, tenant_id, expense_id)
    if expense.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending expenses can be rejected")

    step = int(expense.approval_step or 1)
    settings = await get_approval_settings(db, tenant_id)
    assert_actor_may_act(levels=settings["levels"], step=step, actor_role=actor_role)

    await _record_action(
        db,
        tenant_id=tenant_id,
        expense_id=expense.id,
        step=step,
        action="reject",
        actor_id=user_id,
        comment=reason.strip(),
    )

    expense.status = "rejected"
    expense.approved_by = user_id
    expense.approved_at = datetime.utcnow()
    expense.rejection_reason = reason.strip()
    await db.flush()
    return expense


async def update_expense(
    db: AsyncSession,
    *,
    tenant_id: str,
    expense_id: str,
    user_id: str,
    amount: float | None = None,
    description: str | None = None,
    payee: str | None = None,
    reference: str | None = None,
    expense_date: datetime | None = None,
    payment_method: str | None = None,
    category_id: str | None = None,
    category: str | None = None,
    store_id: str | None = None,
    branch_id: str | None = None,
    department_id: str | None = None,
    clear_store: bool = False,
    clear_branch: bool = False,
    clear_department: bool = False,
) -> m.Expense:
    """Update editable fields on a pending (or rejected) expense. Does not auto-apply OCR."""
    expense = await get_expense(db, tenant_id, expense_id)
    if expense.status == "approved":
        raise HTTPException(status_code=409, detail="Approved expenses cannot be edited")
    if expense.status not in {"pending", "rejected"}:
        raise HTTPException(status_code=409, detail="Only pending or rejected expenses can be edited")

    org_touch = (
        clear_store
        or clear_branch
        or clear_department
        or store_id is not None
        or branch_id is not None
        or department_id is not None
    )
    provided = any(
        x is not None
        for x in (amount, description, payee, reference, expense_date, payment_method, category_id, category)
    ) or org_touch
    if not provided:
        raise HTTPException(status_code=400, detail="No expense fields provided")

    prior = await list_approval_actions(db, tenant_id, expense.id)
    has_human_approve = any(a.action == "approve" for a in prior)
    if amount is not None and has_human_approve:
        raise HTTPException(
            status_code=409,
            detail="Cannot change amount after an approval step has been recorded",
        )

    if category_id is not None or category is not None:
        cat_id, cat_name = await resolve_category(
            db, tenant_id, category_id=category_id, category=category
        )
        expense.category_id = cat_id
        expense.category = cat_name

    if description is not None:
        expense.description = description
    if payee is not None:
        expense.payee = payee.strip() or None
    if reference is not None:
        expense.reference = reference.strip() or None
    if expense_date is not None:
        expense.expense_date = expense_date
    if payment_method is not None:
        expense.payment_method = payment_method.strip() or expense.payment_method

    if org_touch:
        from app import org_units as org_units_svc

        desired_branch = None if clear_branch else (
            branch_id if branch_id is not None else expense.branch_id
        )
        desired_dept = None if clear_department else (
            department_id if department_id is not None else expense.department_id
        )
        resolved_branch, resolved_dept = await org_units_svc.assert_user_org_assignment(
            db,
            tenant_id,
            branch_id=desired_branch,
            department_id=desired_dept,
        )
        expense.branch_id = resolved_branch
        expense.department_id = resolved_dept
        if clear_store:
            expense.store_id = None
        elif store_id is not None:
            expense.store_id = await _resolve_expense_store(
                db, tenant_id, store_id, branch_id=resolved_branch
            )
        elif resolved_branch and expense.store_id:
            # Re-validate existing store if branch changed
            expense.store_id = await _resolve_expense_store(
                db, tenant_id, expense.store_id, branch_id=resolved_branch
            )

    if amount is not None:
        new_amount = round(float(amount), 2)
        if new_amount <= 0:
            raise HTTPException(status_code=400, detail="amount must be positive")
        expense.amount = new_amount
        if expense.status == "pending":
            settings = await get_approval_settings(db, tenant_id)
            steps = steps_required_from_matrix(new_amount, settings["levels"])
            if steps == 0:
                expense.status = "approved"
                expense.approved_by = user_id
                expense.approved_at = datetime.utcnow()
                expense.approval_comment = "Auto-approved under threshold after edit"
                expense.approval_step = 0
                expense.approval_steps_required = 0
                expense.rejection_reason = None
                await _record_action(
                    db,
                    tenant_id=tenant_id,
                    expense_id=expense.id,
                    step=0,
                    action="auto_approve",
                    actor_id=user_id,
                    comment="Auto-approved under threshold after edit",
                )
                from app.accounting import post_expense_journal

                await post_expense_journal(db, tenant_id=tenant_id, user_id=user_id, expense=expense)
            else:
                expense.approval_steps_required = steps
                expense.approval_step = 1
                expense.rejection_reason = None
        elif expense.status == "rejected":
            # Re-open for approval with new amount
            settings = await get_approval_settings(db, tenant_id)
            steps = steps_required_from_matrix(new_amount, settings["levels"])
            if steps == 0:
                expense.status = "approved"
                expense.approved_by = user_id
                expense.approved_at = datetime.utcnow()
                expense.approval_comment = "Auto-approved under threshold after edit"
                expense.approval_step = 0
                expense.approval_steps_required = 0
                expense.rejection_reason = None
                await _record_action(
                    db,
                    tenant_id=tenant_id,
                    expense_id=expense.id,
                    step=0,
                    action="auto_approve",
                    actor_id=user_id,
                    comment="Auto-approved under threshold after edit",
                )
                from app.accounting import post_expense_journal

                await post_expense_journal(db, tenant_id=tenant_id, user_id=user_id, expense=expense)
            else:
                expense.status = "pending"
                expense.approval_steps_required = steps
                expense.approval_step = 1
                expense.rejection_reason = None
                expense.approved_by = None
                expense.approved_at = None

    await db.flush()
    return expense


async def create_recurring(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    amount: float,
    frequency: str,
    description: str = "",
    category_id: str | None = None,
    category: str | None = None,
    payment_method: str = "bank_transfer",
    payee: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    branch_id: str | None = None,
    department_id: str | None = None,
) -> m.RecurringExpense:
    await ensure_default_categories(db, tenant_id)
    cat_id, cat_name = await resolve_category(
        db, tenant_id, category_id=category_id, category=category
    )
    freq = (frequency or "monthly").strip().lower()
    if freq not in RECURRING_FREQUENCIES:
        raise HTTPException(
            status_code=422,
            detail=f"frequency must be one of: {', '.join(sorted(RECURRING_FREQUENCIES))}",
        )
    from app import org_units as org_units_svc

    resolved_branch, resolved_dept = await org_units_svc.assert_user_org_assignment(
        db,
        tenant_id,
        branch_id=branch_id,
        department_id=department_id,
    )
    start = start_date or datetime.utcnow()
    row = m.RecurringExpense(
        tenant_id=tenant_id,
        category_id=cat_id,
        category=cat_name,
        description=description or "",
        amount=round(float(amount), 2),
        frequency=freq,
        payment_method=payment_method or "bank_transfer",
        payee=payee,
        branch_id=resolved_branch,
        department_id=resolved_dept,
        start_date=start,
        end_date=end_date,
        next_run_at=start,
        is_active=True,
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def set_recurring_active(
    db: AsyncSession,
    *,
    tenant_id: str,
    recurring_id: str,
    is_active: bool,
) -> m.RecurringExpense:
    return await update_recurring(
        db,
        tenant_id=tenant_id,
        recurring_id=recurring_id,
        is_active=is_active,
    )


async def update_recurring(
    db: AsyncSession,
    *,
    tenant_id: str,
    recurring_id: str,
    is_active: bool | None = None,
    amount: float | None = None,
    payee: str | None = None,
    clear_payee: bool = False,
    description: str | None = None,
    payment_method: str | None = None,
    frequency: str | None = None,
    category_id: str | None = None,
    category: str | None = None,
    branch_id: str | None = None,
    department_id: str | None = None,
    clear_branch: bool = False,
    clear_department: bool = False,
) -> m.RecurringExpense:
    """Update recurring schedule template fields and/or active flag (BR-9.5)."""
    row = (
        await db.execute(
            select(m.RecurringExpense).where(
                m.RecurringExpense.id == recurring_id,
                m.RecurringExpense.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Recurring expense not found")

    org_touch = (
        clear_branch
        or clear_department
        or branch_id is not None
        or department_id is not None
    )
    provided = any(
        x is not None
        for x in (
            is_active,
            amount,
            payee,
            description,
            payment_method,
            frequency,
            category_id,
            category,
        )
    ) or clear_payee or org_touch
    if not provided:
        raise HTTPException(status_code=400, detail="No recurring fields to update")

    if category_id is not None or category is not None:
        cat_id, cat_name = await resolve_category(
            db, tenant_id, category_id=category_id, category=category
        )
        row.category_id = cat_id
        row.category = cat_name

    if amount is not None:
        row.amount = round(float(amount), 2)
    if clear_payee:
        row.payee = None
    elif payee is not None:
        row.payee = payee.strip() or None
    if description is not None:
        row.description = description
    if payment_method is not None:
        row.payment_method = payment_method.strip() or row.payment_method
    if frequency is not None:
        freq = frequency.strip().lower()
        if freq not in RECURRING_FREQUENCIES:
            raise HTTPException(
                status_code=422,
                detail=f"frequency must be one of: {', '.join(sorted(RECURRING_FREQUENCIES))}",
            )
        row.frequency = freq

    if org_touch:
        from app import org_units as org_units_svc

        desired_branch = None if clear_branch else (
            branch_id if branch_id is not None else row.branch_id
        )
        desired_dept = None if clear_department else (
            department_id if department_id is not None else row.department_id
        )
        resolved_branch, resolved_dept = await org_units_svc.assert_user_org_assignment(
            db,
            tenant_id,
            branch_id=desired_branch,
            department_id=desired_dept,
        )
        row.branch_id = resolved_branch
        row.department_id = resolved_dept

    if is_active is not None:
        row.is_active = bool(is_active)

    await db.flush()
    return row


async def skip_next_recurring(
    db: AsyncSession,
    *,
    tenant_id: str,
    recurring_id: str,
) -> m.RecurringExpense:
    """Advance next_run_at by one frequency period without creating an expense (BR-9.5)."""
    row = (
        await db.execute(
            select(m.RecurringExpense).where(
                m.RecurringExpense.id == recurring_id,
                m.RecurringExpense.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Recurring expense not found")
    if not row.is_active:
        raise HTTPException(status_code=400, detail="Cannot skip inactive recurring expense")
    base = row.next_run_at or datetime.utcnow()
    new_next = next_run_date(base, row.frequency)
    row.next_run_at = new_next
    if row.end_date and new_next > row.end_date:
        row.is_active = False
    await db.flush()
    return row


async def generate_due_recurring(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
) -> list[m.Expense]:
    now = datetime.utcnow()
    rows = (
        await db.execute(
            select(m.RecurringExpense).where(
                m.RecurringExpense.tenant_id == tenant_id,
                m.RecurringExpense.is_active == True,  # noqa: E712
                m.RecurringExpense.next_run_at <= now,
            )
        )
    ).scalars().all()
    created: list[m.Expense] = []
    for row in rows:
        if row.end_date and row.end_date < now:
            row.is_active = False
            continue
        # Omit reference so create_expense allocates EXP-YYYY-NNNN (BR-9.2 / BR-20.4).
        desc = (row.description or f"Recurring {row.category}").strip()
        if "recurring" not in desc.lower():
            desc = f"{desc} (recurring)" if desc else f"Recurring {row.category}"
        expense = await create_expense(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            amount=float(row.amount),
            description=desc,
            category_id=row.category_id,
            category=row.category,
            payment_method=row.payment_method,
            payee=row.payee,
            reference=None,
            expense_date=now,
            branch_id=getattr(row, "branch_id", None),
            department_id=getattr(row, "department_id", None),
        )
        created.append(expense)
        row.next_run_at = next_run_date(now, row.frequency)
    await db.flush()
    return created
