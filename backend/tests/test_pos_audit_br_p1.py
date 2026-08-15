"""POS payment method aliases + product audit before/after (BR-8.1 / BR-17.1)."""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select

from app import models as m
from app.pos import normalize_payment_method
from tests.conftest import auth_headers


def test_normalize_payment_method_aliases():
    assert normalize_payment_method("cash") == "cash"
    assert normalize_payment_method("CARD") == "card"
    assert normalize_payment_method("wallet") == "wallet"
    assert normalize_payment_method("digital_wallet") == "wallet"
    assert normalize_payment_method("digital-wallet") == "wallet"
    assert normalize_payment_method("mobile_money") == "wallet"
    assert normalize_payment_method("MoMo") == "wallet"
    assert normalize_payment_method("credit") == "credit"
    assert normalize_payment_method("weird") == "other"


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_product_update_audit_includes_before_after(client, db_session):
    ac, seed = client
    headers = await _admin(ac, seed)
    product = seed["p1"]
    old_name = product.name

    patched = await ac.patch(
        f"/api/v1/products/{product.id}",
        headers=headers,
        json={"name": "Audit Before After Widget", "selling_price": 9.5},
    )
    assert patched.status_code == 200, patched.text

    row = (
        await db_session.execute(
            select(m.AuditLog)
            .where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "product_update",
                m.AuditLog.entity_id == product.id,
            )
            .order_by(m.AuditLog.created_at.desc())
        )
    ).scalars().first()
    assert row is not None
    changes = (row.details or {}).get("changes") or {}
    assert "name" in changes
    assert changes["name"]["before"] == old_name
    assert changes["name"]["after"] == "Audit Before After Widget"
    assert "selling_price" in changes
    assert float(changes["selling_price"]["after"]) == 9.5
