"""Stage 168 F1 — offline sale → sync/push flush attestation (API proof)."""

from __future__ import annotations

from pathlib import Path

import pyotp
import pytest

from app import accounting as accounting_svc
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


async def _super(ac, seed):
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    return await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )


@pytest.mark.asyncio
async def test_offline_sale_flush_path_via_sync_push_f1(client, db_session):
    """Attests the same path IndexedDB flushOfflineQueue uses: POST /sync/push pos_sale."""
    ac, seed = client
    headers = await _super(ac, seed)
    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)

    product = seed["p1"]
    product.selling_price = 15
    product.stock_qty = 40
    product.reserved_qty = 0
    product.tax_exempt = True
    product.tax_rate_id = None
    await db_session.commit()

    device = await ac.post(
        "/api/v1/offline/devices",
        headers=headers,
        json={"name": "Flush attest device", "platform": "web"},
    )
    device_id = device.json()["data"]["id"]

    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=headers,
        json={"opening_cash": 30},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    # Simulate client flush of one offline-queued pos_sale op.
    flushed = await ac.post(
        "/api/v1/sync/push",
        headers=headers,
        json={
            "device_id": device_id,
            "ops": [
                {
                    "client_op_id": "flush-attest-op-0001",
                    "op_type": "pos_sale",
                    "payload": {
                        "client_request_id": "flush-attest-sale-0001",
                        "session_id": session_id,
                        "items": [{"product_id": product.id, "quantity": 1}],
                        "payments": [{"payment_method": "cash", "amount": 15}],
                    },
                }
            ],
        },
    )
    assert flushed.status_code == 200, flushed.text
    result = flushed.json()["data"]["results"][0]
    assert result["status"] == "applied", flushed.text
    assert result["queue_item"]["result_entity_id"]

    await db_session.refresh(product)
    assert float(product.stock_qty) == 39.0


def test_offline_queue_contract_and_attestation_doc_f1():
    queue = (ROOT / "frontend/lib/offlineQueue.ts").read_text(encoding="utf-8")
    assert "OFFLINE_QUEUE_CONTRACT" in queue
    assert "storesTokens: false" in queue
    assert "offlineCompleteClaimed: false" in queue
    assert "flushEndpoint: '/sync/push'" in queue
    pos = (ROOT / "frontend/app/pos/page.tsx").read_text(encoding="utf-8")
    assert "enqueueOfflineOp" in pos
    assert "flushOfflineQueue" in pos

    attest = (ROOT / "docs/OFFLINE_COMPLETE_ATTESTATION.md").read_text(encoding="utf-8")
    assert "MISSING" in attest
    assert "Offline Complete" in attest
    assert "test_stage168_flush_proof_f1.py" in attest

    mvp = (ROOT / "ops/mvp/offline-complete-attestation.json").read_text(encoding="utf-8")
    assert '"offline_complete_claimed": false' in mvp
    assert '"attestation_claimed": false' in mvp
    assert '"verdict": "PARTIAL"' in mvp
