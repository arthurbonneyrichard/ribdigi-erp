"""GET /webhooks/{id}/deliveries status Query OpenAPI + Integrations filter (BR-18.6)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import WebhookDeliveryStatusFilterValue
from app.webhooks import (
    STATUS_DELIVERED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_PENDING_RETRY,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_webhook_delivery_status_filter_literal_schema():
    adapter = TypeAdapter(WebhookDeliveryStatusFilterValue)
    assert adapter.validate_python("pending") == "pending"
    assert adapter.validate_python("  Pending_Retry ") == "pending_retry"
    assert adapter.validate_python("DELIVERED") == "delivered"
    assert adapter.validate_python("failed") == "failed"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("success")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_webhook_delivery_status_filter_ui_and_docs():
    page = (ROOT / "frontend/app/integrations/page.tsx").read_text(encoding="utf-8")
    assert "deliveryStatusFilter" in page
    assert "managedDeliveries" in page
    assert 'aria-label="Webhook delivery status filter"' in page
    assert 'value="pending_retry"' in page
    assert 'value="delivered"' in page
    assert 'value="failed"' in page
    assert "No deliveries for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Delivery status Query OpenAPI" in agents
    assert "deliveryStatusFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "deliveryStatusFilter" in docs
    assert "pending_retry" in docs and "422" in docs


async def _admin(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_webhook_delivery_status_filter_api_blank_invalid_422(client):
    ac, seed = client
    headers = await _admin(ac, seed)

    created = await ac.post(
        "/api/v1/webhooks",
        headers=headers,
        json={
            "url": "https://example.com/hooks/delivery-status",
            "events": ["webhook.test"],
        },
    )
    assert created.status_code == 200, created.text
    webhook_id = created.json()["data"]["id"]

    blank = await ac.get(
        f"/api/v1/webhooks/{webhook_id}/deliveries?status=", headers=headers
    )
    assert blank.status_code == 422, blank.text

    bad = await ac.get(
        f"/api/v1/webhooks/{webhook_id}/deliveries?status=success", headers=headers
    )
    assert bad.status_code == 422, bad.text

    tested = await ac.post(f"/api/v1/webhooks/{webhook_id}/test", headers=headers)
    assert tested.status_code == 200, tested.text
    delivery_status = tested.json()["data"]["status"]
    assert delivery_status in {
        STATUS_PENDING,
        STATUS_PENDING_RETRY,
        STATUS_DELIVERED,
        STATUS_FAILED,
    }

    filtered = await ac.get(
        f"/api/v1/webhooks/{webhook_id}/deliveries?status={delivery_status}",
        headers=headers,
    )
    assert filtered.status_code == 200, filtered.text
    rows = filtered.json()["data"]
    assert rows
    assert all(r["status"] == delivery_status for r in rows)

    cased = await ac.get(
        f"/api/v1/webhooks/{webhook_id}/deliveries?status={delivery_status.upper()}",
        headers=headers,
    )
    assert cased.status_code == 200, cased.text
    assert all(r["status"] == delivery_status for r in cased.json()["data"])

    other = STATUS_DELIVERED if delivery_status != STATUS_DELIVERED else STATUS_FAILED
    other_rows = await ac.get(
        f"/api/v1/webhooks/{webhook_id}/deliveries?status={other}", headers=headers
    )
    assert other_rows.status_code == 200, other_rows.text
    assert all(r["status"] == other for r in other_rows.json()["data"])

    omit = await ac.get(f"/api/v1/webhooks/{webhook_id}/deliveries", headers=headers)
    assert omit.status_code == 200, omit.text
    assert len(omit.json()["data"]) >= 1
