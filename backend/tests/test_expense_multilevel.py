"""Multi-level expense approval tests."""

import pytest
from fastapi import HTTPException

from app import expenses as expenses_svc
from app import models as m


def test_steps_required_matrix():
    assert expenses_svc.steps_required_for_amount(50, auto_threshold=100, l2_threshold=1000) == 0
    assert expenses_svc.steps_required_for_amount(150, auto_threshold=100, l2_threshold=1000) == 1
    assert expenses_svc.steps_required_for_amount(1500, auto_threshold=100, l2_threshold=1000) == 2


def test_steps_required_from_n_level_matrix():
    levels = expenses_svc.normalize_approval_matrix(
        {
            "levels": [
                {"min_amount": 50, "roles": ["store_manager"], "label": "L1"},
                {"min_amount": 500, "roles": ["accountant"], "label": "L2"},
                {"min_amount": 5000, "roles": ["company_admin"], "label": "L3"},
            ]
        }
    )
    assert expenses_svc.steps_required_from_matrix(40, levels) == 0
    assert expenses_svc.steps_required_from_matrix(100, levels) == 1
    assert expenses_svc.steps_required_from_matrix(600, levels) == 2
    assert expenses_svc.steps_required_from_matrix(6000, levels) == 3


def test_normalize_rejects_non_increasing():
    with pytest.raises(HTTPException) as exc:
        expenses_svc.normalize_approval_matrix(
            {
                "levels": [
                    {"min_amount": 100, "roles": ["store_manager"]},
                    {"min_amount": 50, "roles": ["company_admin"]},
                ]
            }
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_two_level_approval_flow(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    tenant.expense_approval_threshold = 100
    tenant.expense_l2_threshold = 1000
    await db_session.flush()

    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["u1"].id,  # cashier creates
        amount=1500,
        category="Supplies",
        description="Big order",
        payment_method="bank_transfer",
    )
    assert expense.status == "pending"
    assert expense.approval_steps_required == 2
    assert expense.approval_step == 1

    # Manager does L1
    mid = await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["mgr1"].id,
        expense_id=expense.id,
        comment="OK L1",
        actor_role="store_manager",
    )
    assert mid.status == "pending"
    assert mid.approval_step == 2

    # Manager cannot do L2
    with pytest.raises(HTTPException) as blocked:
        await expenses_svc.approve_expense(
            db_session,
            tenant_id=tenant_id,
            user_id=seeded["mgr1"].id,
            expense_id=expense.id,
            actor_role="store_manager",
        )
    assert blocked.value.status_code == 403

    # Admin does L2
    final = await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        expense_id=expense.id,
        comment="OK L2",
        actor_role="company_admin",
    )
    await db_session.commit()
    assert final.status == "approved"
    actions = await expenses_svc.list_approval_actions(db_session, tenant_id, expense.id)
    assert [a.action for a in actions] == ["approve", "approve"]
    assert [a.step for a in actions] == [1, 2]


@pytest.mark.asyncio
async def test_cannot_approve_own_expense(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    tenant.expense_approval_threshold = 10
    await db_session.flush()

    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["mgr1"].id,
        amount=50,
        category="Misc",
        description="Self",
    )
    with pytest.raises(HTTPException) as exc:
        await expenses_svc.approve_expense(
            db_session,
            tenant_id=tenant_id,
            user_id=seeded["mgr1"].id,
            expense_id=expense.id,
            actor_role="store_manager",
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_three_level_matrix_and_role_gate(db_session, seeded):
    tenant_id = seeded["t1"].id
    tenant = await db_session.get(m.Tenant, tenant_id)
    await expenses_svc.update_approval_settings(
        db_session,
        tenant,
        levels=[
            {
                "min_amount": 100,
                "roles": ["store_manager"],
                "label": "Manager",
            },
            {
                "min_amount": 1000,
                "roles": ["company_admin"],
                "label": "Admin",
            },
            {
                "min_amount": 5000,
                "roles": ["super_admin"],
                "label": "Super",
            },
        ],
    )
    await db_session.flush()

    expense = await expenses_svc.create_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["u1"].id,
        amount=6000,
        category="Capex",
        description="Server rack",
    )
    assert expense.approval_steps_required == 3

    # Wrong role for L1
    with pytest.raises(HTTPException) as denied:
        await expenses_svc.approve_expense(
            db_session,
            tenant_id=tenant_id,
            user_id=seeded["admin1"].id,
            expense_id=expense.id,
            actor_role="company_admin",
        )
    assert denied.value.status_code == 403

    await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["mgr1"].id,
        expense_id=expense.id,
        actor_role="store_manager",
    )
    await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["admin1"].id,
        expense_id=expense.id,
        actor_role="company_admin",
    )
    final = await expenses_svc.approve_expense(
        db_session,
        tenant_id=tenant_id,
        user_id=seeded["super"].id,
        expense_id=expense.id,
        actor_role="super_admin",
    )
    await db_session.commit()
    assert final.status == "approved"
    actions = await expenses_svc.list_approval_actions(db_session, tenant_id, expense.id)
    assert [a.step for a in actions] == [1, 2, 3]


@pytest.mark.asyncio
async def test_threshold_patch_preserves_compat_columns(db_session, seeded):
    tenant = seeded["t1"]
    data = await expenses_svc.update_approval_settings(
        db_session,
        tenant,
        expense_approval_threshold=200,
        expense_l2_threshold=2500,
    )
    await db_session.commit()
    assert data["expense_approval_threshold"] == 200
    assert data["expense_l2_threshold"] == 2500
    assert len(data["levels"]) == 2
    assert float(tenant.expense_approval_threshold) == 200
    assert float(tenant.expense_l2_threshold) == 2500
    assert tenant.expense_approval_matrix is not None
