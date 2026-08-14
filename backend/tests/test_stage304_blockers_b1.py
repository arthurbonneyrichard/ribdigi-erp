"""Stage 304 B1 — commercial billing deferred pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "commercial-billing-deferred-pack-rg-blockers.json"


def test_commercial_billing_deferred_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 304 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["billing_complete_claimed"] == "REMAINING"
    assert blockers["payment_provider_claimed"] == "REMAINING"
    assert blockers["checkout_success_claimed"] == "REMAINING"
    assert blockers["deferred_implemented_claimed"] == "REMAINING"
    assert blockers["tos_signed_claimed"] == "REMAINING"
    assert blockers["stage76_as_paid_billing"] == "NON_CLAIM"
    assert blockers["billing_complete_claimed_flag"] == "false"
    assert blockers["payment_provider_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "cbdprb-billing-remaining" and s["status"] == "remaining" for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_commercial_billing_deferred_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/COMMERCIAL_BILLING_DEFERRED_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "payment_provider_claimed" in doc
    assert "Stage 76" in doc
