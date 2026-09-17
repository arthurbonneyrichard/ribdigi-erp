"""Concurrent approval stress pack — no double-approve / double-execute / race.

Covers expense approve/reject and purchase-request approve/convert under near-
simultaneous HTTP calls. Production path uses SELECT FOR UPDATE; in-process
asyncio locks cover SQLite test DB (row locks ignored across StaticPool sessions).
"""

from __future__ import annotations

import asyncio

import pyotp
import pytest
from sqlalchemy import func, select

from app import models as m
from app import purchasing as purchasing_svc
from tests.conftest import auth_headers


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


async def _mgr(ac):
    return await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")


async def _managed_store_and_wh(db_session, seed, *, code_suffix: str) -> tuple[str, str]:
    store = m.Store(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        name=f"Stress Store {code_suffix}",
        code=f"STR-{code_suffix}",
        manager_id=seed["mgr1"].id,
        is_active=True,
    )
    db_session.add(store)
    await db_session.flush()
    wh = m.Warehouse(
        tenant_id=seed["t1"].id,
        company_id=seed["c1"].id,
        store_id=store.id,
        name=f"Stress WH {code_suffix}",
        code=f"WH-{code_suffix}",
        warehouse_type="retail",
        is_active=True,
    )
    db_session.add(wh)
    await db_session.commit()
    return store.id, wh.id


def _statuses(results: list) -> list:
    out = []
    for r in results:
        if isinstance(r, Exception):
            out.append("exc")
        else:
            out.append(r.status_code)
    return out


@pytest.mark.asyncio
async def test_expense_sequential_double_approve_is_409(client, db_session):
    """Idempotency guard: second approve after success must 409 (no second journal)."""
    ac, seed = client
    super_h = await _super(ac, seed)
    mgr_h = await _mgr(ac)
    store_id, _ = await _managed_store_and_wh(db_session, seed, code_suffix="ESEQ")

    settings = await ac.patch(
        "/api/v1/expenses/settings",
        headers=super_h,
        json={"levels": [{"min_amount": 10, "roles": ["store_manager"], "label": "L1"}]},
    )
    assert settings.status_code == 200, settings.text

    created = await ac.post(
        "/api/v1/expenses",
        headers=super_h,
        json={
            "category": "Supplies",
            "amount": 50,
            "payment_method": "cash",
            "description": "seq double-approve",
            "store_id": store_id,
        },
    )
    assert created.status_code == 200, created.text
    eid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "pending"

    first = await ac.post(f"/api/v1/expenses/{eid}/approve", headers=mgr_h, json={})
    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "approved"

    second = await ac.post(f"/api/v1/expenses/{eid}/approve", headers=mgr_h, json={})
    assert second.status_code == 409
    assert "already approved" in str(second.json()["detail"]).lower()

    journals = (
        await db_session.execute(
            select(func.count())
            .select_from(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == seed["t1"].id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == eid,
            )
        )
    ).scalar_one()
    assert int(journals) == 1

    actions = (
        await db_session.execute(
            select(func.count())
            .select_from(m.ExpenseApprovalAction)
            .where(
                m.ExpenseApprovalAction.tenant_id == seed["t1"].id,
                m.ExpenseApprovalAction.expense_id == eid,
                m.ExpenseApprovalAction.action == "approve",
            )
        )
    ).scalar_one()
    assert int(actions) == 1


