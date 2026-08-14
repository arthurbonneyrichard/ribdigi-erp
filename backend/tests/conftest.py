"""Async SQLite fixtures for tenant isolation integration tests."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models as m
from app.db import get_db
from app.main import app
from app.security import hash_password
from app.rbac import permissions_for_role


@pytest.fixture
def _disable_rate_limit(monkeypatch):
    monkeypatch.setattr("app.middleware.settings.RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr("app.config.settings.RATE_LIMIT_ENABLED", False)


@pytest_asyncio.fixture
async def db_engine():
    from sqlalchemy.pool import StaticPool

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


async def _seed_two_tenants(db: AsyncSession) -> dict:
    t1 = m.Tenant(slug="alpha", company_name="Alpha Co", status="active", industry="retail", max_companies=3)
    t2 = m.Tenant(slug="beta", company_name="Beta Co", status="active", industry="retail", max_companies=1)
    db.add_all([t1, t2])
    await db.flush()

    c1 = m.Company(
        tenant_id=t1.id,
        code="MAIN",
        name="Alpha Co",
        industry="retail",
        is_active=True,
        is_default=True,
    )
    c2 = m.Company(
        tenant_id=t2.id,
        code="MAIN",
        name="Beta Co",
        industry="retail",
        is_active=True,
        is_default=True,
    )
    db.add_all([c1, c2])
    await db.flush()

    u1 = m.User(
        tenant_id=t1.id,
        email="cashier@alpha.example.com",
        full_name="Alpha Cashier",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=True,
        permissions=permissions_for_role("cashier"),
        totp_enabled=False,
    )
    u2 = m.User(
        tenant_id=t2.id,
        email="cashier@beta.example.com",
        full_name="Beta Cashier",
        password_hash=hash_password("SecurePass123!"),
        role="cashier",
        email_verified=True,
        permissions=permissions_for_role("cashier"),
        totp_enabled=False,
    )
    admin1 = m.User(
        tenant_id=t1.id,
        email="admin@alpha.example.com",
        full_name="Alpha Admin",
        password_hash=hash_password("SecurePass123!"),
        role="company_admin",
        email_verified=True,
        permissions=permissions_for_role("company_admin"),
        totp_enabled=False,
    )
    mgr1 = m.User(
        tenant_id=t1.id,
        email="mgr@alpha.example.com",
        full_name="Alpha Manager",
        password_hash=hash_password("SecurePass123!"),
        role="store_manager",
        email_verified=True,
        permissions=permissions_for_role("store_manager"),
        totp_enabled=False,
    )
    super_u = m.User(
        tenant_id=t1.id,
        email="super@alpha.example.com",
        full_name="Super Admin",
        password_hash=hash_password("SecurePass123!"),
        role="super_admin",
        email_verified=True,
        permissions=permissions_for_role("super_admin"),
        totp_enabled=True,
    )
    from app import totp as totp_svc
    import pyotp

    secret = pyotp.random_base32()
    super_u.totp_secret_enc = totp_svc.encrypt_secret(secret)
    super_u.totp_confirmed_at = __import__("datetime").datetime.utcnow()

    db.add_all([u1, u2, admin1, mgr1, super_u])
    await db.flush()

    for user, company in ((u1, c1), (u2, c2), (admin1, c1), (mgr1, c1), (super_u, c1)):
        db.add(
            m.UserCompanyMembership(
                tenant_id=user.tenant_id,
                user_id=user.id,
                company_id=company.id,
                role=user.role,
                permissions=user.permissions if isinstance(user.permissions, dict) else None,
                is_active=True,
            )
        )
    await db.flush()

    p1 = m.Product(
        tenant_id=t1.id,
        company_id=c1.id,
        name="Alpha Widget",
        sku="A-1",
        cost_price=1,
        selling_price=2,
        stock_qty=10,
    )
    p2 = m.Product(
        tenant_id=t2.id,
        company_id=c2.id,
        name="Beta Widget",
        sku="B-1",
        cost_price=1,
        selling_price=2,
        stock_qty=5,
    )
    db.add_all([p1, p2])

    party1 = m.Party(
        tenant_id=t1.id, company_id=c1.id, name="Alpha Customer", kind="customer", credit_limit=100
    )
    party2 = m.Party(
        tenant_id=t2.id, company_id=c2.id, name="Beta Customer", kind="customer", credit_limit=0
    )
    supplier2 = m.Party(
        tenant_id=t2.id, company_id=c2.id, name="Beta Supplier", kind="supplier", credit_limit=0
    )
    db.add_all([party1, party2, supplier2])
    await db.flush()

    inv2 = m.SalesInvoice(
        tenant_id=t2.id,
        company_id=c2.id,
        invoice_number="INV-B-1",
        customer_id=party2.id,
        status="draft",
        subtotal=10,
        tax_amount=0,
        total_amount=10,
    )
    db.add(inv2)
    await db.commit()

    return {
        "t1": t1,
        "t2": t2,
        "c1": c1,
        "c2": c2,
        "u1": u1,
        "u2": u2,
        "mgr1": mgr1,
        "admin1": admin1,
        "super": super_u,
        "super_totp_secret": secret,
        "p1": p1,
        "p2": p2,
        "party1": party1,
        "party2": party2,
        "supplier2": supplier2,
        "inv2": inv2,
    }


@pytest_asyncio.fixture
async def seeded(db_session):
    return await _seed_two_tenants(db_session)


@pytest_asyncio.fixture
async def client(db_engine, seeded, _disable_rate_limit):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    previous_factory = getattr(app.state, "session_factory", None)
    app.state.session_factory = session_factory
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, seeded
    app.dependency_overrides.clear()
    app.state.session_factory = previous_factory


async def auth_headers(client: AsyncClient, *, email: str, tenant_slug: str, totp_code: str | None = None):
    body = {"email": email, "password": "SecurePass123!", "tenant_id": tenant_slug}
    if totp_code:
        body["totp_code"] = totp_code
    r = await client.post("/api/v1/auth/login", json=body)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    if data.get("requires_2fa"):
        raise AssertionError("2FA challenge unexpected without totp_code")
    token = data["access_token"]
    tenant_id = data["user"]["tenant_id"]
    return {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant_id}
