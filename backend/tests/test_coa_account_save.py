"""COA create/edit save: session company, unique code, parent, extra-forbid."""

from __future__ import annotations

import inspect
from uuid import uuid4

import pyotp
import pytest

from app import cash_transfers as cash_xfer_svc
from tests.conftest import auth_headers


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


def test_create_account_uses_live_insert_not_orm_add():
    src = inspect.getsource(cash_xfer_svc.create_account)
    assert "insert_and_get" in src
    assert "ensure_tenant_company" in src or "_session_company_id" in src
    assert "db.add(row)" not in src


@pytest.mark.asyncio
async def test_create_gl_account_rejects_client_company_and_maps_unique(client):
    ac, seed = client
    headers = await _admin(ac, seed)
    assert (await ac.get("/api/v1/accounting/accounts", headers=headers)).status_code == 200

    created = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "6105", "name": "Shop Rent", "account_type": "expense"},
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["code"] == "6105"
    assert data["account_type"] == "expense"
    assert data["is_cash_account"] is False
    assert data["is_bank_account"] is False

    extra = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "6106",
            "name": "Utilities",
            "account_type": "expense",
            "company_id": str(uuid4()),
            "tenant_id": str(uuid4()),
        },
    )
    assert extra.status_code == 422, extra.text

    dup = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={"code": "6105", "name": "Shop Rent Dup", "account_type": "expense"},
    )
    assert dup.status_code == 409, dup.text
    detail = dup.json()["detail"]
    if isinstance(detail, list):
        fields = {
            item.get("loc", [None])[-1]
            for item in detail
            if isinstance(item, dict)
        }
        assert "code" in fields
    else:
        assert "code" in str(detail).lower() or "already" in str(detail).lower()

    parent_id = data["id"]
    child = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "6107",
            "name": "Warehouse Rent",
            "account_type": "expense",
            "parent_id": parent_id,
        },
    )
    assert child.status_code == 200, child.text

    cash = next(
        a
        for a in (await ac.get("/api/v1/accounting/accounts", headers=headers)).json()["data"]
        if a["code"] == "1000"
    )
    mismatch = await ac.post(
        "/api/v1/accounting/accounts",
        headers=headers,
        json={
            "code": "6108",
            "name": "Wrong Parent Rent",
            "account_type": "expense",
            "parent_id": cash["id"],
        },
    )
    assert mismatch.status_code == 400, mismatch.text

    patched = await ac.patch(
        f"/api/v1/accounting/accounts/{data['id']}",
        headers=headers,
        json={"name": "Shop Rent Updated"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["name"] == "Shop Rent Updated"
    assert patched.json()["data"]["code"] == "6105"
