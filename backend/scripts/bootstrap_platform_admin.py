"""Bootstrap Ribdigi House platform admin from env (ADR-137).

Requires:
  PLATFORM_ADMIN_EMAIL
  PLATFORM_ADMIN_PASSWORD

Optional:
  PLATFORM_ADMIN_FULL_NAME
  PLATFORM_ADMIN_ROLE  (platform_super_admin | platform_admin)

No hard-coded production password. Idempotent: updates password only when
PLATFORM_ADMIN_FORCE_PASSWORD=1.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app import models as m
from app.platform import ensure_platform_tenant
from app.platform_const import PLATFORM_ADMIN, PLATFORM_SUPER_ADMIN
from app.rbac import permissions_for_role
from app.security import hash_password, validate_password_strength


async def run() -> int:
    email = (settings.PLATFORM_ADMIN_EMAIL or os.environ.get("PLATFORM_ADMIN_EMAIL") or "").strip().lower()
    password = settings.PLATFORM_ADMIN_PASSWORD or os.environ.get("PLATFORM_ADMIN_PASSWORD") or ""
    full_name = (
        settings.PLATFORM_ADMIN_FULL_NAME
        or os.environ.get("PLATFORM_ADMIN_FULL_NAME")
        or "Platform Super Admin"
    ).strip()
    role = (os.environ.get("PLATFORM_ADMIN_ROLE") or PLATFORM_SUPER_ADMIN).strip()
    if role not in {PLATFORM_SUPER_ADMIN, PLATFORM_ADMIN}:
        print(f"Invalid PLATFORM_ADMIN_ROLE: {role}", file=sys.stderr)
        return 2
    if not email or not password:
        print(
            "PLATFORM_ADMIN_EMAIL and PLATFORM_ADMIN_PASSWORD are required",
            file=sys.stderr,
        )
        return 2
    try:
        validate_password_strength(password)
    except Exception as exc:  # noqa: BLE001
        print(f"Password rejected: {exc}", file=sys.stderr)
        return 2

    force = (os.environ.get("PLATFORM_ADMIN_FORCE_PASSWORD") or "").strip() in {"1", "true", "yes"}

    async with SessionLocal() as db:
        tenant = await ensure_platform_tenant(db)
        existing = (
            await db.execute(
                select(m.User).where(
                    m.User.tenant_id == tenant.id,
                    m.User.email == email,
                )
            )
        ).scalar_one_or_none()
        if existing:
            if force:
                existing.password_hash = hash_password(password)
                existing.role = role
                existing.permissions = permissions_for_role(role)
                existing.is_active = True
                existing.email_verified = True
                await db.commit()
                print(f"Updated platform admin {email} (password forced)")
            else:
                print(f"Platform admin {email} already exists — no changes")
            return 0

        user = m.User(
            tenant_id=tenant.id,
            email=email,
            full_name=full_name,
            password_hash=hash_password(password),
            role=role,
            permissions=permissions_for_role(role),
            email_verified=True,
            is_active=True,
            totp_enabled=False,
        )
        db.add(user)
        await db.commit()
        print(f"Created platform admin {email} on tenant {tenant.slug}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
