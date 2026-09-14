"""Opt-in live customer-demo tenant seed.

Never runs automatically. Requires APP_ENV != production and
ALLOW_DEMO_TENANT_SEED=true. Does not enable ALLOW_PUBLIC_TENANT_SIGNUP.

This seeds a repeatable demo tenant + company + store + users + light sample
catalog so operators can recreate customer demos. It does **not** claim Offline
Complete, go-live Complete, paid billing Complete, or store-scoped RBAC Complete.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.rbac import permissions_for_role
from app.security import hash_password, validate_password_strength


DEFAULT_TENANT_SLUG = "demo"
DEFAULT_COMPANY_CODE = "DEMO"
DEFAULT_COMPANY_NAME = "Ribdigi Demo"
DEFAULT_BRANCH_CODE = "HQ"
DEFAULT_BRANCH_NAME = "Demo HQ"
DEFAULT_STORE_CODE = "DEMO-01"
DEFAULT_STORE_NAME = "Demo Store"
DEFAULT_WAREHOUSE_CODE = "DEMO-WH"
DEFAULT_WAREHOUSE_NAME = "Demo Warehouse"
DEFAULT_OWNER_EMAIL = "owner@demo.ribdigi.local"
DEFAULT_CASHIER_EMAIL = "cashier@demo.ribdigi.local"
DEFAULT_OWNER_NAME = "Demo Owner"
DEFAULT_CASHIER_NAME = "Demo Cashier"
# Memorable defaults for live demos — operators must override via env in shared envs
# and change after first login. Never commit real production passwords.
DEFAULT_OWNER_PASSWORD = "DemoOwner-ChangeMe1!"
DEFAULT_CASHIER_PASSWORD = "DemoCashier-ChangeMe1!"

SAMPLE_PRODUCTS = (
    {
        "sku": "DEMO-001",
        "name": "Demo Rice 5kg",
        "barcode": "DEMO0000001",
        "cost_price": 40.0,
        "selling_price": 55.0,
        "stock_qty": 50.0,
        "reorder_level": 10.0,
    },
    {
        "sku": "DEMO-002",
        "name": "Demo Cooking Oil 1L",
        "barcode": "DEMO0000002",
        "cost_price": 18.0,
        "selling_price": 28.0,
        "stock_qty": 80.0,
        "reorder_level": 15.0,
    },
    {
        "sku": "DEMO-003",
        "name": "Demo Soft Drink 500ml",
        "barcode": "DEMO0000003",
        "cost_price": 3.0,
        "selling_price": 5.0,
        "stock_qty": 120.0,
        "reorder_level": 24.0,
    },
)


@dataclass
class DemoSeedConfig:
    tenant_slug: str = DEFAULT_TENANT_SLUG
    company_code: str = DEFAULT_COMPANY_CODE
    company_name: str = DEFAULT_COMPANY_NAME
    branch_code: str = DEFAULT_BRANCH_CODE
    branch_name: str = DEFAULT_BRANCH_NAME
    store_code: str = DEFAULT_STORE_CODE
    store_name: str = DEFAULT_STORE_NAME
    warehouse_code: str = DEFAULT_WAREHOUSE_CODE
    warehouse_name: str = DEFAULT_WAREHOUSE_NAME
    owner_email: str = DEFAULT_OWNER_EMAIL
    cashier_email: str = DEFAULT_CASHIER_EMAIL
    owner_full_name: str = DEFAULT_OWNER_NAME
    cashier_full_name: str = DEFAULT_CASHIER_NAME
    owner_password: str = DEFAULT_OWNER_PASSWORD
    cashier_password: str = DEFAULT_CASHIER_PASSWORD
    force_password: bool = False
    include_sample_data: bool = True
    include_open_shift: bool = True
    currency: str = "GHS"
    industry: str = "retail"


def config_from_env() -> DemoSeedConfig:
    force = (os.environ.get("DEMO_FORCE_PASSWORD") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    sample = (os.environ.get("DEMO_SEED_SAMPLE_DATA") or "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    open_shift = (os.environ.get("DEMO_SEED_OPEN_SHIFT") or "true").strip().lower() not in {
        "0",
        "false",
        "no",
    }
    return DemoSeedConfig(
        tenant_slug=(os.environ.get("DEMO_TENANT_SLUG") or DEFAULT_TENANT_SLUG).strip().lower(),
        company_code=(os.environ.get("DEMO_COMPANY_CODE") or DEFAULT_COMPANY_CODE).strip().upper(),
        company_name=(os.environ.get("DEMO_COMPANY_NAME") or DEFAULT_COMPANY_NAME).strip(),
        branch_code=(os.environ.get("DEMO_BRANCH_CODE") or DEFAULT_BRANCH_CODE).strip().upper(),
        branch_name=(os.environ.get("DEMO_BRANCH_NAME") or DEFAULT_BRANCH_NAME).strip(),
        store_code=(os.environ.get("DEMO_STORE_CODE") or DEFAULT_STORE_CODE).strip().upper(),
        store_name=(os.environ.get("DEMO_STORE_NAME") or DEFAULT_STORE_NAME).strip(),
        warehouse_code=(os.environ.get("DEMO_WAREHOUSE_CODE") or DEFAULT_WAREHOUSE_CODE)
        .strip()
        .upper(),
        warehouse_name=(os.environ.get("DEMO_WAREHOUSE_NAME") or DEFAULT_WAREHOUSE_NAME).strip(),
        owner_email=(os.environ.get("DEMO_OWNER_EMAIL") or DEFAULT_OWNER_EMAIL).strip().lower(),
        cashier_email=(os.environ.get("DEMO_CASHIER_EMAIL") or DEFAULT_CASHIER_EMAIL)
        .strip()
        .lower(),
        owner_full_name=(os.environ.get("DEMO_OWNER_FULL_NAME") or DEFAULT_OWNER_NAME).strip(),
        cashier_full_name=(os.environ.get("DEMO_CASHIER_FULL_NAME") or DEFAULT_CASHIER_NAME).strip(),
        owner_password=os.environ.get("DEMO_OWNER_PASSWORD") or DEFAULT_OWNER_PASSWORD,
        cashier_password=os.environ.get("DEMO_CASHIER_PASSWORD") or DEFAULT_CASHIER_PASSWORD,
        force_password=force,
        include_sample_data=sample,
        include_open_shift=open_shift,
        currency=(os.environ.get("DEMO_CURRENCY") or "GHS").strip().upper() or "GHS",
        industry=(os.environ.get("DEMO_INDUSTRY") or "retail").strip().lower() or "retail",
    )


def assert_demo_seed_allowed(*, app_env: str | None = None, allow_flag: bool | None = None) -> None:
    """Refuse unless explicitly opted in and not production."""
    env = (app_env if app_env is not None else settings.APP_ENV).strip().lower()
    allowed = (
        allow_flag
        if allow_flag is not None
        else bool(getattr(settings, "ALLOW_DEMO_TENANT_SEED", False))
    )
    if env == "production":
        raise RuntimeError("Demo tenant seed is forbidden when APP_ENV=production")
    if not allowed:
        raise RuntimeError(
            "Set ALLOW_DEMO_TENANT_SEED=true explicitly to create the live customer-demo tenant"
        )


def _validate_passwords(cfg: DemoSeedConfig) -> None:
    for label, password in (
        ("DEMO_OWNER_PASSWORD", cfg.owner_password),
        ("DEMO_CASHIER_PASSWORD", cfg.cashier_password),
    ):
        try:
            validate_password_strength(password)
        except HTTPException as exc:
            raise RuntimeError(f"{label} rejected: {exc.detail}") from exc


async def _ensure_user(
    db: AsyncSession,
    *,
    tenant_id: str,
    email: str,
    full_name: str,
    role: str,
    password: str,
    force_password: bool,
    created: list[str],
    updated: list[str],
) -> m.User:
    existing = (
        await db.execute(
            select(m.User).where(m.User.tenant_id == tenant_id, m.User.email == email)
        )
    ).scalar_one_or_none()
    perms = permissions_for_role(role)
    if existing:
        existing.full_name = full_name
        existing.role = role
        existing.permissions = perms
        existing.is_active = True
        existing.email_verified = True
        existing.totp_enabled = False
        if force_password:
            existing.password_hash = hash_password(password)
            updated.append(f"user:{email}:password")
        else:
            updated.append(f"user:{email}")
        return existing

    user = m.User(
        tenant_id=tenant_id,
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        role=role,
        permissions=perms,
        email_verified=True,
        is_active=True,
        totp_enabled=False,
    )
    db.add(user)
    await db.flush()
    created.append(f"user:{email}")
    return user


async def _ensure_membership(
    db: AsyncSession,
    *,
    tenant_id: str,
    user: m.User,
    company_id: str,
    created: list[str],
) -> None:
    existing = (
        await db.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.tenant_id == tenant_id,
                m.UserCompanyMembership.user_id == user.id,
                m.UserCompanyMembership.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.role = user.role
        existing.permissions = user.permissions if isinstance(user.permissions, dict) else None
        existing.is_active = True
        return
    db.add(
        m.UserCompanyMembership(
            tenant_id=tenant_id,
            user_id=user.id,
            company_id=company_id,
            role=user.role,
            permissions=user.permissions if isinstance(user.permissions, dict) else None,
            is_active=True,
        )
    )
    created.append(f"membership:{user.email}")


async def _ensure_store_membership(
    db: AsyncSession,
    *,
    tenant_id: str,
    company_id: str,
    user_id: str,
    store_id: str,
    created: list[str],
    label: str,
) -> None:
    """Optional ADR-005 assignment row for flag-ON demos (does not claim Complete)."""
    existing = (
        await db.execute(
            select(m.UserStoreMembership).where(
                m.UserStoreMembership.tenant_id == tenant_id,
                m.UserStoreMembership.user_id == user_id,
                m.UserStoreMembership.store_id == store_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.is_active = True
        existing.company_id = company_id
        return
    db.add(
        m.UserStoreMembership(
            tenant_id=tenant_id,
            company_id=company_id,
            user_id=user_id,
            store_id=store_id,
            is_active=True,
        )
    )
    created.append(f"store_membership:{label}")


async def seed_demo_tenant(
    db: AsyncSession,
    cfg: DemoSeedConfig | None = None,
    *,
    dry_run: bool = False,
    commit: bool = True,
) -> dict[str, Any]:
    """Create or refresh the live customer-demo tenant graph.

    Idempotent: re-running fills missing pieces; passwords update only when
    ``force_password`` / ``DEMO_FORCE_PASSWORD=1``.
    """
    assert_demo_seed_allowed()
    cfg = cfg or config_from_env()
    _validate_passwords(cfg)

    plan = {
        "tenant_slug": cfg.tenant_slug,
        "company_name": cfg.company_name,
        "store_name": cfg.store_name,
        "owner_email": cfg.owner_email,
        "cashier_email": cfg.cashier_email,
        "include_sample_data": cfg.include_sample_data,
        "include_open_shift": cfg.include_open_shift,
        "force_password": cfg.force_password,
    }
    if dry_run:
        return {
            "dry_run": True,
            "would_create_or_refresh": plan,
            "password_source": {
                "owner": "env:DEMO_OWNER_PASSWORD"
                if os.environ.get("DEMO_OWNER_PASSWORD")
                else "default",
                "cashier": "env:DEMO_CASHIER_PASSWORD"
                if os.environ.get("DEMO_CASHIER_PASSWORD")
                else "default",
            },
            "note": "Passwords are not printed. See docs/DEMO_ACCOUNT.md and local ops artifact.",
        }

    created: list[str] = []
    updated: list[str] = []

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.slug == cfg.tenant_slug))
    ).scalar_one_or_none()
    if tenant is None:
        tenant = m.Tenant(
            slug=cfg.tenant_slug,
            company_name=cfg.company_name,
            industry=cfg.industry,
            currency=cfg.currency,
            status="active",
            plan_code="trial",
            email=cfg.owner_email,
            contact_person_name=cfg.owner_full_name,
            contact_person_email=cfg.owner_email,
            trial_ends_at=datetime.utcnow() + timedelta(days=365),
            max_companies=3,
            max_users=25,
            max_branches=5,
            max_stores=5,
            max_warehouses=5,
        )
        db.add(tenant)
        await db.flush()
        created.append("tenant")
    else:
        tenant.company_name = cfg.company_name
        tenant.industry = cfg.industry
        tenant.currency = cfg.currency
        if tenant.status in {"suspended"}:
            tenant.status = "active"
        updated.append("tenant")

    company = (
        await db.execute(
            select(m.Company).where(
                m.Company.tenant_id == tenant.id,
                m.Company.code == cfg.company_code,
            )
        )
    ).scalar_one_or_none()
    if company is None:
        company = m.Company(
            tenant_id=tenant.id,
            code=cfg.company_code,
            name=cfg.company_name,
            industry=cfg.industry,
            currency=cfg.currency,
            is_active=True,
            is_default=True,
            store_limit=5,
            email=cfg.owner_email,
        )
        db.add(company)
        await db.flush()
        created.append("company")
    else:
        company.name = cfg.company_name
        company.is_active = True
        company.is_default = True
        if company.store_limit is None:
            company.store_limit = 5
        updated.append("company")

    owner = await _ensure_user(
        db,
        tenant_id=tenant.id,
        email=cfg.owner_email,
        full_name=cfg.owner_full_name,
        role="company_admin",
        password=cfg.owner_password,
        force_password=cfg.force_password,
        created=created,
        updated=updated,
    )
    cashier = await _ensure_user(
        db,
        tenant_id=tenant.id,
        email=cfg.cashier_email,
        full_name=cfg.cashier_full_name,
        role="cashier",
        password=cfg.cashier_password,
        force_password=cfg.force_password,
        created=created,
        updated=updated,
    )
    await _ensure_membership(
        db, tenant_id=tenant.id, user=owner, company_id=company.id, created=created
    )
    await _ensure_membership(
        db, tenant_id=tenant.id, user=cashier, company_id=company.id, created=created
    )

    branch = (
        await db.execute(
            select(m.Branch).where(
                m.Branch.tenant_id == tenant.id,
                m.Branch.company_id == company.id,
                m.Branch.code == cfg.branch_code,
            )
        )
    ).scalar_one_or_none()
    if branch is None:
        branch = m.Branch(
            tenant_id=tenant.id,
            company_id=company.id,
            code=cfg.branch_code,
            name=cfg.branch_name,
            is_active=True,
            manager_id=owner.id,
        )
        db.add(branch)
        await db.flush()
        created.append("branch")
    else:
        branch.name = cfg.branch_name
        branch.is_active = True
        branch.manager_id = owner.id
        updated.append("branch")

    store = (
        await db.execute(
            select(m.Store).where(
                m.Store.tenant_id == tenant.id,
                m.Store.company_id == company.id,
                m.Store.code == cfg.store_code,
            )
        )
    ).scalar_one_or_none()
    if store is None:
        store = m.Store(
            tenant_id=tenant.id,
            company_id=company.id,
            branch_id=branch.id,
            code=cfg.store_code,
            name=cfg.store_name,
            is_active=True,
            manager_id=owner.id,
            drawer_mode="mock",
        )
        db.add(store)
        await db.flush()
        created.append("store")
    else:
        store.name = cfg.store_name
        store.is_active = True
        store.branch_id = branch.id
        store.manager_id = owner.id
        updated.append("store")

    warehouse = (
        await db.execute(
            select(m.Warehouse).where(
                m.Warehouse.tenant_id == tenant.id,
                m.Warehouse.company_id == company.id,
                m.Warehouse.code == cfg.warehouse_code,
            )
        )
    ).scalar_one_or_none()
    if warehouse is None:
        warehouse = m.Warehouse(
            tenant_id=tenant.id,
            company_id=company.id,
            store_id=store.id,
            code=cfg.warehouse_code,
            name=cfg.warehouse_name,
            warehouse_type="retail",
            manager_id=owner.id,
            is_active=True,
        )
        db.add(warehouse)
        await db.flush()
        created.append("warehouse")
    else:
        warehouse.name = cfg.warehouse_name
        warehouse.store_id = store.id
        warehouse.is_active = True
        updated.append("warehouse")

    await _ensure_store_membership(
        db,
        tenant_id=tenant.id,
        company_id=company.id,
        user_id=owner.id,
        store_id=store.id,
        created=created,
        label=cfg.owner_email,
    )
    await _ensure_store_membership(
        db,
        tenant_id=tenant.id,
        company_id=company.id,
        user_id=cashier.id,
        store_id=store.id,
        created=created,
        label=cfg.cashier_email,
    )

    sample: dict[str, Any] = {"products": [], "accounts": [], "parties": []}
    if cfg.include_sample_data:
        tax = (
            await db.execute(
                select(m.TaxRate).where(
                    m.TaxRate.tenant_id == tenant.id,
                    m.TaxRate.company_id == company.id,
                    m.TaxRate.name == "VAT",
                )
            )
        ).scalar_one_or_none()
        if tax is None:
            tax = m.TaxRate(
                tenant_id=tenant.id,
                company_id=company.id,
                name="VAT",
                rate=15,
                tax_type="vat",
                pricing_mode="exclusive",
                is_default=True,
                is_active=True,
            )
            db.add(tax)
            await db.flush()
            created.append("tax:VAT")
        else:
            tax.is_default = True
            tax.is_active = True

        for code, name, account_type, cash in (
            ("1000", "Cash", "asset", True),
            ("1100", "Bank", "asset", False),
            ("4000", "Sales Revenue", "income", False),
        ):
            acct = (
                await db.execute(
                    select(m.Account).where(
                        m.Account.tenant_id == tenant.id,
                        m.Account.company_id == company.id,
                        m.Account.code == code,
                    )
                )
            ).scalar_one_or_none()
            if acct is None:
                acct = m.Account(
                    tenant_id=tenant.id,
                    company_id=company.id,
                    code=code,
                    name=name,
                    account_type=account_type,
                    is_cash_account=cash,
                    is_bank_account=(code == "1100"),
                    is_active=True,
                )
                db.add(acct)
                created.append(f"account:{code}")
                sample["accounts"].append(code)
            else:
                sample["accounts"].append(code)

        for kind, party_name in (
            ("customer", "Demo Walk-in Customer"),
            ("supplier", "Demo Supplier"),
        ):
            party = (
                await db.execute(
                    select(m.Party).where(
                        m.Party.tenant_id == tenant.id,
                        m.Party.company_id == company.id,
                        m.Party.name == party_name,
                        m.Party.kind == kind,
                    )
                )
            ).scalar_one_or_none()
            if party is None:
                party = m.Party(
                    tenant_id=tenant.id,
                    company_id=company.id,
                    name=party_name,
                    kind=kind,
                    credit_limit=0 if kind == "supplier" else 500,
                )
                db.add(party)
                created.append(f"party:{kind}")
            sample["parties"].append(party_name)

        for spec in SAMPLE_PRODUCTS:
            product = (
                await db.execute(
                    select(m.Product).where(
                        m.Product.tenant_id == tenant.id,
                        m.Product.company_id == company.id,
                        m.Product.sku == spec["sku"],
                    )
                )
            ).scalar_one_or_none()
            if product is None:
                product = m.Product(
                    tenant_id=tenant.id,
                    company_id=company.id,
                    name=spec["name"],
                    sku=spec["sku"],
                    barcode=spec["barcode"],
                    category="Demo",
                    cost_price=spec["cost_price"],
                    selling_price=spec["selling_price"],
                    stock_qty=spec["stock_qty"],
                    reorder_level=spec["reorder_level"],
                    tax_rate_id=tax.id,
                    is_active=True,
                )
                db.add(product)
                await db.flush()
                created.append(f"product:{spec['sku']}")
            else:
                product.name = spec["name"]
                product.is_active = True
                product.tax_rate_id = tax.id
                if float(product.stock_qty or 0) <= 0:
                    product.stock_qty = spec["stock_qty"]
            sample["products"].append(spec["sku"])

            wh_stock = (
                await db.execute(
                    select(m.WarehouseStock).where(
                        m.WarehouseStock.tenant_id == tenant.id,
                        m.WarehouseStock.warehouse_id == warehouse.id,
                        m.WarehouseStock.product_id == product.id,
                    )
                )
            ).scalar_one_or_none()
            if wh_stock is None:
                db.add(
                    m.WarehouseStock(
                        tenant_id=tenant.id,
                        company_id=company.id,
                        warehouse_id=warehouse.id,
                        product_id=product.id,
                        quantity=spec["stock_qty"],
                        reorder_level=spec["reorder_level"],
                    )
                )
                created.append(f"warehouse_stock:{spec['sku']}")
            elif float(wh_stock.quantity or 0) <= 0:
                wh_stock.quantity = spec["stock_qty"]

        note = (
            await db.execute(
                select(m.Notification).where(
                    m.Notification.tenant_id == tenant.id,
                    m.Notification.company_id == company.id,
                    m.Notification.title == "Demo tenant ready",
                )
            )
        ).scalar_one_or_none()
        if note is None:
            db.add(
                m.Notification(
                    tenant_id=tenant.id,
                    company_id=company.id,
                    user_id=owner.id,
                    category="system",
                    title="Demo tenant ready",
                    message=(
                        "Live customer-demo tenant was seeded explicitly. "
                        "Change demo passwords after first login. "
                        "This does not claim Offline/go-live/billing Completes."
                    ),
                )
            )
            created.append("notification")

    open_shift_id: str | None = None
    if cfg.include_open_shift:
        existing_open = (
            await db.execute(
                select(m.PosSession).where(
                    m.PosSession.tenant_id == tenant.id,
                    m.PosSession.user_id == cashier.id,
                    m.PosSession.status == "open",
                )
            )
        ).scalar_one_or_none()
        if existing_open:
            open_shift_id = existing_open.id
            updated.append("pos_session:open")
        else:
            session_number = f"DEMO-{datetime.utcnow():%Y%m%d}-0001"
            clash = (
                await db.execute(
                    select(m.PosSession).where(
                        m.PosSession.tenant_id == tenant.id,
                        m.PosSession.company_id == company.id,
                        m.PosSession.session_number == session_number,
                    )
                )
            ).scalar_one_or_none()
            if clash and clash.status != "open":
                session_number = f"DEMO-{datetime.utcnow():%Y%m%d%H%M%S}-0001"
            session = m.PosSession(
                tenant_id=tenant.id,
                company_id=company.id,
                store_id=store.id,
                user_id=cashier.id,
                session_number=session_number,
                status="open",
                opening_cash=200,
                expected_cash=200,
            )
            db.add(session)
            await db.flush()
            open_shift_id = session.id
            created.append("pos_session:open")

    if commit:
        await db.commit()

    return {
        "dry_run": False,
        "tenant_id": tenant.id,
        "tenant_slug": tenant.slug,
        "company_id": company.id,
        "company_name": company.name,
        "branch_id": branch.id,
        "store_id": store.id,
        "store_name": store.name,
        "warehouse_id": warehouse.id,
        "owner_email": owner.email,
        "cashier_email": cashier.email,
        "owner_role": owner.role,
        "cashier_role": cashier.role,
        "open_pos_session_id": open_shift_id,
        "sample": sample if cfg.include_sample_data else None,
        "created": created,
        "updated": updated,
        "config": {k: v for k, v in asdict(cfg).items() if "password" not in k},
        "honesty": {
            "offline_complete_claimed": False,
            "go_live_claimed": False,
            "paid_billing_complete_claimed": False,
            "store_scoped_rbac_complete_claimed": False,
            "seven_day_verified_claimed": False,
            "public_tenant_signup_required": False,
        },
    }
