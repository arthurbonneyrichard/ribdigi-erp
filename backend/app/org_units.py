"""Tenant branches and departments for org structure + record scopes."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m

CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")


def _clean_code(code: str) -> str:
    value = (code or "").strip().upper()
    if not CODE_RE.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail="code must be 1–40 chars: letters, digits, underscore, or hyphen",
        )
    return value


async def _assert_tenant_user(db: AsyncSession, tenant_id: str, user_id: str | None) -> str | None:
    if not user_id:
        return None
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in tenant")
    return user.id


def serialize_branch(row: m.Branch) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "address": row.address,
        "phone": getattr(row, "phone", None),
        "email": getattr(row, "email", None),
        "manager_id": getattr(row, "manager_id", None),
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


def serialize_department(row: m.Department) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "branch_id": row.branch_id,
        "head_user_id": getattr(row, "head_user_id", None),
        "is_active": bool(row.is_active),
        "created_at": row.created_at,
    }


async def get_branch(db: AsyncSession, tenant_id: str, branch_id: str) -> m.Branch:
    row = (
        await db.execute(
            select(m.Branch).where(m.Branch.id == branch_id, m.Branch.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Branch not found")
    return row


async def get_department(db: AsyncSession, tenant_id: str, department_id: str) -> m.Department:
    row = (
        await db.execute(
            select(m.Department).where(
                m.Department.id == department_id,
                m.Department.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Department not found")
    return row


async def list_branches(db: AsyncSession, tenant_id: str, *, active_only: bool = False) -> list[m.Branch]:
    stmt = select(m.Branch).where(m.Branch.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(m.Branch.is_active == True)  # noqa: E712
    return list((await db.execute(stmt.order_by(m.Branch.name))).scalars().all())


async def list_departments(
    db: AsyncSession,
    tenant_id: str,
    *,
    branch_id: str | None = None,
    active_only: bool = False,
) -> list[m.Department]:
    stmt = select(m.Department).where(m.Department.tenant_id == tenant_id)
    if branch_id:
        stmt = stmt.where(m.Department.branch_id == branch_id)
    if active_only:
        stmt = stmt.where(m.Department.is_active == True)  # noqa: E712
    return list((await db.execute(stmt.order_by(m.Department.name))).scalars().all())


async def create_branch(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    address: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    manager_id: str | None = None,
) -> m.Branch:
    code = _clean_code(code)
    name_clean = (name or "").strip()
    if len(name_clean) < 2:
        raise HTTPException(status_code=400, detail="name must be at least 2 characters")
    manager_id = await _assert_tenant_user(db, tenant_id, manager_id)
    exists = (
        await db.execute(
            select(m.Branch).where(m.Branch.tenant_id == tenant_id, m.Branch.code == code)
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Branch code already exists")
    row = m.Branch(
        tenant_id=tenant_id,
        code=code,
        name=name_clean,
        address=(address or "").strip() or None,
        phone=(phone or "").strip() or None,
        email=(email or "").strip() or None,
        manager_id=manager_id,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def update_branch(
    db: AsyncSession,
    *,
    tenant_id: str,
    branch_id: str,
    name: str | None = None,
    address: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    manager_id: str | None = None,
    clear_manager: bool = False,
    is_active: bool | None = None,
) -> m.Branch:
    row = await get_branch(db, tenant_id, branch_id)
    if name is not None:
        name_clean = name.strip()
        if len(name_clean) < 2:
            raise HTTPException(status_code=400, detail="name must be at least 2 characters")
        row.name = name_clean
    if address is not None:
        row.address = address.strip() or None
    if phone is not None:
        row.phone = phone.strip() or None
    if email is not None:
        row.email = email.strip() or None
    if clear_manager:
        row.manager_id = None
    elif manager_id is not None:
        row.manager_id = await _assert_tenant_user(db, tenant_id, manager_id)
    if is_active is not None:
        row.is_active = bool(is_active)
    await db.flush()
    return row


async def create_department(
    db: AsyncSession,
    *,
    tenant_id: str,
    code: str,
    name: str,
    branch_id: str | None = None,
    head_user_id: str | None = None,
) -> m.Department:
    code = _clean_code(code)
    name_clean = (name or "").strip()
    if len(name_clean) < 2:
        raise HTTPException(status_code=400, detail="name must be at least 2 characters")
    if branch_id:
        await get_branch(db, tenant_id, branch_id)
    head_user_id = await _assert_tenant_user(db, tenant_id, head_user_id)
    exists = (
        await db.execute(
            select(m.Department).where(m.Department.tenant_id == tenant_id, m.Department.code == code)
        )
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Department code already exists")
    row = m.Department(
        tenant_id=tenant_id,
        branch_id=branch_id,
        code=code,
        name=name_clean,
        head_user_id=head_user_id,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def update_department(
    db: AsyncSession,
    *,
    tenant_id: str,
    department_id: str,
    name: str | None = None,
    branch_id: str | None = None,
    clear_branch: bool = False,
    head_user_id: str | None = None,
    clear_head: bool = False,
    is_active: bool | None = None,
) -> m.Department:
    row = await get_department(db, tenant_id, department_id)
    if name is not None:
        name_clean = name.strip()
        if len(name_clean) < 2:
            raise HTTPException(status_code=400, detail="name must be at least 2 characters")
        row.name = name_clean
    if clear_branch:
        row.branch_id = None
    elif branch_id is not None:
        await get_branch(db, tenant_id, branch_id)
        row.branch_id = branch_id
    if clear_head:
        row.head_user_id = None
    elif head_user_id is not None:
        row.head_user_id = await _assert_tenant_user(db, tenant_id, head_user_id)
    if is_active is not None:
        row.is_active = bool(is_active)
    await db.flush()
    return row


async def assert_user_org_assignment(
    db: AsyncSession,
    tenant_id: str,
    *,
    branch_id: str | None,
    department_id: str | None,
) -> tuple[str | None, str | None]:
    resolved_branch = None
    resolved_dept = None
    if branch_id:
        branch = await get_branch(db, tenant_id, branch_id)
        if not branch.is_active:
            raise HTTPException(status_code=400, detail="Branch is inactive")
        resolved_branch = branch.id
    if department_id:
        dept = await get_department(db, tenant_id, department_id)
        if not dept.is_active:
            raise HTTPException(status_code=400, detail="Department is inactive")
        if dept.branch_id and resolved_branch and dept.branch_id != resolved_branch:
            raise HTTPException(
                status_code=400,
                detail="Department belongs to a different branch",
            )
        if dept.branch_id and not resolved_branch:
            resolved_branch = dept.branch_id
        resolved_dept = dept.id
    return resolved_branch, resolved_dept


async def scope_user_ids(
    db: AsyncSession,
    *,
    tenant_id: str,
    user: m.User,
    scope: str,
) -> list[str] | None:
    """Return user ids visible under record scope, or None for unrestricted (all)."""
    if scope == "all":
        return None
    if scope == "own":
        return [user.id]
    if scope == "department":
        if not user.department_id:
            return [user.id]
        rows = (
            await db.execute(
                select(m.User.id).where(
                    m.User.tenant_id == tenant_id,
                    m.User.department_id == user.department_id,
                    m.User.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        return list(rows) or [user.id]
    if scope == "branch":
        if not user.branch_id:
            return [user.id]
        rows = (
            await db.execute(
                select(m.User.id).where(
                    m.User.tenant_id == tenant_id,
                    m.User.branch_id == user.branch_id,
                    m.User.is_active == True,  # noqa: E712
                )
            )
        ).scalars().all()
        return list(rows) or [user.id]
    return [user.id]


async def count_users_in_department(db: AsyncSession, tenant_id: str, department_id: str) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.User)
                .where(m.User.tenant_id == tenant_id, m.User.department_id == department_id)
            )
        ).scalar_one()
        or 0
    )
