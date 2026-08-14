"""Stage 266 B1 — Ribdigi House console pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "ribdigi-house-console-pack-rg-blockers.json"


def test_ribdigi_house_console_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 266 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["billing_complete_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["billing_complete"] == "REMAINING"
    assert blockers["payment_provider_complete"] == "REMAINING"
    assert blockers["subscriptions_live_complete"] == "REMAINING"
    assert blockers["stage68_h1_as_billing_complete"] == "NON_CLAIM"
    assert blockers["billing_complete_claimed"] == "false"
    assert blockers["subscriptions_live_claimed"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "rhcprb-billing-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_ribdigi_house_console_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/RIBDIGI_HOUSE_CONSOLE_PACK_RG_BLOCKERS_MVP.md").read_text(encoding="utf-8")
    assert "billing_complete_claimed" in doc
    assert "subscriptions_live_claimed" in doc
    assert "Stage 68" in doc
