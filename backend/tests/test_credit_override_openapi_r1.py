"""CreditOverrideReasonValue OpenAPI honesty (BR-11.1)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app import models as m
from app.schemas import CreditLimitOverrideBody, PosSaleCreate, TransactionCreate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "cls,extra",
    [
        (CreditLimitOverrideBody, {}),
        (TransactionCreate, {"items": []}),
        (
            PosSaleCreate,
            {"items": [{"product_id": "p1", "quantity": 1}]},
        ),
    ],
)
def test_credit_override_reason_schema(cls, extra):
    ok = cls.model_validate(
        {
            **extra,
            "override_credit_limit": True,
            "override_reason": "  Manager approved VIP  ",
        }
    )
    assert ok.override_credit_limit is True
    assert ok.override_reason == "Manager approved VIP"

    # Flag false — reason optional
    cls.model_validate({**extra, "override_credit_limit": False})

    with pytest.raises(ValidationError) as missing:
        cls.model_validate({**extra, "override_credit_limit": True})
    assert "override_reason" in str(missing.value).lower()

    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            cls.model_validate(
                {
                    **extra,
                    "override_credit_limit": True,
                    "override_reason": bad,
                }
            )
        # Garbage still 422 even when not overriding
        with pytest.raises(ValidationError):
            cls.model_validate(
                {
                    **extra,
                    "override_credit_limit": False,
                    "override_reason": bad,
                }
            )


def test_credit_override_reason_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Credit override reason"' in sales
    assert "aria-label={`Post sales invoice ${inv.id}`}" in sales
    assert 'aria-label="Credit override reason"' in pos
    assert "creditOverrideReason" in sales and "creditOverrideReason" in pos
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "CreditOverrideReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "CreditOverrideReasonValue" in docs
    brd = (ROOT / "docs/BUSINESS_REQUIREMENTS_DOCUMENT.md").read_text(encoding="utf-8")
    assert "CreditOverrideReasonValue" in brd


@pytest.mark.asyncio
async def test_credit_override_reason_api_blank_invalid_422(client, db_session):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    stock = await ac.post(
        "/api/v1/inventory/stock-in",
        headers=headers,
        json={"product_id": seed["p1"].id, "quantity": 20},
    )
    assert stock.status_code == 200, stock.text

    cust = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Tip209 Override Buyer", "credit_limit": 10},
    )
    assert cust.status_code == 200, cust.text
    customer_id = cust.json()["data"]["id"]

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 40}],
        },
    )
    assert inv.status_code == 200, inv.text
    invoice_id = inv.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/sales/invoices/{invoice_id}/post",
            headers=headers,
            json={"override_credit_limit": True, "override_reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    posted = await ac.post(
        f"/api/v1/sales/invoices/{invoice_id}/post",
        headers=headers,
        json={
            "override_credit_limit": True,
            "override_reason": "Tip209 manager approved — API hello-world",
        },
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["data"].get("credit_limit_overridden") is True

    audits = (
        await db_session.execute(
            select(m.AuditLog).where(
                m.AuditLog.tenant_id == seed["t1"].id,
                m.AuditLog.action == "credit_limit_override",
                m.AuditLog.entity_id == customer_id,
            )
        )
    ).scalars().all()
    assert len(audits) >= 1
    assert audits[-1].details.get("reason") == "Tip209 manager approved — API hello-world"
