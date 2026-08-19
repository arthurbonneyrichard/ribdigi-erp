"""Stage 181 B1 — billing blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "billing-blockers.json"


def test_billing_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 181 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["payment_provider_claimed"] is False
    assert data["checkout_success_claimed"] is False
    assert data["mrr_fabricated_claimed"] is False
    assert data["subscriptions_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["adr002_paid_billing"] == "DEFERRED"
    assert blockers["payment_provider"] == "DEFERRED"
    assert blockers["checkout_success"] == "NON_CLAIM"
    assert blockers["mrr_fabricated"] == "BANNED"
    assert blockers["subscriptions_live"] == "REMAINING"
    assert blockers["billing_complete_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "bb-billing-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_billing_blockers_doc_b1():
    doc = (ROOT / "docs/BILLING_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "ADR-002" in doc or "ADR_002" in doc
    assert "payment provider" in doc.lower() or "payment_provider" in doc
    assert "checkout" in doc.lower()
    assert "mrr" in doc.lower()
    assert "billing_complete_claimed" in doc
