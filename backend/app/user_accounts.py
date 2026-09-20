"""Tenant user account hard-delete (company dashboard staff)."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import is_platform_role


async def delete_tenant_user(
    db: AsyncSession,
    *,
    tenant_id: str,
    actor_id: str,
    user_id: str,
) -> dict:
    """Permanently remove a tenant staff account (not platform roles)."""
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == actor_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if is_platform_role(user.role) or user.role == "super_admin":
        raise HTTPException(
            status_code=400,
            detail="Delete platform staff from the platform Staff directory",
        )
    if user.role == "company_admin":
        other_admins = (
            await db.execute(
                select(m.User).where(
                    m.User.tenant_id == tenant_id,
                    m.User.id != user.id,
                    m.User.role == "company_admin",
                    m.User.is_active.is_(True),
                )
            )
        ).scalars().all()
        if not other_admins:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last active company admin",
            )

    snapshot = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }

    for model in (
        m.AuthSession,
        m.AuthToken,
        m.WebAuthnCredential,
        m.WebAuthnChallenge,
        m.TwoFactorBackupCode,
        m.UserStoreMembership,
        m.NotificationPreference,
    ):
        await db.execute(delete(model).where(model.user_id == user.id))

    await db.execute(
        update(m.Notification).where(m.Notification.user_id == user.id).values(user_id=None)
    )
    await db.execute(
        update(m.PosDevice).where(m.PosDevice.user_id == user.id).values(user_id=None)
    )
    await db.execute(
        update(m.Branch).where(m.Branch.manager_id == user.id).values(manager_id=None)
    )
    await db.execute(
        update(m.Department)
        .where(m.Department.head_user_id == user.id)
        .values(head_user_id=None)
    )
    await db.execute(
        update(m.Store).where(m.Store.manager_id == user.id).values(manager_id=None)
    )
    await db.execute(
        update(m.Warehouse).where(m.Warehouse.manager_id == user.id).values(manager_id=None)
    )

    pos_sessions = (
        await db.execute(select(m.PosSession.id).where(m.PosSession.user_id == user.id).limit(1))
    ).first()
    if pos_sessions:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete this account because it has POS shift history. "
                "Deactivate the account instead."
            ),
        )

    try:
        await db.delete(user)
        await db.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete this account because it is linked to business records. "
                "Deactivate the account instead."
            ),
        ) from exc
    return snapshot
