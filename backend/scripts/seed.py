"""Optional local-development seed data. Never enabled automatically.

This script refuses to run unless APP_ENV is non-production and
ALLOW_DEVELOPMENT_SEED=true. It is not part of production startup.
"""
import asyncio

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Account, Notification, Product, TaxRate, Tenant, User
from app.rbac import permissions_for_role
from app.security import hash_password


async def main():
    if settings.APP_ENV.lower() == "production":
        raise RuntimeError("Development seed is forbidden in production")
    if not settings.ALLOW_DEVELOPMENT_SEED:
        raise RuntimeError("Set ALLOW_DEVELOPMENT_SEED=true explicitly to use local seed data")

    async with SessionLocal() as db:
        slug = "local-dev"
        existing = (await db.execute(select(Tenant).where(Tenant.slug == slug))).scalar_one_or_none()
        if existing:
            print("Local development tenant already exists")
            return

        tenant = Tenant(
            slug=slug,
            company_name="Local Development Company",
            industry="retail",
            currency="GHS",
        )
        db.add(tenant)
        await db.flush()

        db.add(
            User(
                tenant_id=tenant.id,
                email="admin@localhost",
                full_name="Local Administrator",
                password_hash=hash_password("LocalDevOnly-ChangeMe!"),
                role="company_admin",
                email_verified=True,
                permissions=permissions_for_role("company_admin"),
            )
        )
        db.add_all(
            [
                Product(
                    tenant_id=tenant.id,
                    name="Local Test Product",
                    sku="LOCAL-001",
                    cost_price=10,
                    selling_price=15,
                    stock_qty=20,
                    reorder_level=5,
                ),
                TaxRate(
                    tenant_id=tenant.id,
                    name="VAT",
                    rate=15,
                    tax_type="vat",
                    pricing_mode="exclusive",
                    is_default=True,
                    is_active=True,
                ),
                Account(tenant_id=tenant.id, code="1000", name="Cash", account_type="asset"),
                Account(tenant_id=tenant.id, code="4000", name="Sales Revenue", account_type="income"),
                Notification(
                    tenant_id=tenant.id,
                    title="Local environment ready",
                    message="Development seed data was created explicitly.",
                ),
            ]
        )
        await db.commit()
        print("Local-only seed created. Change the local password immediately if this environment is shared.")


if __name__ == "__main__":
    asyncio.run(main())
