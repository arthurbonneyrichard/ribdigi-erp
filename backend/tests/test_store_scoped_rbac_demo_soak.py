"""Local demo-seed membership-scope soak for store-scoped RBAC Complete.

Seeds the opt-in demo tenant and exercises STORE_MEMBERSHIP_SCOPE_ENABLED=true
against demo memberships. Complete ≠ production default ON.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app import models as m
from app import store_memberships as store_memberships_svc
from app.demo_tenant_seed import DemoSeedConfig, seed_demo_tenant
from app.rbac import permissions_for_role
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "docs" / "STORE_SCOPED_RBAC_INTENTIONAL_ALLOWS.md"
LOCAL_EVIDENCE = ROOT / "docs" / "STORE_SCOPED_RBAC_LOCAL_SOAK_EVIDENCE.md"
REMAINING = ROOT / "docs" / "STORE_SCOPED_RBAC_COMPLETE_REMAINING.md"
MARKET = ROOT / "docs" / "MARKET_READY_LAUNCH.md"

pytestmark = pytest.mark.store_scope


def _enable_membership_scope(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.config.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )
    monkeypatch.setattr(
        "app.dashboard_scope.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )
    monkeypatch.setattr(
        "app.store_memberships.settings.STORE_MEMBERSHIP_SCOPE_ENABLED", True
    )


def test_store_scoped_complete_docs_and_allow_policy_present():
    assert POLICY.is_file()
    policy = POLICY.read_text(encoding="utf-8")
    assert "ACCEPT" in policy
    assert "logo" in policy.lower()
    assert "/auth/sessions" in policy
    assert "/notifications/settings" in policy

    assert LOCAL_EVIDENCE.is_file()
    evidence = LOCAL_EVIDENCE.read_text(encoding="utf-8")
    assert "STORE_MEMBERSHIP_SCOPE_ENABLED" in evidence
    assert "PASS" in evidence

    assert REMAINING.is_file()
    remaining = REMAINING.read_text(encoding="utf-8")
    assert "**Complete**" in remaining
    assert "EMPTY" in remaining
    assert "store_scoped_rbac_complete_claimed` = **true**" in remaining

    assert MARKET.is_file()
    market = MARKET.read_text(encoding="utf-8")
    assert "market-ready with conditions" in market.lower()
    assert "DEMO_ACCOUNT.md" in market
    assert "Offline Complete" in market


def test_store_scoped_complete_honesty_true_flag_default_off():
    honesty = store_memberships_svc.honesty_payload()
    assert honesty["adr005_complete_claimed"] is True
    assert honesty["store_scoped_rbac_complete_claimed"] is True
    assert store_memberships_svc.STORE_SCOPED_RBAC_COMPLETE_CLAIMED is True
    assert honesty["store_membership_scope_enabled"] is False
    assert "production_default_flag_remains_off" in (honesty.get("complete_means") or "")


@pytest.mark.asyncio
async def test_store_scoped_demo_seed_membership_scope_soak(
    client, db_session, monkeypatch
):
    """Demo seed + flag ON: cashier sees assigned store only; honesty Complete."""
    monkeypatch.setattr("app.demo_tenant_seed.settings.APP_ENV", "development")
    monkeypatch.setattr("app.demo_tenant_seed.settings.ALLOW_DEMO_TENANT_SEED", True)
    _enable_membership_scope(monkeypatch)

    # Use fixture password so auth_headers works without extending conftest.
    cfg = DemoSeedConfig(
        tenant_slug="demo-soak",
        owner_email="owner@demo-soak.ribdigi.app",
        cashier_email="cashier@demo-soak.ribdigi.app",
        owner_password="SecurePass123!",
        cashier_password="SecurePass123!",
        force_password=True,
        include_sample_data=True,
        include_open_shift=True,
    )
    result = await seed_demo_tenant(db_session, cfg, dry_run=False, commit=True)
    assert result["honesty"]["store_scoped_rbac_complete_claimed"] is True
    assert result["honesty"]["offline_complete_claimed"] is False
    assert result["honesty"]["go_live_claimed"] is False
    assert result["honesty"].get("market_ready_conditional") is True

    tenant = (
        await db_session.execute(select(m.Tenant).where(m.Tenant.slug == "demo-soak"))
    ).scalar_one()
    company = (
        await db_session.execute(
            select(m.Company).where(m.Company.tenant_id == tenant.id)
        )
    ).scalar_one()
    demo_store = (
        await db_session.execute(
            select(m.Store).where(
                m.Store.tenant_id == tenant.id,
                m.Store.code == "DEMO-01",
            )
        )
    ).scalar_one()
    foreign = m.Store(
        tenant_id=tenant.id,
        company_id=company.id,
        name="Foreign Store",
        code="FOREIGN-01",
        is_active=True,
    )
    db_session.add(foreign)

    cashier = (
        await db_session.execute(
            select(m.User).where(
                m.User.tenant_id == tenant.id,
                m.User.email == cfg.cashier_email,
            )
        )
    ).scalar_one()
    perms = dict(permissions_for_role("cashier"))
    perms["stores"] = ["read"]
    cashier.permissions = perms
    mem = (
        await db_session.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.user_id == cashier.id,
                m.UserCompanyMembership.company_id == company.id,
            )
        )
    ).scalar_one()
    mem.permissions = perms
    await db_session.commit()

    ac, _seed = client
    headers = await auth_headers(
        ac, email=cfg.cashier_email, tenant_slug="demo-soak"
    )

    me = await ac.get("/api/v1/me/store-memberships", headers=headers)
    assert me.status_code == 200, me.text
    payload = me.json()["data"]
    assert payload["store_membership_scope_enabled"] is True
    assert payload["adr005_complete_claimed"] is True
    assert payload["store_scoped_rbac_complete_claimed"] is True
    assert payload["pos_store_bind_required"] is True
    assert any(r["store_id"] == demo_store.id for r in payload["memberships"])

    stores = await ac.get("/api/v1/stores", headers=headers)
    assert stores.status_code == 200, stores.text
    store_ids = {row["id"] for row in stores.json()["data"]}
    assert demo_store.id in store_ids
    assert foreign.id not in store_ids
