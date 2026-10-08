import asyncio

from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from app.rbac import permissions_for_role
from app.security import hash_password

EMAIL = "walk-platform@example.com"
OLD_EMAIL = "walk-platform@example.test"


async def main() -> None:
    async with SessionLocal() as db:
        tenant = (
            await db.execute(select(m.Tenant).where(m.Tenant.slug == "platform"))
        ).scalar_one()
        old = (
            await db.execute(
                select(m.User).where(
                    m.User.tenant_id == tenant.id, m.User.email == OLD_EMAIL
                )
            )
        ).scalar_one_or_none()
        if old is not None:
            old.email = EMAIL
            await db.commit()
            print("renamed")
            return
        existing = (
            await db.execute(
                select(m.User).where(
                    m.User.tenant_id == tenant.id, m.User.email == EMAIL
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                m.User(
                    tenant_id=tenant.id,
                    email=EMAIL,
                    full_name="Walkthrough Platform",
                    password_hash=hash_password("SecurePass123!"),
                    role="platform_owner",
                    email_verified=True,
                    is_active=True,
                    permissions=permissions_for_role("platform_owner"),
                )
            )
            await db.commit()
            print("created")
        else:
            print("exists")


if __name__ == "__main__":
    asyncio.run(main())
