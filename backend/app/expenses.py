"""Expense categories, approval workflow, and recurring expenses."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

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


def normalize_approval_matrix(
    raw: dict | list | None,
    *,
    known_roles: set[str] | None = None,
) -> list[dict]:
    """Validate/normalize levels. Raises HTTPException on bad input.

    ``known_roles`` may include tenant custom role slugs (system roles always allowed).
    """
    from app.rbac import VALID_ROLES
    from app.roles import SLUG_RE

    allowed = set(VALID_ROLES) | set(known_roles or ())

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
            # System roles, known custom roles, or well-formed custom slugs.
            if role not in allowed and not SLUG_RE.fullmatch(role):
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


async def notify_expense_approvers(
    db: AsyncSession,
    *,
    tenant_id: str,
    expense: m.Expense,
    step: int,
    title: str,
    message: str,
    exclude_user_ids: set[str] | frozenset[str] | None = None,
) -> int:
    """Dashboard + email (default on) to active users whose role can act at this step."""
    settings = await get_approval_settings(db, tenant_id)
    roles = roles_for_step(settings["levels"], step)
    if not roles:
        return 0
    exclude = set(exclude_user_ids or ())
    users = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == tenant_id,
                m.User.is_active == True,  # noqa: E712
                m.User.role.in_(list(roles)),
            )
        )
    ).scalars().all()
    from app.notifications import create_notification

    notified = 0
    for user in users:
        if user.id in exclude:
            continue
        note = await create_notification(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            category="expense_approval",
            title=title,
            message=message,
            entity_type="expense",
            entity_id=expense.id,
            company_id=getattr(expense, "company_id", None),
        )
        if note is not None:
            notified += 1
    return notified


def next_run_date(from_dt: datetime, frequency: str) -> datetime:
    freq = (frequency or "monthly").lower()
    if freq == "daily":
        return from_dt + timedelta(days=1)
    if freq == "weekly":
        return from_dt + timedelta(weeks=1)
    if freq == "yearly":
        return from_dt + timedelta(days=365)
    return from_dt + timedelta(days=30)


async def ensure_default_categories(
    db: AsyncSession, tenant_id: str, company_id: str | None = None
) -> None:
    q = select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tenant_id)
    if company_id:
        q = q.where(m.ExpenseCategory.company_id == company_id)
    existing = {
        c.code
        for c in (await db.execute(q)).scalars().all()
    }
    for code, name in DEFAULT_CATEGORIES:
        if code not in existing:
            db.add(
                m.ExpenseCategory(
                    tenant_id=tenant_id,
                    company_id=company_id,
                    code=code,
                    name=name,
                    budget_amount=0,
                )
            )
    await db.flush()


async def resolve_expense_gl_account(
    db: AsyncSession, *, tenant_id: str, account_id: str | None
) -> m.Account | None:
    """Validate optional category GL account (must be tenant expense-type, active)."""
    if not account_id:
        return None
    from app.accounting import get_tenant_account

    account = await get_tenant_account(db, tenant_id, account_id)
    if (account.account_type or "").strip().lower() != "expense":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_EXPENSE_ACCOUNT",
                "message": "Expense category account must be an expense-type COA account",
                "account_id": account_id,
                "account_type": account.account_type,
            },
        )
    if not bool(account.is_active):
        raise HTTPException(status_code=400, detail="Expense category account is inactive")
    return account


def serialize_category(cat: m.ExpenseCategory, account: m.Account | None = None) -> dict:
    out = {
        "id": cat.id,
        "company_id": getattr(cat, "company_id", None),
        "code": cat.code,
        "name": cat.name,
        "budget_amount": float(cat.budget_amount or 0),
        "account_id": cat.account_id,
        "is_active": bool(cat.is_active),
    }
    if account is not None:
        out["account_code"] = account.code
        out["account_name"] = account.name
    return out


async def serialize_category_rich(
    db: AsyncSession, tenant_id: str, cat: m.ExpenseCategory
) -> dict:
    account = None
    if cat.account_id:
        account = (
            await db.execute(
                select(m.Account).where(
                    m.Account.id == cat.account_id,
                    m.Account.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
    return serialize_category(cat, account=account)


async def update_category(
    db: AsyncSession,
    *,
    tenant_id: str,
    category_id: str,
    name: str | None = None,
    budget_amount: float | None = None,
    is_active: bool | None = None,
    account_id: str | None = None,
    clear_account: bool = False,
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
    if name is not None:
        name_norm = name.strip()
        if not name_norm:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        cat.name = name_norm
    if budget_amount is not None:
        if float(budget_amount) < 0:
            raise HTTPException(status_code=400, detail="budget_amount cannot be negative")
        cat.budget_amount = round(float(budget_amount), 2)
    if is_active is not None:
        cat.is_active = bool(is_active)
    if clear_account:
        cat.account_id = None
    elif account_id is not None:
        account = await resolve_expense_gl_account(
            db, tenant_id=tenant_id, account_id=account_id
        )
        cat.account_id = account.id if account else None
    await db.flush()
    return cat


async def category_budget_variance(
    db: AsyncSession,
    tenant_id: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    company_id: str | None = None,
) -> dict:
    """Budget vs approved spend by category for a period (defaults to current month)."""
    from app.reports import apply_company_filter

    await ensure_default_categories(db, tenant_id, company_id=company_id)
    now = datetime.utcnow()
    start = from_date or datetime(now.year, now.month, 1)
    if to_date is None:
        if now.month == 12:
            end = datetime(now.year, 12, 31, 23, 59, 59)
        else:
            end = datetime(now.year, now.month + 1, 1) - timedelta(seconds=1)
    else:
        end = to_date

    cat_stmt = (
        select(m.ExpenseCategory)
        .where(m.ExpenseCategory.tenant_id == tenant_id)
        .order_by(m.ExpenseCategory.name)
    )
    cat_stmt = apply_company_filter(cat_stmt, m.ExpenseCategory.company_id, company_id)
    cats = (await db.execute(cat_stmt)).scalars().all()

    exp_stmt = select(m.Expense).where(
        m.Expense.tenant_id == tenant_id,
        m.Expense.expense_date >= start,
        m.Expense.expense_date <= end,
        m.Expense.status.in_(["approved", "pending"]),
    )
    exp_stmt = apply_company_filter(exp_stmt, m.Expense.company_id, company_id)
    expenses = (await db.execute(exp_stmt)).scalars().all()

    spent_by: dict[str, float] = {}
    pending_by: dict[str, float] = {}
    for e in expenses:
        key = e.category_id or f"name:{e.category or 'Uncategorized'}"
        amt = float(e.amount or 0)
        if e.status == "approved":
            spent_by[key] = spent_by.get(key, 0) + amt
        else:
            pending_by[key] = pending_by.get(key, 0) + amt

    rows = []
    total_budget = 0.0
    total_spent = 0.0
    total_pending = 0.0
    for cat in cats:
        budget = float(cat.budget_amount or 0)
        spent = round(spent_by.get(cat.id, 0), 2)
        pending = round(pending_by.get(cat.id, 0), 2)
        variance = round(budget - spent, 2)
        util = round((spent / budget) * 100, 2) if budget > 0 else None
        rows.append(
            {
                **serialize_category(cat),
                "spent": spent,
                "pending": pending,
                "variance": variance,
                "utilization_pct": util,
                "over_budget": bool(budget > 0 and spent > budget),
            }
        )
        total_budget += budget
        total_spent += spent
        total_pending += pending

    return {
        "from_date": start,
        "to_date": end,
        "categories": rows,
        "totals": {
            "budget_amount": round(total_budget, 2),
            "spent": round(total_spent, 2),
            "pending": round(total_pending, 2),
            "variance": round(total_budget - total_spent, 2),
        },
    }


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
        "company_id": getattr(row, "company_id", None),
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
        "company_id": getattr(expense, "company_id", None),
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
    company_id: str | None = None,
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
        from app.workspace import assert_fk_company

        assert_fk_company(cat, company_id, detail="Expense category not found")
        return cat.id, cat.name
    name = (category or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="category or category_id is required")
    return None, name


async def resolve_org_dimensions(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str | None,
    department_id: str | None,
    company_id: str | None = None,
) -> tuple[str | None, str | None]:
    """Validate optional store/department are tenant/company-scoped (404 on foreign ids)."""
    resolved_store = None
    resolved_dept = None
    if store_id:
        from app.stores import get_store

        store = await get_store(db, tenant_id, store_id, company_id=company_id)
        resolved_store = store.id
    if department_id:
        from app.org_units import get_department

        dept = await get_department(db, tenant_id, department_id)
        if not bool(dept.is_active):
            raise HTTPException(status_code=409, detail="Department is not active")
        resolved_dept = dept.id
    return resolved_store, resolved_dept


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
    expense = await db.get(m.Expense, expense_id)
    db.add(
        m.ExpenseApprovalAction(
            tenant_id=tenant_id,
            company_id=getattr(expense, "company_id", None) if expense else None,
            expense_id=expense_id,
            step=step,
            action=action,
            actor_id=actor_id,
            comment=comment,
        )
    )


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
    department_id: str | None = None,
    expense_date: datetime | None = None,
    company_id: str | None = None,
) -> m.Expense:
    await ensure_default_categories(db, tenant_id, company_id=company_id)
    cat_id, cat_name = await resolve_category(
        db,
        tenant_id,
        category_id=category_id,
        category=category,
        company_id=company_id,
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

    resolved_store, resolved_dept = await resolve_org_dimensions(
        db,
        tenant_id=tenant_id,
        store_id=store_id,
        department_id=department_id,
        company_id=company_id,
    )

    expense = m.Expense(
        tenant_id=tenant_id,
        company_id=company_id,
        category_id=cat_id,
        category=cat_name,
        description=description or "",
        amount=round(float(amount), 2),
        expense_date=expense_date or datetime.utcnow(),
        payment_method=payment_method or "cash",
        liquid_account_id=liquid_account_id,
        reference=reference,
        payee=payee,
        store_id=resolved_store,
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

    from app import audit as audit_svc

    if needs_approval:
        await notify_expense_approvers(
            db,
            tenant_id=tenant_id,
            expense=expense,
            step=1,
            title="Expense Approval Required",
            message=(
                f"Expense {cat_name} of {expense.amount:.2f} exceeds approval threshold "
                f"({auto_t:.2f}) and awaits level-1 review"
                + (f" (of {steps} levels)." if steps > 1 else ".")
            ),
            exclude_user_ids={user_id},
        )
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="expense_submitted",
            entity="expense",
            entity_id=expense.id,
            details={
                "category": cat_name,
                "amount": float(expense.amount),
                "approval_steps_required": steps,
                "threshold": float(auto_t),
            },
            module="expenses",
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
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="expense_auto_approved",
            entity="expense",
            entity_id=expense.id,
            details={
                "category": cat_name,
                "amount": float(expense.amount),
                "threshold": float(auto_t),
                "reason": "under_threshold",
            },
            module="expenses",
        )
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

    from app import audit as audit_svc

    if step < required:
        expense.approval_step = step + 1
        expense.approval_comment = comment or f"Level {step} approved; awaiting level {step + 1}"
        await notify_expense_approvers(
            db,
            tenant_id=tenant_id,
            expense=expense,
            step=step + 1,
            title="Expense Needs Next-Level Approval",
            message=(
                f"Expense {expense.category} of {float(expense.amount):.2f} passed level {step} "
                f"and awaits level {step + 1} approval."
            ),
            exclude_user_ids={user_id, expense.created_by} if expense.created_by else {user_id},
        )
        await audit_svc.record_event(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            action="expense_level_approved",
            entity="expense",
            entity_id=expense.id,
            details={
                "category": expense.category,
                "amount": float(expense.amount),
                "step": step,
                "next_step": step + 1,
                "comment": comment,
            },
            module="expenses",
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
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="expense_approved",
        entity="expense",
        entity_id=expense.id,
        details={
            "category": expense.category,
            "amount": float(expense.amount),
            "steps": required,
            "comment": comment,
        },
        module="expenses",
    )
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
    from app import audit as audit_svc

    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="expense_rejected",
        entity="expense",
        entity_id=expense.id,
        details={
            "category": expense.category,
            "amount": float(expense.amount),
            "reason": expense.rejection_reason,
            "step": step,
        },
        module="expenses",
    )
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
    department_id: str | None = None,
    clear_store: bool = False,
    clear_department: bool = False,
) -> m.Expense:
    """Update editable fields on a pending (or rejected) expense. Does not auto-apply OCR."""
    expense = await get_expense(db, tenant_id, expense_id)
    if expense.status == "approved":
        raise HTTPException(status_code=409, detail="Approved expenses cannot be edited")
    if expense.status not in {"pending", "rejected"}:
        raise HTTPException(status_code=409, detail="Only pending or rejected expenses can be edited")

    provided = any(
        x is not None
        for x in (
            amount,
            description,
            payee,
            reference,
            expense_date,
            payment_method,
            category_id,
            category,
            store_id,
            department_id,
        )
    ) or clear_store or clear_department
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
            db,
            tenant_id,
            category_id=category_id,
            category=category,
            company_id=getattr(expense, "company_id", None),
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

    if clear_store:
        expense.store_id = None
    elif store_id is not None:
        resolved_store, _ = await resolve_org_dimensions(
            db,
            tenant_id=tenant_id,
            store_id=store_id,
            department_id=None,
            company_id=getattr(expense, "company_id", None),
        )
        expense.store_id = resolved_store
    if clear_department:
        expense.department_id = None
    elif department_id is not None:
        _, resolved_dept = await resolve_org_dimensions(
            db,
            tenant_id=tenant_id,
            store_id=None,
            department_id=department_id,
            company_id=getattr(expense, "company_id", None),
        )
        expense.department_id = resolved_dept

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
                from app import audit as audit_svc

                await post_expense_journal(db, tenant_id=tenant_id, user_id=user_id, expense=expense)
                await audit_svc.record_event(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="expense_auto_approved",
                    entity="expense",
                    entity_id=expense.id,
                    details={
                        "category": expense.category,
                        "amount": float(expense.amount),
                        "reason": "under_threshold_after_edit",
                    },
                    module="expenses",
                )
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
                from app import audit as audit_svc

                await post_expense_journal(db, tenant_id=tenant_id, user_id=user_id, expense=expense)
                await audit_svc.record_event(
                    db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    action="expense_auto_approved",
                    entity="expense",
                    entity_id=expense.id,
                    details={
                        "category": expense.category,
                        "amount": float(expense.amount),
                        "reason": "under_threshold_after_edit",
                    },
                    module="expenses",
                )
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
    store_id: str | None = None,
    department_id: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    company_id: str | None = None,
) -> m.RecurringExpense:
    await ensure_default_categories(db, tenant_id, company_id=company_id)
    cat_id, cat_name = await resolve_category(
        db,
        tenant_id,
        category_id=category_id,
        category=category,
        company_id=company_id,
    )
    resolved_store, resolved_dept = await resolve_org_dimensions(
        db,
        tenant_id=tenant_id,
        store_id=store_id,
        department_id=department_id,
        company_id=company_id,
    )
    start = start_date or datetime.utcnow()
    row = m.RecurringExpense(
        tenant_id=tenant_id,
        company_id=company_id,
        category_id=cat_id,
        category=cat_name,
        description=description or "",
        amount=round(float(amount), 2),
        frequency=(frequency or "monthly").lower(),
        payment_method=payment_method or "bank_transfer",
        payee=payee,
        store_id=resolved_store,
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


def serialize_recurring(row: m.RecurringExpense) -> dict:
    return {
        "id": row.id,
        "company_id": getattr(row, "company_id", None),
        "category": row.category,
        "category_id": row.category_id,
        "description": row.description,
        "amount": float(row.amount),
        "frequency": row.frequency,
        "payment_method": row.payment_method,
        "payee": row.payee,
        "store_id": getattr(row, "store_id", None),
        "department_id": getattr(row, "department_id", None),
        "next_run_at": row.next_run_at,
        "end_date": row.end_date,
        "is_active": row.is_active,
        "skip_next": bool(row.skip_next),
        "next_amount": float(row.next_amount) if row.next_amount is not None else None,
        "next_description": row.next_description,
        "last_notified_for": row.last_notified_for,
        "created_at": row.created_at,
    }


async def list_recurring(
    db: AsyncSession,
    tenant_id: str,
    *,
    active_only: bool = False,
    is_active: bool | None = None,
    company_id: str | None = None,
) -> list[m.RecurringExpense]:
    """Stage 125 R1 — is_active / active_only for honest paused-only recurring lists."""
    stmt = select(m.RecurringExpense).where(m.RecurringExpense.tenant_id == tenant_id)
    if company_id:
        stmt = stmt.where(m.RecurringExpense.company_id == company_id)
    if is_active is not None:
        stmt = stmt.where(m.RecurringExpense.is_active.is_(bool(is_active)))
    elif active_only:
        stmt = stmt.where(m.RecurringExpense.is_active.is_(True))
    stmt = stmt.order_by(m.RecurringExpense.created_at.desc())
    return list((await db.execute(stmt)).scalars().all())


def _clear_occurrence_overrides(row: m.RecurringExpense) -> None:
    row.skip_next = False
    row.next_amount = None
    row.next_description = None


async def get_recurring(
    db: AsyncSession, tenant_id: str, recurring_id: str
) -> m.RecurringExpense:
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
    return row


async def update_recurring(
    db: AsyncSession,
    *,
    tenant_id: str,
    recurring_id: str,
    skip_next: bool | None = None,
    next_amount: float | None = None,
    next_description: str | None = None,
    clear_next_override: bool | None = None,
    is_active: bool | None = None,
    amount: float | None = None,
    description: str | None = None,
    frequency: str | None = None,
    payment_method: str | None = None,
    payee: str | None = None,
) -> m.RecurringExpense:
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

    if clear_next_override:
        row.next_amount = None
        row.next_description = None
    if skip_next is not None:
        row.skip_next = bool(skip_next)
        if row.skip_next:
            # Skipping cancels a one-off amount/description override for that occurrence.
            row.next_amount = None
            row.next_description = None
    if next_amount is not None:
        row.next_amount = round(float(next_amount), 2)
        row.skip_next = False
    if next_description is not None:
        row.next_description = next_description
        row.skip_next = False
    if is_active is not None:
        row.is_active = bool(is_active)
    if amount is not None:
        row.amount = round(float(amount), 2)
    if description is not None:
        row.description = description
    if frequency is not None:
        freq = (frequency or "monthly").lower()
        if freq not in {"daily", "weekly", "monthly", "yearly"}:
            raise HTTPException(
                status_code=400,
                detail="frequency must be daily, weekly, monthly, or yearly",
            )
        row.frequency = freq
    if payment_method is not None:
        row.payment_method = payment_method
    if payee is not None:
        row.payee = payee

    await db.flush()
    return row


async def generate_due_recurring(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    company_id: str | None = None,
) -> list[m.Expense]:
    now = datetime.utcnow()
    stmt = select(m.RecurringExpense).where(
        m.RecurringExpense.tenant_id == tenant_id,
        m.RecurringExpense.is_active == True,  # noqa: E712
        m.RecurringExpense.next_run_at <= now,
    )
    if company_id:
        stmt = stmt.where(m.RecurringExpense.company_id == company_id)
    rows = (await db.execute(stmt)).scalars().all()
    created: list[m.Expense] = []
    for row in rows:
        if row.end_date and row.end_date < now:
            row.is_active = False
            continue
        if row.skip_next:
            _clear_occurrence_overrides(row)
            row.next_run_at = next_run_date(now, row.frequency)
            row.last_notified_for = None
            continue
        amount = float(row.next_amount) if row.next_amount is not None else float(row.amount)
        description = (
            row.next_description
            if row.next_description is not None
            else (row.description or f"Recurring {row.category}")
        )
        expense = await create_expense(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            amount=amount,
            description=description,
            category_id=row.category_id,
            category=row.category,
            payment_method=row.payment_method,
            payee=row.payee,
            store_id=getattr(row, "store_id", None),
            department_id=getattr(row, "department_id", None),
            reference=f"REC-{row.id[:8]}",
            expense_date=now,
            company_id=getattr(row, "company_id", None) or company_id,
        )
        created.append(expense)
        _clear_occurrence_overrides(row)
        row.next_run_at = next_run_date(now, row.frequency)
        row.last_notified_for = None
    await db.flush()
    return created
