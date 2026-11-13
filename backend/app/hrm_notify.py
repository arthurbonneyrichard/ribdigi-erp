"""In-app HR notices (category "hr"), always addressed to one person, never company-wide.

They say what happened and where to look; they carry no pay figures, because a notice can
show on a shared till screen. Staff are matched to their sign-in by the email on their
staff record. A notice that cannot be delivered is skipped; it never stops the HR action.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

HR_ROLES = ("company_admin", "hrm_manager")


async def _user_for(db: AsyncSession, tenant_id: str, employee: m.HrmEmployee | None) -> str | None:
    email = (getattr(employee, "email", None) or "").strip().lower()
    if not email:
        return None
    rows = (await db.execute(select(m.User.id, m.User.email, m.User.is_active).where(m.User.tenant_id == tenant_id))).all()
    for uid, user_email, active in rows:
        if active and (user_email or "").strip().lower() == email:
            return uid
    return None


async def _send(db, tenant_id, user_id, title, message, entity_type, entity_id) -> None:
    from app import notifications

    try:
        await notifications.create_notification(
            db, tenant_id=tenant_id, user_id=user_id, title=title, message=message, category="hr",
            entity_type=entity_type, entity_id=entity_id,
        )
    except Exception:  # noqa: BLE001 - a notice never undoes the HR action
        pass


async def to_person(db, tenant_id, employee, title, message, *, entity_type=None, entity_id=None, skip_user=None) -> None:
    uid = await _user_for(db, tenant_id, employee)
    if uid and uid != skip_user:
        await _send(db, tenant_id, uid, title, message, entity_type, entity_id)


async def to_hr(db, tenant_id, title, message, *, entity_type=None, entity_id=None, skip_user=None) -> None:
    from app import notifications

    for user in await notifications.users_for_roles(db, tenant_id, list(HR_ROLES)):
        if user.id != skip_user:
            await _send(db, tenant_id, user.id, title, message, entity_type, entity_id)


async def to_manager(db, tenant_id, employee, title, message, *, entity_type=None, entity_id=None, skip_user=None) -> bool:
    """Tell the person's manager. False when there is no manager with a sign-in."""
    if not getattr(employee, "manager_id", None):
        return False
    from app import hrm_delegation

    manager = await db.get(m.HrmEmployee, employee.manager_id)
    cover = await hrm_delegation.active_for(db, employee.manager_id)
    if cover is not None:
        # The manager is away: their cover gets it.
        manager = await db.get(m.HrmEmployee, cover.to_employee_id)
    uid = await _user_for(db, tenant_id, manager)
    if not uid:
        return False
    if uid != skip_user:
        await _send(db, tenant_id, uid, title, message, entity_type, entity_id)
    return True
