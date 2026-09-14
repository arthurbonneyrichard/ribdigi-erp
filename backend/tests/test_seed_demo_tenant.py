"""Opt-in live customer-demo tenant seed (docs/DEMO_ACCOUNT.md)."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app.demo_tenant_seed import (
    DemoSeedConfig,
    assert_demo_seed_allowed,
    seed_demo_tenant,
)
from app.security import verify_password

ROOT = Path(__file__).resolve().parents[2]
ENV_PROD = ROOT / ".env.production.example"
ENV_DEV = ROOT / ".env.example"
COMPOSE_PROD = ROOT / "docker-compose.prod.yml"
DEMO_DOC = ROOT / "docs" / "DEMO_ACCOUNT.md"


def test_demo_seed_gate_blocks_production_and_requires_flag():
    with pytest.raises(RuntimeError, match="production"):
        assert_demo_seed_allowed(app_env="production", allow_flag=True)
    with pytest.raises(RuntimeError, match="ALLOW_DEMO_TENANT_SEED"):
        assert_demo_seed_allowed(app_env="development", allow_flag=False)
    assert_demo_seed_allowed(app_env="development", allow_flag=True)
    assert_demo_seed_allowed(app_env="staging", allow_flag=True)


def test_prod_templates_keep_demo_seed_and_public_signup_false():
    prod = ENV_PROD.read_text(encoding="utf-8")
    assert "ALLOW_DEMO_TENANT_SEED=false" in prod
    assert "ALLOW_PUBLIC_TENANT_SIGNUP=false" in prod
    compose = COMPOSE_PROD.read_text(encoding="utf-8")
    assert 'ALLOW_DEMO_TENANT_SEED: "false"' in compose
    dev = ENV_DEV.read_text(encoding="utf-8")
    assert "ALLOW_DEMO_TENANT_SEED=false" in dev
    assert DEMO_DOC.is_file()
    doc = DEMO_DOC.read_text(encoding="utf-8")
    assert "owner@demo.ribdigi.app" in doc
    assert "ALLOW_PUBLIC_TENANT_SIGNUP" in doc
    assert "Offline Complete" in doc or "offline_complete" in doc.lower() or "not** Offline" in doc


@pytest.mark.asyncio
async def test_seed_demo_tenant_dry_run_and_create(db_session, monkeypatch):
    monkeypatch.setattr("app.demo_tenant_seed.settings.APP_ENV", "development")
    monkeypatch.setattr("app.demo_tenant_seed.settings.ALLOW_DEMO_TENANT_SEED", True)

    cfg = DemoSeedConfig(
        tenant_slug="demo",
        owner_password="DemoOwner-ChangeMe1!",
        cashier_password="DemoCashier-ChangeMe1!",
        force_password=True,
        include_sample_data=True,
        include_open_shift=True,
    )
    dry = await seed_demo_tenant(db_session, cfg, dry_run=True, commit=False)
    assert dry["dry_run"] is True
    assert dry["would_create_or_refresh"]["tenant_slug"] == "demo"
    assert "password_source" in dry
    assert "DemoOwner-ChangeMe1!" not in str(dry)

    result = await seed_demo_tenant(db_session, cfg, dry_run=False, commit=True)
    assert result["dry_run"] is False
    assert result["tenant_slug"] == "demo"
    assert result["owner_email"] == "owner@demo.ribdigi.app"
    assert result["cashier_email"] == "cashier@demo.ribdigi.app"
    assert result["honesty"]["offline_complete_claimed"] is False
    assert result["honesty"]["go_live_claimed"] is False
    assert result["honesty"]["paid_billing_complete_claimed"] is False
    assert result["honesty"]["store_scoped_rbac_complete_claimed"] is True
    assert "DEMO-001" in (result["sample"]["products"] or [])
    assert result["open_pos_session_id"]

    tenant = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "demo"))
    ).scalar_one()
    owner = (
        await db_session.execute(
            select(m.User).where(
                m.User.tenant_id == tenant.id,
                m.User.email == "owner@demo.ribdigi.app",
            )
        )
    ).scalar_one()
    assert owner.role == "company_admin"
    assert owner.email_verified is True
    assert verify_password("DemoOwner-ChangeMe1!", owner.password_hash)

    store = (
        await db_session.execute(
            select(m.Store).where(
                m.Store.tenant_id == tenant.id,
                m.Store.code == "DEMO-01",
            )
        )
    ).scalar_one()
    assert store.name == "Demo Store"

    products = (
        await db_session.execute(
            select(m.Product).where(m.Product.tenant_id == tenant.id)
        )
    ).scalars().all()
    assert len(products) >= 3

    # Idempotent re-run does not duplicate products
    again = await seed_demo_tenant(db_session, cfg, dry_run=False, commit=True)
    assert again["tenant_id"] == result["tenant_id"]
    products2 = (
        await db_session.execute(
            select(m.Product).where(m.Product.tenant_id == tenant.id)
        )
    ).scalars().all()
    assert len(products2) == len(products)

    open_sessions = (
        await db_session.execute(
            select(m.PosSession).where(
                m.PosSession.tenant_id == tenant.id,
                m.PosSession.status == "open",
            )
        )
    ).scalars().all()
    assert len(open_sessions) == 1
