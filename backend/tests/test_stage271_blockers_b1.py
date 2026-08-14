"""Stage 271 B1 — Billing deferred pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "billing-deferred-pack-rg-blockers.json"


def test_billing_deferred_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 271 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["payment_provider_complete"] == "REMAINING"
    assert blockers["checkout_success_complete"] == "REMAINING"
    assert blockers["stage36_b1_as_billing_complete"] == "NON_CLAIM"
    assert blockers["billing_complete_claimed"] == "false"
    assert blockers["payment_provider_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "bdprb-billing-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_billing_deferred_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/BILLING_DEFERRED_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "payment_provider_claimed" in doc
    assert "Stage 36" in doc