@pytest.mark.asyncio
async def test_expense_concurrent_double_approve_single_winner(client, db_session):
    """Two near-simultaneous approve calls → exactly one success, one journal."""
    ac, seed = client
    super_h = await _super(ac, seed)
    mgr_h = await _mgr(ac)
    store_id, _ = await _managed_store_and_wh(db_session, seed, code_suffix="ECON")

    settings = await ac.patch(
        "/api/v1/expenses/settings",
        headers=super_h,
        json={"levels": [{"min_amount": 10, "roles": ["store_manager"], "label": "L1"}]},
    )
    assert settings.status_code == 200, settings.text

    created = await ac.post(
        "/api/v1/expenses",
        headers=super_h,
        json={
            "category": "Utilities",
            "amount": 75,
            "payment_method": "cash",
            "description": "concurrent double-approve",
            "store_id": store_id,
        },
    )
    assert created.status_code == 200, created.text
    eid = created.json()["data"]["id"]

    results = await asyncio.gather(
        ac.post(f"/api/v1/expenses/{eid}/approve", headers=mgr_h, json={}),
        ac.post(f"/api/v1/expenses/{eid}/approve", headers=mgr_h, json={}),
        return_exceptions=True,
    )
    statuses = _statuses(results)
    successes = sum(1 for s in statuses if s == 200)
    # Loser may be 409 (already approved) or 403 (same actor already acted).
    losers = sum(1 for s in statuses if s in {403, 409})
    assert successes == 1, statuses
    assert losers >= 1, statuses

    expense = await db_session.get(m.Expense, eid)
    await db_session.refresh(expense)
    assert expense.status == "approved"

    journals = (
        await db_session.execute(
            select(func.count())
            .select_from(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == seed["t1"].id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == eid,
            )
        )
    ).scalar_one()
    assert int(journals) == 1


@pytest.mark.asyncio
async def test_expense_concurrent_approve_vs_reject_single_terminal(client, db_session):
    """Approve vs reject race → exactly one terminal status (approved or rejected)."""
    ac, seed = client
    super_h = await _super(ac, seed)
    mgr_h = await _mgr(ac)
    store_id, _ = await _managed_store_and_wh(db_session, seed, code_suffix="EAR")

    settings = await ac.patch(
        "/api/v1/expenses/settings",
        headers=super_h,
        json={"levels": [{"min_amount": 10, "roles": ["store_manager"], "label": "L1"}]},
    )
    assert settings.status_code == 200, settings.text

    created = await ac.post(
        "/api/v1/expenses",
        headers=super_h,
        json={
            "category": "Marketing",
            "amount": 40,
            "payment_method": "cash",
            "description": "approve vs reject race",
            "store_id": store_id,
        },
    )
    assert created.status_code == 200, created.text
    eid = created.json()["data"]["id"]

    results = await asyncio.gather(
        ac.post(f"/api/v1/expenses/{eid}/approve", headers=mgr_h, json={}),
        ac.post(
            f"/api/v1/expenses/{eid}/reject",
            headers=mgr_h,
            json={"reason": "race reject"},
        ),
        return_exceptions=True,
    )
    statuses = _statuses(results)
    successes = sum(1 for s in statuses if s == 200)
    assert successes == 1, statuses

    expense = await db_session.get(m.Expense, eid)
    await db_session.refresh(expense)
    assert expense.status in {"approved", "rejected"}

    journals = (
        await db_session.execute(
            select(func.count())
            .select_from(m.JournalEntry)
            .where(
                m.JournalEntry.tenant_id == seed["t1"].id,
                m.JournalEntry.source_type == "expense",
                m.JournalEntry.source_id == eid,
            )
        )
    ).scalar_one()
    if expense.status == "approved":
        assert int(journals) == 1
    else:
        assert int(journals) == 0


@pytest.mark.asyncio
async def test_pr_concurrent_double_approve_single_winner(client, db_session):
    """Two near-simultaneous PR approve calls → exactly one success / one action."""
    ac, seed = client
    super_h = await _super(ac, seed)
    mgr_h = await _mgr(ac)
    _, warehouse_id = await _managed_store_and_wh(db_session, seed, code_suffix="PRAP")

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    await purchasing_svc.update_pr_approval_settings(
        db_session,
        tenant,
        levels=[{"min_amount": 0.01, "roles": ["store_manager"], "label": "L1"}],
    )
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers", headers=super_h, json={"name": "Stress PR Sup"}
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=super_h,
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    pr_id = created.json()["data"]["id"]
    submitted = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/submit", headers=super_h)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["data"]["status"] == "pending"

    results = await asyncio.gather(
        ac.post(f"/api/v1/purchasing/requests/{pr_id}/approve", headers=mgr_h),
        ac.post(f"/api/v1/purchasing/requests/{pr_id}/approve", headers=mgr_h),
        return_exceptions=True,
    )
    statuses = _statuses(results)
    successes = sum(1 for s in statuses if s == 200)
    assert successes == 1, statuses

    pr = await db_session.get(m.PurchaseRequest, pr_id)
    await db_session.refresh(pr)
    assert pr.status == "approved"

    actions = (
        await db_session.execute(
            select(func.count())
            .select_from(m.PurchaseRequestApprovalAction)
            .where(
                m.PurchaseRequestApprovalAction.tenant_id == seed["t1"].id,
                m.PurchaseRequestApprovalAction.purchase_request_id == pr_id,
                m.PurchaseRequestApprovalAction.action == "approve",
            )
        )
    ).scalar_one()
    assert int(actions) == 1


