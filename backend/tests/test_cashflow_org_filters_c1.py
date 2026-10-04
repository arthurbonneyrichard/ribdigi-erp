"""Cash flow store / branch filters (BR-14.5)."""

from __future__ import annotations

import pyotp
import pytest

from app import models as m
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_cash_flow_store_and_branch_filters(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    tenant = seed["t1"]
    # Auto-approve expenses so journals post immediately
    tenant.expense_approval_threshold = 10_000
    tenant.expense_l2_threshold = 10_000
    tenant.expense_approval_matrix = None
    await db_session.flush()

    branch = m.Branch(tenant_id=tenant.id, code="CF-N", name="CF North")
    db_session.add(branch)
    await db_session.flush()
    store_a = m.Store(
        tenant_id=tenant.id, code="CF-A", name="CF Store A", branch_id=branch.id, is_active=True
    )
    store_b = m.Store(
        tenant_id=tenant.id, code="CF-B", name="CF Store B", branch_id=None, is_active=True
    )
    db_session.add_all([store_a, store_b])
    await db_session.commit()

    # HQ financing (unattributable when filtered)
    liq = await ac.get("/api/v1/accounting/liquid-accounts", headers=headers)
    assert liq.status_code == 200, liq.text
    cash_id = next(a["id"] for a in liq.json()["data"] if a["code"] == "1000")
    dep = await ac.post(
        "/api/v1/accounting/transfers",
        headers=headers,
        json={"kind": "deposit", "to_account_id": cash_id, "amount": 900, "reference": "HQ"},
    )
    assert dep.status_code == 200, dep.text

    exp_a = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 40,
            "category": "Supplies",
            "description": "Store A cash out",
            "payment_method": "cash",
            "store_id": store_a.id,
        },
    )
    assert exp_a.status_code == 200, exp_a.text
    assert exp_a.json()["data"]["status"] == "approved"

    exp_b = await ac.post(
        "/api/v1/expenses",
        headers=headers,
        json={
            "amount": 25,
            "category": "Supplies",
            "description": "Store B cash out",
            "payment_method": "cash",
            "store_id": store_b.id,
        },
    )
    assert exp_b.status_code == 200, exp_b.text

    all_cf = await ac.get("/api/v1/reports/cash-flow", headers=headers)
    assert all_cf.status_code == 200, all_cf.text
    all_data = all_cf.json()["data"]
    assert float(all_data["financing"]["inflows"]) >= 900
    assert float(all_data["operating"]["outflows"]) >= 65

    filtered_a = await ac.get(
        f"/api/v1/reports/cash-flow?store_id={store_a.id}", headers=headers
    )
    assert filtered_a.status_code == 200, filtered_a.text
    a_data = filtered_a.json()["data"]
    assert a_data["store_id"] == store_a.id
    assert a_data["mode"] == "journals"
    assert abs(float(a_data["operating"]["outflows"]) - 40) < 0.01
    # HQ deposit omitted under location filter
    assert abs(float(a_data["financing"]["inflows"])) < 0.01
    assert abs(float(a_data["transfers"]["inflows"])) < 0.01

    filtered_b = await ac.get(
        f"/api/v1/reports/cash-flow?store_id={store_b.id}", headers=headers
    )
    assert filtered_b.status_code == 200
    b_data = filtered_b.json()["data"]
    assert abs(float(b_data["operating"]["outflows"]) - 25) < 0.01

    by_branch = await ac.get(
        f"/api/v1/reports/cash-flow?branch_id={branch.id}", headers=headers
    )
    assert by_branch.status_code == 200, by_branch.text
    br = by_branch.json()["data"]
    assert br["branch_id"] == branch.id
    assert abs(float(br["operating"]["outflows"]) - 40) < 0.01

    bad = await ac.get(
        "/api/v1/reports/cash-flow?store_id=00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert bad.status_code == 404
