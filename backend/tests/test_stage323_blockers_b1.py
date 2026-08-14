"""Stage 323 B1 — first-tenant live onboarding pack RG blocker matrix packaging."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "ops" / "mvp" / "first-tenant-live-onboarding-pack-rg-blockers.json"


def test_first_tenant_live_onboarding_pack_rg_blockers_register_b1():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    assert data["stage"] == 323 and data["pack"] == "B1"
    assert data["packaging_complete"] is True
    assert data["first_tenant_onboarded_claimed"] is False
    assert data["go_live_claimed"] is False
    blockers = data["blockers"]
    assert blockers["first_tenant_onboarded_claimed"] == "REMAINING"
    assert blockers["live_onboarding_success_claimed"] == "REMAINING"
    assert blockers["first_paying_tenant_claimed"] == "REMAINING"
    assert blockers["demo_tenant_claimed"] == "REMAINING"
    assert blockers["stage194_as_live_first_tenant"] == "NON_CLAIM"
    assert blockers["first_tenant_onboarded_claimed_flag"] == "false"
    assert blockers["live_onboarding_success_claimed_flag"] == "false"
    assert all(s["done"] is False for s in data["steps"])
    assert any(
        s["id"] == "ftloprb-onboarding-remaining" and s["status"] == "remaining"
        for s in data["steps"]
    )
    for rel in data["related"].values():
        assert (ROOT / rel).is_file(), rel


def test_first_tenant_live_onboarding_pack_rg_blockers_doc_b1():
    doc = (ROOT / "docs/FIRST_TENANT_LIVE_ONBOARDING_PACK_RG_BLOCKERS_MVP.md").read_text(
        encoding="utf-8"
    )
    assert "first_tenant_onboarded_claimed" in doc
    assert "live_onboarding_success_claimed" in doc
    assert "Stage 194" in doc