@pytest.mark.asyncio
async def test_pr_concurrent_convert_single_po(client, db_session):
    """Two near-simultaneous PR→PO converts → exactly one PO (no double-execute)."""
    ac, seed = client
    super_h = await _super(ac, seed)
    mgr_h = await _mgr(ac)
    _, warehouse_id = await _managed_store_and_wh(db_session, seed, code_suffix="PRCV")

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    await purchasing_svc.update_pr_approval_settings(
        db_session,
        tenant,
        levels=[{"min_amount": 0.01, "roles": ["store_manager"], "label": "L1"}],
    )
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers", headers=super_h, json={"name": "Stress Convert Sup"}
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=super_h,
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 3, "unit_price": 5}],
        },
    )
    assert created.status_code == 200, created.text
    pr_id = created.json()["data"]["id"]
    submitted = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/submit", headers=super_h)
    assert submitted.status_code == 200, submitted.text
    approved = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/approve", headers=mgr_h)
    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["status"] == "approved"

    results = await asyncio.gather(
        ac.post(f"/api/v1/purchasing/requests/{pr_id}/convert", headers=super_h),
        ac.post(f"/api/v1/purchasing/requests/{pr_id}/convert", headers=super_h),
        return_exceptions=True,
    )
    statuses = _statuses(results)
    successes = sum(1 for s in statuses if s == 200)
    conflicts = sum(1 for s in statuses if s == 409)
    assert successes == 1, statuses
    assert conflicts >= 1, statuses

    pr = await db_session.get(m.PurchaseRequest, pr_id)
    await db_session.refresh(pr)
    assert pr.status == "converted"
    assert pr.purchase_order_id is not None

    po_count = (
        await db_session.execute(
            select(func.count())
            .select_from(m.PurchaseOrder)
            .where(
                m.PurchaseOrder.tenant_id == seed["t1"].id,
                m.PurchaseOrder.purchase_request_id == pr_id,
            )
        )
    ).scalar_one()
    assert int(po_count) == 1


@pytest.mark.asyncio
async def test_pr_sequential_double_convert_is_409(client, db_session):
    """Idempotency guard: second convert after success must 409."""
    ac, seed = client
    super_h = await _super(ac, seed)
    mgr_h = await _mgr(ac)
    _, warehouse_id = await _managed_store_and_wh(db_session, seed, code_suffix="PRSQ")

    tenant = await db_session.get(m.Tenant, seed["t1"].id)
    await purchasing_svc.update_pr_approval_settings(
        db_session,
        tenant,
        levels=[{"min_amount": 0.01, "roles": ["store_manager"], "label": "L1"}],
    )
    await db_session.commit()

    supplier = await ac.post(
        "/api/v1/suppliers", headers=super_h, json={"name": "Stress Seq Convert Sup"}
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/requests",
        headers=super_h,
        json={
            "supplier_id": supplier_id,
            "warehouse_id": warehouse_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert created.status_code == 200, created.text
    pr_id = created.json()["data"]["id"]
    assert (
        await ac.post(f"/api/v1/purchasing/requests/{pr_id}/submit", headers=super_h)
    ).status_code == 200
    assert (
        await ac.post(f"/api/v1/purchasing/requests/{pr_id}/approve", headers=mgr_h)
    ).status_code == 200

    first = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/convert", headers=super_h)
    assert first.status_code == 200, first.text
    second = await ac.post(f"/api/v1/purchasing/requests/{pr_id}/convert", headers=super_h)
    assert second.status_code == 409

    po_count = (
        await db_session.execute(
            select(func.count())
            .select_from(m.PurchaseOrder)
            .where(
                m.PurchaseOrder.tenant_id == seed["t1"].id,
                m.PurchaseOrder.purchase_request_id == pr_id,
            )
        )
    ).scalar_one()
    assert int(po_count) == 1
