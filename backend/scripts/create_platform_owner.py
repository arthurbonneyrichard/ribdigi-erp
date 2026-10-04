"""One-shot bootstrap for the initial Ribdigi Platform Owner.

Creates the platform workspace tenant (if missing) and a platform_owner user.
Refuses to run unless ALLOW_PLATFORM_OWNER_BOOTSTRAP=true.
Refuses if any platform_owner already exists (prevents accidental duplicates).

Usage (production):
  docker compose -f docker-compose.prod.yml exec \\
    -e ALLOW_PLATFORM_OWNER_BOOTSTRAP=true \\
    -e PLATFORM_OWNER_EMAIL=owner@example.com \\
    -e PLATFORM_OWNER_PASSWORD='YourStrongPass1!' \\
    -e PLATFORM_OWNER_FULL_NAME='Platform Owner' \\
    backend python scripts/create_platform_owner.py

Never commit real passwords. Change the password after first login.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Tenant, User
from app.honesty import require_honest_narrative
from app.rbac import permissions_for_role
from app.security import hash_password, validate_password_strength


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


async def main() -> None:
    if _env("ALLOW_PLATFORM_OWNER_BOOTSTRAP").lower() not in {"1", "true", "yes"}:
        raise RuntimeError(
            "Refusing to run: set ALLOW_PLATFORM_OWNER_BOOTSTRAP=true explicitly"
        )

    email = _env("PLATFORM_OWNER_EMAIL").lower()
    password = os.environ.get("PLATFORM_OWNER_PASSWORD") or ""
    full_name = _env("PLATFORM_OWNER_FULL_NAME", "Platform Owner")
    slug = _env("PLATFORM_TENANT_SLUG", "platform")
    company_name = _env("PLATFORM_TENANT_NAME", "Ribdigi Platform")
    currency = _env("PLATFORM_TENANT_CURRENCY", "GHS")

    if not email or "@" not in email:
        raise RuntimeError("PLATFORM_OWNER_EMAIL is required (valid email)")
    if not password:
        raise RuntimeError("PLATFORM_OWNER_PASSWORD is required")

    # validate_password_strength raises HTTPException — convert for CLI use
    try:
        validate_password_strength(password)
    except Exception as exc:  # noqa: BLE001
        detail = getattr(exc, "detail", None) or str(exc)
        raise RuntimeError(f"Weak password: {detail}") from exc

    async with SessionLocal() as db:
        existing_owner = (
            await db.execute(select(User).where(User.role == "platform_owner").limit(1))
        ).scalar_one_or_none()
        if existing_owner:
            raise RuntimeError(
                f"A platform_owner already exists (email={existing_owner.email}). "
                "Use POST /platform/staff as an authenticated owner instead."
            )

        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == slug))
        ).scalar_one_or_none()
        if tenant is None:
            tenant = Tenant(
                slug=slug,
                company_name=company_name,
                industry="software",
                currency=currency,
                status="active",
                package_code="platform",
            )
            db.add(tenant)
            await db.flush()
            # Best-effort defaults (accounts/catalog); ignore entitlement races
            try:
                from app.api import seed_tenant_defaults

                await seed_tenant_defaults(db, tenant.id)
            except Exception as exc:  # noqa: BLE001
                print(f"Warning: seed_tenant_defaults partial failure: {exc}")

        email_taken = (
            await db.execute(
                select(User).where(User.tenant_id == tenant.id, User.email == email)
            )
        ).scalar_one_or_none()
        if email_taken:
            raise RuntimeError(f"User {email} already exists on tenant {slug}")

        user = User(
            tenant_id=tenant.id,
            email=email,
            full_name=require_honest_narrative(full_name, label="full name", max_length=150),
            password_hash=hash_password(password),
            role="platform_owner",
            email_verified=True,
            permissions=permissions_for_role("platform_owner"),
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        print("Platform Owner created successfully")
        print(f"  tenant_slug: {tenant.slug}")
        print(f"  tenant_id:   {tenant.id}")
        print(f"  email:       {user.email}")
        print(f"  role:        {user.role}")
        print(f"  app_env:     {settings.APP_ENV}")
        print("Unset ALLOW_PLATFORM_OWNER_BOOTSTRAP after use. Change password after login.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
