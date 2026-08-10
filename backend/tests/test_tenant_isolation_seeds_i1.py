"""Stage 21 I1: Tenant isolation & init seeds fidelity (BR-1.4–1.5)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_cross_tenant_isolation_and_header_validation(client):
    """BR-1.4: Tenant A cannot read Tenant B; mismatched X-Tenant-ID denied."""
    ac, seed = client
    headers = await _mgr(ac)

    products = await ac.get("/api/v1/products", headers=headers)
    assert products.status_code == 200, products.text
    names = {p["name"] for p in products.json()["data"]}
    assert "Alpha Widget" in names
    assert "Beta Widget" not in names

    foreign = await ac.get(f"/api/v1/sales/invoices/{seed['inv2'].id}", headers=headers)
    assert foreign.status_code == 404

    bad = {**headers, "X-Tenant-ID": seed["t2"].id}
    denied = await ac.get("/api/v1/products", headers=bad)
    assert denied.status_code == 403
    assert "Cross-tenant" in denied.json()["detail"]

    # Shared-schema honesty: both tenants share tables keyed by tenant_id (ADR-001)
    assert seed["t1"].id != seed["t2"].id
    assert seed["p1"].tenant_id == seed["t1"].id
    assert seed["p2"].tenant_id == seed["t2"].id


@pytest.mark.asyncio
async def test_registration_seeds_coa_tax_uom_expense_categories(client, db_session):
    """BR-1.5: registration seeds COA, tax rates, UoM, expense categories (+ warehouse)."""
    ac, _seed = client
    created = await ac.post(
        "/api/v1/tenants",
        json={
            "company_name": "Delta Seeds Co",
            "slug": "delta-i1",
            "industry": "manufacturing",
            "currency": "GHS",
            "admin_email": "admin@delta-i1.example.com",
            "admin_password": "SecurePass123!",
            "admin_full_name": "Delta Admin",
        },
    )
    assert created.status_code == 200, created.text
    tenant_id = created.json()["data"]["tenant_id"]
    assert created.json()["data"]["status"] == "trial"

    accounts = (
        await db_session.execute(select(m.Account).where(m.Account.tenant_id == tenant_id))
    ).scalars().all()
    codes = {a.code for a in accounts}
    assert "1000" in codes  # Cash
    assert "1010" in codes  # Bank
    assert len(accounts) >= 5

    taxes = (
        await db_session.execute(select(m.TaxRate).where(m.TaxRate.tenant_id == tenant_id))
    ).scalars().all()
    assert taxes
    assert any(t.is_default and float(t.rate or 0) > 0 for t in taxes)

    units = (
        await db_session.execute(
            select(m.UnitOfMeasure).where(m.UnitOfMeasure.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert units
    assert {u.code for u in units}

    cats = (
        await db_session.execute(
            select(m.ExpenseCategory).where(m.ExpenseCategory.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert cats
    assert any(c.name for c in cats)

    warehouses = (
        await db_session.execute(select(m.Warehouse).where(m.Warehouse.tenant_id == tenant_id))
    ).scalars().all()
    assert any(w.code == "WH-MAIN" for w in warehouses)

    # Seeds are tenant-scoped (no beta leakage into new tenant)
    assert all(a.tenant_id == tenant_id for a in accounts)
    assert all(t.tenant_id == tenant_id for t in taxes)


@pytest.mark.asyncio
async def test_backup_operations_are_tenant_scoped(client, db_session, tmp_path, monkeypatch):
    """BR-1.4: backup create/list/get stay on caller's tenant."""
    monkeypatch.setattr("app.backup.settings.BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr("app.backup.settings.BACKUP_ENCRYPTION_KEY", "")
    monkeypatch.setattr("app.config.settings.BACKUP_DIR", str(tmp_path))

    ac, seed = client
    headers = await _super(ac, seed)

    created = await ac.post(
        "/api/v1/backup",
        headers=headers,
        json={"notes": "Stage 21 I1 isolation"},
    )
    assert created.status_code == 200, created.text
    backup_id = created.json()["data"]["id"]
    assert created.json()["data"]["tenant_id"] == seed["t1"].id

    listed = await ac.get("/api/v1/backup", headers=headers)
    assert listed.status_code == 200, listed.text
    ids = {row["id"] for row in listed.json()["data"]}
    assert backup_id in ids

    # Plant beta backup job; alpha cannot fetch it
    beta_job = m.BackupJob(
        tenant_id=seed["t2"].id,
        filename="beta-secret.ribbak",
        status="completed",
        size_bytes=12,
        checksum_sha256="abc",
        storage_path="unused",
        notes="beta",
        created_by=seed["u2"].id,
    )
    db_session.add(beta_job)
    await db_session.commit()
    await db_session.refresh(beta_job)

    missing = await ac.get(f"/api/v1/backup/{beta_job.id}", headers=headers)
    assert missing.status_code == 404

    bad = {**headers, "X-Tenant-ID": seed["t2"].id}
    denied = await ac.get("/api/v1/backup", headers=bad)
    assert denied.status_code == 403
    assert "Cross-tenant" in denied.json()["detail"]


def test_br_1_4_1_5_and_plan_synced():
    br = (ROOT / "docs" / "BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    s14 = br.split("#### BR-1.4 Data Isolation")[1].split("#### BR-1.5")[0]
    assert "[x] Tenant A cannot access Tenant B data under any circumstance" in s14
    assert "[x] Database-level isolation" in s14
    assert "[x] API requests include tenant context validation" in s14
    assert "[x] Backup operations are tenant-scoped" in s14
    assert "Stage 21 I1" in s14
    assert "test_tenant_isolation_seeds_i1.py" in s14
    assert "ADR-001" in s14 or "shared-schema" in s14

    s15 = br.split("#### BR-1.5 Tenant Database Initialization")[1].split("### 4.2")[0]
    assert "[x] Auto-create schema/tables on registration" in s15
    assert "[x] Seed default chart of accounts" in s15
    assert "[x] Seed default tax rates" in s15
    assert "[x] Seed default units of measure" in s15
    assert "[x] Seed default expense categories" in s15
    assert "Stage 21 I1" in s15
    assert "seed_tenant_defaults" in s15 or "POST /tenants" in s15

    plan = (ROOT / "docs" / "STAGE_21_PLAN.md").read_text(encoding="utf-8")
    i1_line = [ln for ln in plan.splitlines() if "| **I1**" in ln][0]
    assert "COMPLETE" in i1_line
    assert "test_tenant_isolation_seeds_i1.py" in plan
